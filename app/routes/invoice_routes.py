"""Finance / Invoice routes."""
import re
from datetime import date as date_type
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.tenant import get_tenant_db as get_db
from app.models import Invoice, InvoiceItem, Client, Company
from app.auth import get_current_company

router = APIRouter(prefix="/api/invoices", tags=["Finance & Invoices"])

GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]$")


def _invoice_dict(inv: Invoice) -> dict:
    return {
        "id": inv.id,
        "invoice_no": inv.invoice_no,
        "client_id": inv.client_id,
        "client_name": inv.client.company_name if inv.client else None,
        "invoice_date": str(inv.invoice_date) if inv.invoice_date else None,
        "buyer_gstin": inv.buyer_gstin,
        "company_gstin": inv.company_gstin,
        "place_of_supply": inv.place_of_supply,
        "subtotal": inv.subtotal,
        "cgst": inv.cgst,
        "sgst": inv.sgst,
        "igst": inv.igst,
        "total": inv.total,
        "created_at": str(inv.created_at) if inv.created_at else None,
        "items": [_item_dict(i) for i in inv.items],
    }


def _item_dict(item: InvoiceItem) -> dict:
    return {
        "id": item.id,
        "description": item.description,
        "hsn_code": item.hsn_code,
        "qty": item.qty,
        "rate": item.rate,
        "gst_rate": item.gst_rate,
        "taxable_value": item.taxable_value,
        "cgst": item.cgst,
        "sgst": item.sgst,
        "igst": item.igst,
        "total": item.total,
    }


def _calc_gst(taxable: float, gst_rate: float, same_state: bool):
    gst_amt = (taxable * gst_rate) / 100
    if same_state:
        return gst_amt / 2, gst_amt / 2, 0.0
    return 0.0, 0.0, gst_amt


@router.get("")
def list_invoices(db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    rows = db.query(Invoice).order_by(Invoice.id.desc()).all()
    return [_invoice_dict(inv) for inv in rows]


@router.get("/{invoice_id}")
def get_invoice(invoice_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _invoice_dict(inv)


@router.post("", status_code=201)
def create_invoice(
    payload: dict,
    db: Session = Depends(get_db),
    _: Company = Depends(get_current_company),
):
    """
    payload = {
      "client_id": 1,
      "invoice_date": "2026-01-15",
      "company_gstin": "29ABCDE1234F1Z5",
      "buyer_gstin": "29XYZPQ9876G1Z3",
      "place_of_supply": "Karnataka",
      "items": [
        {"description": "Flex Banner", "hsn_code": "4911", "qty": 10,
         "rate": 150.0, "gst_rate": 18}
      ]
    }
    """
    required = ("client_id", "invoice_date", "company_gstin", "buyer_gstin", "items")
    for field in required:
        if not payload.get(field):
            raise HTTPException(status_code=422, detail=f"'{field}' is required")

    buyer_gstin = payload["buyer_gstin"].upper().strip()
    company_gstin = payload["company_gstin"].upper().strip()

    if not GSTIN_PATTERN.match(buyer_gstin):
        raise HTTPException(status_code=400, detail="Invalid Buyer GSTIN format")
    if not GSTIN_PATTERN.match(company_gstin):
        raise HTTPException(status_code=400, detail="Invalid Company GSTIN format")

    same_state = buyer_gstin[:2] == company_gstin[:2]

    inv = Invoice(
        client_id=payload["client_id"],
        invoice_date=payload["invoice_date"],
        buyer_gstin=buyer_gstin,
        company_gstin=company_gstin,
        place_of_supply=payload.get("place_of_supply", ""),
        subtotal=0, cgst=0, sgst=0, igst=0, total=0,
    )
    db.add(inv)
    db.flush()

    inv.invoice_no = f"INV-{str(inv.id).zfill(5)}"

    subtotal = cgst_total = sgst_total = igst_total = 0.0

    for item in payload["items"]:
        taxable = item["qty"] * item["rate"]
        cgst, sgst, igst = _calc_gst(taxable, item.get("gst_rate", 18), same_state)
        line_total = taxable + cgst + sgst + igst

        subtotal += taxable
        cgst_total += cgst
        sgst_total += sgst
        igst_total += igst

        db.add(InvoiceItem(
            invoice_id=inv.id,
            description=item.get("description", ""),
            hsn_code=item.get("hsn_code", ""),
            qty=item["qty"],
            rate=item["rate"],
            gst_rate=item.get("gst_rate", 18),
            taxable_value=taxable,
            cgst=cgst,
            sgst=sgst,
            igst=igst,
            total=line_total,
        ))

    inv.subtotal = subtotal
    inv.cgst = cgst_total
    inv.sgst = sgst_total
    inv.igst = igst_total
    inv.total = subtotal + cgst_total + sgst_total + igst_total

    db.commit()
    db.refresh(inv)
    return _invoice_dict(inv)


@router.delete("/{invoice_id}")
def delete_invoice(invoice_id: int, db: Session = Depends(get_db), _: Company = Depends(get_current_company)):
    inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    db.delete(inv)
    db.commit()
    return {"message": "Deleted"}
