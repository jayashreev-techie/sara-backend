"""Job-order APIs for the admin/web application."""
import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, or_
from typing import List as TypingList
from sqlalchemy.orm import Session, aliased

from app.auth import get_current_company
from app.models import (
    Client,
    ClientProductLink,
    Company,
    Installation,
    Job,
    JobProduct,
    Location,
    ProductPhoto,
    ProductType,
    ReceeMeasurement,
    Store,
)
from app.schemas import (
    JobCreateRequest,
    JobDetailResponse,
    JobProductCreateItem,
    JobProductResponse,
    JobProductUpdateRequest,
    JobStatusUpdateRequest,
    JobUpdateRequest,
)
from app.tenant import get_tenant_db as get_db
from app.utils.file_upload import build_photo_url, save_upload


router = APIRouter(prefix="/api/jobs", tags=["Jobs (Admin)"])
job_product_router = APIRouter(prefix="/api/job-products", tags=["Job Products (Admin)"])


def _calc_sqft(width: float, height: float) -> float:
    return round((width * height) / 144, 4)


def _generate_job_order_id(db: Session, client_id: int) -> str:
    """Auto-generate job_order_id like orientbell001, orientbell002..."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Build prefix: lowercase, remove spaces and special chars
    prefix = re.sub(r"[^a-z0-9]", "", client.company_name.lower())

    # Find the last job_order_id with this prefix
    last_job = (
        db.query(Job.job_order_id)
        .filter(Job.job_order_id.ilike(f"{prefix}%"))
        .order_by(Job.job_order_id.desc())
        .first()
    )

    if last_job and last_job[0]:
        # Extract trailing number from e.g. "orientbell005"
        match = re.search(r"(\d+)$", last_job[0])
        next_num = int(match.group(1)) + 1 if match else 1
    else:
        next_num = 1

    return f"{prefix}{next_num:03d}"


def _job_number(job: Job) -> str:
    """Return a stable display number for new and legacy jobs."""
    return job.job_number or job.po_number or f"JOB-{job.id:06d}"


def _ensure_client_and_store(db: Session, client_id: int, store_id: int) -> tuple[Client, Store]:
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    if store.client_id != client_id:
        raise HTTPException(
            status_code=422,
            detail="Selected store does not belong to the selected client",
        )
    return client, store


def _ensure_product_type_for_client(
    db: Session, client_id: int, product_type_id: int
) -> ProductType:
    product_type = db.query(ProductType).filter(ProductType.id == product_type_id).first()
    if not product_type:
        raise HTTPException(status_code=404, detail="Product type not found")
    is_linked = (
        db.query(ClientProductLink.id)
        .filter(
            ClientProductLink.client_id == client_id,
            ClientProductLink.product_type_id == product_type_id,
        )
        .first()
    )
    if not is_linked:
        raise HTTPException(
            status_code=422,
            detail="Selected product type is not linked to the selected client",
        )
    return product_type


def _ensure_location(db: Session, location_id: Optional[int]) -> None:
    if location_id is not None and not db.query(Location.id).filter(Location.id == location_id).first():
        raise HTTPException(status_code=404, detail="Location not found")


def _line_store_id(job: Job, item: JobProductCreateItem) -> int:
    store_id = item.store_id or job.store_id
    if store_id is None:
        raise HTTPException(status_code=422, detail="store_id is required for every job product")
    if job.store_id is not None and store_id != job.store_id:
        raise HTTPException(
            status_code=422,
            detail="Job product store_id must match the job-order store_id",
        )
    return store_id


def _validate_product_item(db: Session, job: Job, item: JobProductCreateItem) -> int:
    store_id = _line_store_id(job, item)
    _ensure_client_and_store(db, job.client_id, store_id)
    _ensure_product_type_for_client(db, job.client_id, item.product_type_id)
    _ensure_location(db, item.location_id)
    return store_id


def _recee_dict(measurement: Optional[ReceeMeasurement]) -> Optional[dict]:
    if not measurement:
        return None
    return {
        "id": measurement.id,
        "job_product_id": measurement.job_product_id,
        "store_id": measurement.store_id,
        "material": measurement.material,
        "width_inch": measurement.width_inch,
        "height_inch": measurement.height_inch,
        "unit": measurement.unit,
        "remarks": measurement.remarks,
        "photo_url": build_photo_url(measurement.photo_path),
        "created_at": measurement.created_at,
    }


def _installation_dict(installation: Optional[Installation]) -> Optional[dict]:
    if not installation:
        return None
    return {
        "id": installation.id,
        "job_product_id": installation.job_product_id,
        "store_id": installation.store_id,
        "material": installation.material,
        "width_inch": installation.width_inch,
        "height_inch": installation.height_inch,
        "unit": installation.unit,
        "remarks": installation.remarks,
        "recee_photo_url": build_photo_url(installation.recee_photo_path),
        "design_photo_url": build_photo_url(installation.design_photo_path),
        "installation_photo_url": build_photo_url(installation.installation_photo_path),
        "created_at": installation.created_at,
    }


def _build_product_response(
    product: JobProduct,
    recee: Optional[ReceeMeasurement] = None,
    installation: Optional[Installation] = None,
) -> JobProductResponse:
    return JobProductResponse(
        id=product.id,
        store_id=product.store_id,
        store_name=product.store.store_name if product.store else None,
        location_id=product.location_id,
        product_type_id=product.product_type_id,
        product_type=product.product_type.product_type if product.product_type else None,
        total_qty=product.total_qty,
        width_inch=product.width_inch,
        height_inch=product.height_inch,
        sq_ft_unit=product.sq_ft_unit,
        total_sq_ft=product.total_sq_ft,
        is_double_sided=product.is_double_sided,
        is_pool=product.is_pool,
        remark=product.remark,
        photo_path=product.photo_path,
        photo_url=build_photo_url(product.photo_path),
        recee_status=product.recee_status,
        installation_status=product.installation_status,
        recee=_recee_dict(recee),
        installation=_installation_dict(installation),
    )


def _latest_records_by_product(db: Session, job_id: int) -> tuple[dict, dict]:
    """Get latest recee and installation rows per product without changing history."""
    recee_by_product = {}
    recee_rows = (
        db.query(ReceeMeasurement)
        .join(JobProduct, JobProduct.id == ReceeMeasurement.job_product_id)
        .filter(JobProduct.job_id == job_id)
        .order_by(ReceeMeasurement.job_product_id, ReceeMeasurement.created_at.desc())
        .all()
    )
    for row in recee_rows:
        recee_by_product.setdefault(row.job_product_id, row)

    installation_by_product = {}
    installation_rows = (
        db.query(Installation)
        .join(JobProduct, JobProduct.id == Installation.job_product_id)
        .filter(JobProduct.job_id == job_id)
        .order_by(Installation.job_product_id, Installation.created_at.desc())
        .all()
    )
    for row in installation_rows:
        installation_by_product.setdefault(row.job_product_id, row)
    return recee_by_product, installation_by_product


def _job_gallery(
    products: list[JobProduct], recee_by_product: dict, installation_by_product: dict
) -> list[dict]:
    gallery = []
    for product in products:
        if product.photo_path:
            gallery.append({
                "type": "job_product",
                "job_product_id": product.id,
                "url": build_photo_url(product.photo_path),
            })
        recee = recee_by_product.get(product.id)
        if recee and recee.photo_path:
            gallery.append({
                "type": "recee",
                "job_product_id": product.id,
                "url": build_photo_url(recee.photo_path),
            })
        installation = installation_by_product.get(product.id)
        if installation:
            for photo_type, photo_path in (
                ("installation_recee", installation.recee_photo_path),
                ("design", installation.design_photo_path),
                ("installation", installation.installation_photo_path),
            ):
                if photo_path:
                    gallery.append({
                        "type": photo_type,
                        "job_product_id": product.id,
                        "url": build_photo_url(photo_path),
                    })
    return gallery


def _get_job_or_404(db: Session, job_id: int) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _create_product(db: Session, job: Job, item: JobProductCreateItem) -> JobProduct:
    store_id = _validate_product_item(db, job, item)
    sq_ft_unit = _calc_sqft(item.width_inch, item.height_inch)
    product = JobProduct(
        job_id=job.id,
        store_id=store_id,
        location_id=item.location_id,
        product_type_id=item.product_type_id,
        total_qty=item.total_qty,
        width_inch=item.width_inch,
        height_inch=item.height_inch,
        sq_ft_unit=sq_ft_unit,
        total_sq_ft=round(sq_ft_unit * item.total_qty, 4),
        is_double_sided=item.is_double_sided,
        is_pool=item.is_pool,
        remark=item.remark,
        recee_status="pending",
        installation_status="pending",
    )
    db.add(product)
    return product


def _update_product(
    db: Session, product: JobProduct, payload: JobProductUpdateRequest
) -> JobProduct:
    job = _get_job_or_404(db, product.job_id)
    fields = payload.model_fields_set
    target_store_id = payload.store_id if "store_id" in fields else product.store_id
    if target_store_id is None:
        raise HTTPException(status_code=422, detail="store_id cannot be empty")
    if job.store_id is not None and target_store_id != job.store_id:
        raise HTTPException(
            status_code=422,
            detail="Job product store_id must match the job-order store_id",
        )
    _ensure_client_and_store(db, job.client_id, target_store_id)

    target_product_type_id = (
        payload.product_type_id if "product_type_id" in fields else product.product_type_id
    )
    if target_product_type_id is None:
        raise HTTPException(status_code=422, detail="product_type_id cannot be empty")
    _ensure_product_type_for_client(db, job.client_id, target_product_type_id)

    if "location_id" in fields:
        _ensure_location(db, payload.location_id)
        product.location_id = payload.location_id
    product.store_id = target_store_id
    product.product_type_id = target_product_type_id
    for field in (
        "total_qty",
        "width_inch",
        "height_inch",
        "is_double_sided",
        "is_pool",
        "remark",
    ):
        if field in fields:
            setattr(product, field, getattr(payload, field))
    product.sq_ft_unit = _calc_sqft(product.width_inch, product.height_inch)
    product.total_sq_ft = round(product.sq_ft_unit * product.total_qty, 4)
    return product


def _raise_if_product_has_work_data(db: Session, product_id: int) -> None:
    recee_count = (
        db.query(func.count(ReceeMeasurement.id))
        .filter(ReceeMeasurement.job_product_id == product_id)
        .scalar()
        or 0
    )
    installation_count = (
        db.query(func.count(Installation.id))
        .filter(Installation.job_product_id == product_id)
        .scalar()
        or 0
    )
    if recee_count or installation_count:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Cannot delete a job product that has recee or installation data",
                "recee_count": recee_count,
                "installation_count": installation_count,
            },
        )


@router.post("", response_model=JobDetailResponse, status_code=201)
def create_job(
    payload: JobCreateRequest,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    _ensure_client_and_store(db, payload.client_id, payload.store_id)
    if payload.job_number and db.query(Job.id).filter(Job.job_number == payload.job_number.strip()).first():
        raise HTTPException(status_code=409, detail="job_number already exists")

    job_order_id = _generate_job_order_id(db, payload.client_id)

    job = Job(
        job_order_id=job_order_id,
        job_creation_date=payload.job_date or payload.job_creation_date or date.today(),
        client_id=payload.client_id,
        store_id=payload.store_id,
        due_date=payload.due_date,
        remarks=payload.remarks,
        client_contact_person_name=payload.client_contact_person_name,
        client_contact_person_mobile=payload.client_contact_person_mobile,
        po_number=payload.po_number,
        po_date=payload.po_date,
        measurement_date=payload.measurement_date,
        measurement_person_name=payload.measurement_person_name,
        measurement_person_mobile=(
            payload.measurement_person_mobile.strip()
            if payload.measurement_person_mobile
            else None
        ),
        status=payload.status,
    )
    db.add(job)
    db.flush()
    job.job_number = payload.job_number.strip() if payload.job_number else f"JOB-{job.id:06d}"
    for product in payload.products:
        _create_product(db, job, product)

    db.commit()
    db.refresh(job)
    return get_job(job.id, db)


@router.get("")
def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    client_id: Optional[int] = Query(None, ge=1),
    measurement_person_mobile: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    header_store = aliased(Store)
    query = (
        db.query(
            Job,
            Client.company_name.label("client_name"),
            header_store.store_name.label("store_name"),
            func.count(JobProduct.id).label("total_products"),
            func.min(JobProduct.store_id).label("legacy_store_id"),
        )
        .outerjoin(Client, Client.id == Job.client_id)
        .outerjoin(header_store, header_store.id == Job.store_id)
        .outerjoin(JobProduct, JobProduct.job_id == Job.id)
        .group_by(Job.id, Client.company_name, header_store.store_name)
    )
    if client_id is not None:
        query = query.filter(Job.client_id == client_id)
    if measurement_person_mobile:
        query = query.filter(Job.measurement_person_mobile == measurement_person_mobile.strip())
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Job.job_order_id.ilike(term),
                Job.job_number.ilike(term),
                Job.po_number.ilike(term),
                Client.company_name.ilike(term),
                header_store.store_name.ilike(term),
            )
        )

    total = query.count()
    rows = query.order_by(Job.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = []
    for job, client_name, store_name, total_products, legacy_store_id in rows:
        store_id = job.store_id or legacy_store_id
        if store_name is None and store_id is not None:
            store = db.query(Store).filter(Store.id == store_id).first()
            store_name = store.store_name if store else None
        items.append({
            "id": job.id,
            "job_order_id": job.job_order_id,
            "job_number": _job_number(job),
            "client_id": job.client_id,
            "client_name": client_name,
            "store_id": store_id,
            "store_name": store_name,
            "status": job.status or "pending",
            "created_at": job.created_at,
            "total_products": int(total_products or 0),
        })
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
    }


@router.get("/{job_id}", response_model=JobDetailResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    job = _get_job_or_404(db, job_id)
    client = db.query(Client).filter(Client.id == job.client_id).first()
    products = db.query(JobProduct).filter(JobProduct.job_id == job_id).order_by(JobProduct.id).all()
    header_store_id = job.store_id or (products[0].store_id if products else None)
    store = db.query(Store).filter(Store.id == header_store_id).first() if header_store_id else None
    recee_by_product, installation_by_product = _latest_records_by_product(db, job_id)
    return JobDetailResponse(
        id=job.id,
        job_order_id=job.job_order_id,
        job_number=_job_number(job),
        job_date=job.job_creation_date,
        job_creation_date=job.job_creation_date,
        client_id=job.client_id,
        client_name=client.company_name if client else None,
        company_name=client.company_name if client else None,
        store_id=header_store_id,
        store_name=store.store_name if store else None,
        due_date=job.due_date,
        remarks=job.remarks,
        client_contact_person_name=job.client_contact_person_name,
        client_contact_person_mobile=job.client_contact_person_mobile,
        po_number=job.po_number,
        po_date=job.po_date,
        measurement_date=job.measurement_date,
        measurement_person_name=job.measurement_person_name,
        measurement_person_mobile=job.measurement_person_mobile,
        status=job.status or "pending",
        created_at=job.created_at,
        total_products=len(products),
        products=[
            _build_product_response(
                product,
                recee_by_product.get(product.id),
                installation_by_product.get(product.id),
            )
            for product in products
        ],
        gallery=_job_gallery(products, recee_by_product, installation_by_product),
    )


@router.put("/{job_id}", response_model=JobDetailResponse)
def update_job(
    job_id: int,
    payload: JobUpdateRequest,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    job = _get_job_or_404(db, job_id)
    fields = payload.model_fields_set
    target_client_id = payload.client_id if "client_id" in fields else job.client_id
    target_store_id = payload.store_id if "store_id" in fields else job.store_id
    if target_client_id is None or target_store_id is None:
        raise HTTPException(status_code=422, detail="client_id and store_id cannot be empty")
    _ensure_client_and_store(db, target_client_id, target_store_id)
    if "client_id" in fields or "store_id" in fields:
        for product in db.query(JobProduct).filter(JobProduct.job_id == job.id).all():
            if product.store_id != target_store_id:
                raise HTTPException(
                    status_code=422,
                    detail="Update job products before changing the job-order client or store",
                )
            _ensure_product_type_for_client(db, target_client_id, product.product_type_id)
        job.client_id = target_client_id
        job.store_id = target_store_id

    if "job_number" in fields:
        if not payload.job_number or not payload.job_number.strip():
            raise HTTPException(status_code=422, detail="job_number cannot be empty")
        duplicate = (
            db.query(Job.id)
            .filter(Job.job_number == payload.job_number.strip(), Job.id != job.id)
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="job_number already exists")
        job.job_number = payload.job_number.strip()
    if "job_date" in fields:
        job.job_creation_date = payload.job_date
    elif "job_creation_date" in fields:
        job.job_creation_date = payload.job_creation_date
    for field in (
        "due_date",
        "remarks",
        "client_contact_person_name",
        "client_contact_person_mobile",
        "po_number",
        "po_date",
        "measurement_date",
        "measurement_person_name",
        "status",
    ):
        if field in fields:
            setattr(job, field, getattr(payload, field))
    if "measurement_person_mobile" in fields:
        job.measurement_person_mobile = (
            payload.measurement_person_mobile.strip()
            if payload.measurement_person_mobile
            else None
        )
    db.commit()
    db.refresh(job)
    return get_job(job.id, db)


@router.put("/{job_id}/status", response_model=JobDetailResponse)
def update_job_status(
    job_id: int,
    payload: JobStatusUpdateRequest,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    job = _get_job_or_404(db, job_id)
    job.status = payload.status
    db.commit()
    return get_job(job.id, db)


@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    job = _get_job_or_404(db, job_id)
    recee_count = (
        db.query(func.count(ReceeMeasurement.id))
        .join(JobProduct, JobProduct.id == ReceeMeasurement.job_product_id)
        .filter(JobProduct.job_id == job.id)
        .scalar()
        or 0
    )
    installation_count = (
        db.query(func.count(Installation.id))
        .join(JobProduct, JobProduct.id == Installation.job_product_id)
        .filter(JobProduct.job_id == job.id)
        .scalar()
        or 0
    )
    if recee_count or installation_count:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Cannot delete job with recee or installation data",
                "recee_count": recee_count,
                "installation_count": installation_count,
            },
        )
    db.delete(job)
    db.commit()
    return {"success": True, "message": "Job deleted successfully"}


@router.post("/{job_id}/products", response_model=JobProductResponse, status_code=201)
def add_product(
    job_id: int,
    payload: JobProductCreateItem,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    job = _get_job_or_404(db, job_id)
    product = _create_product(db, job, payload)
    db.commit()
    db.refresh(product)
    return _build_product_response(product)


@router.put("/{job_id}/products/{product_id}", response_model=JobProductResponse)
def update_product_for_job(
    job_id: int,
    product_id: int,
    payload: JobProductUpdateRequest,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    product = db.query(JobProduct).filter(
        JobProduct.id == product_id, JobProduct.job_id == job_id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Job product not found")
    _update_product(db, product, payload)
    db.commit()
    db.refresh(product)
    return _build_product_response(product)


@router.delete("/{job_id}/products/{product_id}")
def delete_product_for_job(
    job_id: int,
    product_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    product = db.query(JobProduct).filter(
        JobProduct.id == product_id, JobProduct.job_id == job_id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Job product not found")
    _raise_if_product_has_work_data(db, product.id)
    db.delete(product)
    db.commit()
    return {"success": True, "message": "Job product deleted successfully"}


@router.post("/{job_id}/products/{product_id}/photo")
async def upload_product_photo(
    job_id: int,
    product_id: int,
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    product = db.query(JobProduct).filter(
        JobProduct.id == product_id, JobProduct.job_id == job_id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Job product not found")
    path = await save_upload(photo, subfolder=f"jobs/{job_id}/products/{product_id}")
    product.photo_path = path
    db.commit()
    return {
        "success": True,
        "message": "Product photo uploaded",
        "photo_path": path,
        "photo_url": build_photo_url(path),
    }


@job_product_router.get("/{product_id}/recee")
def get_job_product_recee(
    product_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    product = db.query(JobProduct).filter(JobProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Job product not found")
    measurement = db.query(ReceeMeasurement).filter(
        ReceeMeasurement.job_product_id == product_id
    ).order_by(ReceeMeasurement.created_at.desc()).first()
    return {
        "job_product_id": product_id,
        "status": product.recee_status,
        "data": _recee_dict(measurement),
    }


@job_product_router.get("/{product_id}/installation")
def get_job_product_installation(
    product_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    product = db.query(JobProduct).filter(JobProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Job product not found")
    installation = db.query(Installation).filter(
        Installation.job_product_id == product_id
    ).order_by(Installation.created_at.desc()).first()
    return {
        "job_product_id": product_id,
        "status": product.installation_status,
        "data": _installation_dict(installation),
    }


@job_product_router.put("/{product_id}", response_model=JobProductResponse)
def update_job_product(
    product_id: int,
    payload: JobProductUpdateRequest,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    product = db.query(JobProduct).filter(JobProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Job product not found")
    _update_product(db, product, payload)
    db.commit()
    db.refresh(product)
    return _build_product_response(product)


@job_product_router.delete("/{product_id}")
def delete_job_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    product = db.query(JobProduct).filter(JobProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Job product not found")
    _raise_if_product_has_work_data(db, product.id)
    db.delete(product)
    db.commit()
    return {"success": True, "message": "Job product deleted successfully"}


# =====================================================
# PRODUCT PHOTOS — multiple photos per job product
# =====================================================

def _photo_dict(photo: ProductPhoto) -> dict:
    return {
        "id": photo.id,
        "file_path": build_photo_url(photo.file_path),
        "original_name": photo.original_name,
        "created_at": photo.created_at,
    }


@router.post("/{job_id}/products/{product_id}/photos", status_code=201)
async def upload_product_photos(
    job_id: int,
    product_id: int,
    photos: TypingList[UploadFile] = File(...),
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    product = db.query(JobProduct).filter(
        JobProduct.id == product_id, JobProduct.job_id == job_id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Job product not found")

    saved = []
    for photo in photos:
        path = await save_upload(photo, subfolder=f"product_photos/{product_id}")
        record = ProductPhoto(
            product_id=product_id,
            file_path=path,
            original_name=photo.filename,
        )
        db.add(record)
        saved.append(record)

    db.commit()
    for record in saved:
        db.refresh(record)
    return [_photo_dict(record) for record in saved]


@router.get("/{job_id}/products/{product_id}/photos")
def list_product_photos(
    job_id: int,
    product_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    product = db.query(JobProduct).filter(
        JobProduct.id == product_id, JobProduct.job_id == job_id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Job product not found")

    photos = (
        db.query(ProductPhoto)
        .filter(ProductPhoto.product_id == product_id)
        .order_by(ProductPhoto.id)
        .all()
    )
    return [_photo_dict(p) for p in photos]


@router.delete("/{job_id}/products/{product_id}/photos/{photo_id}")
def delete_product_photo(
    job_id: int,
    product_id: int,
    photo_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    product = db.query(JobProduct).filter(
        JobProduct.id == product_id, JobProduct.job_id == job_id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Job product not found")

    photo = db.query(ProductPhoto).filter(
        ProductPhoto.id == photo_id, ProductPhoto.product_id == product_id
    ).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    db.delete(photo)
    db.commit()
    return {"success": True, "message": "Photo deleted successfully"}
