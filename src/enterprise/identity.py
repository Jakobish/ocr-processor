"""Fail-closed identity bridge. No passwords or browser-asserted roles."""
from dataclasses import dataclass
import hashlib
import httpx
from sqlalchemy import select
from enterprise.database import APIKey


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    role: str
    scopes: tuple[str, ...] = ('read', 'write', 'admin')
    key_id: str | None = None

    @property
    def manages_team(self):
        return self.role in ('owner', 'admin')

    def allows(self, scope):
        return scope in self.scopes


class IdentityUnavailable(Exception):
    pass


class IdentityAdapter:
    def __init__(self, settings, db):
        self.settings, self.db = settings, db

    def authenticate(self, token, tenant_id=None):
        if not token:
            return None
        if token.startswith('ocr_'):
            with self.db.session() as s:
                key = s.scalar(select(APIKey).where(APIKey.token_hash == hashlib.sha256(token.encode()).hexdigest(), APIKey.revoked_at.is_(None)))
                if not key or (tenant_id and tenant_id != key.tenant_id):
                    return None
                # Integration keys are independent team service principals. Their
                # scope grants team read/write, never user/owner administration.
                return Principal('key:' + key.id, key.tenant_id, 'admin', tuple(key.scopes), key.id)
        if not self.settings.identity_url or not self.settings.identity_secret:
            raise IdentityUnavailable('Identity adapter is not configured')
        try:
            r = httpx.post(self.settings.identity_url,
                headers={'Authorization': 'Bearer ' + self.settings.identity_secret},
                json={'token': token, 'tenant_id': tenant_id}, timeout=5.0, follow_redirects=False)
            if r.status_code in (401, 403):
                return None
            r.raise_for_status()
            data = r.json()
            if data.get('active') is False:
                return None
            user, team, role = data['user_id'], data['tenant_id'], data['role']
            if not isinstance(user, str) or not isinstance(team, str) or not user or not team or len(user) > 128 or len(team) > 128:
                return None
            if role not in ('owner', 'admin', 'member') or (tenant_id and team != tenant_id):
                return None
            return Principal(user, team, role)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise IdentityUnavailable('Identity service unavailable') from exc
