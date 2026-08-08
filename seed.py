"""Seed test data for Sara API (idempotent — fills missing rows)."""
from datetime import date

from app.database import SessionLocal
from app.models import Client, Job, JobProduct, Location, ProductType, Store

db = SessionLocal()
try:
    client = db.query(Client).first()
    if not client:
        client = Client(
            company_name="City Union Bank",
            contact_person_name="Ramesh Kumar",
            sales_person_name="Suresh",
            mobile="9123456789",
            gst_number="33ABCDE1234F1Z5",
        )
        db.add(client)
        db.flush()
        print(f"+ Client created: id={client.id}")

    if db.query(ProductType).count() == 0:
        db.add_all([
            ProductType(product_type="Glass Signage", hsn_code="7610", price=1500.00),
            ProductType(product_type="ACP Board", hsn_code="7606", price=800.00),
        ])
        db.flush()
        print("+ ProductTypes created")
    pt1, pt2 = db.query(ProductType).order_by(ProductType.id).limit(2).all()

    if db.query(Location).count() == 0:
        db.add_all([
            Location(district="Chennai", location_name="T Nagar"),
            Location(district="Chennai", location_name="Anna Nagar"),
        ])
        db.flush()
        print("+ Locations created")
    loc1, loc2 = db.query(Location).order_by(Location.id).limit(2).all()

    if db.query(Store).count() == 0:
        db.add_all([
            Store(
                store_name="Branch-113 T Nagar",
                store_address="123 Pondy Bazaar, T Nagar, Chennai",
                store_mobile="9876500001",
                location_id=loc1.id,
                client_id=client.id,
            ),
            Store(
                store_name="Branch-114 Anna Nagar",
                store_address="45 2nd Ave, Anna Nagar, Chennai",
                store_mobile="9876500002",
                location_id=loc2.id,
                client_id=client.id,
            ),
        ])
        db.flush()
        print("+ Stores created")
    store1, store2 = db.query(Store).order_by(Store.id).limit(2).all()

    job = db.query(Job).first()
    if not job:
        job = Job(
            job_creation_date=date.today(),
            client_id=client.id,
            client_contact_person_name="Ramesh Kumar",
            client_contact_person_mobile="9123456789",
            po_number="PO-2026-001",
            po_date=date.today(),
            measurement_date=date.today(),
            measurement_person_name="Test Worker",
            measurement_person_mobile="9876543210",
            status="pending",
        )
        db.add(job)
        db.flush()
        print(f"+ Job created: id={job.id}, mobile=9876543210")

    if db.query(JobProduct).count() == 0:
        db.add_all([
            JobProduct(
                job_id=job.id, store_id=store1.id, location_id=loc1.id,
                product_type_id=pt1.id, total_qty=1,
                width_inch=48.0, height_inch=72.0,
                recee_status="pending", installation_status="pending",
            ),
            JobProduct(
                job_id=job.id, store_id=store2.id, location_id=loc2.id,
                product_type_id=pt2.id, total_qty=2,
                width_inch=36.0, height_inch=60.0,
                recee_status="pending", installation_status="pending",
            ),
        ])
        print("+ JobProducts created")

    db.commit()
    print()
    print("=== Final Counts ===")
    print(f"Clients:      {db.query(Client).count()}")
    print(f"ProductTypes: {db.query(ProductType).count()}")
    print(f"Locations:    {db.query(Location).count()}")
    print(f"Stores:       {db.query(Store).count()}")
    print(f"Jobs:         {db.query(Job).count()}")
    print(f"JobProducts:  {db.query(JobProduct).count()}")
    print()
    print("Login mobile: 9876543210 (test mode OTP returned in response)")
finally:
    db.close()
