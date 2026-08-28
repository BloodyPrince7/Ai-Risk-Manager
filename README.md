# AI Risk Manager

AI-powered return abuse detection and risk management system for e-commerce.

The system analyzes customer behavior and return-related signals to estimate the probability of return abuse and recommends an appropriate action.

It combines:

- Machine Learning for risk prediction
- FastAPI for the backend API
- React for the merchant dashboard
- Gemini AI for case investigation and explainability

---

## Prerequisites

- Python 3.11 or newer
- Node.js 20.19+ or 22.12+ and npm (required by Vite 8)
- A Gemini API key

> [!IMPORTANT]
> Run backend and ML commands from the repository root. The SQLite database and
> model loader currently use paths relative to the working directory.

## Quick Start

### 1. Set up the Python environment

```powershell
git clone <repository-url>
cd Ai-Risk-Manager

py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks virtual-environment activation, run
`Set-ExecutionPolicy -Scope Process Bypass` in that terminal and activate it
again. On macOS or Linux, activate with `source .venv/bin/activate` and replace
`py` with `python3` where needed.

### 2. Configure Gemini

```powershell
Copy-Item .env.example .env
```

Open `.env` and replace the placeholder:

```dotenv
GEMINI_API_KEY=your_gemini_api_key_here
```

The key is required when the backend starts because the Gemini investigator is
loaded with the API. Never commit `.env`; it is excluded by `.gitignore`.

Low-risk returns use a one-hour review window before the system finalizes their
approval. Keep the production value at `3600`, or use a shorter value such as
`60` for a local one-minute demo:

```dotenv
AUTO_APPROVAL_DELAY_SECONDS=3600
```

### 3. Generate the baseline model

Generated datasets and model artifacts are intentionally not committed. Create
the raw-data directory, generate the synthetic dataset, and train the model:

```powershell
New-Item -ItemType Directory -Force data/raw | Out-Null
python src/data_generation.py
python src/train.py
```

This creates `data/raw/return_abuse_dataset.csv` and
`models/risk_model.pkl`. Training uses a fixed stratified 80/20 split and saves
the preprocessing pipeline, XGBoost model, held-out metrics, cost analysis, and
routing thresholds in one artifact.

### 4. Start the backend

From the repository root, in the activated Python environment:

```powershell
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Useful URLs:

- API: <http://127.0.0.1:8000>
- Health check: <http://127.0.0.1:8000/health>
- Interactive API docs: <http://127.0.0.1:8000/docs>
- OpenAPI schema: <http://127.0.0.1:8000/openapi.json>

The SQLite tables are created automatically in `risk_manager.db` at startup.

### 5. Start the dashboard

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173> for the AI Risk Manager dashboard and
<http://localhost:5173/store> for the separate ecommerce order page. Both pages expect the API at
`http://127.0.0.1:8000`; this value is currently defined by `API_URL` in
`frontend/src/App.jsx`.

---

## Features

### Risk Prediction

The ML model analyzes signals such as:

- Previous returns
- Previous refunds
- Return ratio
- Refund ratio
- Account reuse
- Address reuse
- Device reuse
- Payment failures
- Customer account age
- Order value
- Claim type
- Product category

The model produces an abuse probability and risk level.

### Risk-Based Decisions

Cases are classified into:

| Risk Level | Action |
|---|---|
| LOW | Auto Approve |
| MEDIUM | Request Evidence |
| HIGH | Manual Review |

The active low/high boundaries are selected from the held-out test set using
the configured false-positive and false-negative costs. They are saved inside
the model artifact and used by both the API and dashboard.

### Merchant Dashboard

The React dashboard provides:

- Total cases
- High-risk cases
- Medium-risk cases
- Low-risk cases
- Recent risk cases
- Risk scores
- Case investigation panel
- Model metrics
- Decision routing
- A test-case form that scores a return through the active model
- Held-out confusion matrix and false-positive cost
- Clear synthetic-baseline or merchant-trained provenance label
- Approve, reject, and escalate controls for human review
- Approve-all, review-all, and AI-policy cost comparison
- Configurable false-positive and false-negative costs
- Model-native XGBoost feature contributions
- Evidence uploads, verified outcomes, and an audit trail
- Multimodal AI verification of uploaded PDFs and images
- A persisted one-hour auto-approval window for low-risk returns
- A separate ecommerce order page with live countdown and override controls
- Live risk-distribution donut and score-band histogram
- Held-out precision/recall/F1/accuracy performance bars
- Interactive cost-versus-threshold curve with the selected policy highlighted

### Custom Model Training

Merchants can open **Settings** to download a CSV template, review the required
schema, and upload labeled historical cases. The backend validates the dataset,
uses a stratified 80/20 train-test split, reports evaluation metrics, and only
replaces the active model after training completes successfully.

The CSV requires the same 14 prediction features plus `is_abuse`, where `0`
means legitimate and `1` means confirmed abuse. At least 20 complete rows and
examples of both labels are required.

Counts must be internally consistent: returns and refunds cannot exceed orders,
and both ratio columns must equal their corresponding count divided by orders.

### Reproducible Demo

Generate the fixed-seed demo dataset and three walkthrough scenarios:

```powershell
py src/prepare_demo.py
```

The files are written to `data/demo/`. See `data/demo/README.md` for the
recommended walkthrough.

To regenerate the full synthetic baseline and train its model artifact:

```powershell
py src/data_generation.py
py src/train.py
```

The saved artifact includes model provenance, held-out metrics, confusion
matrix, cost assumptions, and the selected routing thresholds.

### Gemini AI Investigation

For individual cases, Gemini can analyze the available risk signals and provide:

- Risk summary
- Important risk factors
- Evidence that should be checked
- Recommended action
- AI confidence

This gives merchants an explanation instead of only showing a numerical risk score.

---

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

## Using the Application

### Score and review a case

1. Open **Test a case** in the dashboard.
2. Enter the customer, order, return-history, identity-reuse, claim, and product
   signals.
3. Submit the form to create a persisted case and receive its abuse probability,
   risk level, recommended action, and feature contributions.
4. Open the case to upload evidence, run the Gemini investigation, and record an
   **Approved**, **Rejected**, or **Escalated** merchant decision.
5. Record a verified outcome when the real result is known. The review panel
   keeps model output, evidence, human decisions, and outcomes in its audit trail.

Evidence uploads must be PDF, JPEG, PNG, or WebP files no larger than 5 MB.
Select **Verify** beside an upload to make Gemini inspect the actual file. The
result separates visible facts, inconsistencies, missing authoritative records,
claim consistency, limitations, recommended action, and confidence. File-only AI
analysis never claims that a document is definitively authentic.

### Review orders like a commerce storefront

Open <http://localhost:5173/store> for a shopping-style history that is separate
from the AI Risk Manager dashboard. Every order card clearly shows:

- a scheduled refund and live payment countdown for low-risk returns;
- the final auto-approved result after the countdown expires;
- a reviewer-approved result when **Approve now** is selected;
- a rejected result when **Reject return** is selected.

Use the search box to find an order by reference, product, claim, category, or
status. Combine it with status, product-category, and ML risk-level filters.
Each card also has a confirmed **Delete** action that permanently removes the
case, its evidence files, verifications, and audit events.

During the countdown, **Approve now** releases the return immediately and
**Reject return** stops it. After the deadline, the backend finalizes the case as
`AUTO_APPROVED`; the decision can no longer be changed. The storefront polls the
same API every three seconds, so dashboard and order history stay synchronized.

The **Risk Cases** table is an active work queue. Manually approved and rejected
cases leave the queue immediately. System auto-approved cases also leave the
queue and remain visible in the storefront; escalated cases stay until a final
decision is recorded.

### Timed decision workflow

Creating a case persists the model policy as an order state:

| Model policy | Persisted state |
|---|---|
| `AUTO_APPROVE` | `PENDING_AUTO_APPROVAL`, then `AUTO_APPROVED` after the deadline |
| `REQUEST_EVIDENCE` | `EVIDENCE_REQUIRED` |
| `MANUAL_REVIEW` | `MANUAL_REVIEW` |

The deadline is stored with the case rather than held in browser memory. Any
`GET /cases` request finalizes expired low-risk windows, records an audit event,
and returns the new state. This project intentionally does not call an external
payment provider; the payment state is a demo workflow stored in SQLite.

### Train a merchant model

1. Open **Settings**.
2. Download the CSV template or use `data/demo/demo_training.csv`.
3. Upload a labeled CSV. Files must be UTF-8 CSV and no larger than 10 MB.
4. Review the held-out metrics and cost comparison after training succeeds.

Training is synchronous and only one training request can run at a time. The
active artifact is replaced atomically after validation and training complete;
failed uploads leave the existing model active.

### Tune business costs

In **Settings**, set the estimated cost of a false positive (a legitimate case
incorrectly challenged) and false negative (abuse incorrectly approved). The
backend recalculates the minimum-cost threshold from stored held-out predictions
without retraining the model, then saves the updated policy in the artifact.

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

## Demo Workflow

Generate the deterministic demo pack at any time:

```powershell
python src/prepare_demo.py
```

It uses seed `20260826` and writes:

- `data/demo/demo_training.csv`: 500 labeled training rows
- `data/demo/demo_cases.json`: low-, medium-, and high-risk walkthrough cases

See [`data/demo/README.md`](data/demo/README.md) for the complete presentation
flow and honest-use guidance. Demo data is synthetic and demonstrates the
workflow; it is not evidence of production accuracy.

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

## Troubleshooting

- **`Trained model not found`** — run the data-generation and training commands
  from the repository root before starting the API.
- **`GEMINI_API_KEY not found`** — create `.env`, add a valid key, and restart the
  backend. Avoid quotes or trailing spaces around the value.
- **Prediction returns HTTP 422** — ensure return/refund counts do not exceed
  order count and both ratios exactly match their corresponding count divided by
  orders within 0.001.
- **Dashboard cannot reach the API** — confirm `/health` works on port 8000 and
  that the dashboard is running on port 5173. Those two frontend origins are the
  CORS origins currently allowed by the backend.
- **CSV training returns HTTP 415 or 422** — upload a UTF-8 CSV with `text/csv`,
  exactly the required columns, no blanks, and valid labels and ratios.
- **Port already in use** — stop the conflicting process. If you choose another
  API port, update `API_URL` in `frontend/src/App.jsx`; if you choose another
  frontend origin, also update the API CORS configuration in `api/main.py`.

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
