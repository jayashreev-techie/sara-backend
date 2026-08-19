"""Outward (stock issue) routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.tenant import get_tenant_db as get_db
from app.models import OutwardEntry, InwardProduct, Company
from app.auth import get_current_company

router = APIRouter(prefix="/api/outward", tags=["Outward"])


def _to_dict(o: OutwardEntry) -> dict:
    return {
        "id": o.id,
        "outward_code": o.outward_code,
        "supplier_id": o.supplier_id,
        "supplier_name": o.supplier.name if o.supplier else None,
        "product_id": o.product_id,
        "product_name": o.product.product_name if o.product else None,
        "inward_product_id": o.inward_product_id,
        "act_qty": o.act_qty,
        "out_qty": o.out_qty,
        "remark": o.remark,
        "is_active": o.is_active,
        "created_at": str(o.created_at) if o.created_at else None,
    }


def _next_outward_code(db: Session) -> int:
    result = db.query(func.coalesce(func.max(OutwardEntry.outward_code), 0)).scalar()
    return result + 1


@router.get("")
def list_outward(db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    rows = db.query(OutwardEntry).filter(OutwardEntry.del_flag == False).order_by(OutwardEntry.id.desc()).all()
    return [_to_dict(o) for o in rows]


@router.get("/available-stock")
def available_stock(db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    """Returns inward products with remaining stock (act_qty - already_out_qty)."""
    inward_products = db.query(InwardProduct).filter(InwardProduct.del_flag == False).all()
    result = []
    for ip in inward_products:
        already_out = (
            db.query(func.coalesce(func.sum(OutwardEntry.out_qty), 0))
            .filter(OutwardEntry.inward_product_id == ip.id, OutwardEntry.del_flag == False)
            .scalar()
        )
        balance = ip.qty - already_out
        if balance > 0:
            result.append({
                "inward_product_id": ip.id,
                "product_id": ip.product_id,
                "product_name": ip.product.product_name if ip.product else None,
                "category_id": ip.category_id,
                "category_name": ip.category.category_name if ip.category else None,
                "supplier_id": ip.supplier_id,
                "supplier_name": ip.inward_entry.supplier.name if ip.inward_entry and ip.inward_entry.supplier else None,
                "unit": ip.unit.unit if ip.unit else None,
                "act_qty": ip.qty,
                "already_out_qty": already_out,
                "balance_qty": balance,
            })
    return result


@router.post("", status_code=201)
def create_outward(
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    """
    payload = {
      "items": [
        {"inward_product_id": 1, "product_id": 1, "supplier_id": 1,
         "act_qty": 100, "out_qty": 10, "remark": "..."}
      ]
    }
    """
    items = payload.get("items", [])
    if not items:
        raise HTTPException(status_code=422, detail="'items' list is required")

    code = _next_outward_code(db)
    created = []
    for item in items:
        inward_product_id = item.get("inward_product_id")
        out_qty = item.get("out_qty", 0)

        # Validate balance
        if inward_product_id:
            ip = db.query(InwardProduct).filter(InwardProduct.id == inward_product_id).first()
            if ip:
                already_out = (
                    db.query(func.coalesce(func.sum(OutwardEntry.out_qty), 0))
                    .filter(OutwardEntry.inward_product_id == inward_product_id, OutwardEntry.del_flag == False)
                    .scalar()
                )
                if out_qty > (ip.qty - already_out):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Out quantity {out_qty} exceeds available stock {ip.qty - already_out}"
                    )

        o = OutwardEntry(
            outward_code=code,
            supplier_id=item.get("supplier_id"),
            product_id=item.get("product_id"),
            inward_product_id=inward_product_id,
            act_qty=item.get("act_qty", 0),
            out_qty=out_qty,
            remark=item.get("remark"),
        )
        db.add(o)
        db.flush()
        created.append(o.id)

    db.commit()
    return {"message": "Outward entries created", "ids": created, "outward_code": code}


@router.delete("/{outward_id}")
def delete_outward(
    outward_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    o = db.query(OutwardEntry).filter(OutwardEntry.id == outward_id, OutwardEntry.del_flag == False).first()
    if not o:
        raise HTTPException(status_code=404, detail="Outward entry not found")
    o.del_flag = True
    db.commit()
    return {"message": "Deleted"}
