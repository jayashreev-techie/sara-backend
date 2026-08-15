"""
Tenant schema management (schema-per-tenant on Neon/PostgreSQL).

When a company is created by super admin:
  1. sanitize_schema_name()     → "tenant_acme_corp_1"
  2. create_tenant_schema()     → runs CREATE SCHEMA in master DB
  3. provision_tenant_schema()  → creates all tenant tables inside that schema
  4. schema_name saved to Company.db_name in master DB

On every API request from a company:
  get_tenant_db() → reads company.db_name (schema) from JWT
                  → returns DB session with search_path set to that schema
"""
import re

from fastapi import Depends, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings


def sanitize_schema_name(company_name: str) -> str:
    """Convert a company name to a valid PostgreSQL schema name."""
    name = re.sub(r"[^a-zA-Z0-9]", "_", company_name.lower())
    name = re.sub(r"_+", "_", name).strip("_")
    return f"tenant_{name}"


# Cache engines per schema — one engine per tenant schema
_tenant_engines: dict = {}


def _make_engine_with_search_path(schema_name: str, **kwargs):
    """Create a SQLAlchemy engine that sets search_path on every connection checkout.
    Using an event listener instead of connect_args so it works with Neon's pgBouncer pooler."""
    from sqlalchemy import event

    engine = create_engine(settings.database_url, pool_pre_ping=True, **kwargs)

    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute(f"SET search_path TO \"{schema_name}\", public")
        cursor.close()

    return engine


def _get_schema_engine(schema_name: str):
    """Return a cached SQLAlchemy engine with search_path set to the tenant schema."""
    if schema_name not in _tenant_engines:
        _tenant_engines[schema_name] = _make_engine_with_search_path(
            schema_name,
            pool_recycle=3600,
            pool_size=5,
            max_overflow=10,
        )
    return _tenant_engines[schema_name]




def create_tenant_schema(schema_name: str) -> None:
    """Create a new PostgreSQL schema for a tenant inside the master database."""
    from app.database import engine
    with engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
        conn.commit()


def provision_tenant_schema(schema_name: str) -> None:
    """Create all tenant tables inside the tenant schema."""
    from app.database import TenantBase
    import app.models  # noqa: F401 — register all models on TenantBase

    schema_engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        with schema_engine.begin() as conn:
            # schema_translate_map redirects all unschema'd tables into the tenant schema
            conn = conn.execution_options(schema_translate_map={None: schema_name})
            TenantBase.metadata.create_all(conn)
    finally:
        schema_engine.dispose()


def build_tenant_db_dependency():
    """
    Returns a FastAPI dependency that:
      1. Verifies the company JWT token
      2. Reads the company's schema name from master DB
      3. Returns a session scoped to that tenant's schema
    """
    from app.auth import get_current_company

    def _get_tenant_db(company=Depends(get_current_company)):
        if not company.db_name:
            raise HTTPException(
                status_code=503,
                detail="Company database not provisioned yet. Contact super admin.",
            )
        engine = _get_schema_engine(company.db_name)
        TenantSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = TenantSession()
        try:
            yield db
        finally:
            db.close()

    return _get_tenant_db


# The actual dependency to use in routes
get_tenant_db = build_tenant_db_dependency()
