#!/usr/bin/env python3
"""
Feature Importance Analysis
Analyzes which features are most predictive of market outcomes.

Usage:
    python3 ml/feature_importance.py --input ml/features.csv
    python3 ml/feature_importance.py --input ml/features.csv --method xgboost
    python3 ml/feature_importance.py --input ml/features.csv --output ml/importance_report.txt
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.preprocessing import StandardScaler

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False


@dataclass
class FeatureImportance:
    """Feature importance result"""
    feature: str
    importance: float
    rank: int
    category: str  # 'time', 'price', 'cross-asset'


@dataclass
class ImportanceReport:
    """Complete feature importance analysis report"""
    method: str
    feature_importances: List[FeatureImportance]
    model_accuracy: float
    roc_auc: float
    top_5_features: List[str]
    low_importance_features: List[str]  # < 2% importance
    category_importance: Dict[str, float]


def categorize_feature(feature: str) -> str:
    """Categorize feature into time/price/cross-asset"""
    time_features = {'hour', 'day_of_week', 'minute_in_session', 'epoch_sequence', 'is_market_open'}
    cross_asset_features = {'btc_correlation', 'multi_crypto_agreement', 'market_wide_direction'}

    if feature in time_features:
        return 'time'
    elif feature in cross_asset_features:
        return 'cross-asset'
    else:
        return 'price'


def load_and_split_data(csv_path: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, List[str]]:
    """
    Load features and split into train/val/test

    Returns:
        train_df, val_df, test_df, feature_columns
    """
    df = pd.read_csv(csv_path)

    # Get feature columns (exclude metadata)
    metadata_cols = ['id', 'crypto', 'epoch', 'date', 'hour', 'direction',
                     'start_price', 'end_price', 'change_pct', 'change_abs',
                     'timestamp', 'dt', 'target']
    feature_cols = [col for col in df.columns if col not in metadata_cols]

    # Time-based split (70/15/15)
    n = len(df)
    train_idx = int(n * 0.70)
    val_idx = int(n * 0.85)

    train_df = df.iloc[:train_idx]
    val_df = df.iloc[train_idx:val_idx]
    test_df = df.iloc[val_idx:]

    print(f"Data split:")
    print(f"  Train: {len(train_df)} samples ({len(train_df)/n*100:.1f}%)")
    print(f"  Val:   {len(val_df)} samples ({len(val_df)/n*100:.1f}%)")
    print(f"  Test:  {len(test_df)} samples ({len(test_df)/n*100:.1f}%)")
    print(f"  Features: {len(feature_cols)}")

    return train_df, val_df, test_df, feature_cols


def train_random_forest(train_df: pd.DataFrame, val_df: pd.DataFrame,
                       feature_cols: List[str]) -> Tuple[RandomForestClassifier, float, float]:
    """
    Train Random Forest and return model + metrics

    Returns:
        model, accuracy, roc_auc
    """
    X_train = train_df[feature_cols].values
    y_train = train_df['target'].values
    X_val = val_df[feature_cols].values
    y_val = val_df['target'].values

    # Train model
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=20,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_val)
    y_proba = model.predict_proba(X_val)[:, 1]

    accuracy = (y_pred == y_val).mean()
    roc_auc = roc_auc_score(y_val, y_proba)

    return model, accuracy, roc_auc


def train_xgboost(train_df: pd.DataFrame, val_df: pd.DataFrame,
                 feature_cols: List[str]) -> Tuple[xgb.XGBClassifier, float, float]:
    """
    Train XGBoost and return model + metrics

    Returns:
        model, accuracy, roc_auc
    """
    X_train = train_df[feature_cols].values
    y_train = train_df['target'].values
    X_val = val_df[feature_cols].values
    y_val = val_df['target'].values

    # Train model
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.1,
        random_state=42,
        use_label_encoder=False,
        eval_metric='logloss',
        n_jobs=-1
    )
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_val)
    y_proba = model.predict_proba(X_val)[:, 1]

    accuracy = (y_pred == y_val).mean()
    roc_auc = roc_auc_score(y_val, y_proba)

    return model, accuracy, roc_auc


def train_logistic_regression(train_df: pd.DataFrame, val_df: pd.DataFrame,
                              feature_cols: List[str]) -> Tuple[LogisticRegression, float, float, Dict[str, float]]:
    """
    Train Logistic Regression baseline and return model + metrics + coefficients

    Returns:
        model, accuracy, roc_auc, feature_coefficients
    """
    X_train = train_df[feature_cols].values
    y_train = train_df['target'].values
    X_val = val_df[feature_cols].values
    y_val = val_df['target'].values

    # Standardize features (required for LogReg)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)

    # Train model
    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X_train_scaled, y_train)

    # Evaluate
    y_pred = model.predict(X_val_scaled)
    y_proba = model.predict_proba(X_val_scaled)[:, 1]

    accuracy = (y_pred == y_val).mean()
    roc_auc = roc_auc_score(y_val, y_proba)

    # Extract coefficients (use absolute values for importance)
    coefficients = {feature_cols[i]: abs(model.coef_[0][i])
                   for i in range(len(feature_cols))}

    return model, accuracy, roc_auc, coefficients


def extract_importances(model, feature_cols: List[str], method: str) -> List[FeatureImportance]:
    """
    Extract feature importances from trained model

    Args:
        model: Trained model (RF, XGB, or LogReg)
        feature_cols: List of feature names
        method: 'random_forest', 'xgboost', or 'logistic'

    Returns:
        List of FeatureImportance objects, sorted by importance
    """
    if method == 'logistic':
        # For LogReg, model is tuple (model, accuracy, roc_auc, coefficients)
        raise ValueError("Use extract_logistic_importances() for logistic regression")

    # Get importances
    if hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
    else:
        raise ValueError(f"Model {type(model)} doesn't have feature_importances_")

    # Create FeatureImportance objects
    results = []
    for i, feature in enumerate(feature_cols):
        results.append(FeatureImportance(
            feature=feature,
            importance=float(importances[i]),
            rank=0,  # Will set after sorting
            category=categorize_feature(feature)
        ))

    # Sort by importance (descending)
    results.sort(key=lambda x: x.importance, reverse=True)

    # Set ranks
    for rank, result in enumerate(results, start=1):
        result.rank = rank

    return results


def extract_logistic_importances(coefficients: Dict[str, float]) -> List[FeatureImportance]:
    """Extract feature importances from logistic regression coefficients"""
    results = []
    for feature, coef in coefficients.items():
        results.append(FeatureImportance(
            feature=feature,
            importance=float(coef),
            rank=0,  # Will set after sorting
            category=categorize_feature(feature)
        ))

    # Sort by importance (descending)
    results.sort(key=lambda x: x.importance, reverse=True)

    # Set ranks
    for rank, result in enumerate(results, start=1):
        result.rank = rank

    return results


def calculate_category_importance(importances: List[FeatureImportance]) -> Dict[str, float]:
    """Calculate total importance by category"""
    category_totals = {'time': 0.0, 'price': 0.0, 'cross-asset': 0.0}

    for imp in importances:
        category_totals[imp.category] += imp.importance

    return category_totals


def generate_report(importances: List[FeatureImportance], method: str,
                   accuracy: float, roc_auc: float) -> ImportanceReport:
    """Generate complete feature importance report"""

    # Top 5 features
    top_5 = [imp.feature for imp in importances[:5]]

    # Low importance features (<2%)
    total_importance = sum(imp.importance for imp in importances)
    low_importance = [imp.feature for imp in importances
                     if imp.importance / total_importance < 0.02]

    # Category importance
    category_importance = calculate_category_importance(importances)

    return ImportanceReport(
        method=method,
        feature_importances=importances,
        model_accuracy=accuracy,
        roc_auc=roc_auc,
        top_5_features=top_5,
        low_importance_features=low_importance,
        category_importance=category_importance
    )


def print_report(report: ImportanceReport):
    """Print formatted feature importance report"""
    print()
    print("=" * 80)
    print(f"FEATURE IMPORTANCE ANALYSIS - {report.method.upper()}")
    print("=" * 80)
    print()

    print(f"Model Performance:")
    print(f"  Accuracy:  {report.model_accuracy:.2%}")
    print(f"  ROC AUC:   {report.roc_auc:.3f}")
    print()

    print("Feature Importances (Top 10):")
    print(f"{'Rank':<6} {'Feature':<30} {'Importance':<12} {'Category':<12}")
    print("-" * 80)
    for imp in report.feature_importances[:10]:
        print(f"{imp.rank:<6} {imp.feature:<30} {imp.importance:>10.4f}  {imp.category:<12}")
    print()

    print("Top 5 Most Important Features:")
    for i, feature in enumerate(report.top_5_features, start=1):
        print(f"  {i}. {feature}")
    print()

    if report.low_importance_features:
        print(f"Low Importance Features (<2%): {len(report.low_importance_features)}")
        for feature in report.low_importance_features[:5]:
            print(f"  - {feature}")
        if len(report.low_importance_features) > 5:
            print(f"  ... and {len(report.low_importance_features) - 5} more")
        print()

    print("Importance by Category:")
    total = sum(report.category_importance.values())
    for category, importance in sorted(report.category_importance.items(),
                                      key=lambda x: x[1], reverse=True):
        pct = importance / total * 100 if total > 0 else 0
        print(f"  {category:<15}: {importance:>8.4f} ({pct:>5.1f}%)")
    print()

    print("=" * 80)


def save_report(report: ImportanceReport, output_path: str):
    """Save report to text file"""
    with open(output_path, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write(f"FEATURE IMPORTANCE ANALYSIS - {report.method.upper()}\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Model Performance:\n")
        f.write(f"  Accuracy:  {report.model_accuracy:.2%}\n")
        f.write(f"  ROC AUC:   {report.roc_auc:.3f}\n\n")

        f.write("All Features (Ranked by Importance):\n")
        f.write(f"{'Rank':<6} {'Feature':<30} {'Importance':<12} {'Category':<12}\n")
        f.write("-" * 80 + "\n")
        for imp in report.feature_importances:
            f.write(f"{imp.rank:<6} {imp.feature:<30} {imp.importance:>10.4f}  {imp.category:<12}\n")
        f.write("\n")

        f.write("Importance by Category:\n")
        total = sum(report.category_importance.values())
        for category, importance in sorted(report.category_importance.items(),
                                          key=lambda x: x[1], reverse=True):
            pct = importance / total * 100 if total > 0 else 0
            f.write(f"  {category:<15}: {importance:>8.4f} ({pct:>5.1f}%)\n")
        f.write("\n")

        f.write("=" * 80 + "\n")

    print(f"Report saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Analyze feature importance for ML models')
    parser.add_argument('--input', default='ml/features.csv',
                       help='Path to features CSV file')
    parser.add_argument('--method', default='random_forest',
                       choices=['random_forest', 'xgboost', 'logistic', 'all'],
                       help='Method to use for importance analysis')
    parser.add_argument('--output', default=None,
                       help='Path to save report text file')

    args = parser.parse_args()

    # Check input file
    if not Path(args.input).exists():
        print(f"Error: Input file not found: {args.input}")
        print("Run feature extraction first: python3 ml/feature_extraction.py")
        sys.exit(1)

    # Check XGBoost availability
    if args.method == 'xgboost' and not HAS_XGBOOST:
        print("Error: XGBoost not installed. Install with: pip install xgboost")
        sys.exit(1)

    print(f"Loading data from: {args.input}")
    train_df, val_df, test_df, feature_cols = load_and_split_data(args.input)
    print()

    methods_to_run = ['random_forest', 'xgboost', 'logistic'] if args.method == 'all' else [args.method]

    for method in methods_to_run:
        if method == 'xgboost' and not HAS_XGBOOST:
            print(f"Skipping XGBoost (not installed)")
            continue

        print(f"Training {method.replace('_', ' ').title()} model...")

        if method == 'random_forest':
            model, accuracy, roc_auc = train_random_forest(train_df, val_df, feature_cols)
            importances = extract_importances(model, feature_cols, method)
        elif method == 'xgboost':
            model, accuracy, roc_auc = train_xgboost(train_df, val_df, feature_cols)
            importances = extract_importances(model, feature_cols, method)
        elif method == 'logistic':
            model, accuracy, roc_auc, coefficients = train_logistic_regression(train_df, val_df, feature_cols)
            importances = extract_logistic_importances(coefficients)

        # Generate and print report
        report = generate_report(importances, method, accuracy, roc_auc)
        print_report(report)

        # Save report if requested
        if args.output:
            if args.method == 'all':
                # Save each method to separate file
                base_path = Path(args.output)
                output_path = base_path.parent / f"{base_path.stem}_{method}{base_path.suffix}"
            else:
                output_path = args.output
            save_report(report, str(output_path))

    print("Feature importance analysis complete!")
    print()
    print("Next steps:")
    print("  1. Review top features and understand their predictive power")
    print("  2. Consider removing low-importance features (<2%)")
    print("  3. Document feature definitions (PRD.md task)")
    print("  4. Create live trading integration module")


if __name__ == '__main__':
    main()
