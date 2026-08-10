"""Auth dependency — requires Bearer token on all /api/* and /ws/* routes.

Fail-closed: if HOST != 127.0.0.1 and API_AUTH_TOKEN is unset, the app
refuses to start (enforced in app.py lifespan).
"""

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cudaquant.config.settings import settings

_bearer = HTTPBearer(auto_error=False)


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """Validate Bearer token against API_AUTH_TOKEN.

    Skips auth for /health and /readiness (they're excluded by path prefix).
    """
    token = settings.API_AUTH_TOKEN

    if not token:
        # No auth token configured — only safe on loopback
        return

    if credentials is None:
        raise HTTPException(status_code=401, detail="Authorization header required")

    if credentials.credentials != token:
        raise HTTPException(status_code=401, detail="Invalid API token")
