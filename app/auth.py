"""JWT auth utilities and FastAPI dependency"""
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import MobileUser, Company

bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(sub: str, role: str = "mobile") -> str:
    expire = datetime.utcnow() + timedelta(days=settings.JWT_EXPIRE_DAYS)
    payload = {"sub": sub, "role": role, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def get_current_mobile(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> str:
    """Returns the logged-in user's mobile number from JWT."""
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(creds.credentials)
    if not payload or payload.get("role") not in ("mobile", None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    mobile = payload.get("sub")
    if not mobile:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return mobile


def get_current_user(
    mobile: str = Depends(get_current_mobile),
    db: Session = Depends(get_db),
) -> MobileUser:
    user = db.query(MobileUser).filter(MobileUser.mobile == mobile).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="User not active")
    return user


def get_current_super_admin(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> str:
    """Returns super admin email from JWT. Raises 403 if not super admin."""
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    payload = decode_token(creds.credentials)
    if not payload or payload.get("role") != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super admin access required")
    return payload.get("sub")


def get_current_company(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Company:
    """Returns the logged-in Company object from JWT."""
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    payload = decode_token(creds.credentials)
    if not payload or payload.get("role") != "company":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Company access required")
    email = payload.get("sub")
    company = db.query(Company).filter(Company.email == email).first()
    if not company or not company.is_active:
        raise HTTPException(status_code=403, detail="Company account is disabled")
    return company
