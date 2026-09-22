"""Country / State / District master lookup routes (cascading dropdowns)."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Country, State, District

router = APIRouter(prefix="/api", tags=["Geography Masters"])


# GET /api/countries
@router.get("/countries")
def list_countries(db: Session = Depends(get_db)):
    rows = db.query(Country).order_by(Country.country_name).all()
    return [{"id": r.id, "name": r.country_name} for r in rows]


# GET /api/states?country_id=1
@router.get("/states")
def list_states(country_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(State)
    if country_id is not None:
        q = q.filter(State.country_id == country_id)
    rows = q.order_by(State.state_name).all()
    return [{"id": r.id, "name": r.state_name, "country_id": r.country_id} for r in rows]


# GET /api/districts?state_id=5
@router.get("/districts")
def list_districts(state_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(District)
    if state_id is not None:
        q = q.filter(District.state_id == state_id)
    rows = q.order_by(District.district_name).all()
    return [{"id": r.id, "name": r.district_name, "state_id": r.state_id} for r in rows]
