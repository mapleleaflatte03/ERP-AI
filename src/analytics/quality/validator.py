"""
Data Validator
Great Expectations-inspired data validation framework
"""
import pandas as pd
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a single validation rule"""
    rule_name: str
    success: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    column: Optional[str] = None
    observed_value: Any = None
    expected_value: Any = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule": self.rule_name,
            "success": self.success,
            "message": self.message,
            "column": self.column,
            "observed": self.observed_value,
            "expected": self.expected_value,
            "details": self.details,
        }


@dataclass
class ValidationSuite:
    """Collection of validation results"""
    name: str
    success: bool
    results: List[ValidationResult]
    run_time: datetime = field(default_factory=datetime.utcnow)
    statistics: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.success)
    
    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if not r.success)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "success": self.success,
            "run_time": self.run_time.isoformat(),
            "passed": self.passed_count,
            "failed": self.failed_count,
            "results": [r.to_dict() for r in self.results],
            "statistics": self.statistics,
        }


class ValidationRule(ABC):
    """Base class for validation rules"""
    
    def __init__(self, **kwargs):
        self.kwargs = kwargs
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Rule name for reporting"""
        pass
    
    @abstractmethod
    def validate(self, df: pd.DataFrame) -> ValidationResult:
        """Execute validation and return result"""
        pass


class DataValidator:
    """
    Data quality validator inspired by Great Expectations.
    
    Usage:
        validator = DataValidator("sales_data")
        validator.add_rule(ExpectColumnToExist("amount"))
        validator.add_rule(ExpectColumnValuesNotNull("amount"))
        validator.add_rule(ExpectColumnValuesInRange("amount", min_value=0))
        
        result = validator.validate(df)
        if not result.success:
            print(f"Validation failed: {result.failed_count} rules failed")
    """
    
    def __init__(self, name: str):
        self.name = name
        self.rules: List[ValidationRule] = []
    
    def add_rule(self, rule: ValidationRule) -> "DataValidator":
        """Add a validation rule (chainable)"""
        self.rules.append(rule)
        return self
    
    def expect_column_to_exist(self, column: str) -> "DataValidator":
        """Add column existence check"""
        from .expectations import ExpectColumnToExist
        return self.add_rule(ExpectColumnToExist(column))
    
    def expect_column_values_not_null(self, column: str, threshold: float = 0.0) -> "DataValidator":
        """Add null check for column"""
        from .expectations import ExpectColumnValuesNotNull
        return self.add_rule(ExpectColumnValuesNotNull(column, threshold=threshold))
    
    def expect_column_values_unique(self, column: str) -> "DataValidator":
        """Add uniqueness check for column"""
        from .expectations import ExpectColumnValuesUnique
        return self.add_rule(ExpectColumnValuesUnique(column))
    
    def expect_column_values_in_range(
        self, 
        column: str, 
        min_value: float = None, 
        max_value: float = None
    ) -> "DataValidator":
        """Add range check for numeric column"""
        from .expectations import ExpectColumnValuesInRange
        return self.add_rule(ExpectColumnValuesInRange(column, min_value=min_value, max_value=max_value))
    
    def expect_column_values_in_set(self, column: str, value_set: List[Any]) -> "DataValidator":
        """Add set membership check for column"""
        from .expectations import ExpectColumnValuesInSet
        return self.add_rule(ExpectColumnValuesInSet(column, value_set=value_set))
    
    def expect_table_row_count_between(self, min_rows: int = None, max_rows: int = None) -> "DataValidator":
        """Add row count check"""
        from .expectations import ExpectTableRowCountBetween
        return self.add_rule(ExpectTableRowCountBetween(min_rows=min_rows, max_rows=max_rows))
    
    def validate(self, df: pd.DataFrame) -> ValidationSuite:
        """Run all validation rules against the DataFrame"""
        results = []
        
        for rule in self.rules:
            try:
                result = rule.validate(df)
                results.append(result)
            except Exception as e:
                results.append(ValidationResult(
                    rule_name=rule.name,
                    success=False,
                    message=f"Validation error: {str(e)}",
                ))
        
        # Calculate statistics
        stats = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "total_rules": len(self.rules),
            "memory_bytes": df.memory_usage(deep=True).sum(),
        }
        
        all_passed = all(r.success for r in results)
        
        suite = ValidationSuite(
            name=self.name,
            success=all_passed,
            results=results,
            statistics=stats,
        )
        
        if not all_passed:
            failed = [r for r in results if not r.success]
            logger.warning(f"Validation '{self.name}' failed: {len(failed)} rules failed")
        else:
            logger.info(f"Validation '{self.name}' passed: all {len(results)} rules passed")
        
        return suite
    
    def clear_rules(self) -> None:
        """Clear all rules"""
        self.rules.clear()
    
    @classmethod
    def from_schema(cls, name: str, schema: Dict[str, Any]) -> "DataValidator":
        """
        Create validator from a schema definition.
        
        Schema format:
        {
            "columns": {
                "id": {"type": "int", "required": True, "unique": True},
                "amount": {"type": "float", "required": True, "min": 0},
                "status": {"type": "str", "values": ["pending", "completed"]}
            }
        }
        """
        validator = cls(name)
        
        for col_name, constraints in schema.get("columns", {}).items():
            validator.expect_column_to_exist(col_name)
            
            if constraints.get("required"):
                validator.expect_column_values_not_null(col_name)
            
            if constraints.get("unique"):
                validator.expect_column_values_unique(col_name)
            
            if "min" in constraints or "max" in constraints:
                validator.expect_column_values_in_range(
                    col_name,
                    min_value=constraints.get("min"),
                    max_value=constraints.get("max"),
                )
            
            if "values" in constraints:
                validator.expect_column_values_in_set(col_name, constraints["values"])
        
        if "min_rows" in schema or "max_rows" in schema:
            validator.expect_table_row_count_between(
                min_rows=schema.get("min_rows"),
                max_rows=schema.get("max_rows"),
            )
        
        return validator
