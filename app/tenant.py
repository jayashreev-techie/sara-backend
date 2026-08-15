"""
Tenant database management.

When a company is created by super admin:
  1. sanitize_db_name()        → "tenant_acme_corp"
  2. create_tenant_database()  → runs CREATE DATABASE on postgres server
  3. provision_tenant_schema() → creates all tenant tables in the new DB
  4. db_url saved to Company record in master DB

On every API request from a company:
  get_tenant_db() → reads company.db_url from JWT → returns DB session for that company's DB
"""
import re
from functools import lru_cache

from fastapi import Depends, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings


def sanitize_db_name(company_name: str) -> str:
    """Convert a company name to a valid PostgreSQL database name."""
    name = re.sub(r"[^a-zA-Z0-9]", "_", company_name.lower())
    name = re.sub(r"_+", "_", name).strip("_")
    return f"tenant_{name}"


def _postgres_admin_url() -> str:
    """URL pointing to the 'postgres' default database (needed to CREATE DATABASE)."""
    return (
        f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/postgres?sslmode={settings.DB_SSLMODE}"
    )


def get_tenant_db_url(db_name: str) -> str:
    """Build the connection URL for a tenant database."""
    return (
        f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{db_name}?sslmode={settings.DB_SSLMODE}"
    )


def create_tenant_database(db_name: str) -> str:
    """
    Create a new PostgreSQL database for a tenant.
    Returns the db_url for the new database.
    """
    admin_engine = create_engine(_postgres_admin_url(), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            # Check if DB already exists
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            )
            if not result.fetchone():
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        admin_engine.dispose()

    return get_tenant_db_url(db_name)


def provision_tenant_schema(db_url: str) -> None:
    """Create all tenant tables inside the new tenant database."""
    from app.database import TenantBase
    # Import all models so they register on TenantBase.metadata
    import app.models  # noqa: F401

    engine = create_engine(db_url, pool_pre_ping=True)
    try:
        TenantBase.metadata.create_all(bind=engine)
    finally:
        engine.dispose()


# Cache engines per db_url to avoid creating a new engine on every request
_tenant_engines: dict = {}


def _get_tenant_engine(db_url: str):
    if db_url not in _tenant_engines:
        _tenant_engines[db_url] = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=5,
            max_overflow=10,
        )
    return _tenant_engines[db_url]


def get_tenant_db(company=Depends(lambda: None)) -> Session:
    """
    FastAPI dependency — returns a DB session for the currently logged-in company's database.
    Must be used with get_current_company injected via the router.
    """
    # This placeholder is replaced by the real dependency below.
    raise NotImplementedError


def build_tenant_db_dependency():
    """
    Returns a FastAPI dependency that:
      1. Verifies the company JWT token
      2. Looks up the company's db_url from master DB
      3. Returns a session connected to that tenant's database
    """
    from app.auth import get_current_company

    def _get_tenant_db(company=Depends(get_current_company)):
        if not company.db_url:
            raise HTTPException(
                status_code=503,
                detail="Company database not provisioned yet. Contact super admin.",
            )
        engine = _get_tenant_engine(company.db_url)
        TenantSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = TenantSession()
        try:
            yield db
        finally:
            db.close()

    return _get_tenant_db


# The actual dependency to use in routes
get_tenant_db = build_tenant_db_dependency()
