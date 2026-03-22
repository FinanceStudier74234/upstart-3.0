"""
Self-Improvement / Learning Loop Engine
Tracks predictions, errors, and updates model weights over time.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass
class PredictionRecord:
    """A logged prediction for later validation."""
    prediction_id: str
    model_name: str
    prediction_time: dt.datetime
    target_variable: str
    horizon_days: int
    predicted_value: float
    reference_value: float | None = None  # baseline price at prediction time
    actual_value: float | None = None
    error: float | None = None
    direction_correct: bool | None = None
    validated: bool = False


@dataclass
class ModelPerformance:
    """Tracked performance of a single model."""
    model_name: str
    total_predictions: int = 0
    validated_predictions: int = 0
    mae: float | None = None
    rmse: float | None = None
    direction_accuracy: float | None = None
    brier_score: float | None = None
    current_weight: float = 1.0
    weight_trend: str = "stable"  # improving | stable | degrading
    model_drift_detected: bool = False


class LearningEngine:
    """Tracks and validates model predictions, adjusts weights."""

    def __init__(self):
        self.predictions: list[PredictionRecord] = []
        self.model_performance: dict[str, ModelPerformance] = {}

    def log_prediction(
        self,
        model_name: str,
        target: str,
        horizon: int,
        predicted: float,
    ) -> str:
        """Log a new prediction for future validation."""
        pred_id = f"{model_name}_{target}_{dt.datetime.now().isoformat()}"
        record = PredictionRecord(
            prediction_id=pred_id,
            model_name=model_name,
            prediction_time=dt.datetime.now(dt.timezone.utc),
            target_variable=target,
            horizon_days=horizon,
            predicted_value=predicted,
        )
        self.predictions.append(record)
        return pred_id

    def validate_prediction(self, pred_id: str, actual_value: float):
        """Validate a prediction once the horizon has passed."""
        for pred in self.predictions:
            if pred.prediction_id == pred_id and not pred.validated:
                pred.actual_value = actual_value
                pred.error = actual_value - pred.predicted_value
                # Direction correct: did actual and predicted agree on sign?
                # Both represent returns or directional forecasts, so check
                # if actual moved in the same direction the model predicted.
                if pred.reference_value is not None:
                    pred.direction_correct = (actual_value >= pred.reference_value) == (pred.predicted_value >= pred.reference_value)
                else:
                    pred.direction_correct = (actual_value >= 0) == (pred.predicted_value >= 0)
                pred.validated = True
                self._update_model_performance(pred.model_name)
                return True
        return False

    def get_model_weights(self) -> dict[str, float]:
        """Get current model weights based on historical performance."""
        weights = {}
        for name, perf in self.model_performance.items():
            weights[name] = perf.current_weight
        return weights

    def _update_model_performance(self, model_name: str):
        """Recalculate performance metrics for a model."""
        validated = [p for p in self.predictions if p.model_name == model_name and p.validated]
        if not validated:
            return

        perf = self.model_performance.setdefault(model_name, ModelPerformance(model_name=model_name))
        perf.total_predictions = len([p for p in self.predictions if p.model_name == model_name])
        perf.validated_predictions = len(validated)

        errors = [p.error for p in validated if p.error is not None]
        if errors:
            import numpy as np
            perf.mae = round(float(np.mean(np.abs(errors))), 4)
            perf.rmse = round(float(np.sqrt(np.mean(np.square(errors)))), 4)

        directions = [p.direction_correct for p in validated if p.direction_correct is not None]
        if directions:
            perf.direction_accuracy = round(sum(directions) / len(directions), 4)

        # Brier score: mean squared error of directional probability forecasts
        # Treat direction_correct as binary outcome, predicted probability as 0.5 + normalized predicted value
        brier_pairs = []
        for p in validated:
            if p.direction_correct is not None:
                # Clamp predicted probability to [0, 1]
                forecast_prob = max(0.0, min(1.0, 0.5 + p.predicted_value * 0.01))
                outcome = 1.0 if p.direction_correct else 0.0
                brier_pairs.append((forecast_prob - outcome) ** 2)
        if brier_pairs:
            perf.brier_score = round(sum(brier_pairs) / len(brier_pairs), 4)

        # Adjust weight based on performance
        if perf.direction_accuracy is not None:
            if perf.direction_accuracy > 0.55:
                perf.current_weight = min(2.0, perf.current_weight * 1.05)
                perf.weight_trend = "improving"
            elif perf.direction_accuracy < 0.45:
                perf.current_weight = max(0.2, perf.current_weight * 0.95)
                perf.weight_trend = "degrading"
            else:
                perf.weight_trend = "stable"

    def detect_model_drift(self, model_name: str, window: int = 20) -> bool:
        """Check if recent performance differs significantly from historical."""
        validated = [p for p in self.predictions if p.model_name == model_name and p.validated]
        if len(validated) < window * 2:
            return False

        recent = validated[-window:]
        historical = validated[:-window]

        recent_acc = sum(1 for p in recent if p.direction_correct) / len(recent)
        hist_acc = sum(1 for p in historical if p.direction_correct) / len(historical)

        drift = abs(recent_acc - hist_acc) > 0.15
        if model_name in self.model_performance:
            self.model_performance[model_name].model_drift_detected = drift
        return drift

    def get_report(self) -> dict:
        """Generate learning loop report."""
        return {
            "total_predictions": len(self.predictions),
            "validated": sum(1 for p in self.predictions if p.validated),
            "pending": sum(1 for p in self.predictions if not p.validated),
            "models": {
                name: {
                    "validated": perf.validated_predictions,
                    "mae": perf.mae,
                    "direction_accuracy": perf.direction_accuracy,
                    "weight": perf.current_weight,
                    "trend": perf.weight_trend,
                    "drift": perf.model_drift_detected,
                }
                for name, perf in self.model_performance.items()
            },
        }
