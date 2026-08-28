from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class EmailIn(BaseModel):
    email: EmailStr


class OtpStartOut(BaseModel):
    email: str
    expires_in: int
    resend_in: int
    delivered: bool
    dev_otp: str | None = None
    message: str = "Verification code sent."


class OtpVerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=8)


class SignupTokenOut(BaseModel):
    signup_token: str
    email: str
    expires_in: int


class SignupCompleteIn(BaseModel):
    signup_token: str
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=6, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    dob: date | None = None
    gender: str | None = None

    @field_validator("password")
    @classmethod
    def strong(cls, v: str) -> str:
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Password must contain both letters and numbers.")
        return v

    @field_validator("phone")
    @classmethod
    def digits(cls, v: str) -> str:
        cleaned = "".join(ch for ch in v if ch.isdigit() or ch == "+")
        if len(cleaned.lstrip("+")) < 6:
            raise ValueError("Enter a valid phone number.")
        return cleaned


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GoogleIn(BaseModel):
    id_token: str


class RefreshIn(BaseModel):
    refresh_token: str


class ResetIn(BaseModel):
    reset_token: str
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    phone: str | None = None
    avatar_url: str | None = None
    dob: date | None = None
    birth_time: str | None = None
    birth_place: str | None = None
    gender: str | None = None
    role: str
    is_premium: bool
    is_email_verified: bool
    free_reports_used: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("role", mode="before")
    @classmethod
    def role_str(cls, v):
        return getattr(v, "value", v)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class ProfileUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=20)
    dob: date | None = None
    birth_time: str | None = None
    birth_place: str | None = None
    gender: str | None = None


class PasswordChangeIn(BaseModel):
    current_password: str | None = None
    new_password: str = Field(min_length=8, max_length=128)
