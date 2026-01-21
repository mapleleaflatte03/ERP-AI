"""
ERPX AI Accounting - MLflow Tracking (Skeleton)
===============================================
ML experiment tracking for model performance monitoring.
"""

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MockRun:
    """Mock MLflow run for development"""

    run_id: str
    experiment_id: str
    start_time: str
    end_time: str | None = None
    status: str = "RUNNING"
    params: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)


class MockMLflowClient:
    """
    Mock MLflow client for development without MLflow server.
    Stores runs in memory.
    """

    def __init__(self):
        self._experiments: dict[str, dict] = {}
        self._runs: dict[str, MockRun] = {}
        self._active_run: MockRun | None = None

    def create_experiment(self, name: str) -> str:
        """Create an experiment"""
        exp_id = hashlib.md5(name.encode()).hexdigest()[:8]
        self._experiments[exp_id] = {"experiment_id": exp_id, "name": name, "created_at": datetime.utcnow().isoformat()}
        return exp_id

    def get_experiment_by_name(self, name: str) -> dict | None:
        """Get experiment by name"""
        for exp in self._experiments.values():
            if exp["name"] == name:
                return exp
        return None

    def start_run(self, experiment_id: str = None, run_name: str = None) -> MockRun:
        """Start a new run"""
        run_id = hashlib.md5(f"{datetime.now().isoformat()}{run_name}".encode()).hexdigest()[:16]

        run = MockRun(run_id=run_id, experiment_id=experiment_id or "default", start_time=datetime.utcnow().isoformat())

        if run_name:
            run.tags["mlflow.runName"] = run_name

        self._runs[run_id] = run
        self._active_run = run
        return run

    def end_run(self, status: str = "FINISHED"):
        """End the active run"""
        if self._active_run:
            self._active_run.end_time = datetime.utcnow().isoformat()
            self._active_run.status = status
            self._active_run = None

    def log_param(self, key: str, value: Any):
        """Log a parameter"""
        if self._active_run:
            self._active_run.params[key] = str(value)

    def log_params(self, params: dict[str, Any]):
        """Log multiple parameters"""
        for key, value in params.items():
            self.log_param(key, value)

    def log_metric(self, key: str, value: float, step: int = None):
        """Log a metric"""
        if self._active_run:
            self._active_run.metrics[key] = value

    def log_metrics(self, metrics: dict[str, float], step: int = None):
        """Log multiple metrics"""
        for key, value in metrics.items():
            self.log_metric(key, value, step)

    def set_tag(self, key: str, value: str):
        """Set a tag"""
        if self._active_run:
            self._active_run.tags[key] = value

    def log_artifact(self, local_path: str, artifact_path: str = None):
        """Log an artifact"""
        if self._active_run:
            self._active_run.artifacts.append(local_path)

    def get_run(self, run_id: str) -> MockRun | None:
        """Get a run by ID"""
        return self._runs.get(run_id)

    def search_runs(self, experiment_ids: list[str] = None) -> list[MockRun]:
        """Search for runs"""
        runs = list(self._runs.values())
        if experiment_ids:
            runs = [r for r in runs if r.experiment_id in experiment_ids]
        return runs


class MLflowManager:
    """
    Manages MLflow tracking setup and operations.
    Falls back to mock client if MLflow is not available.
    """

    def __init__(self):
        self._client = None
        self._experiment_name = None
        self._experiment_id = None
        self._initialized = False
        self._use_mock = True

    def setup(self, tracking_uri: str = None, experiment_name: str = "erpx-accounting-copilot"):
        """
        Setup MLflow tracking.

        Args:
            tracking_uri: MLflow tracking server URI
            experiment_name: Experiment name
        """
        tracking_uri = tracking_uri or os.getenv("MLFLOW_TRACKING_URI")
        self._experiment_name = experiment_name

        if not tracking_uri:
            print("MLflow tracking URI not configured, using mock client")
            self._client = MockMLflowClient()
            self._use_mock = True
            self._setup_experiment()
            self._initialized = True
            return

        try:
            import mlflow

            mlflow.set_tracking_uri(tracking_uri)

            # Get or create experiment
            experiment = mlflow.get_experiment_by_name(experiment_name)
            if experiment is None:
                self._experiment_id = mlflow.create_experiment(experiment_name)
            else:
                self._experiment_id = experiment.experiment_id

            mlflow.set_experiment(experiment_name)

            self._client = mlflow
            self._use_mock = False
            self._initialized = True

            print(f"MLflow initialized: tracking_uri={tracking_uri}, experiment={experiment_name}")

        except ImportError:
            print("MLflow not installed, using mock client")
            self._client = MockMLflowClient()
            self._use_mock = True
            self._setup_experiment()
            self._initialized = True
        except Exception as e:
            print(f"Failed to initialize MLflow: {e}, using mock client")
            self._client = MockMLflowClient()
            self._use_mock = True
            self._setup_experiment()
            self._initialized = True

    def _setup_experiment(self):
        """Setup experiment for mock client"""
        if self._use_mock and self._client:
            exp = self._client.get_experiment_by_name(self._experiment_name)
            if exp is None:
                self._experiment_id = self._client.create_experiment(self._experiment_name)
            else:
                self._experiment_id = exp["experiment_id"]

    def get_client(self):
        """Get the MLflow client"""
        if not self._initialized:
            self.setup()
        return self._client

    def is_mock(self) -> bool:
        """Check if using mock client"""
        return self._use_mock

    def start_run(self, run_name: str = None):
        """Start a new run"""
        if self._use_mock:
            return self._client.start_run(self._experiment_id, run_name)
        else:
            return self._client.start_run(run_name=run_name)

    def end_run(self, status: str = "FINISHED"):
        """End the active run"""
        if self._use_mock:
            self._client.end_run(status)
        else:
            self._client.end_run(status=status)

    def log_params(self, params: dict[str, Any]):
        """Log parameters"""
        if self._use_mock:
            self._client.log_params(params)
        else:
            self._client.log_params(params)

    def log_metrics(self, metrics: dict[str, float]):
        """Log metrics"""
        if self._use_mock:
            self._client.log_metrics(metrics)
        else:
            self._client.log_metrics(metrics)

    def set_tag(self, key: str, value: str):
        """Set a tag"""
        if self._use_mock:
            self._client.set_tag(key, value)
        else:
            self._client.set_tag(key, value)


# Global MLflow manager
_mlflow_manager = MLflowManager()


def setup_mlflow(tracking_uri: str = None, experiment_name: str = "erpx-accounting-copilot"):
    """Setup MLflow globally"""
    _mlflow_manager.setup(tracking_uri, experiment_name)


def log_prediction(
    doc_id: str,
    doc_type: str,
    input_size: int,
    processing_time_ms: float,
    needs_review: bool,
    missing_fields_count: int,
    warnings_count: int,
    confidence: float = None,
    extra_params: dict[str, Any] = None,
    extra_metrics: dict[str, float] = None,
):
    """
    Log a prediction/processing event to MLflow.

    This is the main function for tracking copilot performance.
    """
    manager = _mlflow_manager
    if not manager._initialized:
        manager.setup()

    run_name = f"prediction_{doc_id}"
    manager.start_run(run_name)

    try:
        # Log parameters
        params = {
            "doc_id": doc_id,
            "doc_type": doc_type,
            "input_size": input_size,
        }
        if extra_params:
            params.update(extra_params)
        manager.log_params(params)

        # Log metrics
        metrics = {
            "processing_time_ms": processing_time_ms,
            "needs_review": 1.0 if needs_review else 0.0,
            "missing_fields_count": float(missing_fields_count),
            "warnings_count": float(warnings_count),
        }
        if confidence is not None:
            metrics["confidence"] = confidence
        if extra_metrics:
            metrics.update(extra_metrics)
        manager.log_metrics(metrics)

        # Set tags
        manager.set_tag("doc_type", doc_type)
        manager.set_tag("needs_review", str(needs_review))

        manager.end_run("FINISHED")

    except Exception:
        manager.end_run("FAILED")
        raise


def log_batch_processing(
    batch_id: str,
    total_docs: int,
    successful: int,
    failed: int,
    needs_review: int,
    total_time_ms: float,
    avg_time_per_doc_ms: float,
):
    """Log batch processing metrics"""
    manager = _mlflow_manager
    if not manager._initialized:
        manager.setup()

    run_name = f"batch_{batch_id}"
    manager.start_run(run_name)

    try:
        manager.log_params(
            {
                "batch_id": batch_id,
                "total_docs": total_docs,
            }
        )

        manager.log_metrics(
            {
                "successful": float(successful),
                "failed": float(failed),
                "needs_review": float(needs_review),
                "success_rate": successful / total_docs if total_docs > 0 else 0.0,
                "total_time_ms": total_time_ms,
                "avg_time_per_doc_ms": avg_time_per_doc_ms,
            }
        )

        manager.set_tag("type", "batch_processing")

        manager.end_run("FINISHED")

    except Exception:
        manager.end_run("FAILED")
        raise


if __name__ == "__main__":
    # Test MLflow tracking
    setup_mlflow()

    # Log a prediction
    log_prediction(
        doc_id="TEST-001",
        doc_type="receipt",
        input_size=1024,
        processing_time_ms=150.5,
        needs_review=False,
        missing_fields_count=0,
        warnings_count=1,
        confidence=0.95,
    )

    # Log batch
    log_batch_processing(
        batch_id="BATCH-001",
        total_docs=100,
        successful=95,
        failed=2,
        needs_review=3,
        total_time_ms=15000,
        avg_time_per_doc_ms=150,
    )

    print("MLflow tracking test complete")
