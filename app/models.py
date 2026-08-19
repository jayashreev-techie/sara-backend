"""
Database models matching the existing web app schema.

⚠️ IMPORTANT: Web team kitta confirm panni table/column names update pannunga.
Naan web screenshots base pani (Img 7-15) probable column names use panren.
"""
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Date, Float, ForeignKey, Boolean
)
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import MasterBase, TenantBase


# =========================================================
# CLIENT (Img 8 - Client Entry Form)
# =========================================================
class Client(TenantBase):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    contact_person_name = Column(String(255))
    sales_person_name = Column(String(255))
    mobile = Column(String(15))
    gst_number = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================================================
# PRODUCT TYPE (Img 9)
# =========================================================
class ProductType(TenantBase):
    __tablename__ = "product_types"

    id = Column(Integer, primary_key=True, index=True)
    product_type = Column(String(255), nullable=False)
    hsn_code = Column(String(20))
    price = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================================================
# CLIENT-PRODUCT LINK (Img 10)
# =========================================================
class ClientProductLink(TenantBase):
    __tablename__ = "client_product_links"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    product_type_id = Column(Integer, ForeignKey("product_types.id"))


# =========================================================
# LOCATION (Img 11)
# =========================================================
class Location(TenantBase):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    district = Column(String(100))
    location_name = Column(String(255))


# =========================================================
# STORE (Img 12)
# =========================================================
class Store(TenantBase):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    store_name = Column(String(255), nullable=False)
    store_address = Column(Text)
    store_mobile = Column(String(15))
    location_id = Column(Integer, ForeignKey("locations.id"))
    client_id = Column(Integer, ForeignKey("clients.id"))


# =========================================================
# JOB (Img 14 - Job Creation Entry Form)
# =========================================================
class Job(TenantBase):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_creation_date = Column(Date)
    client_id = Column(Integer, ForeignKey("clients.id"))
    client_contact_person_name = Column(String(255))
    client_contact_person_mobile = Column(String(15))
    po_number = Column(String(100))
    po_date = Column(Date, nullable=True)
    measurement_date = Column(Date)
    measurement_person_name = Column(String(255))
    # ⭐ THIS is the link between web admin and mobile app login
    measurement_person_mobile = Column(String(15), index=True)
    status = Column(String(50), default="pending")  # pending|in_progress|completed
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", backref="jobs")
    products = relationship("JobProduct", back_populates="job", cascade="all, delete")


# =========================================================
# JOB PRODUCT (each row in Img 14 "Product #1" section)
# Adhuthan mobile la "Store 1, Store 2..." aa varum
# =========================================================
class JobProduct(TenantBase):
    __tablename__ = "job_products"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    store_id = Column(Integer, ForeignKey("stores.id"))
    location_id = Column(Integer, ForeignKey("locations.id"))
    product_type_id = Column(Integer, ForeignKey("product_types.id"))
    total_qty = Column(Integer, default=1)

    # Estimate from web admin
    width_inch = Column(Float, default=0.0)
    height_inch = Column(Float, default=0.0)
    sq_ft_unit = Column(Float, default=0.0)
    total_sq_ft = Column(Float, default=0.0)
    is_double_sided = Column(Boolean, default=False)
    is_pool = Column(Boolean, default=False)
    remark = Column(Text)
    photo_path = Column(String(500))

    # Recee status (mobile updates this)
    recee_status = Column(String(50), default="pending")  # pending|completed
    recee_completed_at = Column(DateTime, nullable=True)

    # Installation status (mobile updates this after recee complete)
    installation_status = Column(String(50), default="pending")  # pending|completed
    installation_completed_at = Column(DateTime, nullable=True)

    job = relationship("Job", back_populates="products")
    store = relationship("Store")
    product_type = relationship("ProductType")


# =========================================================
# RECEE MEASUREMENT (mobile worker enter panrathu)
# =========================================================
class ReceeMeasurement(TenantBase):
    __tablename__ = "recee_measurements"

    id = Column(Integer, primary_key=True, index=True)
    job_product_id = Column(Integer, ForeignKey("job_products.id"))
    store_id = Column(Integer, ForeignKey("stores.id"))
    measured_by_mobile = Column(String(15))
    material = Column(String(255))
    width_inch = Column(Float)
    height_inch = Column(Float)
    unit = Column(String(20), default="inches")
    photo_path = Column(String(500))  # tap-to-upload / camera (Img 4)
    remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================================================
# INSTALLATION ENTRY (mobile - Img 6 last screen)
# 3 photo sections: Recee (reference), Design, Installation
# =========================================================
class Installation(TenantBase):
    __tablename__ = "installations"

    id = Column(Integer, primary_key=True, index=True)
    job_product_id = Column(Integer, ForeignKey("job_products.id"))
    store_id = Column(Integer, ForeignKey("stores.id"))
    installed_by_mobile = Column(String(15))
    material = Column(String(255))
    width_inch = Column(Float)
    height_inch = Column(Float)
    unit = Column(String(20), default="inches")
    recee_photo_path = Column(String(500))      # auto-pulled from recee
    design_photo_path = Column(String(500))     # design reference
    installation_photo_path = Column(String(500))  # actual installed photo
    remarks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================================================
# USER (Sara Fabrications web registration — 3-step form)
# =========================================================
class User(TenantBase):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    gender = Column(String(20))
    city = Column(String(100))
    state = Column(String(100))
    terms_agreed = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================================================
# OTP (transient - clean up after expiry)
# =========================================================
class OTPRecord(TenantBase):
    __tablename__ = "otp_records"

    id = Column(Integer, primary_key=True, index=True)
    mobile = Column(String(15), index=True, nullable=False)
    otp_code = Column(String(10), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================================================
# MOBILE APP USER (optional - track mobile users)
# Login mobile = jobs.measurement_person_mobile
# =========================================================
class MobileUser(TenantBase):
    __tablename__ = "mobile_users"

    id = Column(Integer, primary_key=True, index=True)
    mobile = Column(String(15), unique=True, index=True, nullable=False)
    name = Column(String(255))
    role = Column(String(50), default="worker")  # worker | supervisor
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================================================
# SUPER ADMIN (stored in master DB)
# =========================================================
class SuperAdmin(MasterBase):
    __tablename__ = "super_admins"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================================================
# COMPANY (created by Super Admin)
# =========================================================
class Company(MasterBase):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    phone = Column(String(15))
    address = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Tenant database info (set when company is created)
    db_name = Column(String(255), nullable=True)
    db_url = Column(Text, nullable=True)


# =========================================================
# SUPPLIER
# =========================================================
class Supplier(TenantBase):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    mobile = Column(String(15))
    gst = Column(String(20))
    bank_details = Column(String(500))
    address = Column(Text)
    is_active = Column(Boolean, default=True)
    del_flag = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================================================
# PRODUCT CATEGORY
# =========================================================
class ProductCategory(TenantBase):
    __tablename__ = "product_categories"

    id = Column(Integer, primary_key=True, index=True)
    category_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    del_flag = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================================================
# PRODUCT UNIT
# =========================================================
class ProductUnit(TenantBase):
    __tablename__ = "product_units"

    id = Column(Integer, primary_key=True, index=True)
    unit = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    del_flag = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================================================
# PRODUCT MASTER
# =========================================================
class Product(TenantBase):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("product_categories.id"), nullable=True)
    hsn_number = Column(String(50))
    product_name = Column(String(255), nullable=False)
    product_description = Column(Text)
    product_unit_id = Column(Integer, ForeignKey("product_units.id"), nullable=True)
    gst = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    del_flag = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    category = relationship("ProductCategory")
    unit = relationship("ProductUnit")


# =========================================================
# INWARD ENTRY (header)
# =========================================================
class InwardEntry(TenantBase):
    __tablename__ = "inward_entries"

    id = Column(Integer, primary_key=True, index=True)
    inward_code = Column(Integer)
    inward_date = Column(Date)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    bill_file_name = Column(String(255))
    bill_file_path = Column(String(500))
    is_active = Column(Boolean, default=True)
    del_flag = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    supplier = relationship("Supplier")
    products = relationship("InwardProduct", back_populates="inward_entry", cascade="all, delete")


# =========================================================
# INWARD PRODUCT (line items)
# =========================================================
class InwardProduct(TenantBase):
    __tablename__ = "inward_products"

    id = Column(Integer, primary_key=True, index=True)
    inward_entry_id = Column(Integer, ForeignKey("inward_entries.id"))
    inward_code = Column(Integer)
    inward_date = Column(Date)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("product_categories.id"), nullable=True)
    unit_id = Column(Integer, ForeignKey("product_units.id"), nullable=True)
    gst = Column(String(10))
    qty = Column(Float, default=0.0)
    per_qty_amt = Column(Float, default=0.0)
    total_amount = Column(Float, default=0.0)
    total_gst_amount = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    del_flag = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    inward_entry = relationship("InwardEntry", back_populates="products")
    product = relationship("Product")
    category = relationship("ProductCategory")
    unit = relationship("ProductUnit")


# =========================================================
# OUTWARD ENTRY
# =========================================================
class OutwardEntry(TenantBase):
    __tablename__ = "outward_entries"

    id = Column(Integer, primary_key=True, index=True)
    outward_code = Column(Integer)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    inward_product_id = Column(Integer, ForeignKey("inward_products.id"), nullable=True)
    act_qty = Column(Float, default=0.0)
    out_qty = Column(Float, default=0.0)
    remark = Column(Text)
    is_active = Column(Boolean, default=True)
    del_flag = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    supplier = relationship("Supplier")
    product = relationship("Product")
    inward_product = relationship("InwardProduct")


# =========================================================
# DESIGNER
# =========================================================
class Designer(TenantBase):
    __tablename__ = "designers"

    id = Column(Integer, primary_key=True, index=True)
    designer_name = Column(String(255), nullable=False)
    mobile = Column(String(15))
    is_active = Column(Boolean, default=True)
    del_flag = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================================================
# PRINTER
# =========================================================
class Printer(TenantBase):
    __tablename__ = "printers"

    id = Column(Integer, primary_key=True, index=True)
    printer_name = Column(String(255), nullable=False)
    contact_person_name = Column(String(255))
    mobile = Column(String(15))
    address = Column(Text)
    gst_no = Column(String(20))
    is_active = Column(Boolean, default=True)
    del_flag = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================================================
# WORK DESIGN (Design → Printing → Fabrication workflow)
# Links to a Job via job_id
# =========================================================
class WorkDesign(TenantBase):
    __tablename__ = "work_designs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    design_file_1 = Column(String(255))
    design_file_1_path = Column(String(500))
    design_file_2 = Column(String(255))
    design_file_2_path = Column(String(500))
    printer_id = Column(Integer, ForeignKey("printers.id"), nullable=True)
    printing_done = Column(Boolean, default=False)
    move_to_fabrication = Column(Boolean, default=False)
    fabrication_done = Column(Boolean, default=False)
    del_flag = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job")
    printer = relationship("Printer")


# =========================================================
# INVOICE (Finance / Billing)
# =========================================================
class Invoice(TenantBase):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_no = Column(String(50), unique=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    invoice_date = Column(Date)
    buyer_gstin = Column(String(20))
    company_gstin = Column(String(20))
    place_of_supply = Column(String(100))
    subtotal = Column(Float, default=0.0)
    cgst = Column(Float, default=0.0)
    sgst = Column(Float, default=0.0)
    igst = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete")


# =========================================================
# INVOICE ITEM (line items)
# =========================================================
class InvoiceItem(TenantBase):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    description = Column(String(500))
    hsn_code = Column(String(20))
    qty = Column(Float, default=0.0)
    rate = Column(Float, default=0.0)
    gst_rate = Column(Float, default=18.0)
    taxable_value = Column(Float, default=0.0)
    cgst = Column(Float, default=0.0)
    sgst = Column(Float, default=0.0)
    igst = Column(Float, default=0.0)
    total = Column(Float, default=0.0)

    invoice = relationship("Invoice", back_populates="items")


# =========================================================
# USER ROLE (for company users)
# =========================================================
class UserRole(TenantBase):
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, index=True)
    role_name = Column(String(100), nullable=False)


# =========================================================
# COMPANY USER (web admin users within a tenant)
# =========================================================
class CompanyUser(TenantBase):
    __tablename__ = "company_users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey("user_roles.id"), nullable=True)
    status = Column(Integer, default=1)  # 0=inactive, 1=active, 2=suspended
    created_at = Column(DateTime, default=datetime.utcnow)

    role = relationship("UserRole")
