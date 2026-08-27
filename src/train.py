"""Train the reproducible baseline model from the synthetic dataset."""

from pathlib import Path

import pandas as pd

from model_training import train_model


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT_DIR / "data" / "raw" / "return_abuse_dataset.csv"
MODEL_PATH = ROOT_DIR / "models" / "risk_model.pkl"


if __name__ == "__main__":
    frame = pd.read_csv(DATA_PATH)
    model, metadata = train_model(
        frame,
        MODEL_PATH,
        source="synthetic_baseline",
        dataset_name=DATA_PATH.name,
    )

    print("\n========== MODEL TRAINED ==========")
    print(f"Source:       {metadata['model_source']}")
    print(f"Rows:         {metadata['rows']}")
    print(f"ROC-AUC:      {metadata['metrics']['roc_auc']:.4f}")
    print(f"Precision:    {metadata['metrics']['precision']:.4f}")
    print(f"Recall:       {metadata['metrics']['recall']:.4f}")
    print(f"Thresholds:   {metadata['routing_thresholds']}")
    print(f"Confusion:    {metadata['confusion_matrix']}")
    print(f"FP cost:      INR {metadata['cost_analysis']['false_positive_cost']:,}")
    print(f"Total cost:   INR {metadata['cost_analysis']['total_cost']:,}")
    print(f"Model saved:  {MODEL_PATH}")
