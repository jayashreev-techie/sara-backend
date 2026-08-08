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
from app.database import Base


# =========================================================
# CLIENT (Img 8 - Client Entry Form)
# =========================================================
class Client(Base):
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
class ProductType(Base):
    __tablename__ = "product_types"

    id = Column(Integer, primary_key=True, index=True)
    product_type = Column(String(255), nullable=False)
    hsn_code = Column(String(20))
    price = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================================================
# CLIENT-PRODUCT LINK (Img 10)
# =========================================================
class ClientProductLink(Base):
    __tablename__ = "client_product_links"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    product_type_id = Column(Integer, ForeignKey("product_types.id"))


# =========================================================
# LOCATION (Img 11)
# =========================================================
class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    district = Column(String(100))
    location_name = Column(String(255))


# =========================================================
# STORE (Img 12)
# =========================================================
class Store(Base):
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
class Job(Base):
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
class JobProduct(Base):
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
class ReceeMeasurement(Base):
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
class Installation(Base):
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
class User(Base):
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
class OTPRecord(Base):
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
class MobileUser(Base):
    __tablename__ = "mobile_users"

    id = Column(Integer, primary_key=True, index=True)
    mobile = Column(String(15), unique=True, index=True, nullable=False)
    name = Column(String(255))
    role = Column(String(50), default="worker")  # worker | supervisor
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# =========================================================
# COMPANY (created by Super Admin)
# =========================================================
class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    phone = Column(String(15))
    address = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
