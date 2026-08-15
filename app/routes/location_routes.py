"""Location CRUD routes."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.tenant import get_tenant_db as get_db
from app.models import Location, Store, Company
from app.auth import get_current_company

router = APIRouter(prefix="/api/locations", tags=["Locations"])


def _to_dict(loc: Location, store_names: Optional[List[str]] = None) -> dict:
    return {
        "id": loc.id,
        "location_name": loc.location_name,
        "store_names": store_names or [],
    }


def _enrich(db: Session, loc: Location) -> dict:
    stores = db.query(Store).filter(Store.location_id == loc.id).all()
    return _to_dict(loc, store_names=[s.store_name for s in stores])


# =====================================================
# LIST (optional ?store_id filter)
# =====================================================
@router.get("")
def list_locations(
    store_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    if store_id is not None:
        store = db.query(Store).filter(Store.id == store_id).first()
        if not store or store.location_id is None:
            return []
        loc = db.query(Location).filter(Location.id == store.location_id).first()
        return [_enrich(db, loc)] if loc else []

    return [_enrich(db, loc) for loc in db.query(Location).all()]


# =====================================================
# GET SINGLE
# =====================================================
@router.get("/{location_id}")
def get_location(
    location_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    return _enrich(db, loc)


# =====================================================
# CREATE
# =====================================================
@router.post("", status_code=201)
def create_location(
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    if not payload.get("location_name"):
        raise HTTPException(status_code=422, detail="'location_name' is required")

    loc = Location(location_name=payload["location_name"])
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return _enrich(db, loc)


# =====================================================
# UPDATE
# =====================================================
@router.put("/{location_id}")
def update_location(
    location_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    if "location_name" in payload:
        loc.location_name = payload["location_name"]

    db.commit()
    db.refresh(loc)
    return _enrich(db, loc)


# =====================================================
# DELETE
# =====================================================
@router.delete("/{location_id}")
def delete_location(
    location_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    db.delete(loc)
    db.commit()
    return {"success": True, "message": "Deleted"}
