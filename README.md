# AI Risk Manager 🛡️

AI-powered ecommerce return-abuse risk detection and decision system.

## What it does

The system analyzes customer and return behavior and predicts the probability of abuse.

```text
Return Request
      ↓
XGBoost ML Model
      ↓
Risk Probability
      ↓
Decision Engine
      ↓
LOW / MEDIUM / HIGH
      ↓
Merchant Action
```

## Current Features

- Customer history analysis
- Return and refund behavior
- Account reuse detection
- Address/device reuse signals
- Payment failure signals
- Claim type and product category
- XGBoost risk model
- Probability/threshold analysis
- Cost-sensitive decision analysis
- Risk decision engine
- New-case prediction
- Saved trained model

## Current Model Results

Dataset: 20,000 synthetic return requests.

| Metric | Score |
|---|---:|
| Precision | 75.00% |
| Recall | 49.76% |
| F1 Score | 59.83% |
| ROC-AUC | 0.7731 |
| Brier Score | 0.1738 |

These results are from synthetic data and are for prototype evaluation only.

## Risk Decisions

| Risk Score | Risk Level | Action |

| < 20% | 🟢 LOW | Auto Approve |
| 20% - 60% | 🟡 MEDIUM | Request Evidence |
| >= 60% | 🔴 HIGH | Manual Review |

## Project Structure

```text
Ai-Risk-Manager/
│
├── data/
│   └── raw/
│
├── models/
│
├── src/
│   ├── data_generation.py
│   ├── explore_data.py
│   ├── train.py
│   ├── evaluate_thresholds.py
│   ├── cost_analysis.py
│   ├── calibration.py
│   ├── decision_engine.py
│   └── predict.py
│
├── .gitignore
├── README.md
└── requirements.txt
```

## Setup

Create and activate a virtual environment:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

## Run

Generate data:

```powershell
py src/data_generation.py
```

Explore data:

```powershell
py src/explore_data.py
```

Train the model:

```powershell
py src/train.py
```

Evaluate thresholds:

```powershell
py src/evaluate_thresholds.py
```

Analyze merchant costs:

```powershell
py src/cost_analysis.py
```

Check calibration:

```powershell
py src/calibration.py
```

Test a new return request:

```powershell
py src/predict.py
```

## Current Example

A low-risk request can produce:

```text
Risk Score: 11.43%
Risk Level: LOW
Action: AUTO_APPROVE
```

A suspicious request can produce:

```text
Risk Score: 99.66%
Risk Level: HIGH
Action: MANUAL_REVIEW
```

## Roadmap 🚀

- [x] Dataset generation
- [x] Exploratory analysis
- [x] XGBoost model
- [x] Threshold analysis
- [x] Cost analysis
- [x] Calibration analysis
- [x] Decision engine
- [x] New-case prediction
- [x] Model persistence
- [ ] FastAPI backend
- [ ] Merchant dashboard
- [ ] AI explanation layer
- [ ] Agentic risk investigation
- [ ] Production deployment

## Note

This project currently uses synthetic data. The model performance and cost assumptions should not be treated as real-world merchant or fraud statistics.

Built as an AI risk-management prototype. 🚀
