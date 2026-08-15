"""SQLAlchemy database session"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# Master DB engine (holds only the companies table)
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# MasterBase: only Company model uses this (stays in master DB)
MasterBase = declarative_base()

# TenantBase: all business models use this (goes into each company's own DB)
TenantBase = declarative_base()

# Backward-compat alias (auth_routes still references Base)
Base = TenantBase


def get_db():
    """Master DB session — use only for Company lookups (login, super admin)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
