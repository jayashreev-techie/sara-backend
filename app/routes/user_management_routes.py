"""Company User Management routes (UserRole + CompanyUser)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.tenant import get_tenant_db as get_db
from app.models import CompanyUser, UserRole, Company
from app.auth import get_current_company

router = APIRouter(tags=["User Management"])
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =====================================================
# USER ROLES
# =====================================================
role_router = APIRouter(prefix="/api/user-roles")


@role_router.get("")
def list_roles(db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    rows = db.query(UserRole).all()
    return [{"id": r.id, "role_name": r.role_name} for r in rows]


@role_router.post("", status_code=201)
def create_role(payload: dict, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    if not payload.get("role_name"):
        raise HTTPException(status_code=422, detail="'role_name' is required")
    row = UserRole(role_name=payload["role_name"])
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "role_name": row.role_name}


@role_router.put("/{role_id}")
def update_role(role_id: int, payload: dict, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    row = db.query(UserRole).filter(UserRole.id == role_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Role not found")
    if "role_name" in payload:
        row.role_name = payload["role_name"]
    db.commit()
    db.refresh(row)
    return {"id": row.id, "role_name": row.role_name}


@role_router.delete("/{role_id}")
def delete_role(role_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    row = db.query(UserRole).filter(UserRole.id == role_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Role not found")
    db.delete(row)
    db.commit()
    return {"message": "Deleted"}


# =====================================================
# COMPANY USERS
# =====================================================
user_router = APIRouter(prefix="/api/company-users")


def _user_dict(u: CompanyUser) -> dict:
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "role_id": u.role_id,
        "role_name": u.role.role_name if u.role else None,
        "status": u.status,
        "created_at": str(u.created_at) if u.created_at else None,
    }


@user_router.get("")
def list_users(db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    return [_user_dict(u) for u in db.query(CompanyUser).all()]


@user_router.post("", status_code=201)
def create_user(payload: dict, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    for field in ("name", "email", "password"):
        if not payload.get(field):
            raise HTTPException(status_code=422, detail=f"'{field}' is required")

    existing = db.query(CompanyUser).filter(CompanyUser.email == payload["email"]).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already in use")

    u = CompanyUser(
        name=payload["name"],
        email=payload["email"],
        password_hash=_pwd.hash(payload["password"]),
        role_id=payload.get("role_id"),
        status=payload.get("status", 1),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return _user_dict(u)


@user_router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    u = db.query(CompanyUser).filter(CompanyUser.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_dict(u)


@user_router.put("/{user_id}")
def update_user(user_id: int, payload: dict, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    u = db.query(CompanyUser).filter(CompanyUser.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    if "name" in payload:
        u.name = payload["name"]
    if "email" in payload:
        u.email = payload["email"]
    if "password" in payload:
        u.password_hash = _pwd.hash(payload["password"])
    if "role_id" in payload:
        u.role_id = payload["role_id"]
    if "status" in payload:
        u.status = payload["status"]
    db.commit()
    db.refresh(u)
    return _user_dict(u)


@user_router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    u = db.query(CompanyUser).filter(CompanyUser.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(u)
    db.commit()
    return {"message": "Deleted"}


# Combine sub-routers
router.include_router(role_router)
router.include_router(user_router)
