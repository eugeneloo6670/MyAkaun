import os
import secrets
from dataclasses import dataclass
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthContext:
    enabled: bool
    user_name: str

    def actor(self, fallback: str | None = None) -> str:
        if self.enabled:
            return self.user_name
        return fallback or self.user_name


def configured_token() -> str | None:
    return os.getenv("ACCOUNTMAXXER_API_TOKEN") or os.getenv("ACCOUNTING_API_TOKEN")


def configured_user() -> str:
    return os.getenv("ACCOUNTMAXXER_API_USER") or os.getenv("ACCOUNTING_API_USER") or "System"


def require_api_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> AuthContext:
    expected = configured_token()
    if not expected:
        return AuthContext(enabled=False, user_name=configured_user())

    if (
        not credentials
        or credentials.scheme.lower() != "bearer"
        or not secrets.compare_digest(credentials.credentials, expected)
    ):
        raise HTTPException(status_code=401, detail="Valid bearer token required")

    return AuthContext(enabled=True, user_name=configured_user())
