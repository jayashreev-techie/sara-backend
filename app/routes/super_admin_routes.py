"""
Super Admin routes — master account that manages companies.
Login: POST /api/super-admin/login
Companies CRUD: /api/super-admin/companies
"""
from passlib.context import CryptContext
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.auth import create_access_token, get_current_super_admin
from app.models import Company
from app.schemas import (
    SuperAdminLoginRequest, SuperAdminLoginResponse,
    CompanyCreateRequest, CompanyUpdateRequest, CompanyResponse,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/api/super-admin", tags=["Super Admin"])


# =====================================================
# LOGIN
# =====================================================
@router.post("/login", response_model=SuperAdminLoginResponse)
def super_admin_login(payload: SuperAdminLoginRequest):
    """Super admin login with hardcoded credentials from .env"""
    if payload.email != settings.SUPER_ADMIN_EMAIL:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if payload.password != settings.SUPER_ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(sub=settings.SUPER_ADMIN_EMAIL, role="super_admin")
    return SuperAdminLoginResponse(
        success=True,
        message="Super admin login successful",
        access_token=token,
    )


# =====================================================
# LIST ALL COMPANIES
# =====================================================
@router.get("/companies", response_model=list[CompanyResponse])
def list_companies(
    _: str = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """Get all registered companies"""
    return db.query(Company).order_by(Company.created_at.desc()).all()


# =====================================================
# REGISTER A COMPANY
# =====================================================
@router.post("/companies", response_model=CompanyResponse, status_code=201)
def create_company(
    payload: CompanyCreateRequest,
    _: str = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """Register a new company"""
    if db.query(Company).filter(Company.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    company = Company(
        company_name=payload.company_name,
        email=payload.email,
        password_hash=pwd_context.hash(payload.password),
        phone=payload.phone,
        address=payload.address,
        is_active=True,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


# =====================================================
# UPDATE A COMPANY
# =====================================================
@router.put("/companies/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: int,
    payload: CompanyUpdateRequest,
    _: str = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """Update company details"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    if payload.company_name is not None:
        company.company_name = payload.company_name
    if payload.email is not None:
        existing = db.query(Company).filter(Company.email == payload.email, Company.id != company_id).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email already in use")
        company.email = payload.email
    if payload.password is not None:
        company.password_hash = pwd_context.hash(payload.password)
    if payload.phone is not None:
        company.phone = payload.phone
    if payload.address is not None:
        company.address = payload.address
    if payload.is_active is not None:
        company.is_active = payload.is_active

    db.commit()
    db.refresh(company)
    return company


# =====================================================
# DELETE A COMPANY
# =====================================================
@router.delete("/companies/{company_id}")
def delete_company(
    company_id: int,
    _: str = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """Delete a company"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    db.delete(company)
    db.commit()
    return {"success": True, "message": "Company deleted successfully"}
