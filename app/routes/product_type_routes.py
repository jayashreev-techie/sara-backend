"""Product Type CRUD routes."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.tenant import get_tenant_db as get_db
from app.models import Client, ClientProductLink, Company, JobProduct, ProductType
from app.auth import get_current_company

router = APIRouter(prefix="/api/product-types", tags=["Product Types"])


def _to_dict(pt: ProductType, linked_clients: Optional[List[dict]] = None) -> dict:
    return {
        "id": pt.id,
        "product_type_name": pt.product_type,
        "hsn_code": pt.hsn_code,
        "price": pt.price,
        "is_active": True,
        "linked_clients": linked_clients or [],
    }


def _enrich(db: Session, pt: ProductType) -> dict:
    links = db.query(ClientProductLink).filter(ClientProductLink.product_type_id == pt.id).all()
    linked_clients = []
    for link in links:
        client = db.query(Client).filter(Client.id == link.client_id).first()
        if client:
            linked_clients.append({"id": client.id, "company_name": client.company_name})
    return _to_dict(pt, linked_clients=linked_clients)


# =====================================================
# LIST (optional ?client_id filter via link table)
# =====================================================
@router.get("")
def list_product_types(
    client_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    if client_id is not None:
        linked_ids = (
            db.query(ClientProductLink.product_type_id)
            .filter(ClientProductLink.client_id == client_id)
            .all()
        )
        ids = [row[0] for row in linked_ids]
        if not ids:
            return []
        pts = db.query(ProductType).filter(ProductType.id.in_(ids)).all()
    else:
        pts = db.query(ProductType).all()
    return [_enrich(db, pt) for pt in pts]


# =====================================================
# GET SINGLE
# =====================================================
@router.get("/{product_type_id}")
def get_product_type(
    product_type_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    pt = db.query(ProductType).filter(ProductType.id == product_type_id).first()
    if not pt:
        raise HTTPException(status_code=404, detail="Product type not found")
    return _enrich(db, pt)


# =====================================================
# CREATE
# =====================================================
@router.post("", status_code=201)
def create_product_type(
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    if not payload.get("product_type_name"):
        raise HTTPException(status_code=422, detail="'product_type_name' is required")

    pt = ProductType(
        product_type=payload["product_type_name"],
        hsn_code=payload.get("hsn_code"),
        price=payload.get("price", 0.0),
    )
    db.add(pt)
    db.commit()
    db.refresh(pt)
    return _enrich(db, pt)


# =====================================================
# UPDATE
# =====================================================
@router.put("/{product_type_id}")
def update_product_type(
    product_type_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    pt = db.query(ProductType).filter(ProductType.id == product_type_id).first()
    if not pt:
        raise HTTPException(status_code=404, detail="Product type not found")

    if "product_type_name" in payload:
        pt.product_type = payload["product_type_name"]
    if "hsn_code" in payload:
        pt.hsn_code = payload["hsn_code"]
    if "price" in payload:
        pt.price = payload["price"]

    db.commit()
    db.refresh(pt)
    return _enrich(db, pt)


# =====================================================
# UNLINK product type from client
# =====================================================
@router.delete("/link")
def unlink_product_type(
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    client_id = payload.get("client_id")
    product_type_id = payload.get("product_type_id")

    if not client_id or not product_type_id:
        raise HTTPException(status_code=422, detail="'client_id' and 'product_type_id' are required")

    link = db.query(ClientProductLink).filter(
        ClientProductLink.client_id == client_id,
        ClientProductLink.product_type_id == product_type_id,
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    db.delete(link)
    db.commit()
    return {"success": True, "message": "Unlinked"}


# =====================================================
# BULK DELETE
# =====================================================
@router.delete("/bulk")
def bulk_delete_product_types(
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    """Delete selected product types that have no client or job references."""
    product_type_ids = payload.get("product_type_ids")
    if not isinstance(product_type_ids, list) or not product_type_ids:
        raise HTTPException(status_code=422, detail="'product_type_ids' must be a non-empty list")
    if any(
        not isinstance(product_type_id, int)
        or isinstance(product_type_id, bool)
        or product_type_id <= 0
        for product_type_id in product_type_ids
    ):
        raise HTTPException(
            status_code=422,
            detail="'product_type_ids' must contain positive integer IDs",
        )

    # Preserve request order while avoiding duplicate deletion attempts.
    unique_product_type_ids = list(dict.fromkeys(product_type_ids))
    existing_ids = {
        row[0]
        for row in db.query(ProductType.id)
        .filter(ProductType.id.in_(unique_product_type_ids))
        .all()
    }
    missing_ids = [
        product_type_id
        for product_type_id in unique_product_type_ids
        if product_type_id not in existing_ids
    ]
    if missing_ids:
        return JSONResponse(
            status_code=404,
            content={
                "detail": "Some selected product types were not found",
                "missing_ids": missing_ids,
            },
        )

    client_linked_ids = {
        row[0]
        for row in db.query(ClientProductLink.product_type_id)
        .filter(ClientProductLink.product_type_id.in_(unique_product_type_ids))
        .distinct()
        .all()
    }
    job_linked_ids = {
        row[0]
        for row in db.query(JobProduct.product_type_id)
        .filter(JobProduct.product_type_id.in_(unique_product_type_ids))
        .distinct()
        .all()
    }
    blocked_product_type_ids = client_linked_ids | job_linked_ids
    blocked_ids = [
        product_type_id
        for product_type_id in unique_product_type_ids
        if product_type_id in blocked_product_type_ids
    ]
    deleted_ids = [
        product_type_id
        for product_type_id in unique_product_type_ids
        if product_type_id not in blocked_product_type_ids
    ]

    if not deleted_ids:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Selected product types are linked to clients or jobs, so they cannot be deleted",
                "blocked_ids": blocked_ids,
            },
        )

    try:
        db.query(ProductType).filter(ProductType.id.in_(deleted_ids)).delete(
            synchronize_session=False
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    response = {"deleted_ids": deleted_ids, "blocked_ids": blocked_ids}
    if blocked_ids:
        response["detail"] = "Some product types are linked to clients or jobs and could not be deleted"
    return response


# =====================================================
# DELETE
# =====================================================
@router.delete("/{product_type_id}")
def delete_product_type(
    product_type_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    pt = db.query(ProductType).filter(ProductType.id == product_type_id).first()
    if not pt:
        raise HTTPException(status_code=404, detail="Product type not found")

    is_linked_to_client = (
        db.query(ClientProductLink.id)
        .filter(ClientProductLink.product_type_id == product_type_id)
        .first()
    )
    is_linked_to_job = (
        db.query(JobProduct.id)
        .filter(JobProduct.product_type_id == product_type_id)
        .first()
    )
    if is_linked_to_client or is_linked_to_job:
        raise HTTPException(
            status_code=409,
            detail="This product type is linked to clients or jobs, so it cannot be deleted",
        )

    db.delete(pt)
    db.commit()
    return {"success": True, "message": "Deleted"}


# =====================================================
# LINK product type to client
# =====================================================
@router.post("/link", status_code=201)
def link_product_type(
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    client_id = payload.get("client_id")
    product_type_id = payload.get("product_type_id")

    if not client_id or not product_type_id:
        raise HTTPException(status_code=422, detail="'client_id' and 'product_type_id' are required")

    if not db.query(Client).filter(Client.id == client_id).first():
        raise HTTPException(status_code=404, detail="Client not found")
    if not db.query(ProductType).filter(ProductType.id == product_type_id).first():
        raise HTTPException(status_code=404, detail="ProductType not found")

    existing = db.query(ClientProductLink).filter(
        ClientProductLink.client_id == client_id,
        ClientProductLink.product_type_id == product_type_id,
    ).first()
    if existing:
        return {"message": "Already linked"}

    link = ClientProductLink(client_id=client_id, product_type_id=product_type_id)
    db.add(link)
    db.commit()
    return {"message": "Linked"}
