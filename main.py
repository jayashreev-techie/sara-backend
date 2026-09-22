"""
Sara Fabrication Mobile App API
FastAPI backend for Flutter mobile app (Recee + Installation flows)
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.database import engine, MasterBase
from app.routes import (
    auth_routes, recee_routes, installation_routes, job_routes,
    super_admin_routes, company_routes,
    client_routes, location_routes, store_routes, product_type_routes,
    dashboard_routes,
    supplier_routes, product_routes, inward_routes, outward_routes,
    designer_routes, printer_routes, design_routes, invoice_routes,
    user_management_routes, geo_routes,
)
import app.models  # noqa: F401 — ensure all models are registered on their respective bases
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext
from app.models import SuperAdmin

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Only create the master DB tables (companies, super_admins) on startup.
# Each company's tenant tables are created automatically when the company is registered.
MasterBase.metadata.create_all(bind=engine)

# Add new columns to companies table if they don't exist yet (safe to run every startup)
with engine.connect() as conn:
    for col, col_type in [("db_name", "VARCHAR(255)"), ("db_url", "TEXT")]:
        exists = conn.execute(text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='companies' AND column_name=:col"
        ), {"col": col}).fetchone()
        if not exists:
            conn.execute(text(f"ALTER TABLE companies ADD COLUMN {col} {col_type}"))
    conn.commit()

# Tenant databases predate some application fields. Add them to every tenant
# schema, including legacy schemas that no longer have a company master record.
# New tenant schemas receive them through the SQLAlchemy models automatically.
with engine.connect() as conn:
    tenant_schemas = conn.execute(text(
        "SELECT schema_name FROM information_schema.schemata "
        "WHERE schema_name LIKE 'tenant_%'"
    )).scalars()
    # Older installations kept tenant data in the public schema, so migrate
    # that legacy clients table as well.
    for schema_name in ["public", *tenant_schemas]:
        if (
            schema_name
            and schema_name.replace("_", "").isalnum()
            and schema_name[0].isalpha()
        ):
            for col, col_type in [
                ("address", "TEXT"),
                ("company_employer", "VARCHAR(255)"),
                ("email_id", "VARCHAR(255)"),
                ("address_line1", "VARCHAR(500)"),
                ("address_line2", "VARCHAR(500)"),
                ("country", "VARCHAR(100)"),
                ("state", "VARCHAR(100)"),
                ("district", "VARCHAR(100)"),
                ("pincode", "VARCHAR(10)"),
                ("pan_no", "VARCHAR(20)"),
                ("website_link", "VARCHAR(500)"),
            ]:
                conn.execute(text(
                    f'ALTER TABLE IF EXISTS "{schema_name}".clients '
                    f'ADD COLUMN IF NOT EXISTS {col} {col_type}'
                ))
            for column, column_type in [
                ("job_order_id", "VARCHAR(150)"),
                ("job_number", "VARCHAR(100)"),
                ("store_id", "INTEGER"),
                ("due_date", "DATE"),
                ("remarks", "TEXT"),
            ]:
                conn.execute(text(
                    f'ALTER TABLE IF EXISTS "{schema_name}".jobs '
                    f'ADD COLUMN IF NOT EXISTS {column} {column_type}'
                ))
            for col, col_type in [
                ("address_line1", "VARCHAR(500)"),
                ("address_line2", "VARCHAR(500)"),
                ("country", "VARCHAR(100)"),
                ("state", "VARCHAR(100)"),
                ("district", "VARCHAR(100)"),
                ("pincode", "VARCHAR(10)"),
                ("gst_no", "VARCHAR(20)"),
                ("pan_no", "VARCHAR(20)"),
                ("website_link", "VARCHAR(500)"),
            ]:
                conn.execute(text(
                    f'ALTER TABLE IF EXISTS "{schema_name}".stores '
                    f'ADD COLUMN IF NOT EXISTS {col} {col_type}'
                ))
            conn.execute(text(
                f'CREATE TABLE IF NOT EXISTS "{schema_name}".product_photos ('
                'id SERIAL PRIMARY KEY, '
                'product_id INTEGER NOT NULL REFERENCES '
                f'"{schema_name}".job_products(id), '
                'file_path VARCHAR(500) NOT NULL, '
                'original_name VARCHAR(255), '
                'created_at TIMESTAMP DEFAULT NOW()'
                ')'
            ))
    conn.commit()

# Seed default super admin from .env if none exists in DB
_MasterSession = sessionmaker(bind=engine)
with _MasterSession() as session:
    if not session.query(SuperAdmin).first():
        session.add(SuperAdmin(
            email=settings.SUPER_ADMIN_EMAIL,
            password_hash=_pwd_context.hash(settings.SUPER_ADMIN_PASSWORD),
        ))
        session.commit()

app = FastAPI(
    title="Sara Fabrication Mobile API",
    description="Backend for Sara Recee Flutter mobile app",
    version="1.0.0",
)

# CORS — browser clients must be listed explicitly when credentials are enabled.
# Native Flutter Android/iOS clients are not affected by CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://sara-fabrications-app.vercel.app",
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file serving for uploaded photos (only in non-serverless environments)
import os
if os.environ.get("VERCEL") != "1":
    upload_path = Path(settings.UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(upload_path)), name="uploads")

# Routers
app.include_router(auth_routes.router)
app.include_router(client_routes.router)
app.include_router(location_routes.router)
app.include_router(store_routes.router)
app.include_router(product_type_routes.router)
app.include_router(job_routes.router)
app.include_router(job_routes.job_product_router)
app.include_router(recee_routes.router)
app.include_router(installation_routes.router)
app.include_router(super_admin_routes.router)
app.include_router(company_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(supplier_routes.router)
app.include_router(product_routes.router)
app.include_router(inward_routes.router)
app.include_router(outward_routes.router)
app.include_router(designer_routes.router)
app.include_router(printer_routes.router)
app.include_router(design_routes.router)
app.include_router(invoice_routes.router)
app.include_router(user_management_routes.router)
app.include_router(geo_routes.router)


@app.get("/")
def root():
    return {
        "app": "Sara Fabrication Mobile API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "auth": "/api/auth/*",
            "jobs": "/api/jobs/*",
            "recee": "/api/recee/*",
            "installation": "/api/installation/*",
        },
    }


@app.get("/health")
def health():
    return {"status": "ok", "env": settings.APP_ENV}


@app.get("/debug/routes")
def debug_routes():
    return [{"path": r.path, "methods": list(r.methods)} for r in app.routes if hasattr(r, "methods")]
