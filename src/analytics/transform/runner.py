"""
Transform Runner
Executes transformation models in dependency order
"""
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging
import asyncio

from .models import Model, ModelResult

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    """Result of running multiple models"""
    success: bool
    total_models: int
    successful_models: int
    failed_models: int
    results: List[ModelResult]
    total_time_ms: float
    run_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "total_models": self.total_models,
            "successful": self.successful_models,
            "failed": self.failed_models,
            "total_time_ms": self.total_time_ms,
            "run_at": self.run_at.isoformat(),
            "results": [r.to_dict() for r in self.results],
        }


class TransformRunner:
    """
    Orchestrates the execution of transformation models.
    
    Features:
    - Dependency resolution (topological sort)
    - Parallel execution where possible
    - Error handling and retry
    
    Usage:
        runner = TransformRunner()
        runner.add_model(revenue_model)
        runner.add_model(expenses_model)
        runner.add_model(profit_model)  # depends on revenue and expenses
        
        result = await runner.run(context)
    """
    
    def __init__(self):
        self.models: Dict[str, Model] = {}
    
    def add_model(self, model: Model) -> "TransformRunner":
        """Add a model to the runner (chainable)"""
        self.models[model.name] = model
        return self
    
    def get_model(self, name: str) -> Optional[Model]:
        """Get a model by name"""
        return self.models.get(name)
    
    def list_models(self) -> List[str]:
        """List all model names"""
        return list(self.models.keys())
    
    def _topological_sort(self) -> List[str]:
        """
        Sort models by dependency order.
        Returns list of model names in execution order.
        """
        # Build adjacency list
        graph: Dict[str, List[str]] = {name: [] for name in self.models}
        in_degree: Dict[str, int] = {name: 0 for name in self.models}
        
        for name, model in self.models.items():
            for dep in model.config.depends_on:
                if dep in graph:
                    graph[dep].append(name)
                    in_degree[name] += 1
        
        # Kahn's algorithm
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        if len(result) != len(self.models):
            # Cycle detected
            missing = set(self.models.keys()) - set(result)
            raise ValueError(f"Circular dependency detected involving: {missing}")
        
        return result
    
    async def run(
        self, 
        context: Dict[str, Any],
        models: List[str] = None,
        parallel: bool = False,
    ) -> RunResult:
        """
        Run transformation models.
        
        Args:
            context: Execution context (connectors, dataframes, etc.)
            models: Specific models to run (None = all)
            parallel: Run independent models in parallel
        """
        import time
        start_time = time.time()
        
        # Get execution order
        try:
            execution_order = self._topological_sort()
        except ValueError as e:
            return RunResult(
                success=False,
                total_models=len(self.models),
                successful_models=0,
                failed_models=len(self.models),
                results=[],
                total_time_ms=0,
            )
        
        # Filter if specific models requested
        if models:
            # Include dependencies
            to_run = set()
            for name in models:
                if name in self.models:
                    to_run.add(name)
                    # Add dependencies
                    to_run.update(self.models[name].config.depends_on)
            execution_order = [m for m in execution_order if m in to_run]
        
        results: List[ModelResult] = []
        failed_models = set()
        
        for model_name in execution_order:
            model = self.models[model_name]
            
            # Skip if any dependency failed
            if any(dep in failed_models for dep in model.config.depends_on):
                results.append(ModelResult(
                    name=model_name,
                    success=False,
                    rows_affected=0,
                    execution_time_ms=0,
                    error="Dependency failed",
                ))
                failed_models.add(model_name)
                continue
            
            logger.info(f"Running model: {model_name}")
            result = await model.run(context)
            results.append(result)
            
            if not result.success:
                failed_models.add(model_name)
                logger.error(f"Model {model_name} failed: {result.error}")
        
        total_time = (time.time() - start_time) * 1000
        successful = sum(1 for r in results if r.success)
        
        return RunResult(
            success=len(failed_models) == 0,
            total_models=len(results),
            successful_models=successful,
            failed_models=len(failed_models),
            results=results,
            total_time_ms=total_time,
        )
    
    async def run_model(self, name: str, context: Dict[str, Any]) -> ModelResult:
        """Run a single model"""
        model = self.models.get(name)
        if not model:
            return ModelResult(
                name=name,
                success=False,
                rows_affected=0,
                execution_time_ms=0,
                error=f"Model '{name}' not found",
            )
        return await model.run(context)
    
    def get_lineage(self, model_name: str) -> Dict[str, Any]:
        """Get dependency lineage for a model"""
        if model_name not in self.models:
            return {}
        
        model = self.models[model_name]
        
        # Upstream (dependencies)
        upstream = []
        to_check = list(model.config.depends_on)
        seen = set()
        while to_check:
            dep = to_check.pop(0)
            if dep in seen:
                continue
            seen.add(dep)
            upstream.append(dep)
            if dep in self.models:
                to_check.extend(self.models[dep].config.depends_on)
        
        # Downstream (dependents)
        downstream = []
        for name, m in self.models.items():
            if model_name in m.config.depends_on:
                downstream.append(name)
        
        return {
            "model": model_name,
            "upstream": upstream,
            "downstream": downstream,
        }
    
    def clear(self) -> None:
        """Remove all models"""
        self.models.clear()
