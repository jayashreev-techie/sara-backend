"""Client CRUD routes."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.tenant import get_tenant_db as get_db
from app.models import Client, Company
from app.auth import get_current_company

router = APIRouter(prefix="/api/clients", tags=["Clients"])


def _to_dict(c: Client) -> dict:
    return {
        "id": c.id,
        "company_name": c.company_name,
        "contact_person_name": c.contact_person_name,
        "sales_person_name": c.sales_person_name,
        "mobile": c.mobile,
        "gst_no": c.gst_number,
        "is_active": True,
    }


# =====================================================
# LIST
# =====================================================
@router.get("")
def list_clients(
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    return [_to_dict(c) for c in db.query(Client).all()]


# =====================================================
# CREATE
# =====================================================
@router.post("", status_code=201)
def create_client(
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    # Accept both "contact_person_name" and "contact_person"
    contact = payload.get("contact_person_name") or payload.get("contact_person")

    if not payload.get("company_name"):
        raise HTTPException(status_code=422, detail="'company_name' is required")
    if not payload.get("mobile"):
        raise HTTPException(status_code=422, detail="'mobile' is required")

    client = Client(
        company_name=payload["company_name"],
        contact_person_name=contact,
        sales_person_name=payload.get("sales_person_name"),
        mobile=payload["mobile"],
        gst_number=payload.get("gst_no"),
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return _to_dict(client)


# =====================================================
# UPDATE
# =====================================================
@router.put("/{client_id}")
def update_client(
    client_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if "company_name" in payload:
        client.company_name = payload["company_name"]
    if "contact_person_name" in payload:
        client.contact_person_name = payload["contact_person_name"]
    elif "contact_person" in payload:
        client.contact_person_name = payload["contact_person"]
    if "sales_person_name" in payload:
        client.sales_person_name = payload["sales_person_name"]
    if "mobile" in payload:
        client.mobile = payload["mobile"]
    if "gst_no" in payload:
        client.gst_number = payload["gst_no"]

    db.commit()
    db.refresh(client)
    return _to_dict(client)


# =====================================================
# DELETE
# =====================================================
@router.delete("/{client_id}")
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(client)
    db.commit()
    return {"message": "Deleted"}
