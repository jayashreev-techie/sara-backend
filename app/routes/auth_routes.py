"""
Authentication routes — maps to mobile screens:
- Img 1: Login screen (Enter mobile)
- Img 2: OTP Verification screen
- Web: 3-step registration form (Sara Fabrications)
"""
from datetime import datetime
from passlib.context import CryptContext
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import (
    SendOTPRequest, SendOTPResponse,
    VerifyOTPRequest, VerifyOTPResponse,
    RegisterRequest, RegisterResponse,
    LoginRequest, LoginResponse,
)
from app.models import MobileUser, Job, User
from app.utils.otp import create_and_send_otp, verify_otp
from app.auth import create_access_token, get_current_mobile

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/api/auth", tags=["Auth"])


# =====================================================
# 0. REGISTER — 3-step web form "Create Account"
# =====================================================
@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """
    Sara Fabrications web registration form — 3 steps:
    Step 1: email, username, password
    Step 2: full_name, gender, city, state
    Step 3: terms_agreed review & submit
    """
    # Passwords must match
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    # Terms must be accepted
    if not payload.terms_agreed:
        raise HTTPException(status_code=400, detail="You must agree to the Terms of Service")

    # Unique email check
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Unique username check
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=409, detail="Username already taken")

    # Hash password
    hashed = pwd_context.hash(payload.password)

    user = User(
        email=payload.email,
        username=payload.username,
        password_hash=hashed,
        full_name=payload.full_name,
        gender=payload.gender,
        city=payload.city,
        state=payload.state,
        terms_agreed=payload.terms_agreed,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Issue JWT using email as subject
    token = create_access_token(user.email, role="mobile")

    return RegisterResponse(
        success=True,
        message="Account created successfully",
        user_id=user.id,
        access_token=token,
        token_type="bearer",
    )


# =====================================================
# 1. LOGIN — web email + password
# =====================================================
@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Web login with email and password.
    Returns JWT token on success.
    """
    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not pwd_context.verify(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_access_token(user.email, role="mobile")

    return LoginResponse(
        success=True,
        message="Login successful",
        user_id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        access_token=token,
        token_type="bearer",
    )


# =====================================================
# 2. SEND OTP — Img 1 "Register" button press
# =====================================================
@router.post("/send-otp", response_model=SendOTPResponse)
def send_otp(payload: SendOTPRequest, db: Session = Depends(get_db)):
    """
    Mobile app sends 10-digit number → backend generates OTP →
    SMS-aa send aagum (production) or response la return aagum (test).
    """
    mobile = payload.mobile.strip()

    if not mobile.isdigit() or len(mobile) != 10:
        raise HTTPException(status_code=400, detail="Invalid mobile number")

    # Check if this mobile is registered as a measurement person in any job
    job_exists = (
        db.query(Job).filter(Job.measurement_person_mobile == mobile).first()
    )
    user_exists = db.query(MobileUser).filter(MobileUser.mobile == mobile).first()

    if not job_exists and not user_exists:
        raise HTTPException(
            status_code=404,
            detail="Mobile number not registered. Contact admin.",
        )

    result = create_and_send_otp(db, mobile)
    return result


# =====================================================
# 2. VERIFY OTP — Img 2 "Verify" button press
# =====================================================
@router.post("/verify-otp", response_model=VerifyOTPResponse)
def verify_otp_endpoint(payload: VerifyOTPRequest, db: Session = Depends(get_db)):
    """
    OTP correct-aana → JWT token + user info return aagum →
    Welcome / Successfully verified screen show aagum.
    """
    mobile = payload.mobile.strip()
    otp = payload.otp.strip()

    if not verify_otp(db, mobile, otp):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    # Auto-create mobile user record if not exists
    user = db.query(MobileUser).filter(MobileUser.mobile == mobile).first()
    if not user:
        # Pull name from any job assigned to this mobile
        job = db.query(Job).filter(Job.measurement_person_mobile == mobile).first()
        name = job.measurement_person_name if job else None
        user = MobileUser(mobile=mobile, name=name, role="worker", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

    user.last_login_at = datetime.utcnow()
    db.commit()

    token = create_access_token(mobile, role="mobile")

    return VerifyOTPResponse(
        success=True,
        message="Successfully verified",
        access_token=token,
        token_type="bearer",
        user={
            "id": user.id,
            "mobile": user.mobile,
            "name": user.name,
            "role": user.role,
        },
    )


# =====================================================
# 3. ME — current user details
# =====================================================
@router.get("/me")
def get_me(
    mobile: str = Depends(get_current_mobile),
    db: Session = Depends(get_db),
):
    user = db.query(MobileUser).filter(MobileUser.mobile == mobile).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "mobile": user.mobile,
        "name": user.name,
        "role": user.role,
        "last_login_at": user.last_login_at,
    }


# =====================================================
# 4. LOGOUT (client-side token clear; this just confirms)
# =====================================================
@router.post("/logout")
def logout(mobile: str = Depends(get_current_mobile)):
    return {"success": True, "message": "Logged out"}
