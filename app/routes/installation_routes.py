"""
Installation flow routes — maps to mobile screens (Img 6):
- Home page (Clients list - same pattern as Recee but installation progress)
- Installation list (Stores under client)
- Installation updates (3 photo sections: Recee/Design/Installation)

Logic: Only stores where recee_status = 'completed' show up here.
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from app.database import get_db
from app.models import (
    Job, JobProduct, Store, Client, ProductType, Installation, MobileUser
)
from app.schemas import (
    ClientHomeItem, StoreListItem, InstallationSubmitResponse
)
from app.auth import get_current_mobile
from app.utils.file_upload import save_upload, build_photo_url

router = APIRouter(prefix="/api/installation", tags=["Installation"])


# =====================================================
# 1. CLIENTS HOME for Installation (Img 6 first screen)
#    Same client list, but installation progress shown
# =====================================================
@router.get("/clients", response_model=List[ClientHomeItem])
def get_clients_for_installation(
    mobile: str = Depends(get_current_mobile),
    db: Session = Depends(get_db),
):
    """
    Logged-in worker ku assign aana clients with installation progress.
    Only counts job_products where recee is already completed
    (because installation can start only after recee).
    """
    rows = (
        db.query(
            Job.client_id,
            Client.company_name,
            func.count(JobProduct.id).label("total"),
            func.sum(
                case((JobProduct.installation_status == "completed", 1), else_=0)
            ).label("completed"),
        )
        .join(Client, Client.id == Job.client_id)
        .join(JobProduct, JobProduct.job_id == Job.id)
        .filter(
            Job.measurement_person_mobile == mobile,
            JobProduct.recee_status == "completed",  # ⭐ key filter
        )
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
# 2. STORES LIST for Installation (Img 6 second/third screen)
#    Only recee-completed stores show here
# =====================================================
@router.get("/clients/{client_id}/stores", response_model=List[StoreListItem])
def get_stores_for_installation(
    client_id: int,
    mobile: str = Depends(get_current_mobile),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(JobProduct, Store, ProductType)
        .join(Job, JobProduct.job_id == Job.id)
        .join(Store, JobProduct.store_id == Store.id)
        .outerjoin(ProductType, JobProduct.product_type_id == ProductType.id)
        .filter(
            Job.client_id == client_id,
            Job.measurement_person_mobile == mobile,
            JobProduct.recee_status == "completed",  # ⭐ recee done only
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
                status=jp.installation_status,
            )
        )
    return result


# =====================================================
# 3. GET RECEE PHOTO for installation reference (Img 6 last screen "Recee" section)
# =====================================================
@router.get("/job-products/{job_product_id}/recee-info")
def get_recee_reference(
    job_product_id: int,
    mobile: str = Depends(get_current_mobile),
    db: Session = Depends(get_db),
):
    """
    Installation form la "Recee" photo section auto-fill panna.
    Returns recee photo + measurements that worker captured earlier.
    """
    from app.models import ReceeMeasurement

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
        raise HTTPException(status_code=404, detail="Job product not found")

    # Latest recee measurement for this job_product
    measurement = (
        db.query(ReceeMeasurement)
        .filter(ReceeMeasurement.job_product_id == job_product_id)
        .order_by(ReceeMeasurement.created_at.desc())
        .first()
    )

    return {
        "job_product_id": jp.id,
        "store_id": jp.store_id,
        "width_inch": measurement.width_inch if measurement else jp.width_inch,
        "height_inch": measurement.height_inch if measurement else jp.height_inch,
        "material": measurement.material if measurement else None,
        "recee_photo_url": (
            build_photo_url(measurement.photo_path)
            if measurement and measurement.photo_path
            else None
        ),
    }


# =====================================================
# 4. SUBMIT INSTALLATION (Img 6 last screen SAVE button)
#    3 photo sections: recee_photo (auto), design_photo, installation_photo
# =====================================================
@router.post("/submit", response_model=InstallationSubmitResponse)
async def submit_installation(
    job_product_id: int = Form(...),
    width_inch: float = Form(...),
    height_inch: float = Form(...),
    material: Optional[str] = Form(None),
    unit: str = Form("inches"),
    remarks: Optional[str] = Form(None),
    design_photo: Optional[UploadFile] = File(None),
    installation_photo: UploadFile = File(...),  # required
    mobile: str = Depends(get_current_mobile),
    db: Session = Depends(get_db),
):
    """
    Mobile app submits installation form with design + installation photos.
    Recee photo = auto-pulled from earlier recee measurement (no upload here).
    """
    # Verify job_product belongs to this user AND recee is done
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
            status_code=404, detail="Job product not found"
        )
    if jp.recee_status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Recee must be completed before installation",
        )

    # Auto-pull recee photo
    from app.models import ReceeMeasurement
    recee_meas = (
        db.query(ReceeMeasurement)
        .filter(ReceeMeasurement.job_product_id == job_product_id)
        .order_by(ReceeMeasurement.created_at.desc())
        .first()
    )
    recee_photo_path = recee_meas.photo_path if recee_meas else jp.photo_path

    # Save uploaded photos
    design_photo_path = None
    if design_photo:
        design_photo_path = await save_upload(design_photo, "installation")

    installation_photo_path = await save_upload(installation_photo, "installation")

    # Save installation record
    installation = Installation(
        job_product_id=jp.id,
        store_id=jp.store_id,
        installed_by_mobile=mobile,
        material=material,
        width_inch=width_inch,
        height_inch=height_inch,
        unit=unit,
        recee_photo_path=recee_photo_path,
        design_photo_path=design_photo_path,
        installation_photo_path=installation_photo_path,
        remarks=remarks,
    )
    db.add(installation)

    # Update job_product status
    jp.installation_status = "completed"
    jp.installation_completed_at = datetime.utcnow()

    db.commit()
    db.refresh(installation)

    return InstallationSubmitResponse(
        success=True,
        message="Installation saved successfully",
        installation_id=installation.id,
    )


# =====================================================
# 5. INSTALLATION HISTORY (Branch view for installations)
# =====================================================
@router.get("/history")
def get_installation_history(
    store_id: Optional[int] = None,
    client_id: Optional[int] = None,
    mobile: str = Depends(get_current_mobile),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Installation, Store, MobileUser)
        .outerjoin(Store, Installation.store_id == Store.id)
        .outerjoin(MobileUser, Installation.installed_by_mobile == MobileUser.mobile)
        .filter(Installation.installed_by_mobile == mobile)
    )

    if store_id:
        query = query.filter(Installation.store_id == store_id)
    if client_id:
        query = query.filter(Store.client_id == client_id)

    rows = query.order_by(Installation.created_at.desc()).all()

    result = []
    for inst, store, user in rows:
        result.append({
            "id": inst.id,
            "user_name": user.name if user else None,
            "date": inst.created_at.strftime("%d/%m/%y"),
            "time": inst.created_at.strftime("%I:%M%p"),
            "store_name": store.store_name if store else None,
            "location": store.store_address if store else None,
            "width_inch": inst.width_inch,
            "height_inch": inst.height_inch,
            "material": inst.material,
            "remarks": inst.remarks,
            "recee_photo_url": build_photo_url(inst.recee_photo_path) if inst.recee_photo_path else None,
            "design_photo_url": build_photo_url(inst.design_photo_path) if inst.design_photo_path else None,
            "installation_photo_url": build_photo_url(inst.installation_photo_path) if inst.installation_photo_path else None,
        })
    return result


# =====================================================
# 6. SINGLE INSTALLATION DETAILS
# =====================================================
@router.get("/{installation_id}")
def get_installation_detail(
    installation_id: int,
    mobile: str = Depends(get_current_mobile),
    db: Session = Depends(get_db),
):
    inst = (
        db.query(Installation)
        .filter(
            Installation.id == installation_id,
            Installation.installed_by_mobile == mobile,
        )
        .first()
    )
    if not inst:
        raise HTTPException(status_code=404, detail="Installation not found")
    return {
        "id": inst.id,
        "job_product_id": inst.job_product_id,
        "material": inst.material,
        "width_inch": inst.width_inch,
        "height_inch": inst.height_inch,
        "unit": inst.unit,
        "remarks": inst.remarks,
        "recee_photo_url": build_photo_url(inst.recee_photo_path) if inst.recee_photo_path else None,
        "design_photo_url": build_photo_url(inst.design_photo_path) if inst.design_photo_path else None,
        "installation_photo_url": build_photo_url(inst.installation_photo_path) if inst.installation_photo_path else None,
        "created_at": inst.created_at,
    }
