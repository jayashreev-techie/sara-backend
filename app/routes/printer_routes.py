"""Printer Management routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.tenant import get_tenant_db as get_db
from app.models import Printer, Company
from app.auth import get_current_company

router = APIRouter(prefix="/api/printers", tags=["Printers"])


def _to_dict(p: Printer) -> dict:
    return {
        "id": p.id,
        "printer_name": p.printer_name,
        "contact_person_name": p.contact_person_name,
        "mobile": p.mobile,
        "address": p.address,
        "gst_no": p.gst_no,
        "is_active": p.is_active,
    }


@router.get("")
def list_printers(db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    return [_to_dict(p) for p in db.query(Printer).filter(Printer.del_flag == False).all()]


@router.post("", status_code=201)
def create_printer(payload: dict, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    if not payload.get("printer_name"):
        raise HTTPException(status_code=422, detail="'printer_name' is required")
    p = Printer(
        printer_name=payload["printer_name"],
        contact_person_name=payload.get("contact_person_name"),
        mobile=payload.get("mobile"),
        address=payload.get("address"),
        gst_no=payload.get("gst_no"),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _to_dict(p)


@router.get("/{printer_id}")
def get_printer(printer_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    p = db.query(Printer).filter(Printer.id == printer_id, Printer.del_flag == False).first()
    if not p:
        raise HTTPException(status_code=404, detail="Printer not found")
    return _to_dict(p)


@router.put("/{printer_id}")
def update_printer(printer_id: int, payload: dict, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    p = db.query(Printer).filter(Printer.id == printer_id, Printer.del_flag == False).first()
    if not p:
        raise HTTPException(status_code=404, detail="Printer not found")
    for field in ("printer_name", "contact_person_name", "mobile", "address", "gst_no"):
        if field in payload:
            setattr(p, field, payload[field])
    if "is_active" in payload:
        p.is_active = payload["is_active"]
    db.commit()
    db.refresh(p)
    return _to_dict(p)


@router.delete("/{printer_id}")
def delete_printer(printer_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    p = db.query(Printer).filter(Printer.id == printer_id, Printer.del_flag == False).first()
    if not p:
        raise HTTPException(status_code=404, detail="Printer not found")
    p.del_flag = True
    db.commit()
    return {"message": "Deleted"}
