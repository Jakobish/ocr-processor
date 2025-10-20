-- OCR Processor Database Initialization
-- Creates necessary tables and indexes for PostgreSQL

-- Create database if it doesn't exist
-- (This is handled by POSTGRES_DB environment variable)

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_ocr_jobs_status ON ocr_jobs(status);
CREATE INDEX IF NOT EXISTS idx_ocr_jobs_created_at ON ocr_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ocr_jobs_job_id ON ocr_jobs(job_id);

-- Create indexes for files table
CREATE INDEX IF NOT EXISTS idx_ocr_files_job_id ON ocr_files(job_id);
CREATE INDEX IF NOT EXISTS idx_ocr_files_status ON ocr_files(status);
CREATE INDEX IF NOT EXISTS idx_ocr_files_file_path ON ocr_files(file_path);

-- Create indexes for audit logs
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON ocr_audit_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON ocr_audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_job_id ON ocr_audit_logs(job_id);

-- Create indexes for performance metrics
CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp ON ocr_performance_metrics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_name ON ocr_performance_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_job_id ON ocr_performance_metrics(job_id);

-- Create a view for job summary
CREATE OR REPLACE VIEW job_summary AS
SELECT
    j.job_id,
    j.status,
    j.mode,
    j.language,
    j.created_at,
    j.started_at,
    j.completed_at,
    j.total_files,
    j.processed_files,
    j.failed_files,
    j.progress,
    j.processing_time,
    COUNT(f.id) as actual_file_count,
    COUNT(CASE WHEN f.status = 'completed' THEN 1 END) as actual_processed,
    COUNT(CASE WHEN f.status = 'failed' THEN 1 END) as actual_failed
FROM ocr_jobs j
LEFT JOIN ocr_files f ON j.id = f.job_id
GROUP BY j.id, j.job_id, j.status, j.mode, j.language, j.created_at,
         j.started_at, j.completed_at, j.total_files, j.processed_files,
         j.failed_files, j.progress, j.processing_time;

-- Create a view for recent activity
CREATE OR REPLACE VIEW recent_activity AS
SELECT
    'job' as activity_type,
    j.job_id as reference_id,
    j.status as details,
    j.created_at as timestamp,
    j.metadata->>'priority' as priority
FROM ocr_jobs j
WHERE j.created_at >= NOW() - INTERVAL '24 hours'

UNION ALL

SELECT
    'audit' as activity_type,
    a.job_id::text as reference_id,
    a.event_type as details,
    a.timestamp,
    a.severity as priority
FROM ocr_audit_logs a
WHERE a.timestamp >= NOW() - INTERVAL '24 hours'

ORDER BY timestamp DESC
LIMIT 100;

-- Create function to clean up old records
CREATE OR REPLACE FUNCTION cleanup_old_records(days_old INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_jobs INTEGER;
    deleted_files INTEGER;
    deleted_audit INTEGER;
    deleted_metrics INTEGER;
BEGIN
    -- Delete old completed/failed jobs and related records
    DELETE FROM ocr_files
    WHERE job_id IN (
        SELECT id FROM ocr_jobs
        WHERE created_at < NOW() - INTERVAL '1 day' * days_old
        AND status IN ('completed', 'failed', 'cancelled')
    );

    GET DIAGNOSTICS deleted_files = ROW_COUNT;

    DELETE FROM ocr_audit_logs
    WHERE job_id IN (
        SELECT id FROM ocr_jobs
        WHERE created_at < NOW() - INTERVAL '1 day' * days_old
        AND status IN ('completed', 'failed', 'cancelled')
    );

    GET DIAGNOSTICS deleted_audit = ROW_COUNT;

    DELETE FROM ocr_jobs
    WHERE created_at < NOW() - INTERVAL '1 day' * days_old
    AND status IN ('completed', 'failed', 'cancelled');

    GET DIAGNOSTICS deleted_jobs = ROW_COUNT;

    -- Delete old performance metrics
    DELETE FROM ocr_performance_metrics
    WHERE timestamp < NOW() - INTERVAL '1 day' * days_old;

    GET DIAGNOSTICS deleted_metrics = ROW_COUNT;

    RETURN deleted_jobs + deleted_files + deleted_audit + deleted_metrics;
END;
$$ LANGUAGE plpgsql;

-- Grant necessary permissions (adjust as needed for your security model)
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO ocr_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ocr_user;
-- GRANT EXECUTE ON FUNCTION cleanup_old_records TO ocr_user;

-- Insert sample data for testing (optional)
-- INSERT INTO ocr_jobs (job_id, status, input_path, mode, language) VALUES
-- ('test-job-001', 'completed', '/test/input.pdf', 'cli', 'heb+eng');

COMMIT;