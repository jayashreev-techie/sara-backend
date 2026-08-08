# Sara Fabrication — Mobile API (FastAPI)

Flutter mobile app ku backend API. Recee + Installation flows.

---

## 📁 Project Structure

```
sara_api/
├── main.py                    # FastAPI entry
├── requirements.txt
├── .env                       # Config (DB creds, JWT, OTP)
├── README.md
├── app/
│   ├── config.py              # Settings loader
│   ├── database.py            # SQLAlchemy session
│   ├── models.py              # DB tables
│   ├── schemas.py             # Pydantic request/response
│   ├── auth.py                # JWT helpers
│   ├── routes/
│   │   ├── auth_routes.py     # Login + OTP (Img 1, 2)
│   │   ├── recee_routes.py    # Recee flow (Img 3, 4, 5)
│   │   └── installation_routes.py  # Installation flow (Img 6)
│   └── utils/
│       ├── otp.py             # OTP generator + MSG91
│       └── file_upload.py     # Photo upload helper
└── uploads/                   # Photo storage
    ├── recee/
    └── installation/
```

---

## 🚀 Setup

### 1. Install dependencies
```bash
cd sara_api
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure `.env`
Open `.env` and update:
- **DB credentials** (web team kitta kekkanum)
- **JWT_SECRET** — random 32+ char string
- **OTP_MODE** — `test` for dev, `production` for live
- **MSG91_AUTH_KEY** — production OTP gateway

### 3. Run server
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Open Swagger docs
http://localhost:8000/docs — full interactive API testing

---

## 📱 Flutter Mobile Screens → API Mapping

### Authentication (Img 1, 2)
| Screen | Method | Endpoint |
|---|---|---|
| Login - Enter mobile | `POST` | `/api/auth/send-otp` |
| OTP Verification | `POST` | `/api/auth/verify-otp` → JWT token |
| Get current user | `GET` | `/api/auth/me` |
| Logout | `POST` | `/api/auth/logout` |

### Recee Flow (Img 3, 4, 5)
| Screen | Method | Endpoint |
|---|---|---|
| Clients home (CUB 15/60) | `GET` | `/api/recee/clients` |
| Stores list (Store 1-6) | `GET` | `/api/recee/clients/{client_id}/stores` |
| SAVE measurement + photo | `POST` | `/api/recee/measurements` |
| Branch-113 history view | `GET` | `/api/recee/measurements?store_id=...` |
| Single measurement | `GET` | `/api/recee/measurements/{id}` |

### Installation Flow (Img 6)
| Screen | Method | Endpoint |
|---|---|---|
| Home - Clients | `GET` | `/api/installation/clients` |
| Stores list (recee-completed only) | `GET` | `/api/installation/clients/{client_id}/stores` |
| Get recee photo (auto-fill) | `GET` | `/api/installation/job-products/{id}/recee-info` |
| SAVE installation + photos | `POST` | `/api/installation/submit` |
| Installation history | `GET` | `/api/installation/history` |

---

## 🔐 Authentication Flow

1. Mobile app sends 10-digit number → `POST /api/auth/send-otp`
2. Backend checks if mobile exists in `jobs.measurement_person_mobile`
3. If yes → OTP generated, sent via SMS (or returned in test mode)
4. App sends OTP back → `POST /api/auth/verify-otp`
5. Backend returns `access_token` (JWT, valid 30 days)
6. App stores token, sends in **every** subsequent request:
   ```
   Authorization: Bearer <token>
   ```

---

## 📸 Photo Upload Format

All measurement/installation submits use `multipart/form-data`:

### Flutter example (using `dio` or `http`):
```dart
var request = http.MultipartRequest(
  'POST',
  Uri.parse('http://api.sara.com/api/recee/measurements'),
);
request.headers['Authorization'] = 'Bearer $token';
request.fields['job_product_id'] = '5';
request.fields['width_inch'] = '48';
request.fields['height_inch'] = '72';
request.fields['material'] = 'Glass';
request.files.add(await http.MultipartFile.fromPath('photo', imagePath));
final response = await request.send();
```

---

## 🔑 Key Business Logic

1. **Auth link** — `jobs.measurement_person_mobile` = mobile login number. Worker sees only their assigned jobs.

2. **Recee → Installation gate** — A store appears in Installation flow **only after** its `recee_status = 'completed'`.

3. **Photo carry-forward** — Installation form's "Recee" section auto-pulls the photo from earlier recee submission. Worker uploads only Design + Installation photos.

4. **Progress counter** — `15/60` = `completed_count / total_count` of `job_products` per client.

---

## ⚠️ Web Team Confirmation Needed

Naan probable column names use panren. Real DB schema confirm panni `app/models.py` adjust pannunga:

1. `clients` table — `company_name`-aa illa `client_name`-aa?
2. `jobs` table — `measurement_person_mobile` exact column name?
3. Photo storage — server filesystem (`/uploads/`) ok-aa, illa S3?
4. OTP gateway — MSG91 account iruka, illa other provider?
5. `job_products` la W×H — admin estimate-aa illa final values storage?
6. Multiple recee entries (re-survey) per store allow pannanuma?

---

## 🧪 Testing in TEST mode

`.env` la `OTP_MODE=test` set pannina:
- `POST /api/auth/send-otp` response la OTP return aagum
- SMS gateway venam — direct test panna mudiyum

```bash
curl -X POST http://localhost:8000/api/auth/send-otp \
  -H "Content-Type: application/json" \
  -d '{"mobile": "9876543210"}'

# Response: {"success": true, "otp": "123456", ...}
```

---

## 📦 Production Deployment

1. Set `OTP_MODE=production` + MSG91 credentials
2. Use a process manager (systemd / pm2 / supervisor)
3. Run behind nginx with HTTPS
4. Restrict CORS origins in `main.py`
5. Use strong `JWT_SECRET` (64+ chars, random)

```bash
# Production run
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```
