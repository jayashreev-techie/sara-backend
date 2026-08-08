"""
Sara Fabrication Mobile App API
FastAPI backend for Flutter mobile app (Recee + Installation flows)
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.database import engine, Base
from app.routes import auth_routes, recee_routes, installation_routes, job_routes, super_admin_routes, company_routes

# Create tables (only for first-time setup; comment out if web app already created tables)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Sara Fabrication Mobile API",
    description="Backend for Sara Recee Flutter mobile app",
    version="1.0.0",
)

# CORS — allow Flutter app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production la specific domains restrict pannunga
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file serving for uploaded photos
upload_path = Path(settings.UPLOAD_DIR)
upload_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_path)), name="uploads")

# Routers
app.include_router(auth_routes.router)
app.include_router(job_routes.router)
app.include_router(recee_routes.router)
app.include_router(installation_routes.router)
app.include_router(super_admin_routes.router)
app.include_router(company_routes.router)


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
