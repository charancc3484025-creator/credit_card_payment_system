from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core.validators import validate_password_strength, validate_phone_number
from app.schemas.common import ORMModel, UTCDateTime


class RegisterRequest(BaseModel):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=150)
    last_name: str = Field(min_length=1, max_length=150)
    phone_number: str = Field(default="", max_length=15)
    role: Literal["CUSTOMER", "ADMIN"] = "CUSTOMER"
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return value.lower().strip()

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    @field_validator("phone_number")
    @classmethod
    def check_phone(cls, value: str) -> str:
        return validate_phone_number(value.strip())

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, value):
        if value is None or value == "":
            return "CUSTOMER"
        if isinstance(value, str):
            value = value.strip().upper()
        if value not in ("CUSTOMER", "ADMIN"):
            raise ValueError("Role must be CUSTOMER or ADMIN.")
        return value

    @model_validator(mode="after")
    def check_passwords(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        errors = validate_password_strength(self.password, self.email)
        if errors:
            raise ValueError(" ".join(errors))
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh: str


class LogoutRequest(BaseModel):
    refresh: str


class TokenPair(BaseModel):
    access: str
    refresh: str


class UserOut(ORMModel):
    id: int
    email: str
    first_name: str
    last_name: str
    full_name: str
    phone_number: str
    role: str
    is_active: bool
    date_joined: UTCDateTime
    last_login: Optional[UTCDateTime] = None


class AuthResponse(BaseModel):
    success: bool = True
    message: str
    user: UserOut
    tokens: TokenPair


class ProfileUpdate(BaseModel):
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    phone_number: Optional[str] = Field(default=None, max_length=15)

    @field_validator("phone_number")
    @classmethod
    def check_phone(cls, value):
        return validate_phone_number(value.strip()) if value is not None else value


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str

    @model_validator(mode="after")
    def check_passwords(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        if self.new_password == self.old_password:
            raise ValueError("New password must be different from old password.")
        errors = validate_password_strength(self.new_password)
        if errors:
            raise ValueError(" ".join(errors))
        return self
