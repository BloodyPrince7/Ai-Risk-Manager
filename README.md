# AI Risk Manager

A merchant dashboard for understanding return requests, spotting shared customer details, and deciding when to investigate or pause new requests.

**You stay in control.** A busy graph or a matching IP address does not automatically block a customer.

> This project is a local demonstration. Test requests are clearly labelled, identity details are supplied with requests, and no real payment gateway is connected.

## Which page should I use?

| Page | What it helps you do |
|---|---|
| **Overview** | See the return queue and overall risk summary. |
| **Request Patterns** | Find requests that share a customer account, device, IP address, location, or payment/address reference. |
| **Request Traffic** | Watch request counts over time, check a selected period, and optionally pause new requests. |
| **Risk Cases** | Review individual returns, upload evidence, and approve, reject, or escalate a case. |
| **Analytics** | Explore risk scores and model evaluation results. |
| **Settings** | Train a model on your historical data and adjust review costs. |
| **Order history** (`/store`) | View existing returns, refund countdowns, and final decisions. |

## Try the demo

Start the app using the instructions below, then:

1. Open **Request Traffic**. Keep **Customer + test requests** selected.
2. Under **Try a demo**, send **10 test requests**.
3. Watch the current graph bar grow. Click the bar, then **Check these requests**.
4. Read the matching details. Open a group to see its requests.
5. Visit **Request Patterns** to see the same connections being checked automatically.
6. Back on **Request Traffic**, choose **Review pause**, check the scope and duration, and confirm.
7. Send more test requests. They are blocked while paused, but still counted on the graph.
8. Select **Resume requests**, confirm, and send another test request.

You can also create one custom test with your own sample customer, device, IP, and location. Test records are saved locally. They are not real customer activity.

## Understand the two monitoring pages

### Request Patterns: “Are these requests connected?”

This page compares all recorded requests every five seconds. A match appears as soon as **two requests share a detail**; it does not wait for a traffic spike.

For example, two different accounts might submit returns using the same device. You can open the device group to inspect both requests and any other details they share.

- Use **Shared detail** to look at just devices, IPs, locations, or another detail.
- One request can appear in several groups.
- Customer and test requests are never matched to each other.
- Missing details cannot be compared.
- A shared city, family device, or Wi-Fi network can be completely legitimate.

The page includes **What do these details mean?** for a plain-language explanation of each field.

### Request Traffic: “Is an unusual number of requests arriving?”

Choose the last hour, six hours, or day. Each bar shows the number of requests received in that period. Customer and test requests use different colours.

1. **Watch requests.** Test requests appear on the graph immediately after submission; the page refreshes every five seconds.
2. **Check a busy period.** Click a bar and select **Check these requests**. You can also check the entire chart.
3. **Pause only if needed.** Reviewing a period does not start a pause. That is a separate decision.

Orange outlines flag periods with at least ten requests and at least three times the average of up to twelve earlier periods. With no earlier traffic, this is only a high-volume flag. The newest bar is still growing. See **How are busy periods highlighted?** on the page.

A request check compares the recorded details locally. It explains similarities; it does not establish fraud or run an external AI investigation.

### What happens when I pause new requests?

| During a pause | What happens |
|---|---|
| New matching submissions | Temporarily blocked; no return case is created. |
| The traffic graph | Still counts blocked attempts so you can see whether requests keep arriving. |
| Existing returns and refunds | Continue as before; their decisions are not changed by this pause. |
| Reviewing cases or checking patterns | Remains available. |
| When the timer ends | New requests can be accepted again. |
| Requests that were blocked | Must be submitted again; they are not automatically retried. |

Choose **customer requests**, **test requests**, or **both**, and a duration of **5, 15, 30, or 60 minutes**. Every pause requires confirmation. You can end it early. If multiple pauses apply, all must end before the affected requests are accepted.

## Run locally

### Requirements

- Python 3.11 or newer.
- Node.js 20.19+ or 22.12+ and npm.
- A Gemini API key. The backend currently requires it at startup, even though the two monitoring pages do not call Gemini.

Run these commands from the project folder. They use PowerShell and do not require activating the virtual environment.

### 1. Install dependencies

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm --prefix frontend install
```

### 2. Add your configuration

If you do not already have an `.env` file:

```powershell
Copy-Item .env.example .env
```

Set these values in `.env`:

```dotenv
GEMINI_API_KEY=your_key_here
AUTO_APPROVAL_DELAY_SECONDS=3600
```

Keep your key private. The approval delay controls existing low-risk return decisions, not the incoming-request pause. For a short local countdown demo, you may set it to `60`.

### 3. Create the initial model

**Skip this if you already have a model you want to keep.** Training replaces `models/risk_model.pkl`.

```powershell
New-Item -ItemType Directory -Force data/raw | Out-Null
.\.venv\Scripts\python.exe src/data_generation.py
.\.venv\Scripts\python.exe src/train.py
```

This creates a baseline using synthetic data. Its evaluation results are not evidence of accuracy on real customer traffic.

### 4. Start the API

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

### 5. Start the dashboard

In a second terminal, from the project folder:

```powershell
npm --prefix frontend run dev
```

Open the [dashboard](http://localhost:5173), [Request Patterns](http://localhost:5173/patterns), [Request Traffic](http://localhost:5173/traffic), or [order history](http://localhost:5173/store).

On macOS/Linux, use `python3 -m venv .venv` and `.venv/bin/python` instead of the Windows Python path.

## Review a return

Open **Risk Cases**, select a case, and review its model recommendation and customer details. You can:

- Upload a PDF, JPEG, PNG, or WebP as evidence, up to 5 MB.
- Ask Gemini to investigate the case or inspect an uploaded file.
- Approve, reject, or escalate the return.
- Record the verified outcome when you know what happened.

Low-risk returns use a saved approval countdown. Once automatically approved, that decision cannot be reopened. An incoming-request pause does not stop this countdown.

In **Settings**, you can upload historical cases to train your own model. CSV files need at least 20 complete rows and both legitimate and confirmed-abuse examples. Use the downloadable template; the [developer reference](docs/DEVELOPMENT.md#input-and-training-data-schema) lists the exact schema.

## Common questions

**Why are there no matches?**

At least two requests must share a supplied detail. Check the customer/test filter. A blank device or IP cannot be matched.

**Why does one request appear in multiple groups?**

It may share a device with one request and an IP with another. The groups show individual shared details, not separate fraud verdicts.

**Why does the graph include requests that were blocked?**

They still arrived at the system. Counting them lets you see whether a burst continues during a pause.

**Can I delete test cases?**

Use the delete action in order history. The case, evidence, and review records are removed. Its traffic record is anonymized, so aggregate graph counts remain.

**The dashboard cannot load data.**

Check the [API health endpoint](http://127.0.0.1:8000/health) and confirm both terminals are running. Missing-model errors mean you need step 3; missing-key errors mean you need to configure `.env`.

**A case or CSV is rejected.**

Return/refund counts cannot exceed previous orders. Each ratio must match its count divided by orders. Training CSVs must use the exact template columns.

## Development

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm --prefix frontend run lint
npm --prefix frontend run build
```

See the [developer reference](docs/DEVELOPMENT.md) for architecture, API routes, data validation, local files, and production requirements.

Optional environment settings:

| Variable | Purpose |
|---|---|
| `RISK_DATABASE_URL` | Use another SQLite file for isolated testing. Default: `sqlite:///./risk_manager.db`. |
| `VITE_API_URL` | Override the dashboard's API URL. Default: `http://127.0.0.1:8000`. |
| `RISK_CORS_ORIGINS` | Comma-separated frontend origins allowed by the API. |

Startup adds missing local tables/columns and imports existing case timestamps into the traffic history once. Back up `risk_manager.db`, `models/risk_model.pkl`, and `data/evidence/` before changing an environment you want to preserve.

The older Sentinel approval-hold endpoints remain for compatibility. The two current monitoring pages do not create those holds; any existing legacy hold keeps its original expiry.

## Before production

This demo does not include merchant authentication, tenant isolation, a real refund provider, or independently verified device/location collection. Add those controls, request idempotency, data-retention policies, and a shared pause coordinator before deploying multiple API workers. Evaluate the model on representative merchant data and keep human review for consequential decisions.
