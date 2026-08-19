"""Dashboard summary endpoints for the ERP web dashboard."""
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.tenant import get_tenant_db as get_db
from app.models import Client, Installation, Job, JobProduct, ReceeMeasurement, Store
from app.auth import get_current_company
from app.models import Company

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


# ── Response schemas ──────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    active_jobs: int
    jobs_this_week: int
    pending_installs: int
    next_install_date: Optional[str]
    receivables_amount: float
    receivables_invoice_count: int
    completed_jobs: int
    total_jobs: int


class ReceeProgressItem(BaseModel):
    client_name: str
    done: int
    total: int


class ActivityItem(BaseModel):
    id: int
    type: str
    description: str
    user: str
    timestamp: str


class ModuleStat(BaseModel):
    label: str
    count: int


class ModuleStats(BaseModel):
    purchase: ModuleStat
    inventory: ModuleStat
    operations: ModuleStat
    store: ModuleStat
    job_orders: ModuleStat
    design: ModuleStat
    hr: ModuleStat
    accounts: ModuleStat
    crm: ModuleStat
    reports: ModuleStat


# ── 1. Stats ─────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=DashboardStats)
def get_stats(
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday

    total_jobs = db.query(func.count(Job.id)).scalar() or 0
    completed_jobs = (
        db.query(func.count(Job.id)).filter(Job.status == "completed").scalar() or 0
    )
    active_jobs = total_jobs - completed_jobs

    jobs_this_week = (
        db.query(func.count(Job.id))
        .filter(Job.job_creation_date >= week_start)
        .scalar()
        or 0
    )

    pending_installs = (
        db.query(func.count(JobProduct.id))
        .filter(JobProduct.installation_status == "pending")
        .scalar()
        or 0
    )

    # Next upcoming measurement date from non-completed jobs
    next_date_row = (
        db.query(Job.measurement_date)
        .filter(Job.status != "completed", Job.measurement_date >= today)
        .order_by(Job.measurement_date.asc())
        .first()
    )
    next_install_date = (
        next_date_row[0].isoformat() if next_date_row and next_date_row[0] else None
    )

    return DashboardStats(
        active_jobs=active_jobs,
        jobs_this_week=jobs_this_week,
        pending_installs=pending_installs,
        next_install_date=next_install_date,
        # Invoices/receivables module not yet built — return 0
        receivables_amount=0.0,
        receivables_invoice_count=0,
        completed_jobs=completed_jobs,
        total_jobs=total_jobs,
    )


# ── 2. Recee progress per client ──────────────────────────────────────────────

@router.get("/recee-progress", response_model=List[ReceeProgressItem])
def get_recee_progress(
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    rows = (
        db.query(
            Client.company_name,
            func.sum(
                case((JobProduct.recee_status == "completed", 1), else_=0)
            ).label("done"),
            func.count(JobProduct.id).label("total"),
        )
        .join(Job, Job.client_id == Client.id)
        .join(JobProduct, JobProduct.job_id == Job.id)
        .group_by(Client.id, Client.company_name)
        .order_by(Client.company_name)
        .all()
    )

    return [
        ReceeProgressItem(
            client_name=company_name,
            done=int(done or 0),
            total=int(total or 0),
        )
        for company_name, done, total in rows
    ]


# ── 3. Activity feed ──────────────────────────────────────────────────────────

@router.get("/activity", response_model=List[ActivityItem])
def get_activity(
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    events = []

    # Recent jobs created
    recent_jobs = (
        db.query(Job, Client.company_name)
        .outerjoin(Client, Client.id == Job.client_id)
        .order_by(Job.created_at.desc())
        .limit(8)
        .all()
    )
    for job, client_name in recent_jobs:
        events.append({
            "sort_key": job.created_at or datetime.min,
            "type": "job_created" if job.status != "completed" else "job_completed",
            "description": (
                f"New job order created — {client_name or 'Unknown'}"
                if job.status != "completed"
                else f"Job completed — {client_name or 'Unknown'}"
            ),
            "user": job.measurement_person_name or "System",
            "timestamp": (job.created_at or datetime.utcnow()).isoformat() + "Z",
        })

    # Recent recee completions
    recent_recee = (
        db.query(ReceeMeasurement)
        .order_by(ReceeMeasurement.created_at.desc())
        .limit(8)
        .all()
    )
    for rm in recent_recee:
        jp = db.query(JobProduct).filter(JobProduct.id == rm.job_product_id).first()
        client_name = None
        recee_count = 0
        total_count = 0
        if jp:
            job = db.query(Job).filter(Job.id == jp.job_id).first()
            if job:
                client = db.query(Client).filter(Client.id == job.client_id).first()
                client_name = client.company_name if client else None
                total_count = (
                    db.query(func.count(JobProduct.id))
                    .filter(JobProduct.job_id == job.id)
                    .scalar()
                    or 0
                )
                recee_count = (
                    db.query(func.count(JobProduct.id))
                    .filter(
                        JobProduct.job_id == job.id,
                        JobProduct.recee_status == "completed",
                    )
                    .scalar()
                    or 0
                )
        events.append({
            "sort_key": rm.created_at or datetime.min,
            "type": "measurement_done",
            "description": f"Recee completed — {client_name or 'Unknown'} ({recee_count}/{total_count})",
            "user": rm.measured_by_mobile or "Worker",
            "timestamp": (rm.created_at or datetime.utcnow()).isoformat() + "Z",
        })

    # Recent installations
    recent_installs = (
        db.query(Installation)
        .order_by(Installation.created_at.desc())
        .limit(8)
        .all()
    )
    for inst in recent_installs:
        jp = db.query(JobProduct).filter(JobProduct.id == inst.job_product_id).first()
        client_name = None
        if jp:
            job = db.query(Job).filter(Job.id == jp.job_id).first()
            if job:
                client = db.query(Client).filter(Client.id == job.client_id).first()
                client_name = client.company_name if client else None
        events.append({
            "sort_key": inst.created_at or datetime.min,
            "type": "installation_done",
            "description": f"Installation completed — {client_name or 'Unknown'}",
            "user": inst.installed_by_mobile or "Worker",
            "timestamp": (inst.created_at or datetime.utcnow()).isoformat() + "Z",
        })

    # Sort all events newest first, take top 15, assign sequential IDs
    events.sort(key=lambda e: e["sort_key"], reverse=True)
    return [
        ActivityItem(
            id=idx + 1,
            type=e["type"],
            description=e["description"],
            user=e["user"],
            timestamp=e["timestamp"],
        )
        for idx, e in enumerate(events[:15])
    ]


# ── 4. Module stats ───────────────────────────────────────────────────────────

@router.get("/module-stats", response_model=ModuleStats)
def get_module_stats(
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    active_jobs = (
        db.query(func.count(Job.id)).filter(Job.status != "completed").scalar() or 0
    )
    store_count = db.query(func.count(Store.id)).scalar() or 0
    client_count = db.query(func.count(Client.id)).scalar() or 0

    pending_installs = (
        db.query(func.count(JobProduct.id))
        .filter(JobProduct.installation_status == "pending")
        .scalar()
        or 0
    )

    total_jobs = db.query(func.count(Job.id)).scalar() or 0

    return ModuleStats(
        purchase=ModuleStat(label="Open POs", count=0),
        inventory=ModuleStat(label="SKUs in stock", count=0),
        operations=ModuleStat(label="Active tasks", count=pending_installs),
        store=ModuleStat(label="Stores managed", count=store_count),
        job_orders=ModuleStat(label="Active jobs", count=active_jobs),
        design=ModuleStat(label="Pending designs", count=0),
        hr=ModuleStat(label="Employees", count=0),
        accounts=ModuleStat(label="Pending invoices", count=0),
        crm=ModuleStat(label="Active clients", count=client_count),
        reports=ModuleStat(label="Reports this month", count=0),
    )
