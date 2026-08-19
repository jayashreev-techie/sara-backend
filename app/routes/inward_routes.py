"""Inward (stock entry) routes."""
from datetime import date as date_type
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.tenant import get_tenant_db as get_db
from app.models import InwardEntry, InwardProduct, Product, Company
from app.auth import get_current_company
import shutil, os, uuid
from app.config import settings

router = APIRouter(prefix="/api/inward", tags=["Inward"])


def _entry_dict(e: InwardEntry) -> dict:
    return {
        "id": e.id,
        "inward_code": e.inward_code,
        "inward_date": str(e.inward_date) if e.inward_date else None,
        "supplier_id": e.supplier_id,
        "supplier_name": e.supplier.name if e.supplier else None,
        "bill_file_name": e.bill_file_name,
        "bill_file_path": e.bill_file_path,
        "is_active": e.is_active,
        "products": [_product_dict(p) for p in e.products if not p.del_flag],
    }


def _product_dict(p: InwardProduct) -> dict:
    return {
        "id": p.id,
        "product_id": p.product_id,
        "product_name": p.product.product_name if p.product else None,
        "category_id": p.category_id,
        "unit_id": p.unit_id,
        "unit": p.unit.unit if p.unit else None,
        "gst": p.gst,
        "qty": p.qty,
        "per_qty_amt": p.per_qty_amt,
        "total_amount": p.total_amount,
        "total_gst_amount": p.total_gst_amount,
    }


def _next_inward_code(db: Session) -> int:
    result = db.query(func.coalesce(func.max(InwardEntry.inward_code), 0)).scalar()
    return result + 1


@router.get("")
def list_inward(db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    entries = db.query(InwardEntry).filter(InwardEntry.del_flag == False).order_by(InwardEntry.id.desc()).all()
    return [_entry_dict(e) for e in entries]


@router.get("/{entry_id}")
def get_inward(entry_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    e = db.query(InwardEntry).filter(InwardEntry.id == entry_id, InwardEntry.del_flag == False).first()
    if not e:
        raise HTTPException(status_code=404, detail="Inward entry not found")
    return _entry_dict(e)


@router.post("", status_code=201)
def create_inward(
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    """
    payload = {
      "inward_date": "2026-01-15",
      "supplier_id": 1,
      "products": [
        {"product_id": 1, "category_id": 1, "unit_id": 1, "gst": "18%",
         "qty": 10, "per_qty_amt": 100.0, "total_amount": 1000.0, "total_gst_amount": 180.0}
      ]
    }
    Bill file upload is handled separately via POST /api/inward/{id}/bill
    """
    if not payload.get("inward_date"):
        raise HTTPException(status_code=422, detail="'inward_date' is required")

    code = _next_inward_code(db)
    entry = InwardEntry(
        inward_code=code,
        inward_date=payload["inward_date"],
        supplier_id=payload.get("supplier_id"),
    )
    db.add(entry)
    db.flush()

    for item in payload.get("products", []):
        ip = InwardProduct(
            inward_entry_id=entry.id,
            inward_code=code,
            inward_date=payload["inward_date"],
            supplier_id=payload.get("supplier_id"),
            product_id=item.get("product_id"),
            category_id=item.get("category_id"),
            unit_id=item.get("unit_id"),
            gst=item.get("gst"),
            qty=item.get("qty", 0),
            per_qty_amt=item.get("per_qty_amt", 0),
            total_amount=item.get("total_amount", 0),
            total_gst_amount=item.get("total_gst_amount", 0),
        )
        db.add(ip)

    db.commit()
    db.refresh(entry)
    return _entry_dict(entry)


@router.put("/{entry_id}")
def update_inward(
    entry_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    e = db.query(InwardEntry).filter(InwardEntry.id == entry_id, InwardEntry.del_flag == False).first()
    if not e:
        raise HTTPException(status_code=404, detail="Inward entry not found")
    if "inward_date" in payload:
        e.inward_date = payload["inward_date"]
    if "supplier_id" in payload:
        e.supplier_id = payload["supplier_id"]
    db.commit()
    db.refresh(e)
    return _entry_dict(e)


@router.delete("/{entry_id}")
def delete_inward(
    entry_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    e = db.query(InwardEntry).filter(InwardEntry.id == entry_id, InwardEntry.del_flag == False).first()
    if not e:
        raise HTTPException(status_code=404, detail="Inward entry not found")
    e.del_flag = True
    db.commit()
    return {"message": "Deleted"}


@router.post("/{entry_id}/bill")
async def upload_bill(
    entry_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    e = db.query(InwardEntry).filter(InwardEntry.id == entry_id, InwardEntry.del_flag == False).first()
    if not e:
        raise HTTPException(status_code=404, detail="Inward entry not found")

    ext = os.path.splitext(file.filename)[1].lower()
    allowed = {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".doc", ".docx"}
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Invalid file type")

    filename = f"bill_{entry_id}_{uuid.uuid4().hex}{ext}"
    upload_dir = os.path.join(settings.UPLOAD_DIR, "bills")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    e.bill_file_name = filename
    e.bill_file_path = file_path
    db.commit()
    return {"message": "Bill uploaded", "file_name": filename}
