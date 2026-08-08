"""
Job management routes (admin / web side).
- Create a new job (with optional job_products = stores to measure)
- List jobs

Note: Web admin panel-la job create panrathukku equivalent. Currently open
(no auth) — admin auth add panna venumna later add pannalam.
"""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Client, Job, JobProduct, ProductType, Store
from app.schemas import JobCreateRequest, JobCreateResponse, JobListItem

router = APIRouter(prefix="/api/jobs", tags=["Jobs (Admin)"])


# =====================================================
# 1. CREATE JOB (+ optional job_products)
# =====================================================
@router.post("", response_model=JobCreateResponse, status_code=201)
def create_job(payload: JobCreateRequest, db: Session = Depends(get_db)):
    # Validate client
    client = db.query(Client).filter(Client.id == payload.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Validate stores / product types if products given
    for p in payload.products:
        if not db.query(Store).filter(Store.id == p.store_id).first():
            raise HTTPException(status_code=400, detail=f"Store {p.store_id} not found")
        if p.product_type_id and not db.query(ProductType).filter(
            ProductType.id == p.product_type_id
        ).first():
            raise HTTPException(
                status_code=400, detail=f"ProductType {p.product_type_id} not found"
            )

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
    db.flush()

    job_product_ids: List[int] = []
    for p in payload.products:
        jp = JobProduct(
            job_id=job.id,
            store_id=p.store_id,
            location_id=p.location_id,
            product_type_id=p.product_type_id,
            total_qty=p.total_qty,
            width_inch=p.width_inch,
            height_inch=p.height_inch,
            is_double_sided=p.is_double_sided,
            is_pool=p.is_pool,
            remark=p.remark,
            recee_status="pending",
            installation_status="pending",
        )
        db.add(jp)
        db.flush()
        job_product_ids.append(jp.id)

    db.commit()
    return JobCreateResponse(
        success=True,
        message="Job created successfully",
        job_id=job.id,
        job_product_ids=job_product_ids,
    )


# =====================================================
# 2. LIST JOBS
# =====================================================
@router.get("", response_model=List[JobListItem])
def list_jobs(
    client_id: Optional[int] = None,
    measurement_person_mobile: Optional[str] = None,
    db: Session = Depends(get_db),
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
@router.get("/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    products = db.query(JobProduct).filter(JobProduct.job_id == job_id).all()
    return {
        "id": job.id,
        "job_creation_date": job.job_creation_date,
        "client_id": job.client_id,
        "client_contact_person_name": job.client_contact_person_name,
        "client_contact_person_mobile": job.client_contact_person_mobile,
        "po_number": job.po_number,
        "po_date": job.po_date,
        "measurement_date": job.measurement_date,
        "measurement_person_name": job.measurement_person_name,
        "measurement_person_mobile": job.measurement_person_mobile,
        "status": job.status,
        "products": [
            {
                "id": jp.id,
                "store_id": jp.store_id,
                "product_type_id": jp.product_type_id,
                "total_qty": jp.total_qty,
                "width_inch": jp.width_inch,
                "height_inch": jp.height_inch,
                "recee_status": jp.recee_status,
                "installation_status": jp.installation_status,
            }
            for jp in products
        ],
    }
