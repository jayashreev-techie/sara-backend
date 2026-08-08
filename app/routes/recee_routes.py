"""
Recee flow routes — maps to mobile screens:
- Img 3: Take Next Step → Recee → Clients home (CUB 15/60)
- Img 4: Stores list (Store 1-6) → Measurement form
- Img 5: SAVE → Branch-113 history view
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from app.database import get_db
from app.models import (
    Job, JobProduct, Store, Client, ProductType,
    ReceeMeasurement, MobileUser
)
from app.schemas import (
    ClientHomeItem, StoreListItem, ReceeSubmitResponse, ReceeHistoryItem
)
from app.auth import get_current_mobile
from app.utils.file_upload import save_upload, build_photo_url

router = APIRouter(prefix="/api/recee", tags=["Recee"])


# =====================================================
# 1. CLIENTS HOME (Img 3 right side)
#    "City Union Bank 15/60", "Wix 10/30"...
# =====================================================
@router.get("/clients", response_model=List[ClientHomeItem])
def get_clients_for_recee(
    mobile: str = Depends(get_current_mobile),
    db: Session = Depends(get_db),
):
    """
    Logged-in worker ku assign aana clients list with progress.
    Filter: jobs.measurement_person_mobile = current user mobile
    Filter: only stores where recee is pending or in progress
    """
    from sqlalchemy import case

    # Group by client_id, count total and completed job_products
    rows = (
        db.query(
            Job.client_id,
            Client.company_name,
            func.count(JobProduct.id).label("total"),
            func.sum(
                case((JobProduct.recee_status == "completed", 1), else_=0)
            ).label("completed"),
        )
        .join(Client, Client.id == Job.client_id)
        .join(JobProduct, JobProduct.job_id == Job.id)
        .filter(Job.measurement_person_mobile == mobile)
        .group_by(Job.client_id, Client.company_name)
        .all()
    )

    result = []
    for row in rows:
        total = int(row.total or 0)
        completed = int(row.completed or 0)
        result.append(
            ClientHomeItem(
                client_id=row.client_id,
                company_name=row.company_name,
                total_stores=total,
                completed_stores=completed,
                progress_label=f"{completed}/{total}",
            )
        )
    return result


# =====================================================
# 2. STORES LIST under a client (Img 4 left/middle)
#    "1. Store 1 →", "2. Store 2 ✓"...
# =====================================================
@router.get("/clients/{client_id}/stores", response_model=List[StoreListItem])
def get_stores_for_client(
    client_id: int,
    mobile: str = Depends(get_current_mobile),
    db: Session = Depends(get_db),
):
    """
    Adha client kulla, current user-ku assign aana stores (job_products) list.
    """
    rows = (
        db.query(JobProduct, Store, ProductType)
        .join(Job, JobProduct.job_id == Job.id)
        .join(Store, JobProduct.store_id == Store.id)
        .outerjoin(ProductType, JobProduct.product_type_id == ProductType.id)
        .filter(
            Job.client_id == client_id,
            Job.measurement_person_mobile == mobile,
        )
        .all()
    )

    result = []
    for jp, store, ptype in rows:
        result.append(
            StoreListItem(
                job_product_id=jp.id,
                store_id=store.id,
                store_name=store.store_name,
                store_address=store.store_address,
                product_type=ptype.product_type if ptype else None,
                total_qty=jp.total_qty or 1,
                status=jp.recee_status,
            )
        )
    return result


# =====================================================
# 3. SUBMIT MEASUREMENT (Img 4 right, Img 5 left)
#    SAVE button press → measurement + photo upload
# =====================================================
@router.post("/measurements", response_model=ReceeSubmitResponse)
async def submit_measurement(
    job_product_id: int = Form(...),
    width_inch: float = Form(...),
    height_inch: float = Form(...),
    material: Optional[str] = Form(None),
    unit: str = Form("inches"),
    remarks: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    mobile: str = Depends(get_current_mobile),
    db: Session = Depends(get_db),
):
    """
    Mobile app submits measurement form (multipart/form-data because of photo).
    """
    # Verify job_product belongs to this user
    jp = (
        db.query(JobProduct)
        .join(Job, JobProduct.job_id == Job.id)
        .filter(
            JobProduct.id == job_product_id,
            Job.measurement_person_mobile == mobile,
        )
        .first()
    )
    if not jp:
        raise HTTPException(
            status_code=404,
            detail="Job product not found or not assigned to you",
        )

    # Save photo if provided
    photo_path = None
    if photo:
        photo_path = await save_upload(photo, "recee")

    # Save measurement
    measurement = ReceeMeasurement(
        job_product_id=jp.id,
        store_id=jp.store_id,
        measured_by_mobile=mobile,
        material=material,
        width_inch=width_inch,
        height_inch=height_inch,
        unit=unit,
        photo_path=photo_path,
        remarks=remarks,
    )
    db.add(measurement)

    # Update job_product status → completed
    jp.recee_status = "completed"
    jp.recee_completed_at = datetime.utcnow()
    # Also store final values on job_product (optional - per business decision)
    jp.width_inch = width_inch
    jp.height_inch = height_inch
    if photo_path:
        jp.photo_path = photo_path

    db.commit()
    db.refresh(measurement)

    return ReceeSubmitResponse(
        success=True,
        message="Measurement saved successfully",
        measurement_id=measurement.id,
    )


# =====================================================
# 4. RECEE HISTORY (Img 5 right - Branch-113 view)
#    Past measurements list with photos
# =====================================================
@router.get("/measurements", response_model=List[ReceeHistoryItem])
def get_recee_history(
    store_id: Optional[int] = None,
    client_id: Optional[int] = None,
    mobile: str = Depends(get_current_mobile),
    db: Session = Depends(get_db),
):
    """
    Filter by store_id or client_id; default = all measurements by this user.
    """
    query = (
        db.query(ReceeMeasurement, Store, MobileUser)
        .outerjoin(Store, ReceeMeasurement.store_id == Store.id)
        .outerjoin(
            MobileUser, ReceeMeasurement.measured_by_mobile == MobileUser.mobile
        )
        .filter(ReceeMeasurement.measured_by_mobile == mobile)
    )

    if store_id:
        query = query.filter(ReceeMeasurement.store_id == store_id)

    if client_id:
        query = query.filter(Store.client_id == client_id)

    rows = query.order_by(ReceeMeasurement.created_at.desc()).all()

    result = []
    for m, store, user in rows:
        result.append(
            ReceeHistoryItem(
                id=m.id,
                user_name=user.name if user else None,
                date=m.created_at.strftime("%d/%m/%y"),
                time=m.created_at.strftime("%I:%M%p"),
                store_name=store.store_name if store else None,
                location=store.store_address if store else None,
                width_inch=m.width_inch or 0,
                height_inch=m.height_inch or 0,
                photo_url=build_photo_url(m.photo_path) if m.photo_path else None,
                pole=None,
                qty=None,
            )
        )
    return result


# =====================================================
# 5. SINGLE MEASUREMENT DETAILS (optional)
# =====================================================
@router.get("/measurements/{measurement_id}")
def get_measurement_detail(
    measurement_id: int,
    mobile: str = Depends(get_current_mobile),
    db: Session = Depends(get_db),
):
    m = (
        db.query(ReceeMeasurement)
        .filter(
            ReceeMeasurement.id == measurement_id,
            ReceeMeasurement.measured_by_mobile == mobile,
        )
        .first()
    )
    if not m:
        raise HTTPException(status_code=404, detail="Measurement not found")
    return {
        "id": m.id,
        "job_product_id": m.job_product_id,
        "material": m.material,
        "width_inch": m.width_inch,
        "height_inch": m.height_inch,
        "unit": m.unit,
        "remarks": m.remarks,
        "photo_url": build_photo_url(m.photo_path) if m.photo_path else None,
        "created_at": m.created_at,
    }
