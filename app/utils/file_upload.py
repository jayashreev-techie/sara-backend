"""File upload utilities for photos"""
import os
import uuid
from datetime import datetime
from pathlib import Path
from fastapi import UploadFile, HTTPException
from app.config import settings

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_SIZE_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


async def save_upload(file: UploadFile, subfolder: str) -> str:
    """
    Save uploaded file to /uploads/<subfolder>/YYYY-MM-DD/<uuid>.ext
    Returns the relative path for DB storage.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read content and validate size
    content = await file.read()
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    # Build path: uploads/<subfolder>/YYYY-MM-DD/<uuid>.<ext>
    date_folder = datetime.now().strftime("%Y-%m-%d")
    folder = Path(settings.UPLOAD_DIR) / subfolder / date_folder
    folder.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{ext}"
    full_path = folder / filename
    full_path.write_bytes(content)

    # Return relative path (for DB + URL building)
    relative_path = f"{subfolder}/{date_folder}/{filename}"
    return relative_path


def build_photo_url(relative_path: str, base_url: str = "") -> str:
    """Convert DB-stored relative path → full URL for mobile app."""
    if not relative_path:
        return ""
    if relative_path.startswith("http"):
        return relative_path
    return f"{base_url}/uploads/{relative_path}"
