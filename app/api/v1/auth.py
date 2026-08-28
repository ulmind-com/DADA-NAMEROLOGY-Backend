from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import current_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_reset_token,
    create_signup_token,
    decode_token,
    hash_password,
    sha256,
    verify_password,
)
from app.db.mongo import DB, get_db
from app.models import OtpPurpose, RefreshToken, Role, User
from app.schemas.auth import (
    EmailIn,
    GoogleIn,
    LoginIn,
    OtpStartOut,
    OtpVerifyIn,
    PasswordChangeIn,
    ProfileUpdateIn,
    RefreshIn,
    ResetIn,
    SignupCompleteIn,
    SignupTokenOut,
    TokenOut,
    UserOut,
)
from app.services.email import send_welcome_email
from app.services.google import verify_google_id_token
from app.services.otp import check_otp, issue_otp
from app.services.storage import (
    ALLOWED_IMAGE_TYPES,
    MAX_IMAGE_BYTES,
    destroy,
    upload_avatar,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _now() -> datetime:
    return datetime.now(UTC)


def _issue_session(db: DB, user: User, device: str = "") -> TokenOut:
    access = create_access_token(user.id, user.role.value)
    refresh = create_refresh_token(user.id)
    db.refresh_tokens.insert(
        RefreshToken(
            user_id=user.id,
            token_hash=sha256(refresh),
            expires_at=_now() + timedelta(days=settings.REFRESH_TOKEN_DAYS),
            device=device or None,
        )
    )
    user.last_login_at = _now()
    db.users.update(user.id, {"last_login_at": user.last_login_at})
    return TokenOut(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_MINUTES * 60,
        user=UserOut.model_validate(user),
    )


def _by_email(db: DB, email: str) -> User | None:
    return db.users.find_one({"email": email.lower().strip()})


# ---------------------------------------------------------------- SIGN UP (3 steps)
@router.post("/signup/start", response_model=OtpStartOut, summary="Step 1 - send OTP to email")
def signup_start(body: EmailIn, db: DB = Depends(get_db)):
    if _by_email(db, body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "This email is already registered. Please sign in.")
    return OtpStartOut(**issue_otp(db, body.email, OtpPurpose.signup))


@router.post("/signup/resend", response_model=OtpStartOut, summary="Resend the signup OTP")
def signup_resend(body: EmailIn, db: DB = Depends(get_db)):
    if _by_email(db, body.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "This email is already registered.")
    return OtpStartOut(**issue_otp(db, body.email, OtpPurpose.signup))


@router.post("/signup/verify", response_model=SignupTokenOut, summary="Step 2 - verify the 6-digit OTP")
def signup_verify(body: OtpVerifyIn, db: DB = Depends(get_db)):
    check_otp(db, body.email, body.code, OtpPurpose.signup)
    return SignupTokenOut(
        signup_token=create_signup_token(body.email.lower()),
        email=body.email.lower(),
        expires_in=settings.SIGNUP_TOKEN_MINUTES * 60,
    )


@router.post("/signup/complete", response_model=TokenOut, summary="Step 3 - name, phone, password")
def signup_complete(body: SignupCompleteIn, db: DB = Depends(get_db)):
    payload = decode_token(body.signup_token, "signup")
    if not payload:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Verification expired. Please start again.")
    email = payload["email"]
    if _by_email(db, email):
        raise HTTPException(status.HTTP_409_CONFLICT, "This email is already registered.")

    user = db.users.insert(
        User(
            email=email,
            full_name=body.full_name.strip(),
            phone=body.phone,
            hashed_password=hash_password(body.password),
            dob=body.dob,
            gender=body.gender,
            is_email_verified=True,
        )
    )
    send_welcome_email(user.email, user.full_name.split(" ")[0])
    return _issue_session(db, user)


# ------------------------------------------------------------------------ LOGIN
@router.post("/login", response_model=TokenOut, summary="Email + password sign in")
def login(body: LoginIn, db: DB = Depends(get_db)):
    user = _by_email(db, body.email)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been disabled.")
    return _issue_session(db, user)


@router.post("/google", response_model=TokenOut, summary="Sign in / sign up with Google")
def google_auth(body: GoogleIn, db: DB = Depends(get_db)):
    info = verify_google_id_token(body.id_token)
    user = db.users.find_one({"google_id": info["google_id"]})

    if not user:
        user = _by_email(db, info["email"])
        if user:
            # link Google to the existing password account
            changes = {"google_id": info["google_id"], "is_email_verified": True}
            if not user.avatar_url:
                changes["avatar_url"] = info["picture"]
            db.users.update(user.id, changes)
            user = db.users.get(user.id)
        else:
            user = db.users.insert(
                User(
                    email=info["email"],
                    full_name=info["name"],
                    google_id=info["google_id"],
                    avatar_url=info["picture"],
                    is_email_verified=info["email_verified"],
                )
            )
            send_welcome_email(user.email, (user.full_name or "there").split(" ")[0])

    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been disabled.")
    return _issue_session(db, user, device="google")


# ---------------------------------------------------------------------- TOKENS
@router.post("/refresh", response_model=TokenOut, summary="Exchange a refresh token for a new session")
def refresh(body: RefreshIn, db: DB = Depends(get_db)):
    payload = decode_token(body.refresh_token, "refresh")
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Please sign in again.")
    row = db.refresh_tokens.find_one({"token_hash": sha256(body.refresh_token)})
    if not row or row.revoked:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session revoked. Please sign in again.")
    user = db.users.get(payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account unavailable.")
    db.refresh_tokens.update(row.id, {"revoked": True})   # rotate
    return _issue_session(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke the current refresh token")
def logout(body: RefreshIn, db: DB = Depends(get_db)):
    row = db.refresh_tokens.find_one({"token_hash": sha256(body.refresh_token)})
    if row:
        db.refresh_tokens.update(row.id, {"revoked": True})


# --------------------------------------------------------------- PASSWORD RESET
@router.post("/forgot/start", response_model=OtpStartOut, summary="Password reset - send OTP")
def forgot_start(body: EmailIn, db: DB = Depends(get_db)):
    user = _by_email(db, body.email)
    if not user:
        # do not leak which emails exist
        return OtpStartOut(
            email=body.email, expires_in=settings.OTP_TTL_MINUTES * 60,
            resend_in=settings.OTP_RESEND_SECONDS, delivered=True,
            message="If this email is registered, a code has been sent.",
        )
    return OtpStartOut(**issue_otp(db, body.email, OtpPurpose.reset, user.full_name))


@router.post("/forgot/verify", response_model=SignupTokenOut, summary="Password reset - verify OTP")
def forgot_verify(body: OtpVerifyIn, db: DB = Depends(get_db)):
    check_otp(db, body.email, body.code, OtpPurpose.reset)
    return SignupTokenOut(
        signup_token=create_reset_token(body.email.lower()),
        email=body.email.lower(),
        expires_in=settings.SIGNUP_TOKEN_MINUTES * 60,
    )


@router.post("/forgot/reset", response_model=TokenOut, summary="Password reset - set the new password")
def forgot_reset(body: ResetIn, db: DB = Depends(get_db)):
    payload = decode_token(body.reset_token, "reset")
    if not payload:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Reset link expired. Please start again.")
    user = _by_email(db, payload["email"])
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found.")
    db.users.update(user.id, {"hashed_password": hash_password(body.password)})
    db.refresh_tokens.update_many({"user_id": user.id}, {"revoked": True})
    user = db.users.get(user.id)
    return _issue_session(db, user)


# ----------------------------------------------------------------------- PROFILE
@router.get("/me", response_model=UserOut, summary="The signed-in user")
def me(user: User = Depends(current_user)):
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut, summary="Update profile details")
def update_me(
    body: ProfileUpdateIn,
    user: User = Depends(current_user),
    db: DB = Depends(get_db),
):
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    db.users.update(user.id, changes)
    return UserOut.model_validate(db.users.get(user.id))


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT, summary="Change password")
def change_password(
    body: PasswordChangeIn,
    user: User = Depends(current_user),
    db: DB = Depends(get_db),
):
    if user.hashed_password:
        if not body.current_password or not verify_password(body.current_password, user.hashed_password):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")
    db.users.update(user.id, {"hashed_password": hash_password(body.new_password)})


@router.post("/me/avatar", response_model=UserOut, summary="Upload a profile photo")
def upload_profile_photo(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
    db: DB = Depends(get_db),
):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Please upload a JPG, PNG, WEBP or HEIC image."
        )
    content = file.file.read()
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The uploaded file is empty.")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Images must be 5 MB or smaller."
        )

    uploaded = upload_avatar(content, user.id, file.content_type)
    if not uploaded:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Photo uploads are unavailable right now."
        )

    # replacing an image the user previously uploaded under a different id
    if user.avatar_public_id and user.avatar_public_id != uploaded["public_id"]:
        destroy(user.avatar_public_id)

    db.users.update(
        user.id, {"avatar_url": uploaded["url"], "avatar_public_id": uploaded["public_id"]}
    )
    return UserOut.model_validate(db.users.get(user.id))


@router.delete("/me/avatar", response_model=UserOut, summary="Remove the profile photo")
def delete_profile_photo(user: User = Depends(current_user), db: DB = Depends(get_db)):
    destroy(user.avatar_public_id)
    db.users.update(user.id, {"avatar_url": None, "avatar_public_id": None})
    return UserOut.model_validate(db.users.get(user.id))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, summary="Delete my account")
def delete_me(user: User = Depends(current_user), db: DB = Depends(get_db)):
    if user.role == Role.superadmin:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Super-admin accounts cannot be self-deleted.")
    destroy(user.avatar_public_id)
    db.delete_user_cascade(user.id)
