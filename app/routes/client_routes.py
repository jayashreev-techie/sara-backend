"""Client CRUD routes."""
import math
import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.tenant import get_tenant_db as get_db
from app.models import Client, Company, Job, Store
from app.auth import get_current_company

router = APIRouter(prefix="/api/clients", tags=["Clients"])


def _validate_mobile(value: object) -> str:
    """Return a normalized Indian mobile number or raise a client error."""
    mobile = str(value or "").strip()
    if not re.fullmatch(r"\d{10}", mobile):
        raise HTTPException(
            status_code=422,
            detail="'mobile' must be a 10-digit numeric phone number",
        )
    return mobile


def _to_dict(c: Client) -> dict:
    return {
        "id": c.id,
        "company_name": c.company_name,
        "gst_no": c.gst_number,
        "address": c.address,
        "contact_person": c.contact_person_name,
        "mobile": c.mobile,
        "sales_person": c.sales_person_name,
        # Keep the original response field names for existing clients.
        "contact_person_name": c.contact_person_name,
        "sales_person_name": c.sales_person_name,
        "company_employer": c.company_employer,
        "email_id": c.email_id,
        "address_line1": c.address_line1,
        "address_line2": c.address_line2,
        "country": c.country,
        "state": c.state,
        "district": c.district,
        "pincode": c.pincode,
        "pan_no": c.pan_no,
        "website_link": c.website_link,
        "is_active": True,
    }


# =====================================================
# LIST
# =====================================================
@router.get("")
def list_clients(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    """Return a searchable, paginated client list."""
    query = db.query(Client)
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            Client.company_name.ilike(term)
            | Client.contact_person_name.ilike(term)
            | Client.mobile.ilike(term)
            | Client.gst_number.ilike(term)
        )

    total = query.count()
    clients = (
        query.order_by(Client.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_to_dict(client) for client in clients],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total else 0,
    }


# =====================================================
# GET SINGLE
# =====================================================
@router.get("/{client_id}")
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return _to_dict(client)


# =====================================================
# CREATE
# =====================================================
@router.post("", status_code=201)
def create_client(
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    # Accept legacy field names as well as the current API payload.
    contact = payload.get("contact_person_name") or payload.get("contact_person")
    sales_person = payload.get("sales_person_name") or payload.get("sales_person")

    if not payload.get("company_name"):
        raise HTTPException(status_code=422, detail="'company_name' is required")
    if not payload.get("mobile"):
        raise HTTPException(status_code=422, detail="'mobile' is required")
    mobile = _validate_mobile(payload["mobile"])

    client = Client(
        company_name=payload["company_name"],
        contact_person_name=contact,
        sales_person_name=sales_person,
        mobile=mobile,
        gst_number=payload.get("gst_no"),
        address=payload.get("address"),
        company_employer=payload.get("company_employer"),
        email_id=payload.get("email_id"),
        address_line1=payload.get("address_line1"),
        address_line2=payload.get("address_line2"),
        country=payload.get("country"),
        state=payload.get("state"),
        district=payload.get("district"),
        pincode=payload.get("pincode"),
        pan_no=payload.get("pan_no"),
        website_link=payload.get("website_link"),
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
    elif "sales_person" in payload:
        client.sales_person_name = payload["sales_person"]
    if "mobile" in payload:
        client.mobile = _validate_mobile(payload["mobile"])
    if "gst_no" in payload:
        client.gst_number = payload["gst_no"]
    if "address" in payload:
        client.address = payload["address"]
    for field in (
        "company_employer", "email_id", "address_line1", "address_line2",
        "country", "state", "district", "pincode", "pan_no", "website_link",
    ):
        if field in payload:
            setattr(client, field, payload[field])

    db.commit()
    db.refresh(client)
    return _to_dict(client)


# =====================================================
# BULK DELETE
# =====================================================
@router.delete("/bulk")
def bulk_delete_clients(
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    """Delete the selected clients that have no related stores or jobs."""
    client_ids = payload.get("client_ids")
    if not isinstance(client_ids, list) or not client_ids:
        raise HTTPException(status_code=422, detail="'client_ids' must be a non-empty list")
    if any(
        not isinstance(client_id, int)
        or isinstance(client_id, bool)
        or client_id <= 0
        for client_id in client_ids
    ):
        raise HTTPException(status_code=422, detail="'client_ids' must contain positive integer IDs")

    # Preserve the request order while avoiding duplicate delete attempts.
    unique_client_ids = list(dict.fromkeys(client_ids))
    existing_ids = {
        row[0]
        for row in db.query(Client.id)
        .filter(Client.id.in_(unique_client_ids))
        .all()
    }
    missing_ids = [client_id for client_id in unique_client_ids if client_id not in existing_ids]
    if missing_ids:
        return JSONResponse(
            status_code=404,
            content={
                "detail": "Some selected clients were not found",
                "missing_ids": missing_ids,
            },
        )

    client_ids_with_stores = {
        row[0]
        for row in db.query(Store.client_id)
        .filter(Store.client_id.in_(unique_client_ids))
        .distinct()
        .all()
    }
    client_ids_with_jobs = {
        row[0]
        for row in db.query(Job.client_id)
        .filter(Job.client_id.in_(unique_client_ids))
        .distinct()
        .all()
    }
    blocked_client_ids = client_ids_with_stores | client_ids_with_jobs
    blocked_ids = [client_id for client_id in unique_client_ids if client_id in blocked_client_ids]
    deleted_ids = [client_id for client_id in unique_client_ids if client_id not in blocked_client_ids]

    if not deleted_ids:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Selected clients have related stores or jobs, so they cannot be deleted",
                "blocked_ids": blocked_ids,
            },
        )

    try:
        db.query(Client).filter(Client.id.in_(deleted_ids)).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
        raise

    response = {"deleted_ids": deleted_ids, "blocked_ids": blocked_ids}
    if blocked_ids:
        response["detail"] = "Some clients have related stores or jobs and could not be deleted"
    else:
        response["detail"] = "Selected clients deleted successfully"
    return response


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

    has_related_store = db.query(Store.id).filter(Store.client_id == client_id).first()
    has_related_job = db.query(Job.id).filter(Job.client_id == client_id).first()
    if has_related_store or has_related_job:
        raise HTTPException(
            status_code=409,
            detail="This client has related stores or jobs, so it cannot be deleted",
        )

    db.delete(client)
    db.commit()
    return {"message": "Deleted"}
