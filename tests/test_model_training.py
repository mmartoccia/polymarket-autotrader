#!/usr/bin/env python3
"""
Unit tests for ML model training with walk-forward validation.

Tests cover:
- ModelConfig dataclass
- ValidationFold dataclass
- TrainingResult dataclass
- ModelTrainer class
- Walk-forward validation logic
- XGBoost, Random Forest, Logistic Regression models
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.model_training import (
    ModelConfig,
    ValidationFold,
    TrainingResult,
    ModelTrainer,
)


class TestModelConfig(unittest.TestCase):
    """Test ModelConfig dataclass."""

    def test_default_params(self):
        """Test default hyperparameters."""
        config = ModelConfig(model_type='xgboost')

        # XGBoost defaults
        self.assertEqual(config.xgb_params['n_estimators'], 200)
        self.assertEqual(config.xgb_params['max_depth'], 6)
        self.assertEqual(config.xgb_params['learning_rate'], 0.1)

        # RF defaults
        self.assertEqual(config.rf_params['n_estimators'], 100)
        self.assertEqual(config.rf_params['max_depth'], 10)

        # LR defaults
        self.assertEqual(config.lr_params['C'], 1.0)

    def test_custom_params(self):
        """Test custom hyperparameters."""
        config = ModelConfig(
            model_type='random_forest',
            xgb_params={'n_estimators': 50},
        )

        self.assertEqual(config.xgb_params['n_estimators'], 50)

    def test_validation_settings(self):
        """Test validation settings."""
        config = ModelConfig(
            model_type='logistic',
            min_train_size=300,
            validation_size=75,
            step_size=25,
        )

        self.assertEqual(config.min_train_size, 300)
        self.assertEqual(config.validation_size, 75)
        self.assertEqual(config.step_size, 25)


class TestValidationFold(unittest.TestCase):
    """Test ValidationFold dataclass."""

    def test_fold_creation(self):
        """Test creating validation fold."""
        fold = ValidationFold(
            fold_id=0,
            train_start=0,
            train_end=400,
            val_start=400,
            val_end=500,
            train_size=400,
            val_size=100,
            accuracy=0.65,
            precision=0.68,
            recall=0.62,
            f1=0.65,
            roc_auc=0.70,
            confusion=[[40, 15], [20, 25]],
            feature_importances={'rsi': 0.3, 'hour': 0.1},
        )

        self.assertEqual(fold.fold_id, 0)
        self.assertEqual(fold.accuracy, 0.65)
        self.assertEqual(fold.train_size, 400)
        self.assertEqual(fold.val_size, 100)
        self.assertIn('rsi', fold.feature_importances)


class TestTrainingResult(unittest.TestCase):
    """Test TrainingResult dataclass."""

    def test_result_creation(self):
        """Test creating training result."""
        config = ModelConfig(model_type='xgboost')
        folds = [
            ValidationFold(
                fold_id=0, train_start=0, train_end=400,
                val_start=400, val_end=500, train_size=400, val_size=100,
                accuracy=0.65, precision=0.68, recall=0.62, f1=0.65,
                roc_auc=0.70, confusion=[[40, 15], [20, 25]],
            ),
        ]

        result = TrainingResult(
            model_type='xgboost',
            config=config,
            folds=folds,
            avg_accuracy=0.65,
            avg_precision=0.68,
            avg_recall=0.62,
            avg_f1=0.65,
            avg_roc_auc=0.70,
            std_accuracy=0.02,
            std_roc_auc=0.03,
            total_train_samples=400,
            total_val_samples=100,
            num_folds=1,
        )

        self.assertEqual(result.model_type, 'xgboost')
        self.assertEqual(result.num_folds, 1)
        self.assertIsNotNone(result.trained_at)

    def test_success_criteria(self):
        """Test success criteria checking."""
        config = ModelConfig(model_type='xgboost')

        # Passing result (60%+)
        result_pass = TrainingResult(
            model_type='xgboost', config=config, folds=[],
            avg_accuracy=0.65, avg_precision=0.68, avg_recall=0.62,
            avg_f1=0.65, avg_roc_auc=0.70, std_accuracy=0.02,
            std_roc_auc=0.03, total_train_samples=400,
            total_val_samples=100, num_folds=1,
        )
        self.assertTrue(result_pass.meets_success_criteria(0.60))

        # Failing result (<60%)
        result_fail = TrainingResult(
            model_type='xgboost', config=config, folds=[],
            avg_accuracy=0.55, avg_precision=0.58, avg_recall=0.52,
            avg_f1=0.55, avg_roc_auc=0.60, std_accuracy=0.02,
            std_roc_auc=0.03, total_train_samples=400,
            total_val_samples=100, num_folds=1,
        )
        self.assertFalse(result_fail.meets_success_criteria(0.60))

    def test_summary(self):
        """Test summary generation."""
        config = ModelConfig(model_type='random_forest')
        result = TrainingResult(
            model_type='random_forest', config=config, folds=[],
            avg_accuracy=0.68, avg_precision=0.70, avg_recall=0.65,
            avg_f1=0.67, avg_roc_auc=0.75, std_accuracy=0.03,
            std_roc_auc=0.04, total_train_samples=800,
            total_val_samples=200, num_folds=2,
            feature_importances={'market_wide_direction': 0.8, 'rsi': 0.1, 'hour': 0.05},
        )

        summary = result.summary()

        self.assertIn('RANDOM_FOREST', summary)
        self.assertIn('0.680', summary)  # Accuracy
        self.assertIn('✓ PASS', summary)  # Success criteria
        self.assertIn('market_wide_direction', summary)  # Top feature


class TestModelTrainer(unittest.TestCase):
    """Test ModelTrainer class."""

    def setUp(self):
        """Create synthetic test data."""
        np.random.seed(42)

        # Create 600 samples with 5 features
        n_samples = 600
        self.X = pd.DataFrame({
            'rsi': np.random.uniform(30, 70, n_samples),
            'hour': np.random.randint(0, 24, n_samples),
            'volatility': np.random.uniform(0.01, 0.05, n_samples),
            'price_momentum': np.random.uniform(-0.02, 0.02, n_samples),
            'market_wide_direction': np.random.choice([-1, 0, 1], n_samples),
        })

        # Create target (simple pattern: UP if market_wide_direction == 1)
        self.y = pd.Series((self.X['market_wide_direction'] == 1).astype(int))

        # Create temporary CSV
        self.temp_dir = tempfile.mkdtemp()
        self.csv_path = os.path.join(self.temp_dir, 'test_features.csv')

        # Combine X and y
        df = self.X.copy()
        df['target'] = self.y
        df.to_csv(self.csv_path, index=False)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_data(self):
        """Test data loading."""
        config = ModelConfig(model_type='xgboost')
        trainer = ModelTrainer(config)

        X, y = trainer.load_data(self.csv_path)

        self.assertEqual(len(X), 600)
        self.assertEqual(len(y), 600)
        self.assertEqual(list(X.columns), list(self.X.columns))

    def test_create_xgboost_model(self):
        """Test XGBoost model creation."""
        try:
            import xgboost
        except ImportError:
            self.skipTest("XGBoost not available")

        config = ModelConfig(model_type='xgboost')
        trainer = ModelTrainer(config)

        model = trainer.create_model()

        self.assertIsInstance(model, xgboost.XGBClassifier)
        self.assertEqual(model.n_estimators, 200)

    def test_create_random_forest_model(self):
        """Test Random Forest model creation."""
        config = ModelConfig(model_type='random_forest')
        trainer = ModelTrainer(config)

        model = trainer.create_model()

        from sklearn.ensemble import RandomForestClassifier
        self.assertIsInstance(model, RandomForestClassifier)
        self.assertEqual(model.n_estimators, 100)

    def test_create_logistic_model(self):
        """Test Logistic Regression model creation."""
        config = ModelConfig(model_type='logistic')
        trainer = ModelTrainer(config)

        model = trainer.create_model()

        from sklearn.linear_model import LogisticRegression
        self.assertIsInstance(model, LogisticRegression)

    def test_walk_forward_validation(self):
        """Test walk-forward validation logic."""
        config = ModelConfig(
            model_type='random_forest',
            min_train_size=300,
            validation_size=100,
            step_size=50,
            save_model=False,
        )
        trainer = ModelTrainer(config)

        X, y = trainer.load_data(self.csv_path)
        result = trainer.walk_forward_validate(X, y)

        # Should have at least 2 folds (300+100, roll 50 → 350+100)
        self.assertGreaterEqual(result.num_folds, 2)

        # Check metrics are in valid range
        self.assertGreaterEqual(result.avg_accuracy, 0.0)
        self.assertLessEqual(result.avg_accuracy, 1.0)
        self.assertGreaterEqual(result.avg_roc_auc, 0.0)
        self.assertLessEqual(result.avg_roc_auc, 1.0)

        # Check folds have correct structure
        for fold in result.folds:
            self.assertGreaterEqual(fold.train_size, 300)
            self.assertEqual(fold.val_size, 100)
            self.assertIsNotNone(fold.confusion)

    def test_feature_importances_extraction(self):
        """Test feature importance extraction."""
        config = ModelConfig(model_type='random_forest', save_model=False)
        trainer = ModelTrainer(config)

        X, y = trainer.load_data(self.csv_path)
        model = trainer.create_model()
        model.fit(X.values, y.values)

        importances = trainer.extract_feature_importances(model, X.columns.tolist())

        self.assertIsNotNone(importances)
        self.assertEqual(len(importances), 5)  # 5 features
        self.assertIn('rsi', importances)
        self.assertGreaterEqual(importances['rsi'], 0.0)

    def test_train_final_model(self):
        """Test training final model on all data."""
        config = ModelConfig(model_type='random_forest', save_model=False)
        trainer = ModelTrainer(config)

        X, y = trainer.load_data(self.csv_path)
        model = trainer.train_final_model(X, y)

        # Check model can predict
        predictions = model.predict(X.values[:10])
        self.assertEqual(len(predictions), 10)

    def test_full_training_pipeline(self):
        """Test complete training pipeline."""
        output_dir = os.path.join(self.temp_dir, 'models')

        config = ModelConfig(
            model_type='random_forest',
            min_train_size=300,
            validation_size=100,
            step_size=100,
            save_model=True,
            output_dir=output_dir,
        )
        trainer = ModelTrainer(config)

        result = trainer.train(self.csv_path)

        # Check result
        self.assertIsNotNone(result)
        self.assertEqual(result.model_type, 'random_forest')
        self.assertGreater(result.num_folds, 0)

        # Check files created
        self.assertTrue(os.path.exists(os.path.join(output_dir, 'random_forest_results.json')))
        self.assertTrue(os.path.exists(os.path.join(output_dir, 'random_forest_summary.txt')))
        self.assertTrue(os.path.exists(os.path.join(output_dir, 'random_forest_model.pkl')))


def run_tests():
    """Run all tests."""
    unittest.main(argv=[''], exit=False, verbosity=2)


if __name__ == '__main__':
    run_tests()
