from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings


security = HTTPBearer(auto_error=False)


class TokenData:
    def __init__(self, tenant_id: str, role: str, user_id: str):
        self.tenant_id = tenant_id
        self.role = role
        self.user_id = user_id


def create_access_token(tenant_id: str, role: str, user_id: str, expires_minutes: Optional[int] = None) -> str:
    settings = get_settings()
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes or settings.access_token_expire_minutes)
    to_encode = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> TokenData:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing credentials")
    settings = get_settings()
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[settings.algorithm])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    tenant_id = payload.get("tenant_id")
    role = payload.get("role")
    user_id = payload.get("sub")
    if not tenant_id or not role or not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    return TokenData(tenant_id=tenant_id, role=role, user_id=user_id)


def require_role(*allowed_roles: str):
    def dependency(user: TokenData = Depends(get_current_user)) -> TokenData:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return dependency
