#!/usr/bin/env python3
"""
ML Model Training with Walk-Forward Validation

Trains XGBoost, Random Forest, and Logistic Regression models on historical
epoch data with proper time-series validation to avoid lookahead bias.

Walk-Forward Validation:
- Split data into chronological chunks
- Train on past data, validate on future data
- Roll window forward for multiple validation rounds
- Average metrics across all folds

Usage:
    python3 ml/model_training.py --model xgboost
    python3 ml/model_training.py --model all --output ml/models/
"""

import argparse
import json
import os
import pickle
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
)
from sklearn.preprocessing import StandardScaler

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("Warning: XGBoost not available. Install with: pip install xgboost")


@dataclass
class ModelConfig:
    """Configuration for model training."""
    model_type: str  # 'xgboost', 'random_forest', 'logistic'

    # Walk-forward validation settings
    min_train_size: int = 400  # Minimum training samples
    validation_size: int = 100  # Validation window size
    step_size: int = 50  # Roll window forward by this many samples

    # Model hyperparameters
    xgb_params: Dict = None
    rf_params: Dict = None
    lr_params: Dict = None

    # Output settings
    save_model: bool = True
    output_dir: str = "ml/models"

    def __post_init__(self):
        """Set default hyperparameters."""
        if self.xgb_params is None:
            self.xgb_params = {
                'n_estimators': 200,
                'max_depth': 6,
                'learning_rate': 0.1,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'min_child_weight': 3,
                'gamma': 0.1,
                'reg_alpha': 0.1,  # L1 regularization
                'reg_lambda': 1.0,  # L2 regularization
                'random_state': 42,
                'n_jobs': -1,
            }

        if self.rf_params is None:
            self.rf_params = {
                'n_estimators': 100,
                'max_depth': 10,
                'min_samples_split': 20,
                'min_samples_leaf': 10,
                'max_features': 'sqrt',
                'random_state': 42,
                'n_jobs': -1,
            }

        if self.lr_params is None:
            self.lr_params = {
                'C': 1.0,  # Regularization strength (lower = more regularization)
                'penalty': 'l2',
                'solver': 'lbfgs',
                'max_iter': 1000,
                'random_state': 42,
            }


@dataclass
class ValidationFold:
    """Results from one walk-forward validation fold."""
    fold_id: int
    train_start: int
    train_end: int
    val_start: int
    val_end: int
    train_size: int
    val_size: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    confusion: List[List[int]]  # [[TN, FP], [FN, TP]]
    feature_importances: Optional[Dict[str, float]] = None


@dataclass
class TrainingResult:
    """Complete training results across all folds."""
    model_type: str
    config: ModelConfig
    folds: List[ValidationFold]
    avg_accuracy: float
    avg_precision: float
    avg_recall: float
    avg_f1: float
    avg_roc_auc: float
    std_accuracy: float
    std_roc_auc: float
    total_train_samples: int
    total_val_samples: int
    num_folds: int
    feature_importances: Optional[Dict[str, float]] = None
    trained_at: str = None

    def __post_init__(self):
        """Set timestamp."""
        if self.trained_at is None:
            self.trained_at = datetime.utcnow().isoformat()

    def meets_success_criteria(self, min_accuracy: float = 0.60) -> bool:
        """Check if model meets PRD success criteria (60%+ out-of-sample accuracy)."""
        return self.avg_accuracy >= min_accuracy

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Model Type: {self.model_type.upper()}",
            f"Walk-Forward Validation: {self.num_folds} folds",
            f"Training Samples: {self.total_train_samples}",
            f"Validation Samples: {self.total_val_samples}",
            "",
            "Performance Metrics (Out-of-Sample):",
            f"  Accuracy:  {self.avg_accuracy:.3f} ± {self.std_accuracy:.3f}",
            f"  Precision: {self.avg_precision:.3f}",
            f"  Recall:    {self.avg_recall:.3f}",
            f"  F1 Score:  {self.avg_f1:.3f}",
            f"  ROC AUC:   {self.avg_roc_auc:.3f} ± {self.std_roc_auc:.3f}",
            "",
            f"Success Criteria: {'✓ PASS' if self.meets_success_criteria(0.60) else '✗ FAIL'} (target 60%+)",
            f"PRD Target (65%+): {'✓ PASS' if self.meets_success_criteria(0.65) else '✗ FAIL'}",
        ]

        if self.feature_importances:
            lines.append("")
            lines.append("Top 5 Features:")
            sorted_features = sorted(
                self.feature_importances.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            for i, (feature, importance) in enumerate(sorted_features, 1):
                lines.append(f"  {i}. {feature}: {importance:.3f}")

        return "\n".join(lines)


class ModelTrainer:
    """Trains and validates ML models with walk-forward validation."""

    def __init__(self, config: ModelConfig):
        self.config = config
        self.scaler = StandardScaler()  # For Logistic Regression

    def load_data(self, csv_path: str) -> Tuple[pd.DataFrame, pd.Series]:
        """Load feature matrix and target labels."""
        df = pd.read_csv(csv_path)

        # Drop rows with NaN (from rolling calculations)
        df_clean = df.dropna()

        # Separate features and target
        # Exclude metadata and non-feature columns
        excluded_cols = [
            'id', 'crypto', 'epoch', 'date', 'direction', 'target',
            'timestamp', 'hour_timestamp', 'dt',  # Timestamp columns
            'start_price', 'end_price', 'change_pct', 'change_abs',  # Raw price data
        ]
        feature_cols = [
            col for col in df_clean.columns
            if col not in excluded_cols
        ]

        X = df_clean[feature_cols]
        y = df_clean['target']

        print(f"Loaded {len(X)} samples with {len(feature_cols)} features")
        print(f"Target distribution: {y.value_counts().to_dict()}")

        return X, y

    def create_model(self):
        """Create model instance based on config."""
        if self.config.model_type == 'xgboost':
            if not XGBOOST_AVAILABLE:
                raise ImportError("XGBoost not available. Install with: pip install xgboost")
            return xgb.XGBClassifier(**self.config.xgb_params)
        elif self.config.model_type == 'random_forest':
            return RandomForestClassifier(**self.config.rf_params)
        elif self.config.model_type == 'logistic':
            return LogisticRegression(**self.config.lr_params)
        else:
            raise ValueError(f"Unknown model type: {self.config.model_type}")

    def extract_feature_importances(self, model, feature_names: List[str]) -> Dict[str, float]:
        """Extract feature importances from trained model."""
        if hasattr(model, 'feature_importances_'):
            # XGBoost and Random Forest
            importances = model.feature_importances_
        elif hasattr(model, 'coef_'):
            # Logistic Regression
            importances = np.abs(model.coef_[0])
        else:
            return None

        return dict(zip(feature_names, importances.tolist()))

    def walk_forward_validate(self, X: pd.DataFrame, y: pd.Series) -> TrainingResult:
        """
        Perform walk-forward validation.

        Process:
        1. Start with min_train_size samples for training
        2. Validate on next validation_size samples
        3. Roll window forward by step_size samples
        4. Repeat until we run out of data
        """
        folds = []
        feature_names = X.columns.tolist()

        # Convert to numpy for easier indexing
        X_array = X.values
        y_array = y.values
        n_samples = len(X_array)

        # Walk forward through data
        train_start = 0
        fold_id = 0

        while True:
            train_end = train_start + self.config.min_train_size
            val_start = train_end
            val_end = val_start + self.config.validation_size

            # Stop if we don't have enough data for validation
            if val_end > n_samples:
                break

            # Split data
            X_train = X_array[train_start:train_end]
            y_train = y_array[train_start:train_end]
            X_val = X_array[val_start:val_end]
            y_val = y_array[val_start:val_end]

            # Train model
            model = self.create_model()

            # Scale features for Logistic Regression
            if self.config.model_type == 'logistic':
                X_train = self.scaler.fit_transform(X_train)
                X_val = self.scaler.transform(X_val)

            model.fit(X_train, y_train)

            # Predict on validation set
            y_pred = model.predict(X_val)
            y_pred_proba = model.predict_proba(X_val)[:, 1]

            # Calculate metrics
            accuracy = accuracy_score(y_val, y_pred)
            precision = precision_score(y_val, y_pred, zero_division=0)
            recall = recall_score(y_val, y_pred, zero_division=0)
            f1 = f1_score(y_val, y_pred, zero_division=0)
            roc_auc = roc_auc_score(y_val, y_pred_proba)
            cm = confusion_matrix(y_val, y_pred).tolist()

            # Extract feature importances
            importances = self.extract_feature_importances(model, feature_names)

            fold = ValidationFold(
                fold_id=fold_id,
                train_start=train_start,
                train_end=train_end,
                val_start=val_start,
                val_end=val_end,
                train_size=len(X_train),
                val_size=len(X_val),
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                f1=f1,
                roc_auc=roc_auc,
                confusion=cm,
                feature_importances=importances,
            )

            folds.append(fold)
            print(f"Fold {fold_id}: train={train_start}-{train_end} val={val_start}-{val_end} "
                  f"acc={accuracy:.3f} auc={roc_auc:.3f}")

            # Roll window forward
            train_start += self.config.step_size
            fold_id += 1

        # Aggregate results across folds
        accuracies = [f.accuracy for f in folds]
        precisions = [f.precision for f in folds]
        recalls = [f.recall for f in folds]
        f1_scores = [f.f1 for f in folds]
        roc_aucs = [f.roc_auc for f in folds]

        # Average feature importances across folds
        avg_importances = {}
        if folds[0].feature_importances:
            for feature in feature_names:
                importances = [f.feature_importances[feature] for f in folds]
                avg_importances[feature] = float(np.mean(importances))

        result = TrainingResult(
            model_type=self.config.model_type,
            config=self.config,
            folds=folds,
            avg_accuracy=float(np.mean(accuracies)),
            avg_precision=float(np.mean(precisions)),
            avg_recall=float(np.mean(recalls)),
            avg_f1=float(np.mean(f1_scores)),
            avg_roc_auc=float(np.mean(roc_aucs)),
            std_accuracy=float(np.std(accuracies)),
            std_roc_auc=float(np.std(roc_aucs)),
            total_train_samples=sum(f.train_size for f in folds),
            total_val_samples=sum(f.val_size for f in folds),
            num_folds=len(folds),
            feature_importances=avg_importances if avg_importances else None,
        )

        return result

    def train_final_model(self, X: pd.DataFrame, y: pd.Series):
        """Train final model on all available data."""
        model = self.create_model()

        X_array = X.values

        # Scale for Logistic Regression
        if self.config.model_type == 'logistic':
            X_array = self.scaler.fit_transform(X_array)

        model.fit(X_array, y.values)

        return model

    def save_results(self, result: TrainingResult, final_model=None):
        """Save training results and model to disk."""
        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save results as JSON
        result_path = output_dir / f"{self.config.model_type}_results.json"
        with open(result_path, 'w') as f:
            # Convert dataclasses to dict for JSON serialization
            result_dict = asdict(result)
            # Remove config (too verbose)
            result_dict.pop('config', None)
            json.dump(result_dict, f, indent=2)
        print(f"Saved results to {result_path}")

        # Save human-readable summary
        summary_path = output_dir / f"{self.config.model_type}_summary.txt"
        with open(summary_path, 'w') as f:
            f.write(result.summary())
        print(f"Saved summary to {summary_path}")

        # Save final model
        if final_model:
            model_path = output_dir / f"{self.config.model_type}_model.pkl"
            with open(model_path, 'wb') as f:
                pickle.dump(final_model, f)
            print(f"Saved model to {model_path}")

            # Save scaler for Logistic Regression
            if self.config.model_type == 'logistic':
                scaler_path = output_dir / f"{self.config.model_type}_scaler.pkl"
                with open(scaler_path, 'wb') as f:
                    pickle.dump(self.scaler, f)
                print(f"Saved scaler to {scaler_path}")

    def train(self, csv_path: str) -> TrainingResult:
        """Full training pipeline."""
        print(f"Training {self.config.model_type.upper()} model")
        print(f"Walk-forward validation: min_train={self.config.min_train_size}, "
              f"val={self.config.validation_size}, step={self.config.step_size}")

        # Load data
        X, y = self.load_data(csv_path)

        # Walk-forward validation
        print("\nRunning walk-forward validation...")
        result = self.walk_forward_validate(X, y)

        # Train final model on all data
        print("\nTraining final model on all data...")
        final_model = self.train_final_model(X, y)

        # Save results
        if self.config.save_model:
            self.save_results(result, final_model)

        # Print summary
        print("\n" + "="*80)
        print(result.summary())
        print("="*80)

        return result


def main():
    parser = argparse.ArgumentParser(
        description="Train ML models with walk-forward validation"
    )
    parser.add_argument(
        '--model',
        choices=['xgboost', 'random_forest', 'logistic', 'all'],
        default='xgboost',
        help="Model type to train"
    )
    parser.add_argument(
        '--data',
        default='ml/features.csv',
        help="Path to feature CSV file"
    )
    parser.add_argument(
        '--output',
        default='ml/models',
        help="Output directory for models"
    )
    parser.add_argument(
        '--min-train-size',
        type=int,
        default=400,
        help="Minimum training samples per fold"
    )
    parser.add_argument(
        '--val-size',
        type=int,
        default=100,
        help="Validation window size"
    )
    parser.add_argument(
        '--step-size',
        type=int,
        default=50,
        help="Roll window forward by this many samples"
    )

    args = parser.parse_args()

    # Check if data file exists
    if not os.path.exists(args.data):
        print(f"Error: Data file not found: {args.data}")
        print("Run feature extraction first: python3 ml/feature_extraction.py")
        sys.exit(1)

    # Determine which models to train
    if args.model == 'all':
        model_types = ['xgboost', 'random_forest', 'logistic']
    else:
        model_types = [args.model]

    # Train each model
    results = {}
    for model_type in model_types:
        config = ModelConfig(
            model_type=model_type,
            min_train_size=args.min_train_size,
            validation_size=args.val_size,
            step_size=args.step_size,
            output_dir=args.output,
        )

        trainer = ModelTrainer(config)
        result = trainer.train(args.data)
        results[model_type] = result

    # Print comparison if multiple models
    if len(results) > 1:
        print("\n" + "="*80)
        print("MODEL COMPARISON")
        print("="*80)
        for model_type, result in results.items():
            print(f"{model_type.upper():15} | Accuracy: {result.avg_accuracy:.3f} | "
                  f"ROC AUC: {result.avg_roc_auc:.3f} | "
                  f"Success: {'✓' if result.meets_success_criteria(0.60) else '✗'}")
        print("="*80)


if __name__ == '__main__':
    main()
