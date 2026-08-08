"""OTP generation and SMS sending"""
import random
import requests
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.config import settings
from app.models import OTPRecord


def generate_otp(length: int = 6) -> str:
    return "".join([str(random.randint(0, 9)) for _ in range(length)])


def send_otp_via_msg91(mobile: str, otp: str) -> bool:
    """Production OTP sender via MSG91. Configure auth_key + template_id in .env"""
    if not settings.MSG91_AUTH_KEY or not settings.MSG91_TEMPLATE_ID:
        return False
    try:
        url = "https://control.msg91.com/api/v5/otp"
        params = {
            "template_id": settings.MSG91_TEMPLATE_ID,
            "mobile": f"91{mobile}",
            "authkey": settings.MSG91_AUTH_KEY,
            "otp": otp,
        }
        r = requests.post(url, params=params, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


def create_and_send_otp(db: Session, mobile: str) -> dict:
    """Create OTP, save to DB, and send via SMS (or return in test mode)."""
    otp = generate_otp(6)
    expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

    # Invalidate older OTPs for this mobile
    db.query(OTPRecord).filter(
        OTPRecord.mobile == mobile, OTPRecord.is_used == False
    ).update({"is_used": True})

    record = OTPRecord(mobile=mobile, otp_code=otp, expires_at=expires_at)
    db.add(record)
    db.commit()

    response = {"success": True, "message": "OTP sent successfully"}

    if settings.OTP_MODE == "test":
        # TEST MODE: return OTP in response (for development)
        response["otp"] = otp
        response["message"] = "OTP generated (test mode)"
    else:
        # PRODUCTION: send via SMS gateway
        sent = send_otp_via_msg91(mobile, otp)
        if not sent:
            response["success"] = False
            response["message"] = "Failed to send OTP. Try again."

    return response


def verify_otp(db: Session, mobile: str, otp: str) -> bool:
    """Check if OTP is valid and not expired."""
    record = (
        db.query(OTPRecord)
        .filter(
            OTPRecord.mobile == mobile,
            OTPRecord.otp_code == otp,
            OTPRecord.is_used == False,
            OTPRecord.expires_at > datetime.utcnow(),
        )
        .order_by(OTPRecord.id.desc())
        .first()
    )
    if not record:
        return False
    record.is_used = True
    db.commit()
    return True
