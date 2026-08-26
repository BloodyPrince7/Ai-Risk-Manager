# AI Risk Manager

AI-powered return abuse detection and risk management system for e-commerce.

The system analyzes customer behavior and return-related signals to estimate the probability of return abuse and recommends an appropriate action.

It combines:

- Machine Learning for risk prediction
- FastAPI for the backend API
- React for the merchant dashboard
- Gemini AI for case investigation and explainability

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
                 │     React Frontend  │
                 │   Merchant Console  │
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