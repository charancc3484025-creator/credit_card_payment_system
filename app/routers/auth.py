from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, login_rate_limiter
from app.models import User
from app.schemas.common import MessageResponse
from app.schemas.user import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    ProfileUpdate,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)
from app.services import auth_service
from app.services.audit_service import log_action

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    user = auth_service.register_user(db, data)
    log_action(db, user.id, "USER_REGISTERED", f"New user {user.email}", request)
    return {
        "message": "Registration successful.",
        "user": UserOut.model_validate(user),
        "tokens": auth_service.issue_tokens(db, user),
    }


@router.post("/login", response_model=AuthResponse, dependencies=[Depends(login_rate_limiter)])
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = auth_service.authenticate(db, data.email, data.password)
    log_action(db, user.id, "USER_LOGIN", "Logged in via FastAPI", request)
    return {
        "message": "Login successful.",
        "user": UserOut.model_validate(user),
        "tokens": auth_service.issue_tokens(db, user),
    }


@router.post("/token/refresh", response_model=TokenPair)
def refresh_token(data: RefreshRequest, db: Session = Depends(get_db)):
    return auth_service.refresh_tokens(db, data.refresh)


@router.post("/logout", response_model=MessageResponse)
def logout(data: LogoutRequest, request: Request, db: Session = Depends(get_db),
           current_user: User = Depends(get_current_user)):
    auth_service.logout(db, current_user, data.refresh)
    log_action(db, current_user.id, "USER_LOGOUT", "", request)
    return {"message": "Logged out successfully."}


@router.get("/profile", response_model=UserOut)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/profile", response_model=UserOut)
def update_profile(data: ProfileUpdate, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(current_user, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/change-password", response_model=MessageResponse)
def change_password(data: ChangePasswordRequest, request: Request, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    auth_service.change_password(db, current_user, data.old_password, data.new_password)
    log_action(db, current_user.id, "PASSWORD_CHANGED", "", request)
    return {"message": "Password changed successfully. Please login again."}
