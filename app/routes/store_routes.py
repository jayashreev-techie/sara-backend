"""Store CRUD routes."""
import math
import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.tenant import get_tenant_db as get_db
from app.models import Client, Company, Installation, JobProduct, Location, ReceeMeasurement, Store
from app.auth import get_current_company

router = APIRouter(prefix="/api/stores", tags=["Stores"])


def _validate_optional_mobile(value: object) -> Optional[str]:
    """Normalize an optional mobile number, rejecting non-phone values."""
    if value is None or not str(value).strip():
        return None

    mobile = str(value).strip()
    if not re.fullmatch(r"\d{10}", mobile):
        raise HTTPException(
            status_code=422,
            detail="'mobile' must be a 10-digit numeric phone number",
        )
    return mobile


def _to_dict(s: Store, location_name: Optional[str] = None, client_name: Optional[str] = None) -> dict:
    return {
        "id": s.id,
        "store_name": s.store_name,
        "client_id": s.client_id,
        "client_name": client_name,
        "location_id": s.location_id,
        "location_name": location_name,
        "address": s.store_address,
        "mobile": s.store_mobile,
        "is_active": True,
    }


def _enrich(db: Session, store: Store) -> dict:
    loc = db.query(Location).filter(Location.id == store.location_id).first() if store.location_id else None
    client = db.query(Client).filter(Client.id == store.client_id).first() if store.client_id else None
    return _to_dict(
        store,
        location_name=loc.location_name if loc else None,
        client_name=client.company_name if client else None,
    )


# =====================================================
# LIST (optional client filter, search, and pagination)
# =====================================================
@router.get("")
def list_stores(
    client_id: Optional[int] = Query(None, ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    q = db.query(Store).outerjoin(Client, Client.id == Store.client_id)
    if client_id is not None:
        q = q.filter(Store.client_id == client_id)
    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.filter(
            Store.store_name.ilike(term)
            | Store.store_address.ilike(term)
            | Store.store_mobile.ilike(term)
            | Client.company_name.ilike(term)
        )

    total = q.count()
    stores = (
        q.order_by(Store.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_enrich(db, store) for store in stores],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total else 0,
    }


# =====================================================
# GET SINGLE
# =====================================================
@router.get("/{store_id}")
def get_store(
    store_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return _enrich(db, store)


# =====================================================
# CREATE
# =====================================================
@router.post("", status_code=201)
def create_store(
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    if payload.get("client_id") is None:
        raise HTTPException(status_code=422, detail="'client_id' is required")
    if not str(payload.get("store_name") or "").strip():
        raise HTTPException(status_code=422, detail="'store_name' is required")
    store_name = str(payload["store_name"]).strip()

    if not db.query(Client).filter(Client.id == payload["client_id"]).first():
        raise HTTPException(status_code=404, detail="Client not found")
    if payload.get("location_id") and not db.query(Location).filter(Location.id == payload["location_id"]).first():
        raise HTTPException(status_code=404, detail="Location not found")
    mobile = _validate_optional_mobile(payload.get("mobile"))

    store = Store(
        client_id=payload["client_id"],
        store_name=store_name,
        location_id=payload.get("location_id"),
        store_address=payload.get("address"),
        store_mobile=mobile,
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    return _enrich(db, store)


# =====================================================
# UPDATE
# =====================================================
@router.put("/{store_id}")
def update_store(
    store_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    if "store_name" in payload:
        store.store_name = payload["store_name"]
    if "location_id" in payload:
        if payload["location_id"] and not db.query(Location).filter(Location.id == payload["location_id"]).first():
            raise HTTPException(status_code=404, detail="Location not found")
        store.location_id = payload["location_id"]
    if "address" in payload:
        store.store_address = payload["address"]
    if "mobile" in payload:
        store.store_mobile = _validate_optional_mobile(payload["mobile"])
    if "client_id" in payload:
        if not db.query(Client).filter(Client.id == payload["client_id"]).first():
            raise HTTPException(status_code=404, detail="Client not found")
        store.client_id = payload["client_id"]

    db.commit()
    db.refresh(store)
    return _enrich(db, store)


# =====================================================
# BULK DELETE
# =====================================================
@router.delete("/bulk")
def bulk_delete_stores(
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    """Delete selected stores that are not referenced by job-related data."""
    store_ids = payload.get("store_ids")
    if not isinstance(store_ids, list) or not store_ids:
        raise HTTPException(status_code=422, detail="'store_ids' must be a non-empty list")
    if any(
        not isinstance(store_id, int)
        or isinstance(store_id, bool)
        or store_id <= 0
        for store_id in store_ids
    ):
        raise HTTPException(status_code=422, detail="'store_ids' must contain positive integer IDs")

    # Preserve request order while avoiding duplicate delete attempts.
    unique_store_ids = list(dict.fromkeys(store_ids))
    existing_ids = {
        row[0]
        for row in db.query(Store.id).filter(Store.id.in_(unique_store_ids)).all()
    }
    missing_ids = [store_id for store_id in unique_store_ids if store_id not in existing_ids]
    if missing_ids:
        return JSONResponse(
            status_code=404,
            content={
                "detail": "Some selected stores were not found",
                "missing_ids": missing_ids,
            },
        )

    job_product_store_ids = {
        row[0]
        for row in db.query(JobProduct.store_id)
        .filter(JobProduct.store_id.in_(unique_store_ids))
        .distinct()
        .all()
    }
    recee_measurement_store_ids = {
        row[0]
        for row in db.query(ReceeMeasurement.store_id)
        .filter(ReceeMeasurement.store_id.in_(unique_store_ids))
        .distinct()
        .all()
    }
    installation_store_ids = {
        row[0]
        for row in db.query(Installation.store_id)
        .filter(Installation.store_id.in_(unique_store_ids))
        .distinct()
        .all()
    }
    blocked_store_ids = (
        job_product_store_ids | recee_measurement_store_ids | installation_store_ids
    )
    blocked_ids = [store_id for store_id in unique_store_ids if store_id in blocked_store_ids]
    deleted_ids = [store_id for store_id in unique_store_ids if store_id not in blocked_store_ids]

    if not deleted_ids:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Selected stores have related job data, so they cannot be deleted",
                "blocked_ids": blocked_ids,
            },
        )

    try:
        db.query(Store).filter(Store.id.in_(deleted_ids)).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
        raise

    response = {"deleted_ids": deleted_ids, "blocked_ids": blocked_ids}
    if blocked_ids:
        response["detail"] = "Some stores have related job data and could not be deleted"
    return response


# =====================================================
# DELETE
# =====================================================
@router.delete("/{store_id}")
def delete_store(
    store_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    has_job_product = db.query(JobProduct.id).filter(JobProduct.store_id == store_id).first()
    has_recee_measurement = (
        db.query(ReceeMeasurement.id).filter(ReceeMeasurement.store_id == store_id).first()
    )
    has_installation = db.query(Installation.id).filter(Installation.store_id == store_id).first()
    if has_job_product or has_recee_measurement or has_installation:
        raise HTTPException(
            status_code=409,
            detail="This store has related job data, so it cannot be deleted",
        )

    db.delete(store)
    db.commit()
    return {"success": True, "message": "Deleted"}
