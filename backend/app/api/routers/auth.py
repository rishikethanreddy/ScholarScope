from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_user
from app.core.ratelimit import rate_limit
from app.core.security import create_token, hash_password, verify_password
from app.database import get_db
from app.models import StudentProfile, User, utcnow
from app.schemas import LoginIn, RegisterIn

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _session(user: User, db: Session) -> dict:
    has_profile = db.scalar(select(StudentProfile.id).where(StudentProfile.user_id == user.id)) is not None
    return {"token": create_token(user), "user": {"id": user.id, "email": user.email, "role": user.role,
                                                  "has_profile": has_profile}}


@router.post("/register", dependencies=[Depends(rate_limit("register", 10, 3600))])
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(email=body.email, password_hash=hash_password(body.password), role="student")
    db.add(user)
    db.commit()
    return _session(user, db)


@router.post("/login", dependencies=[Depends(rate_limit("login", 20, 900))])
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    user.last_login_at = utcnow()
    db.commit()
    return _session(user, db)


@router.get("/me")
def me(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return _session(user, db)["user"]
