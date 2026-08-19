"""Product Master routes — Categories, Units, Products."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.tenant import get_tenant_db as get_db
from app.models import Product, ProductCategory, ProductUnit, Company
from app.auth import get_current_company

router = APIRouter(tags=["Products"])


# =====================================================
# CATEGORIES
# =====================================================
cat_router = APIRouter(prefix="/api/product-categories")


@cat_router.get("")
def list_categories(db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    rows = db.query(ProductCategory).filter(ProductCategory.del_flag == False).all()
    return [{"id": r.id, "category_name": r.category_name, "is_active": r.is_active} for r in rows]


@cat_router.post("", status_code=201)
def create_category(payload: dict, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    if not payload.get("category_name"):
        raise HTTPException(status_code=422, detail="'category_name' is required")
    row = ProductCategory(category_name=payload["category_name"])
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "category_name": row.category_name, "is_active": row.is_active}


@cat_router.put("/{cat_id}")
def update_category(cat_id: int, payload: dict, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    row = db.query(ProductCategory).filter(ProductCategory.id == cat_id, ProductCategory.del_flag == False).first()
    if not row:
        raise HTTPException(status_code=404, detail="Category not found")
    if "category_name" in payload:
        row.category_name = payload["category_name"]
    if "is_active" in payload:
        row.is_active = payload["is_active"]
    db.commit()
    db.refresh(row)
    return {"id": row.id, "category_name": row.category_name, "is_active": row.is_active}


@cat_router.delete("/{cat_id}")
def delete_category(cat_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    row = db.query(ProductCategory).filter(ProductCategory.id == cat_id, ProductCategory.del_flag == False).first()
    if not row:
        raise HTTPException(status_code=404, detail="Category not found")
    row.del_flag = True
    db.commit()
    return {"message": "Deleted"}


# =====================================================
# UNITS
# =====================================================
unit_router = APIRouter(prefix="/api/product-units")


@unit_router.get("")
def list_units(db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    rows = db.query(ProductUnit).filter(ProductUnit.del_flag == False).all()
    return [{"id": r.id, "unit": r.unit, "is_active": r.is_active} for r in rows]


@unit_router.post("", status_code=201)
def create_unit(payload: dict, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    if not payload.get("unit"):
        raise HTTPException(status_code=422, detail="'unit' is required")
    row = ProductUnit(unit=payload["unit"])
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "unit": row.unit, "is_active": row.is_active}


@unit_router.put("/{unit_id}")
def update_unit(unit_id: int, payload: dict, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    row = db.query(ProductUnit).filter(ProductUnit.id == unit_id, ProductUnit.del_flag == False).first()
    if not row:
        raise HTTPException(status_code=404, detail="Unit not found")
    if "unit" in payload:
        row.unit = payload["unit"]
    if "is_active" in payload:
        row.is_active = payload["is_active"]
    db.commit()
    db.refresh(row)
    return {"id": row.id, "unit": row.unit, "is_active": row.is_active}


@unit_router.delete("/{unit_id}")
def delete_unit(unit_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    row = db.query(ProductUnit).filter(ProductUnit.id == unit_id, ProductUnit.del_flag == False).first()
    if not row:
        raise HTTPException(status_code=404, detail="Unit not found")
    row.del_flag = True
    db.commit()
    return {"message": "Deleted"}


# =====================================================
# PRODUCTS
# =====================================================
prod_router = APIRouter(prefix="/api/products")


def _product_dict(p: Product) -> dict:
    return {
        "id": p.id,
        "category_id": p.category_id,
        "category_name": p.category.category_name if p.category else None,
        "hsn_number": p.hsn_number,
        "product_name": p.product_name,
        "product_description": p.product_description,
        "product_unit_id": p.product_unit_id,
        "unit": p.unit.unit if p.unit else None,
        "gst": p.gst,
        "is_active": p.is_active,
    }


@prod_router.get("")
def list_products(
    category_id: int = None,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    q = db.query(Product).filter(Product.del_flag == False)
    if category_id:
        q = q.filter(Product.category_id == category_id)
    return [_product_dict(p) for p in q.all()]


@prod_router.post("", status_code=201)
def create_product(payload: dict, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    if not payload.get("product_name"):
        raise HTTPException(status_code=422, detail="'product_name' is required")
    p = Product(
        category_id=payload.get("category_id"),
        hsn_number=payload.get("hsn_number"),
        product_name=payload["product_name"],
        product_description=payload.get("product_description"),
        product_unit_id=payload.get("product_unit_id"),
        gst=payload.get("gst", 0.0),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _product_dict(p)


@prod_router.get("/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    p = db.query(Product).filter(Product.id == product_id, Product.del_flag == False).first()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return _product_dict(p)


@prod_router.put("/{product_id}")
def update_product(product_id: int, payload: dict, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    p = db.query(Product).filter(Product.id == product_id, Product.del_flag == False).first()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    for field in ("category_id", "hsn_number", "product_name", "product_description", "product_unit_id", "gst"):
        if field in payload:
            setattr(p, field, payload[field])
    if "is_active" in payload:
        p.is_active = payload["is_active"]
    db.commit()
    db.refresh(p)
    return _product_dict(p)


@prod_router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    p = db.query(Product).filter(Product.id == product_id, Product.del_flag == False).first()
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    p.del_flag = True
    db.commit()
    return {"message": "Deleted"}


# Combine all sub-routers under one importable router
router.include_router(cat_router)
router.include_router(unit_router)
router.include_router(prod_router)
