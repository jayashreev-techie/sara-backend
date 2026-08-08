"""
Company routes — login for companies registered by Super Admin.
Login: POST /api/company/login
Me:    GET  /api/company/me
"""
from passlib.context import CryptContext
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import create_access_token, get_current_company
from app.models import Company
from app.schemas import CompanyLoginRequest, CompanyLoginResponse

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=False)

router = APIRouter(prefix="/api/company", tags=["Company"])


# =====================================================
# COMPANY LOGIN
# =====================================================
@router.post("/login", response_model=CompanyLoginResponse)
def company_login(payload: CompanyLoginRequest, db: Session = Depends(get_db)):
    """Company login with email and password (credentials created by super admin)"""
    company = db.query(Company).filter(Company.email == payload.email).first()

    if not company or not pwd_context.verify(payload.password, company.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not company.is_active:
        raise HTTPException(status_code=403, detail="Company account is disabled")

    token = create_access_token(sub=company.email, role="company")

    return CompanyLoginResponse(
        success=True,
        message="Login successful",
        company_id=company.id,
        company_name=company.company_name,
        email=company.email,
        access_token=token,
    )


# =====================================================
# COMPANY ME
# =====================================================
@router.get("/me")
def company_me(company: Company = Depends(get_current_company)):
    """Get current logged-in company details"""
    return {
        "id": company.id,
        "company_name": company.company_name,
        "email": company.email,
        "phone": company.phone,
        "address": company.address,
        "is_active": company.is_active,
    }
