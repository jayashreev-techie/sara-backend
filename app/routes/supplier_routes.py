"""Supplier Management routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.tenant import get_tenant_db as get_db
from app.models import Supplier, Company
from app.auth import get_current_company

router = APIRouter(prefix="/api/suppliers", tags=["Suppliers"])


def _to_dict(s: Supplier) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "mobile": s.mobile,
        "gst": s.gst,
        "bank_details": s.bank_details,
        "address": s.address,
        "is_active": s.is_active,
    }


@router.get("")
def list_suppliers(
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    return [_to_dict(s) for s in db.query(Supplier).filter(Supplier.del_flag == False).all()]


@router.post("", status_code=201)
def create_supplier(
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    if not payload.get("name"):
        raise HTTPException(status_code=422, detail="'name' is required")
    s = Supplier(
        name=payload["name"],
        mobile=payload.get("mobile"),
        gst=payload.get("gst"),
        bank_details=payload.get("bank_details"),
        address=payload.get("address"),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _to_dict(s)


@router.get("/{supplier_id}")
def get_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    s = db.query(Supplier).filter(Supplier.id == supplier_id, Supplier.del_flag == False).first()
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return _to_dict(s)


@router.put("/{supplier_id}")
def update_supplier(
    supplier_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    s = db.query(Supplier).filter(Supplier.id == supplier_id, Supplier.del_flag == False).first()
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found")
    for field in ("name", "mobile", "gst", "bank_details", "address"):
        if field in payload:
            setattr(s, field, payload[field])
    if "is_active" in payload:
        s.is_active = payload["is_active"]
    db.commit()
    db.refresh(s)
    return _to_dict(s)


@router.delete("/{supplier_id}")
def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    s = db.query(Supplier).filter(Supplier.id == supplier_id, Supplier.del_flag == False).first()
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found")
    s.del_flag = True
    db.commit()
    return {"message": "Deleted"}
