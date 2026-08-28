from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models import Role, User

bearer = HTTPBearer(auto_error=False)
optional_bearer = HTTPBearer(auto_error=False)


def _user_from_token(db: Session, token: str) -> User:
    payload = decode_token(token, "access")
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Please sign in again.")
    user = db.get(User, payload.get("sub"))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found.")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been disabled.")
    return user


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    return _user_from_token(db, creds.credentials)


def optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    if not creds:
        return None
    try:
        return _user_from_token(db, creds.credentials)
    except HTTPException:
        return None


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role not in (Role.admin, Role.superadmin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required.")
    return user


def superadmin_user(user: User = Depends(current_user)) -> User:
    if user.role != Role.superadmin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Super-admin access required.")
    return user


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
