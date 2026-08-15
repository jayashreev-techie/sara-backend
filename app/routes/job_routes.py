"""Job management routes (admin / web side)."""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.tenant import get_tenant_db as get_db
from app.models import Client, Company, Job, JobProduct, ProductType, Store
from app.auth import get_current_company
from app.schemas import (
    JobCreateRequest, JobDetailResponse, JobListItem,
    JobProductCreateItem, JobProductResponse, JobProductUpdateRequest,
    JobUpdateRequest,
)
from app.utils.file_upload import save_upload

router = APIRouter(prefix="/api/jobs", tags=["Jobs (Admin)"])


def _calc_sqft(width: float, height: float) -> float:
    """Convert width x height (inches) to square feet."""
    return round((width * height) / 144, 4)


def _build_product_response(jp: JobProduct) -> JobProductResponse:
    return JobProductResponse(
        id=jp.id,
        store_id=jp.store_id,
        store_name=jp.store.store_name if jp.store else None,
        location_id=jp.location_id,
        product_type_id=jp.product_type_id,
        product_type=jp.product_type.product_type if jp.product_type else None,
        total_qty=jp.total_qty,
        width_inch=jp.width_inch,
        height_inch=jp.height_inch,
        sq_ft_unit=jp.sq_ft_unit,
        total_sq_ft=jp.total_sq_ft,
        is_double_sided=jp.is_double_sided,
        is_pool=jp.is_pool,
        remark=jp.remark,
        photo_path=jp.photo_path,
        recee_status=jp.recee_status,
        installation_status=jp.installation_status,
    )


# =====================================================
# 1. CREATE JOB (+ optional job_products)
# =====================================================
@router.post("", response_model=JobDetailResponse, status_code=201)
def create_job(payload: JobCreateRequest, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    client = db.query(Client).filter(Client.id == payload.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    for p in payload.products:
        if not db.query(Store).filter(Store.id == p.store_id).first():
            raise HTTPException(status_code=400, detail=f"Store {p.store_id} not found")
        if p.product_type_id and not db.query(ProductType).filter(
            ProductType.id == p.product_type_id
        ).first():
            raise HTTPException(status_code=400, detail=f"ProductType {p.product_type_id} not found")

    job = Job(
        job_creation_date=payload.job_creation_date or date.today(),
        client_id=payload.client_id,
        client_contact_person_name=payload.client_contact_person_name,
        client_contact_person_mobile=payload.client_contact_person_mobile,
        po_number=payload.po_number,
        po_date=payload.po_date,
        measurement_date=payload.measurement_date,
        measurement_person_name=payload.measurement_person_name,
        measurement_person_mobile=payload.measurement_person_mobile.strip(),
        status="pending",
    )
    db.add(job)
    db.flush()  # flush once to get job.id

    for p in payload.products:
        sq_ft_unit = _calc_sqft(p.width_inch, p.height_inch)
        db.add(JobProduct(
            job_id=job.id,
            store_id=p.store_id,
            location_id=p.location_id,
            product_type_id=p.product_type_id,
            total_qty=p.total_qty,
            width_inch=p.width_inch,
            height_inch=p.height_inch,
            sq_ft_unit=sq_ft_unit,
            total_sq_ft=round(sq_ft_unit * p.total_qty, 4),
            is_double_sided=p.is_double_sided,
            is_pool=p.is_pool,
            remark=p.remark,
            recee_status="pending",
            installation_status="pending",
        ))

    db.commit()
    db.refresh(job)
    return get_job(job.id, db)


# =====================================================
# 2. LIST JOBS
# =====================================================
@router.get("", response_model=List[JobListItem])
def list_jobs(
    client_id: Optional[int] = None,
    measurement_person_mobile: Optional[str] = None,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    q = (
        db.query(
            Job,
            Client.company_name.label("company_name"),
            func.count(JobProduct.id).label("product_count"),
        )
        .outerjoin(Client, Client.id == Job.client_id)
        .outerjoin(JobProduct, JobProduct.job_id == Job.id)
        .group_by(Job.id, Client.company_name)
    )
    if client_id is not None:
        q = q.filter(Job.client_id == client_id)
    if measurement_person_mobile:
        q = q.filter(Job.measurement_person_mobile == measurement_person_mobile.strip())

    rows = q.order_by(Job.id.desc()).all()
    return [
        JobListItem(
            id=job.id,
            job_creation_date=job.job_creation_date,
            client_id=job.client_id,
            company_name=company_name,
            po_number=job.po_number,
            measurement_person_name=job.measurement_person_name,
            measurement_person_mobile=job.measurement_person_mobile,
            status=job.status,
            product_count=int(product_count or 0),
        )
        for job, company_name, product_count in rows
    ]


# =====================================================
# 3. SINGLE JOB DETAIL
# =====================================================
@router.get("/{job_id}", response_model=JobDetailResponse)
def get_job(job_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    client = db.query(Client).filter(Client.id == job.client_id).first()
    products = db.query(JobProduct).filter(JobProduct.job_id == job_id).all()

    return JobDetailResponse(
        id=job.id,
        job_creation_date=job.job_creation_date,
        client_id=job.client_id,
        company_name=client.company_name if client else None,
        client_contact_person_name=job.client_contact_person_name,
        client_contact_person_mobile=job.client_contact_person_mobile,
        po_number=job.po_number,
        po_date=job.po_date,
        measurement_date=job.measurement_date,
        measurement_person_name=job.measurement_person_name,
        measurement_person_mobile=job.measurement_person_mobile,
        status=job.status,
        created_at=job.created_at,
        products=[_build_product_response(jp) for jp in products],
    )


# =====================================================
# 4. UPDATE JOB HEADER
# =====================================================
@router.put("/{job_id}", response_model=JobDetailResponse)
def update_job(job_id: int, payload: JobUpdateRequest, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if payload.client_id is not None:
        if not db.query(Client).filter(Client.id == payload.client_id).first():
            raise HTTPException(status_code=404, detail="Client not found")
        job.client_id = payload.client_id
    if payload.job_creation_date is not None:
        job.job_creation_date = payload.job_creation_date
    if payload.client_contact_person_name is not None:
        job.client_contact_person_name = payload.client_contact_person_name
    if payload.client_contact_person_mobile is not None:
        job.client_contact_person_mobile = payload.client_contact_person_mobile
    if payload.po_number is not None:
        job.po_number = payload.po_number
    if payload.po_date is not None:
        job.po_date = payload.po_date
    if payload.measurement_date is not None:
        job.measurement_date = payload.measurement_date
    if payload.measurement_person_name is not None:
        job.measurement_person_name = payload.measurement_person_name
    if payload.measurement_person_mobile is not None:
        job.measurement_person_mobile = payload.measurement_person_mobile.strip()
    if payload.status is not None:
        job.status = payload.status

    db.commit()
    db.refresh(job)
    return get_job(job_id, db)


# =====================================================
# 5. DELETE JOB
# =====================================================
@router.delete("/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
    return {"success": True, "message": "Job deleted successfully"}


# =====================================================
# 6. ADD PRODUCT TO EXISTING JOB
# =====================================================
@router.post("/{job_id}/products", status_code=201)
def add_product(job_id: int, payload: JobProductCreateItem, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    if not db.query(Job).filter(Job.id == job_id).first():
        raise HTTPException(status_code=404, detail="Job not found")
    if not db.query(Store).filter(Store.id == payload.store_id).first():
        raise HTTPException(status_code=404, detail="Store not found")
    if payload.product_type_id and not db.query(ProductType).filter(
        ProductType.id == payload.product_type_id
    ).first():
        raise HTTPException(status_code=404, detail="ProductType not found")

    sq_ft_unit = _calc_sqft(payload.width_inch, payload.height_inch)
    jp = JobProduct(
        job_id=job_id,
        store_id=payload.store_id,
        location_id=payload.location_id,
        product_type_id=payload.product_type_id,
        total_qty=payload.total_qty,
        width_inch=payload.width_inch,
        height_inch=payload.height_inch,
        sq_ft_unit=sq_ft_unit,
        total_sq_ft=round(sq_ft_unit * payload.total_qty, 4),
        is_double_sided=payload.is_double_sided,
        is_pool=payload.is_pool,
        remark=payload.remark,
        recee_status="pending",
        installation_status="pending",
    )
    db.add(jp)
    db.commit()
    db.refresh(jp)
    return {"success": True, "message": "Product added", "job_product_id": jp.id}


# =====================================================
# 7. UPDATE PRODUCT
# =====================================================
@router.put("/{job_id}/products/{product_id}", response_model=JobProductResponse)
def update_product(
    job_id: int, product_id: int, payload: JobProductUpdateRequest, db: Session = Depends(get_db), _: Company = Depends(get_current_company)
):
    jp = db.query(JobProduct).filter(
        JobProduct.id == product_id, JobProduct.job_id == job_id
    ).first()
    if not jp:
        raise HTTPException(status_code=404, detail="Product not found")

    if payload.store_id is not None:
        if not db.query(Store).filter(Store.id == payload.store_id).first():
            raise HTTPException(status_code=404, detail="Store not found")
        jp.store_id = payload.store_id
    if payload.location_id is not None:
        jp.location_id = payload.location_id
    if payload.product_type_id is not None:
        if not db.query(ProductType).filter(ProductType.id == payload.product_type_id).first():
            raise HTTPException(status_code=404, detail="ProductType not found")
        jp.product_type_id = payload.product_type_id
    if payload.total_qty is not None:
        jp.total_qty = payload.total_qty
    if payload.width_inch is not None:
        jp.width_inch = payload.width_inch
    if payload.height_inch is not None:
        jp.height_inch = payload.height_inch
    if payload.is_double_sided is not None:
        jp.is_double_sided = payload.is_double_sided
    if payload.is_pool is not None:
        jp.is_pool = payload.is_pool
    if payload.remark is not None:
        jp.remark = payload.remark

    # Recalculate sq ft
    jp.sq_ft_unit = _calc_sqft(jp.width_inch, jp.height_inch)
    jp.total_sq_ft = round(jp.sq_ft_unit * jp.total_qty, 4)

    db.commit()
    db.refresh(jp)
    return _build_product_response(jp)


# =====================================================
# 8. DELETE PRODUCT
# =====================================================
@router.delete("/{job_id}/products/{product_id}")
def delete_product(job_id: int, product_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    jp = db.query(JobProduct).filter(
        JobProduct.id == product_id, JobProduct.job_id == job_id
    ).first()
    if not jp:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(jp)
    db.commit()
    return {"success": True, "message": "Product deleted"}


# =====================================================
# 9. UPLOAD PHOTO FOR A PRODUCT
# =====================================================
@router.post("/{job_id}/products/{product_id}/photo")
async def upload_product_photo(
    job_id: int,
    product_id: int,
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    jp = db.query(JobProduct).filter(
        JobProduct.id == product_id, JobProduct.job_id == job_id
    ).first()
    if not jp:
        raise HTTPException(status_code=404, detail="Product not found")

    path = await save_upload(photo, subfolder=f"jobs/{job_id}/products/{product_id}")
    jp.photo_path = path
    db.commit()
    return {"success": True, "message": "Photo uploaded", "photo_path": path}
