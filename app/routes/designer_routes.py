"""Designer Management routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.tenant import get_tenant_db as get_db
from app.models import Designer, Company
from app.auth import get_current_company

router = APIRouter(prefix="/api/designers", tags=["Designers"])


def _to_dict(d: Designer) -> dict:
    return {
        "id": d.id,
        "designer_name": d.designer_name,
        "mobile": d.mobile,
        "is_active": d.is_active,
    }


@router.get("")
def list_designers(db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    return [_to_dict(d) for d in db.query(Designer).filter(Designer.del_flag == False).all()]


@router.post("", status_code=201)
def create_designer(payload: dict, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    if not payload.get("designer_name"):
        raise HTTPException(status_code=422, detail="'designer_name' is required")
    d = Designer(designer_name=payload["designer_name"], mobile=payload.get("mobile"))
    db.add(d)
    db.commit()
    db.refresh(d)
    return _to_dict(d)


@router.get("/{designer_id}")
def get_designer(designer_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    d = db.query(Designer).filter(Designer.id == designer_id, Designer.del_flag == False).first()
    if not d:
        raise HTTPException(status_code=404, detail="Designer not found")
    return _to_dict(d)


@router.put("/{designer_id}")
def update_designer(designer_id: int, payload: dict, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    d = db.query(Designer).filter(Designer.id == designer_id, Designer.del_flag == False).first()
    if not d:
        raise HTTPException(status_code=404, detail="Designer not found")
    if "designer_name" in payload:
        d.designer_name = payload["designer_name"]
    if "mobile" in payload:
        d.mobile = payload["mobile"]
    if "is_active" in payload:
        d.is_active = payload["is_active"]
    db.commit()
    db.refresh(d)
    return _to_dict(d)


@router.delete("/{designer_id}")
def delete_designer(designer_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    d = db.query(Designer).filter(Designer.id == designer_id, Designer.del_flag == False).first()
    if not d:
        raise HTTPException(status_code=404, detail="Designer not found")
    d.del_flag = True
    db.commit()
    return {"message": "Deleted"}
