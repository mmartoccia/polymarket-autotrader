"""
Tests for ml/feature_importance.py
"""

import pytest
import tempfile
from pathlib import Path
import pandas as pd
import numpy as np

from ml.feature_importance import (
    categorize_feature,
    load_and_split_data,
    train_random_forest,
    train_logistic_regression,
    extract_importances,
    extract_logistic_importances,
    calculate_category_importance,
    generate_report,
    FeatureImportance,
    ImportanceReport
)


@pytest.fixture
def sample_features_csv():
    """Create sample features.csv for testing"""
    # Create sample data (50 samples)
    np.random.seed(42)
    data = {
        'id': range(1, 51),
        'crypto': ['btc'] * 50,
        'epoch': [1767802500 + i * 900 for i in range(50)],
        'date': ['2026-01-07'] * 50,
        'hour': [10] * 50,
        'direction': ['Up', 'Down'] * 25,
        'start_price': np.random.uniform(90000, 92000, 50),
        'end_price': np.random.uniform(90000, 92000, 50),
        'change_pct': np.random.uniform(-0.5, 0.5, 50),
        'change_abs': np.random.uniform(-500, 500, 50),
        'timestamp': [1768442315.31232 + i * 900 for i in range(50)],
        'dt': ['2026-01-15 01:58:35.312319994'] * 50,
        'day_of_week': [3] * 50,
        'minute_in_session': [718] * 50,
        'epoch_sequence': range(10, 60),
        'is_market_open': [1] * 50,
        'rsi': np.random.uniform(30, 70, 50),
        'volatility': np.random.uniform(0.1, 0.5, 50),
        'price_momentum': np.random.uniform(-0.01, 0.01, 50),
        'spread_proxy': np.random.uniform(0.0, 0.5, 50),
        'position_in_range': np.random.uniform(0, 1, 50),
        'price_z_score': np.random.uniform(-2, 2, 50),
        'btc_correlation': [1.0] * 50,
        'multi_crypto_agreement': np.random.uniform(0.5, 1.0, 50),
        'market_wide_direction': np.random.choice([-1, 0, 1], 50),
        'target': np.random.choice([0, 1], 50)
    }

    df = pd.DataFrame(data)

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        df.to_csv(f.name, index=False)
        return f.name


def test_categorize_feature():
    """Test feature categorization"""
    assert categorize_feature('hour') == 'time'
    assert categorize_feature('day_of_week') == 'time'
    assert categorize_feature('is_market_open') == 'time'

    assert categorize_feature('rsi') == 'price'
    assert categorize_feature('volatility') == 'price'
    assert categorize_feature('price_momentum') == 'price'

    assert categorize_feature('btc_correlation') == 'cross-asset'
    assert categorize_feature('multi_crypto_agreement') == 'cross-asset'
    assert categorize_feature('market_wide_direction') == 'cross-asset'


def test_load_and_split_data(sample_features_csv):
    """Test data loading and splitting"""
    train_df, val_df, test_df, feature_cols = load_and_split_data(sample_features_csv)

    # Check splits
    assert len(train_df) == 35  # 70% of 50
    assert len(val_df) == 7     # 15% of 50
    assert len(test_df) == 8    # 15% of 50

    # Check feature columns (should be 13)
    # Note: 'hour' is in metadata, so we have 13 features not 14
    assert len(feature_cols) == 13
    assert 'target' not in feature_cols
    assert 'id' not in feature_cols
    assert 'crypto' not in feature_cols

    # Check expected features
    assert 'rsi' in feature_cols
    assert 'hour' not in feature_cols  # hour is metadata
    assert 'day_of_week' in feature_cols

    # Cleanup
    Path(sample_features_csv).unlink()


def test_train_random_forest(sample_features_csv):
    """Test Random Forest training"""
    train_df, val_df, test_df, feature_cols = load_and_split_data(sample_features_csv)
    model, accuracy, roc_auc = train_random_forest(train_df, val_df, feature_cols)

    # Check model trained
    assert model is not None
    assert hasattr(model, 'feature_importances_')

    # Check metrics
    assert 0.0 <= accuracy <= 1.0
    assert 0.0 <= roc_auc <= 1.0

    # Check feature importances length
    assert len(model.feature_importances_) == len(feature_cols)

    # Cleanup
    Path(sample_features_csv).unlink()


def test_train_logistic_regression(sample_features_csv):
    """Test Logistic Regression training"""
    train_df, val_df, test_df, feature_cols = load_and_split_data(sample_features_csv)
    model, accuracy, roc_auc, coefficients = train_logistic_regression(train_df, val_df, feature_cols)

    # Check model trained
    assert model is not None
    assert hasattr(model, 'coef_')

    # Check metrics
    assert 0.0 <= accuracy <= 1.0
    assert 0.0 <= roc_auc <= 1.0

    # Check coefficients
    assert len(coefficients) == len(feature_cols)
    assert all(coef >= 0 for coef in coefficients.values())  # Absolute values

    # Cleanup
    Path(sample_features_csv).unlink()


def test_extract_importances(sample_features_csv):
    """Test feature importance extraction from Random Forest"""
    train_df, val_df, test_df, feature_cols = load_and_split_data(sample_features_csv)
    model, accuracy, roc_auc = train_random_forest(train_df, val_df, feature_cols)

    importances = extract_importances(model, feature_cols, 'random_forest')

    # Check structure
    assert len(importances) == len(feature_cols)
    assert all(isinstance(imp, FeatureImportance) for imp in importances)

    # Check sorted by importance (descending)
    for i in range(len(importances) - 1):
        assert importances[i].importance >= importances[i + 1].importance

    # Check ranks
    assert importances[0].rank == 1
    assert importances[-1].rank == len(feature_cols)

    # Check categories
    assert all(imp.category in ['time', 'price', 'cross-asset'] for imp in importances)

    # Cleanup
    Path(sample_features_csv).unlink()


def test_extract_logistic_importances():
    """Test feature importance extraction from Logistic Regression"""
    coefficients = {
        'rsi': 0.5,
        'volatility': 0.3,
        'btc_correlation': 0.8,
        'hour': 0.1
    }

    importances = extract_logistic_importances(coefficients)

    # Check structure
    assert len(importances) == 4
    assert all(isinstance(imp, FeatureImportance) for imp in importances)

    # Check sorted by importance (descending)
    assert importances[0].feature == 'btc_correlation'
    assert importances[0].importance == 0.8
    assert importances[0].rank == 1

    assert importances[-1].feature == 'hour'
    assert importances[-1].rank == 4


def test_calculate_category_importance():
    """Test category importance calculation"""
    importances = [
        FeatureImportance('hour', 0.1, 1, 'time'),
        FeatureImportance('day_of_week', 0.05, 2, 'time'),
        FeatureImportance('rsi', 0.3, 3, 'price'),
        FeatureImportance('volatility', 0.2, 4, 'price'),
        FeatureImportance('btc_correlation', 0.35, 5, 'cross-asset'),
    ]

    category_totals = calculate_category_importance(importances)

    assert category_totals['time'] == pytest.approx(0.15)
    assert category_totals['price'] == pytest.approx(0.50)
    assert category_totals['cross-asset'] == pytest.approx(0.35)


def test_generate_report(sample_features_csv):
    """Test report generation"""
    train_df, val_df, test_df, feature_cols = load_and_split_data(sample_features_csv)
    model, accuracy, roc_auc = train_random_forest(train_df, val_df, feature_cols)
    importances = extract_importances(model, feature_cols, 'random_forest')

    report = generate_report(importances, 'random_forest', accuracy, roc_auc)

    # Check report structure
    assert isinstance(report, ImportanceReport)
    assert report.method == 'random_forest'
    assert report.model_accuracy == accuracy
    assert report.roc_auc == roc_auc

    # Check top 5
    assert len(report.top_5_features) == 5
    assert report.top_5_features[0] == importances[0].feature

    # Check category importance
    assert 'time' in report.category_importance
    assert 'price' in report.category_importance
    assert 'cross-asset' in report.category_importance

    # Cleanup
    Path(sample_features_csv).unlink()


def test_feature_importance_dataclass():
    """Test FeatureImportance dataclass"""
    imp = FeatureImportance(
        feature='rsi',
        importance=0.25,
        rank=1,
        category='price'
    )

    assert imp.feature == 'rsi'
    assert imp.importance == 0.25
    assert imp.rank == 1
    assert imp.category == 'price'


def test_importance_report_dataclass():
    """Test ImportanceReport dataclass"""
    importances = [
        FeatureImportance('rsi', 0.25, 1, 'price'),
        FeatureImportance('hour', 0.15, 2, 'time'),
    ]

    report = ImportanceReport(
        method='random_forest',
        feature_importances=importances,
        model_accuracy=0.65,
        roc_auc=0.70,
        top_5_features=['rsi', 'hour'],
        low_importance_features=[],
        category_importance={'time': 0.15, 'price': 0.25, 'cross-asset': 0.0}
    )

    assert report.method == 'random_forest'
    assert len(report.feature_importances) == 2
    assert report.model_accuracy == 0.65
    assert report.roc_auc == 0.70
