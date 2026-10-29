from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database import get_db
from app.models import StudentProfile, User


def current_user_optional(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    payload = decode_token(auth[7:].strip())
    if not payload:
        return None
    user = db.get(User, payload.get("sub"))
    return user if user and user.is_active else None


def require_user(user: Optional[User] = Depends(current_user_optional)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in required", headers={"WWW-Authenticate": "Bearer"})
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator role required")
    return user


def require_profile(user: User = Depends(require_user), db: Session = Depends(get_db)) -> StudentProfile:
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Create your profile first")
    return profile
