"""Design → Printing → Fabrication workflow routes."""
import os, uuid, shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.tenant import get_tenant_db as get_db
from app.models import WorkDesign, Job, Company
from app.auth import get_current_company
from app.config import settings

router = APIRouter(prefix="/api/design", tags=["Design & Fabrication"])


def _to_dict(w: WorkDesign) -> dict:
    return {
        "id": w.id,
        "job_id": w.job_id,
        "design_file_1": w.design_file_1,
        "design_file_1_path": w.design_file_1_path,
        "design_file_2": w.design_file_2,
        "design_file_2_path": w.design_file_2_path,
        "printer_id": w.printer_id,
        "printer_name": w.printer.printer_name if w.printer else None,
        "printing_done": w.printing_done,
        "move_to_fabrication": w.move_to_fabrication,
        "fabrication_done": w.fabrication_done,
        "created_at": str(w.created_at) if w.created_at else None,
    }


# ---- Design Management ----

@router.get("")
def list_designs(
    job_id: int = None,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    q = db.query(WorkDesign).filter(WorkDesign.del_flag == False)
    if job_id:
        q = q.filter(WorkDesign.job_id == job_id)
    return [_to_dict(w) for w in q.order_by(WorkDesign.id.desc()).all()]


@router.post("", status_code=201)
def create_design(
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    if not payload.get("job_id"):
        raise HTTPException(status_code=422, detail="'job_id' is required")
    job = db.query(Job).filter(Job.id == payload["job_id"]).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    w = WorkDesign(
        job_id=payload["job_id"],
        printer_id=payload.get("printer_id"),
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return _to_dict(w)


@router.get("/{design_id}")
def get_design(design_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    w = db.query(WorkDesign).filter(WorkDesign.id == design_id, WorkDesign.del_flag == False).first()
    if not w:
        raise HTTPException(status_code=404, detail="Design not found")
    return _to_dict(w)


@router.post("/{design_id}/upload")
async def upload_design_file(
    design_id: int,
    slot: int = 1,  # 1 or 2
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    w = db.query(WorkDesign).filter(WorkDesign.id == design_id, WorkDesign.del_flag == False).first()
    if not w:
        raise HTTPException(status_code=404, detail="Design not found")
    if slot not in (1, 2):
        raise HTTPException(status_code=400, detail="slot must be 1 or 2")

    ext = os.path.splitext(file.filename)[1].lower()
    filename = f"design_{design_id}_slot{slot}_{uuid.uuid4().hex}{ext}"
    upload_dir = os.path.join(settings.UPLOAD_DIR, "designs")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    if slot == 1:
        w.design_file_1 = filename
        w.design_file_1_path = file_path
    else:
        w.design_file_2 = filename
        w.design_file_2_path = file_path

    db.commit()
    return {"message": "Design file uploaded", "file_name": filename, "slot": slot}


# ---- Printing ----

@router.post("/{design_id}/assign-printer")
def assign_printer(
    design_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    w = db.query(WorkDesign).filter(WorkDesign.id == design_id, WorkDesign.del_flag == False).first()
    if not w:
        raise HTTPException(status_code=404, detail="Design not found")
    if not payload.get("printer_id"):
        raise HTTPException(status_code=422, detail="'printer_id' is required")
    w.printer_id = payload["printer_id"]
    db.commit()
    db.refresh(w)
    return _to_dict(w)


@router.post("/{design_id}/mark-printing-done")
def mark_printing_done(
    design_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    w = db.query(WorkDesign).filter(WorkDesign.id == design_id, WorkDesign.del_flag == False).first()
    if not w:
        raise HTTPException(status_code=404, detail="Design not found")
    w.printing_done = True
    db.commit()
    db.refresh(w)
    return _to_dict(w)


@router.post("/{design_id}/move-to-fabrication")
def move_to_fabrication(
    design_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    w = db.query(WorkDesign).filter(WorkDesign.id == design_id, WorkDesign.del_flag == False).first()
    if not w:
        raise HTTPException(status_code=404, detail="Design not found")
    if not w.printing_done:
        raise HTTPException(status_code=400, detail="Printing must be completed before moving to fabrication")
    w.move_to_fabrication = True
    db.commit()
    db.refresh(w)
    return _to_dict(w)


# ---- Fabrication ----

@router.get("/fabrication/queue")
def fabrication_queue(db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    """Jobs ready for fabrication: printing_done=True and move_to_fabrication=True."""
    designs = (
        db.query(WorkDesign)
        .filter(
            WorkDesign.del_flag == False,
            WorkDesign.printing_done == True,
            WorkDesign.move_to_fabrication == True,
        )
        .order_by(WorkDesign.id.desc())
        .all()
    )
    return [_to_dict(w) for w in designs]


@router.post("/{design_id}/mark-fabrication-done")
def mark_fabrication_done(
    design_id: int,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    w = db.query(WorkDesign).filter(WorkDesign.id == design_id, WorkDesign.del_flag == False).first()
    if not w:
        raise HTTPException(status_code=404, detail="Design not found")
    if not w.move_to_fabrication:
        raise HTTPException(status_code=400, detail="Design must be moved to fabrication first")
    w.fabrication_done = True
    db.commit()
    db.refresh(w)
    return _to_dict(w)


@router.delete("/{design_id}")
def delete_design(design_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    w = db.query(WorkDesign).filter(WorkDesign.id == design_id, WorkDesign.del_flag == False).first()
    if not w:
        raise HTTPException(status_code=404, detail="Design not found")
    w.del_flag = True
    db.commit()
    return {"message": "Deleted"}
