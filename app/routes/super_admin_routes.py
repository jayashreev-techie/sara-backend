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
from app.models import Company, SuperAdmin
from app.schemas import (
    SuperAdminLoginRequest, SuperAdminLoginResponse,
    SuperAdminCreateRequest, SuperAdminResponse,
    CompanyCreateRequest, CompanyUpdateRequest, CompanyResponse,
)
from app.tenant import sanitize_schema_name, create_tenant_schema, provision_tenant_schema

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/api/super-admin", tags=["Super Admin"])


# =====================================================
# LOGIN
# =====================================================
@router.post("/login", response_model=SuperAdminLoginResponse)
def super_admin_login(payload: SuperAdminLoginRequest, db: Session = Depends(get_db)):
    """Super admin login — credentials verified against master DB"""
    admin = db.query(SuperAdmin).filter(SuperAdmin.email == payload.email).first()
    if not admin or not pwd_context.verify(payload.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(sub=admin.email, role="super_admin")
    return SuperAdminLoginResponse(
        success=True,
        message="Super admin login successful",
        access_token=token,
    )


# =====================================================
# LIST ALL SUPER ADMINS
# =====================================================
@router.get("/admins", response_model=list[SuperAdminResponse])
def list_admins(
    _: str = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """List all super admins"""
    return db.query(SuperAdmin).order_by(SuperAdmin.created_at.desc()).all()


# =====================================================
# CREATE A NEW SUPER ADMIN
# =====================================================
@router.post("/admins", response_model=SuperAdminResponse, status_code=201)
def create_admin(
    payload: SuperAdminCreateRequest,
    _: str = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """Create a new super admin — only existing super admin can do this"""
    if db.query(SuperAdmin).filter(SuperAdmin.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    admin = SuperAdmin(
        email=payload.email,
        password_hash=pwd_context.hash(payload.password),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


# =====================================================
# DELETE A SUPER ADMIN
# =====================================================
@router.delete("/admins/{admin_id}")
def delete_admin(
    admin_id: int,
    _: str = Depends(get_current_super_admin),
    db: Session = Depends(get_db),
):
    """Delete a super admin — cannot delete the last one"""
    admin = db.query(SuperAdmin).filter(SuperAdmin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin not found")

    if db.query(SuperAdmin).count() == 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last super admin")

    db.delete(admin)
    db.commit()
    return {"success": True, "message": "Admin deleted successfully"}


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

    # Step 1: Save company record in master DB
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

    # Step 2: Create a dedicated schema for this company
    schema_name = sanitize_schema_name(payload.company_name)
    schema_name = f"{schema_name}_{company.id}"
    try:
        create_tenant_schema(schema_name)
        provision_tenant_schema(schema_name)
        # Step 3: Save schema name back to company record
        company.db_name = schema_name
        company.db_url = None
        db.commit()
        db.refresh(company)
    except Exception as e:
        # Keep the company record but expose the real error so we can debug
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Company created (id={company.id}) but schema provisioning failed: {type(e).__name__}: {e}")

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
