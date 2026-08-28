# Developer reference

[Back to the merchant guide](../README.md). Run commands below from the repository root.

## Architecture

```text
                 ┌─────────────────────┐
                 │    React Frontends  │
                 │ Console + /store UI │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │      FastAPI        │
                 │     Backend API     │
                 └──────────┬──────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
      ┌─────────────────┐       ┌─────────────────┐
      │   ML Risk Model │       │    Gemini AI    │
      │     XGBoost     │       │ Investigation   │
      └─────────────────┘       └─────────────────┘
```

The backend owns prediction, model training, threshold selection, persistence,
evidence storage, and Gemini calls. The frontend communicates with it over JSON
HTTP requests. SQLite stores cases and review history locally; uploaded evidence
is stored on disk.

---


## Input and Training Data Schema

Prediction requests use 14 features. Training CSVs contain those features plus
the label `is_abuse`.

| Column | Type | Validation |
|---|---:|---|
| `customer_age_days` | integer | 0 or greater |
| `previous_orders` | integer | 1 or greater |
| `previous_returns` | integer | 0 to `previous_orders` |
| `previous_refunds` | integer | 0 to `previous_orders` |
| `return_ratio` | number | `previous_returns / previous_orders`, tolerance 0.001 |
| `refund_ratio` | number | `previous_refunds / previous_orders`, tolerance 0.001 |
| `order_value` | number | 0 or greater |
| `days_since_purchase` | integer | 0 or greater |
| `account_count` | integer | 1 or greater |
| `address_reuse_count` | integer | 0 or greater |
| `device_reuse_count` | integer | 0 or greater |
| `payment_failures` | integer | 0 or greater |
| `claim_type` | string | non-empty |
| `product_category` | string | non-empty |
| `is_abuse` | integer | training only: `0` legitimate, `1` abuse |

Training data must contain exactly these 15 columns, no blank cells, at least 20
rows, both labels, and at least two rows per label. Categorical values do not
need a fixed vocabulary; unseen values are handled by the fitted one-hot encoder.

The API applies the same history and ratio consistency rules to prediction and
case-creation requests.

---

## API Reference

The full request and response schemas are available in Swagger at `/docs`.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | API name, version, and status |
| `GET` | `/health` | Service and model health |
| `POST` | `/predict` | Score a case without saving it |
| `POST` | `/cases` | Score and persist a case |
| `GET` | `/cases` | List cases |
| `GET` | `/cases/{case_id}` | Read one case |
| `DELETE` | `/cases/{case_id}` | Permanently delete a case and its related review data |
| `GET` | `/cases/{case_id}/explanation` | Get XGBoost feature contributions |
| `POST` | `/cases/{case_id}/investigate` | Run the Gemini investigation |
| `PATCH` | `/cases/{case_id}/decision` | Record `APPROVED`, `REJECTED`, or `ESCALATED` |
| `GET` | `/cases/{case_id}/review` | Read evidence and audit events |
| `POST` | `/cases/{case_id}/evidence` | Upload raw evidence with `Content-Type` and `X-Filename` headers |
| `GET` | `/cases/{case_id}/evidence/{evidence_id}` | Download evidence |
| `POST` | `/cases/{case_id}/evidence/{evidence_id}/verify` | Analyze the actual PDF/image against the claim |
| `POST` | `/cases/{case_id}/outcome` | Record a verified outcome |
| `GET` | `/feedback/summary` | Get review, disagreement, and loss estimates |
| `GET` | `/monitoring/patterns?source=all` | Continuous shared-signal analysis across all recorded requests |
| `GET` | `/monitoring/traffic?source=all&scale=minute` | Traffic buckets, volume flags, and intake-pause status |
| `POST` | `/monitoring/traffic/research` | Research `start`/`end` timestamps and `source` on merchant request |
| `POST` | `/monitoring/intake/pauses` | Confirm `scope`, `duration_minutes`, and `reason` to refuse new requests |
| `POST` | `/monitoring/intake/pauses/{id}/resume` | Resume an intake pause early |
| `POST` | `/monitoring/sentinel/demo` | Send `count` test requests (`ip`, `device`, `account`, `location`, `ring`, `normal`) |
| `GET` | `/monitoring/sentinel?is_test=false` | Legacy velocity/approval-hold status |
| `PATCH` | `/monitoring/sentinel/settings` | Legacy velocity settings, unused by the two new pages |
| `POST` | `/monitoring/sentinel/restrictions` | Legacy approval hold |
| `POST` | `/monitoring/sentinel/restrictions/{id}/resume` | Resume a legacy approval hold |
| `GET` | `/model/status` | Read model provenance, metrics, policy, and cost curve |
| `GET` | `/model/training-schema` | Read required CSV columns and label rules |
| `POST` | `/model/train` | Validate, train, and activate a CSV model |
| `PATCH` | `/model/cost-settings` | Recalculate thresholds for new FP/FN costs |

Example prediction request:

```powershell
$case = @{
  customer_age_days = 900
  previous_orders = 24
  previous_returns = 1
  previous_refunds = 0
  return_ratio = 1 / 24
  refund_ratio = 0
  order_value = 1299
  days_since_purchase = 12
  account_count = 1
  address_reuse_count = 1
  device_reuse_count = 1
  payment_failures = 0
  claim_type = "changed_mind"
  product_category = "fashion"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/predict `
  -Method Post `
  -ContentType "application/json" `
  -Body $case
```

---


## Validation and Development Commands

Run backend workflow tests from the repository root with the model generated and
`GEMINI_API_KEY` configured:

```powershell
python -m unittest discover -s tests -v
```

Run local prediction and Gemini smoke checks:

```powershell
python src/predict.py
python src/test_gemini.py
```

Validate the frontend:

```powershell
cd frontend
npm run lint
npm run build
npm run preview
```

`npm run preview` serves the production build locally; keep the backend running
on port 8000 when exercising API-backed screens.

---

## Generated Files and Local State

| Path | Purpose | Git behavior |
|---|---|---|
| `.env` | Gemini credentials | ignored |
| `data/raw/return_abuse_dataset.csv` | generated synthetic baseline data | ignored |
| `data/demo/` | reproducible demo assets | tracked |
| `data/evidence/{case_id}/` | uploaded review evidence | ignored |
| `models/risk_model.pkl` | active model, metadata, metrics, and policy | ignored |
| `risk_manager.db` | local SQLite cases and audit data | local application state |

Back up `risk_manager.db`, `models/risk_model.pkl`, and `data/evidence/` together
if you need to preserve a working local environment. The database stores evidence
metadata, while the uploaded files themselves live under `data/evidence/`.

---


## Production Considerations

This repository is a local demonstration baseline. Before production use:

- replace synthetic data with consented, anonymized, representative merchant
  history and evaluate on a later-time holdout set;
- move secrets to a managed secret store and add authentication and authorization;
- replace local SQLite and evidence storage with backed-up, access-controlled
  services;
- add malware scanning, retention rules, and encryption for uploaded evidence;
- run training as a background job and version model artifacts and policies;
- add rate limits, structured monitoring, drift checks, fairness review, and a
  rollback path;
- retain human review for consequential decisions and validate cost assumptions
  against real operational outcomes.

