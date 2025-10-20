"""
Enterprise OCR Security Validation and Input Sanitization
Provides comprehensive security checks, input validation, and threat protection
"""
import os
import magic
import hashlib
import mimetypes
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import re
import logging
from urllib.parse import urlparse
import tempfile
import shutil
from logger import log_manager


@dataclass
class ValidationResult:
    """Result of security validation"""
    is_valid: bool
    risk_level: str  # low, medium, high, critical
    issues: List[str]
    recommendations: List[str]
    metadata: Dict[str, Any]


@dataclass
class FileSecurityInfo:
    """Security information about a file"""
    file_path: str
    file_size: int
    mime_type: str
    magic_type: str
    checksum_sha256: str
    is_pdf: bool
    is_encrypted: bool
    has_embedded_files: bool
    suspicious_patterns: List[str]
    permissions: str


class SecurityValidator:
    """Comprehensive security validation for OCR processing"""

    def __init__(self, config):
        self.config = config
        self.quarantine_dir = Path("quarantine")
        self.quarantine_dir.mkdir(exist_ok=True)

        # Initialize MIME type detection
        try:
            self.mime_detector = magic.Magic(mime=True)
            self.magic_detector = magic.Magic()
        except Exception as e:
            log_manager.logger.warning("Magic library not available, using basic detection", error=str(e))
            self.mime_detector = None
            self.magic_detector = None

        # Suspicious patterns to detect
        self.suspicious_patterns = [
            # Script injections
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'vbscript:',
            r'onload\s*=',
            r'onerror\s*=',

            # Embedded executable patterns
            r'%PDF-.*\n.*\x00\x00\x00\x00',
            r'obj\n.*\nstream\n.*\nendstream',

            # Malicious file signatures (basic)
            r'MZ\x90\x00',  # PE executable
            r'\x7fELF',     # ELF executable
            r'\x89PNG',     # PNG (check for polyglots)
        ]

        # Allowed MIME types for PDF processing
        self.allowed_mime_types = [
            'application/pdf',
            'application/x-pdf',
            'application/acrobat',
            'applications/vnd.pdf',
            'text/pdf',
            'text/x-pdf'
        ]

        # Maximum file sizes by risk level
        self.max_sizes = {
            'low': 50 * 1024 * 1024,      # 50MB
            'medium': 100 * 1024 * 1024,  # 100MB
            'high': 500 * 1024 * 1024,    # 500MB
            'critical': 1024 * 1024 * 1024 # 1GB
        }

    def validate_input_path(self, input_path: str) -> ValidationResult:
        """Validate and sanitize input path"""
        issues = []
        recommendations = []

        try:
            path = Path(input_path).resolve()

            # Check for path traversal attempts
            if self._check_path_traversal(input_path):
                issues.append("Potential path traversal attempt detected")
                recommendations.append("Use absolute paths or ensure input is within allowed directories")

            # Check if path exists
            if not path.exists():
                issues.append(f"Path does not exist: {input_path}")
                return ValidationResult(False, "critical", issues, recommendations, {})

            # Check permissions
            if not os.access(path, os.R_OK):
                issues.append(f"No read permission for path: {input_path}")
                recommendations.append("Ensure proper file permissions are set")

            # Check for suspicious paths
            suspicious_paths = ['/proc/', '/sys/', '/dev/', '/etc/passwd', '/etc/shadow']
            path_str = str(path).lower()
            for suspicious in suspicious_paths:
                if suspicious in path_str:
                    issues.append(f"Suspicious path detected: {path}")
                    recommendations.append("Avoid system directories and sensitive files")

            # Validate individual files or directories
            if path.is_file():
                file_result = self.validate_pdf_file(path)
                issues.extend(file_result.issues)
                recommendations.extend(file_result.recommendations)
                metadata = file_result.metadata
            elif path.is_dir():
                dir_result = self.validate_directory(path)
                issues.extend(dir_result.issues)
                recommendations.extend(dir_result.recommendations)
                metadata = dir_result.metadata
            else:
                issues.append(f"Unsupported path type: {input_path}")
                metadata = {}

            risk_level = self._calculate_risk_level(issues)

            return ValidationResult(
                len(issues) == 0,
                risk_level,
                issues,
                recommendations,
                metadata
            )

        except Exception as e:
            return ValidationResult(
                False,
                "critical",
                [f"Validation error: {str(e)}"],
                ["Check file permissions and path validity"],
                {}
            )

    def validate_pdf_file(self, file_path: Path) -> ValidationResult:
        """Comprehensive PDF file validation"""
        issues = []
        recommendations = []
        metadata = {}

        try:
            # Get file info
            stat = file_path.stat()
            file_size = stat.st_size

            # Check file size against configured limits
            if file_size > self.config.max_file_size:
                issues.append(f"File size {file_size} exceeds maximum allowed size {self.config.max_file_size}")
                recommendations.append("Reduce file size or increase max_file_size limit in configuration")

            # Detect MIME type
            mime_type = self._detect_mime_type(file_path)
            magic_type = self._detect_magic_type(file_path)

            metadata.update({
                'file_size': file_size,
                'mime_type': mime_type,
                'magic_type': magic_type,
                'modified_time': stat.st_mtime
            })

            # Validate MIME type
            if mime_type not in self.allowed_mime_types:
                issues.append(f"Invalid MIME type: {mime_type}. Expected PDF.")
                recommendations.append("Ensure file is a valid PDF document")

            # Check for file corruption or polyglots
            if not self._is_valid_pdf_structure(file_path):
                issues.append("File does not appear to be a valid PDF or may be corrupted")
                recommendations.append("Verify PDF integrity and try re-saving the document")

            # Check for suspicious content
            suspicious_issues = self._scan_for_suspicious_content(file_path)
            if suspicious_issues:
                issues.extend(suspicious_issues)
                recommendations.append("File contains suspicious patterns - review content before processing")

            # Check for encryption
            is_encrypted = self._check_pdf_encryption(file_path)
            if is_encrypted:
                issues.append("PDF file is encrypted or password-protected")
                recommendations.append("Remove password protection or provide decryption credentials")

            metadata.update({
                'is_encrypted': is_encrypted,
                'suspicious_patterns': len(suspicious_issues)
            })

            # Calculate security score
            security_info = FileSecurityInfo(
                file_path=str(file_path),
                file_size=file_size,
                mime_type=mime_type,
                magic_type=magic_type,
                checksum_sha256=self._calculate_checksum(file_path),
                is_pdf=mime_type in self.allowed_mime_types,
                is_encrypted=is_encrypted,
                has_embedded_files=self._check_embedded_files(file_path),
                suspicious_patterns=suspicious_issues,
                permissions=oct(stat.st_mode)[-3:]
            )

            metadata['security_info'] = security_info.__dict__

            risk_level = self._calculate_risk_level(issues)

            return ValidationResult(
                len(issues) == 0,
                risk_level,
                issues,
                recommendations,
                metadata
            )

        except Exception as e:
            return ValidationResult(
                False,
                "critical",
                [f"File validation error: {str(e)}"],
                ["Check file accessibility and format"],
                metadata
            )

    def validate_directory(self, dir_path: Path) -> ValidationResult:
        """Validate directory for batch processing"""
        issues = []
        recommendations = []
        metadata = {'total_files': 0, 'valid_pdfs': 0, 'risky_files': 0}

        try:
            # Check directory permissions
            if not os.access(dir_path, os.R_OK):
                issues.append(f"No read permission for directory: {dir_path}")
                return ValidationResult(False, "critical", issues, recommendations, metadata)

            # Scan directory contents
            pdf_files = list(dir_path.glob("**/*.pdf")) if self.config.recursive else list(dir_path.glob("*.pdf"))

            if not pdf_files:
                issues.append(f"No PDF files found in directory: {dir_path}")
                recommendations.append("Check directory contents and file extensions")
            else:
                metadata['total_files'] = len(pdf_files)

                # Validate each PDF file
                for pdf_file in pdf_files:
                    file_result = self.validate_pdf_file(pdf_file)
                    if not file_result.is_valid:
                        metadata['risky_files'] += 1
                        if file_result.risk_level in ['high', 'critical']:
                            issues.append(f"High-risk file detected: {pdf_file.name}")
                    else:
                        metadata['valid_pdfs'] += 1

                # Check for too many files
                if len(pdf_files) > self.config.max_files_per_job:
                    issues.append(f"Too many files ({len(pdf_files)}) exceeds limit ({self.config.max_files_per_job})")
                    recommendations.append("Process files in smaller batches or increase max_files_per_job limit")

            risk_level = self._calculate_risk_level(issues)

            return ValidationResult(
                len(issues) == 0,
                risk_level,
                issues,
                recommendations,
                metadata
            )

        except Exception as e:
            return ValidationResult(
                False,
                "critical",
                [f"Directory validation error: {str(e)}"],
                ["Check directory permissions and contents"],
                metadata
            )

    def quarantine_file(self, file_path: Path, reason: str) -> str:
        """Move suspicious file to quarantine"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"{timestamp}_{file_path.name}"
            quarantine_path = self.quarantine_dir / file_name

            shutil.move(str(file_path), quarantine_path)

            log_manager.logger.warning(
                "File quarantined",
                file_path=str(file_path),
                quarantine_path=str(quarantine_path),
                reason=reason,
                event_type="file_quarantined"
            )

            return str(quarantine_path)

        except Exception as e:
            log_manager.logger.error(
                "Quarantine failed",
                file_path=str(file_path),
                error=str(e),
                event_type="quarantine_error"
            )
            return ""

    def _check_path_traversal(self, path: str) -> bool:
        """Check for path traversal attempts"""
        # Common traversal patterns
        traversal_patterns = [
            '../', '..\\',
            '%2e%2e%2f', '%2e%2e%5c',  # URL encoded
            '..%252f', '..%255c',       # Double URL encoded
        ]

        path_lower = path.lower()
        return any(pattern in path_lower for pattern in traversal_patterns)

    def _detect_mime_type(self, file_path: Path) -> str:
        """Detect MIME type of file"""
        try:
            if self.mime_detector:
                return self.mime_detector.from_file(str(file_path))
            else:
                # Fallback to mimetypes
                return mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'
        except Exception:
            return 'application/octet-stream'

    def _detect_magic_type(self, file_path: Path) -> str:
        """Detect file type using magic numbers"""
        try:
            if self.magic_detector:
                return self.magic_detector.from_file(str(file_path))
            else:
                return 'unknown'
        except Exception:
            return 'unknown'

    def _is_valid_pdf_structure(self, file_path: Path) -> bool:
        """Check if file has valid PDF structure"""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(8)

            # PDF files should start with %PDF-
            if not header.startswith(b'%PDF-'):
                return False

            # Check for PDF version
            try:
                version_part = header[5:8].decode('ascii')
                float(version_part)
            except:
                return False

            return True

        except Exception:
            return False

    def _scan_for_suspicious_content(self, file_path: Path) -> List[str]:
        """Scan file for suspicious patterns"""
        issues = []

        try:
            with open(file_path, 'rb') as f:
                content = f.read(1024 * 1024)  # Read first 1MB for scanning

            # Check for suspicious patterns
            for pattern in self.suspicious_patterns:
                try:
                    if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                        issues.append(f"Suspicious pattern detected: {pattern[:50]}...")
                except:
                    continue

            # Check for embedded PE files (basic check)
            if b'MZ\x90\x00' in content[:1024]:
                issues.append("Potential embedded executable detected")

        except Exception as e:
            issues.append(f"Content scanning error: {str(e)}")

        return issues

    def _check_pdf_encryption(self, file_path: Path) -> bool:
        """Check if PDF is encrypted"""
        try:
            # Basic check for encryption markers
            with open(file_path, 'rb') as f:
                content = f.read(2048)

            # Look for encryption dictionary markers
            encryption_markers = [
                b'/Encrypt',
                b'/Type/Encrypt',
                b'/StmF',
                b'/StrF'
            ]

            for marker in encryption_markers:
                if marker in content:
                    return True

            return False

        except Exception:
            return False

    def _check_embedded_files(self, file_path: Path) -> bool:
        """Check for embedded files in PDF"""
        try:
            with open(file_path, 'rb') as f:
                content = f.read(4096)

            # Look for embedded file markers
            embedded_markers = [
                b'/EmbeddedFile',
                b'/Type/EmbeddedFile',
                b'/Names/EmbeddedFiles'
            ]

            for marker in embedded_markers:
                if marker in content:
                    return True

            return False

        except Exception:
            return False

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file"""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception:
            return 'unknown'

    def _calculate_risk_level(self, issues: List[str]) -> str:
        """Calculate overall risk level based on issues"""
        if not issues:
            return "low"

        critical_keywords = ['traversal', 'executable', 'malicious', 'unauthorized']
        high_keywords = ['encrypted', 'suspicious', 'corrupted', 'permission']

        critical_count = sum(1 for issue in issues if any(keyword in issue.lower() for keyword in critical_keywords))
        high_count = sum(1 for issue in issues if any(keyword in issue.lower() for keyword in high_keywords))

        if critical_count > 0:
            return "critical"
        elif high_count > 0:
            return "high"
        elif len(issues) > 2:
            return "medium"
        else:
            return "low"

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage"""
        # Remove or replace dangerous characters
        dangerous_chars = '<>:"/\\|?*'
        sanitized = filename

        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '_')

        # Remove control characters
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)

        # Limit length
        if len(sanitized) > 255:
            name, ext = os.path.splitext(sanitized)
            sanitized = name[:255-len(ext)] + ext

        return sanitized

    def validate_output_path(self, output_path: str) -> bool:
        """Validate output path for security"""
        try:
            path = Path(output_path).resolve()

            # Ensure output directory is within allowed locations
            allowed_dirs = [
                Path.cwd(),
                Path.cwd() / "ocr_output",
                Path.cwd() / "ocr_force",
                Path.cwd() / "ocr_visual"
            ]

            # Check if output path is within allowed directories
            is_safe = any(
                str(path).startswith(str(allowed_dir))
                for allowed_dir in allowed_dirs
            )

            if not is_safe:
                log_manager.logger.warning(
                    "Unsafe output path",
                    output_path=output_path,
                    event_type="unsafe_output_path"
                )
                return False

            return True

        except Exception as e:
            log_manager.logger.error(
                "Output path validation error",
                output_path=output_path,
                error=str(e)
            )
            return False


class InputSanitizer:
    """Input sanitization utilities"""

    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            return ""

        # Remove null bytes
        sanitized = value.replace('\x00', '')

        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        return sanitized

    @staticmethod
    def sanitize_language_code(lang_code: str) -> str:
        """Sanitize language code input"""
        # Only allow valid Tesseract language codes
        valid_langs = [
            'eng', 'heb', 'fra', 'deu', 'spa', 'ita', 'por', 'rus', 'ara', 'chi_sim', 'chi_tra',
            'heb+eng', 'eng+fra', 'eng+deu', 'eng+spa', 'eng+ita', 'eng+por', 'eng+rus'
        ]

        sanitized = InputSanitizer.sanitize_string(lang_code).lower()

        # Check for valid combinations
        if '+' in sanitized:
            parts = sanitized.split('+')
            if all(part in valid_langs for part in parts):
                return sanitized

        return sanitized if sanitized in valid_langs else 'heb+eng'

    @staticmethod
    def sanitize_mode(mode: str) -> str:
        """Sanitize processing mode"""
        valid_modes = ['cli', 'force', 'visual']
        sanitized = InputSanitizer.sanitize_string(mode).lower()
        return sanitized if sanitized in valid_modes else 'cli'


# Global security validator instance
security_validator = None

def get_security_validator(config) -> SecurityValidator:
    """Get or create global security validator"""
    global security_validator
    if security_validator is None:
        security_validator = SecurityValidator(config)
    return security_validator