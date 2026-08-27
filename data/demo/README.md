# Reproducible demo

The demo pack is generated with the fixed random seed `20260826`.

```powershell
py src/prepare_demo.py
```

This creates:

- `demo_training.csv`: 500 labeled, internally consistent synthetic cases for the Settings upload flow.
- `demo_cases.json`: three API-ready scenarios covering auto-approve, evidence request, and manual review.

## Suggested walkthrough

1. Open **Settings** and point out the current `SYNTHETIC DATA` model label.
2. Upload `data/demo/demo_training.csv` and train it.
3. Show the held-out confusion matrix, false-positive cost, and approve-all/review-all comparison.
4. In **Merchant loss assumptions**, change a cost and show the threshold recalculate without retraining.
5. Open **Test a case** and enter one scenario from `demo_cases.json`.
6. Open the result and show the model-native feature contributions.
7. Upload a PDF or image as evidence and run the AI investigation.
8. Record Approve, Reject, or Escalate, then record a verified outcome.
9. Finish on the audit trail, which separates model output, human decision, evidence, and final outcome.

The expected route is a narrative expectation, not a hard-coded assertion. The exact score may move after retraining because routing is based on the newly selected thresholds.

## Honest disclosure

This demo dataset is synthetic and is intended to prove the workflow, not production accuracy. For a merchant pilot, keep a later-time dataset untouched and replace these estimates with results from anonymized historical outcomes.
