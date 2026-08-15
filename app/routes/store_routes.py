"""Store CRUD routes."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.tenant import get_tenant_db as get_db
from app.models import Store, Location, Client, Company
from app.auth import get_current_company

router = APIRouter(prefix="/api/stores", tags=["Stores"])


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
# LIST (optional ?client_id filter)
# =====================================================
@router.get("")
def list_stores(
    client_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    q = db.query(Store)
    if client_id is not None:
        q = q.filter(Store.client_id == client_id)
    return [_enrich(db, s) for s in q.all()]


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
    for field in ("client_id", "store_name"):
        if payload.get(field) is None:
            raise HTTPException(status_code=422, detail=f"'{field}' is required")

    if not db.query(Client).filter(Client.id == payload["client_id"]).first():
        raise HTTPException(status_code=404, detail="Client not found")
    if payload.get("location_id") and not db.query(Location).filter(Location.id == payload["location_id"]).first():
        raise HTTPException(status_code=404, detail="Location not found")

    store = Store(
        client_id=payload["client_id"],
        store_name=payload["store_name"],
        location_id=payload.get("location_id"),
        store_address=payload.get("address"),
        store_mobile=payload.get("mobile"),
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
        store.store_mobile = payload["mobile"]
    if "client_id" in payload:
        if not db.query(Client).filter(Client.id == payload["client_id"]).first():
            raise HTTPException(status_code=404, detail="Client not found")
        store.client_id = payload["client_id"]

    db.commit()
    db.refresh(store)
    return _enrich(db, store)


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
    db.delete(store)
    db.commit()
    return {"success": True, "message": "Deleted"}
