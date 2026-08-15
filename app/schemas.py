"""Pydantic schemas for request/response validation"""
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, date
from typing import Optional, List


# =====================================================
# REGISTER SCHEMAS (3-step web form — Sara Fabrications)
# Step 1: Account  |  Step 2: Profile  |  Step 3: Review
# =====================================================
class RegisterRequest(BaseModel):
    # Step 1 — Account
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    confirm_password: str

    # Step 2 — Profile
    full_name: str = Field(..., min_length=1, max_length=255)
    gender: str = Field(..., pattern="^(Male|Female|Other)$")
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=1, max_length=100)

    # Step 3 — Review
    terms_agreed: bool


class RegisterResponse(BaseModel):
    success: bool
    message: str
    user_id: int
    access_token: str
    token_type: str = "bearer"


# =====================================================
# LOGIN SCHEMA (web — email + password)
# =====================================================
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str
    user_id: int
    email: str
    username: str
    full_name: str
    access_token: str
    token_type: str = "bearer"


# =====================================================
# AUTH SCHEMAS (Img 1, 2 - Login & OTP)
# =====================================================
class SendOTPRequest(BaseModel):
    mobile: str = Field(..., min_length=10, max_length=10)


class SendOTPResponse(BaseModel):
    success: bool
    message: str
    # Only in test mode (for development)
    otp: Optional[str] = None


class VerifyOTPRequest(BaseModel):
    mobile: str = Field(..., min_length=10, max_length=10)
    otp: str = Field(..., min_length=4, max_length=6)


class VerifyOTPResponse(BaseModel):
    success: bool
    message: str
    access_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[dict] = None


# =====================================================
# CLIENTS HOME (Img 3 - Clients list with progress)
# =====================================================
class ClientHomeItem(BaseModel):
    client_id: int
    company_name: str
    total_stores: int
    completed_stores: int
    progress_label: str  # "15/60"

    class Config:
        from_attributes = True


# =====================================================
# STORES LIST (Img 4 - Store 1, 2, 3... with status)
# =====================================================
class StoreListItem(BaseModel):
    job_product_id: int
    store_id: int
    store_name: str
    store_address: Optional[str] = None
    product_type: Optional[str] = None
    total_qty: int = 1
    status: str  # pending | completed

    class Config:
        from_attributes = True


# =====================================================
# MEASUREMENT FORM (Img 4, 5 - Recee submission)
# =====================================================
class ReceeSubmitRequest(BaseModel):
    job_product_id: int
    material: Optional[str] = None
    width_inch: float
    height_inch: float
    unit: str = "inches"
    remarks: Optional[str] = None
    # photo will come via multipart upload separately


class ReceeSubmitResponse(BaseModel):
    success: bool
    message: str
    measurement_id: Optional[int] = None


# =====================================================
# RECEE HISTORY (Img 5 - Branch-113 view)
# =====================================================
class ReceeHistoryItem(BaseModel):
    id: int
    user_name: Optional[str] = None
    date: str  # "12/2/25"
    time: Optional[str] = None  # "06:21AM"
    store_name: Optional[str] = None
    location: Optional[str] = None
    width_inch: float
    height_inch: float
    photo_url: Optional[str] = None
    pole: Optional[str] = None
    qty: Optional[str] = None

    class Config:
        from_attributes = True


# =====================================================
# INSTALLATION (Img 6 - 3 photo sections)
# =====================================================
class InstallationSubmitRequest(BaseModel):
    job_product_id: int
    material: Optional[str] = None
    width_inch: float
    height_inch: float
    unit: str = "inches"
    remarks: Optional[str] = None


class InstallationSubmitResponse(BaseModel):
    success: bool
    message: str
    installation_id: Optional[int] = None


# =====================================================
# JOB CREATION (admin/web side — Img 14 Job Creation Form)
# =====================================================
class JobProductCreateItem(BaseModel):
    store_id: int
    location_id: Optional[int] = None
    product_type_id: Optional[int] = None
    total_qty: int = 1
    width_inch: float = 0.0
    height_inch: float = 0.0
    is_double_sided: bool = False
    is_pool: bool = False
    remark: Optional[str] = None


class JobCreateRequest(BaseModel):
    client_id: int
    job_creation_date: Optional[date] = None  # default: today
    client_contact_person_name: Optional[str] = None
    client_contact_person_mobile: Optional[str] = None
    po_number: Optional[str] = None
    po_date: Optional[date] = None
    measurement_date: Optional[date] = None
    measurement_person_name: Optional[str] = None
    measurement_person_mobile: str = Field(..., min_length=10, max_length=15)
    products: List[JobProductCreateItem] = []


class JobCreateResponse(BaseModel):
    success: bool
    message: str
    job_id: int
    job_product_ids: List[int] = []


class JobListItem(BaseModel):
    id: int
    job_creation_date: Optional[date] = None
    client_id: int
    company_name: Optional[str] = None
    po_number: Optional[str] = None
    measurement_person_name: Optional[str] = None
    measurement_person_mobile: Optional[str] = None
    status: Optional[str] = None
    product_count: int = 0

    class Config:
        from_attributes = True


# =====================================================
# SUPER ADMIN
# =====================================================
class SuperAdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class SuperAdminLoginResponse(BaseModel):
    success: bool
    message: str
    access_token: str
    token_type: str = "bearer"


class SuperAdminCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class SuperAdminResponse(BaseModel):
    id: int
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


# =====================================================
# COMPANY (managed by Super Admin)
# =====================================================
class CompanyCreateRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=6)
    phone: Optional[str] = None
    address: Optional[str] = None


class CompanyUpdateRequest(BaseModel):
    company_name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=6)
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None


class CompanyResponse(BaseModel):
    id: int
    company_name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# =====================================================
# COMPANY LOGIN
# =====================================================
class CompanyLoginRequest(BaseModel):
    email: EmailStr
    password: str


class CompanyLoginResponse(BaseModel):
    success: bool
    message: str
    company_id: int
    company_name: str
    email: str
    access_token: str
    token_type: str = "bearer"


# =====================================================
# JOB UPDATE
# =====================================================
class JobUpdateRequest(BaseModel):
    client_id: Optional[int] = None
    job_creation_date: Optional[date] = None
    client_contact_person_name: Optional[str] = None
    client_contact_person_mobile: Optional[str] = None
    po_number: Optional[str] = None
    po_date: Optional[date] = None
    measurement_date: Optional[date] = None
    measurement_person_name: Optional[str] = None
    measurement_person_mobile: Optional[str] = None
    status: Optional[str] = None


class JobProductUpdateRequest(BaseModel):
    store_id: Optional[int] = None
    location_id: Optional[int] = None
    product_type_id: Optional[int] = None
    total_qty: Optional[int] = None
    width_inch: Optional[float] = None
    height_inch: Optional[float] = None
    is_double_sided: Optional[bool] = None
    is_pool: Optional[bool] = None
    remark: Optional[str] = None


class JobProductResponse(BaseModel):
    id: int
    store_id: Optional[int] = None
    store_name: Optional[str] = None
    location_id: Optional[int] = None
    product_type_id: Optional[int] = None
    product_type: Optional[str] = None
    total_qty: int = 1
    width_inch: float = 0.0
    height_inch: float = 0.0
    sq_ft_unit: float = 0.0
    total_sq_ft: float = 0.0
    is_double_sided: bool = False
    is_pool: bool = False
    remark: Optional[str] = None
    photo_path: Optional[str] = None
    recee_status: str = "pending"
    installation_status: str = "pending"

    class Config:
        from_attributes = True


class JobDetailResponse(BaseModel):
    id: int
    job_creation_date: Optional[date] = None
    client_id: int
    company_name: Optional[str] = None
    client_contact_person_name: Optional[str] = None
    client_contact_person_mobile: Optional[str] = None
    po_number: Optional[str] = None
    po_date: Optional[date] = None
    measurement_date: Optional[date] = None
    measurement_person_name: Optional[str] = None
    measurement_person_mobile: Optional[str] = None
    status: str = "pending"
    created_at: Optional[datetime] = None
    products: List[JobProductResponse] = []

    class Config:
        from_attributes = True


# =====================================================
# GENERIC
# =====================================================
class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None
