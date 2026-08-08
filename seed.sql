USE sara_fabrication;

INSERT INTO clients (company_name, contact_person_name, sales_person_name, mobile, gst_number)
VALUES ('City Union Bank', 'Ramesh Kumar', 'Suresh', '9123456789', '33ABCDE1234F1Z5');

INSERT INTO product_types (product_type, hsn_code, price)
VALUES ('Glass Signage', '7610', 1500.00),
       ('ACP Board', '7606', 800.00);

INSERT INTO locations (district, location_name)
VALUES ('Chennai', 'T Nagar'),
       ('Chennai', 'Anna Nagar');

INSERT INTO stores (store_name, store_address, store_mobile, location_id, client_id)
VALUES ('Branch-113 T Nagar', '123 Pondy Bazaar, T Nagar, Chennai', '9876500001', 1, 1),
       ('Branch-114 Anna Nagar', '45 2nd Ave, Anna Nagar, Chennai', '9876500002', 2, 1);

INSERT INTO jobs (job_creation_date, client_id, client_contact_person_name, client_contact_person_mobile,
                  po_number, po_date, measurement_date, measurement_person_name, measurement_person_mobile, status)
VALUES (CURDATE(), 1, 'Ramesh Kumar', '9123456789',
        'PO-2026-001', CURDATE(), CURDATE(), 'Test Worker', '9876543210', 'pending');

INSERT INTO job_products (job_id, store_id, location_id, product_type_id, total_qty,
                          width_inch, height_inch, recee_status, installation_status)
VALUES (1, 1, 1, 1, 1, 48.0, 72.0, 'pending', 'pending'),
       (1, 2, 2, 2, 2, 36.0, 60.0, 'pending', 'pending');

SELECT (SELECT COUNT(*) FROM clients) AS clients,
       (SELECT COUNT(*) FROM jobs) AS jobs,
       (SELECT COUNT(*) FROM job_products) AS job_products,
       (SELECT COUNT(*) FROM stores) AS stores;
