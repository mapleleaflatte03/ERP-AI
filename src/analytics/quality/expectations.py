"""
Data Quality Expectations
Great Expectations-style validation rules
"""
import pandas as pd
from typing import Any, List, Optional
from .validator import ValidationRule, ValidationResult


class ExpectColumnToExist(ValidationRule):
    """Expect a column to exist in the DataFrame"""
    
    def __init__(self, column: str):
        super().__init__(column=column)
        self.column = column
    
    @property
    def name(self) -> str:
        return f"expect_column_to_exist({self.column})"
    
    def validate(self, df: pd.DataFrame) -> ValidationResult:
        exists = self.column in df.columns
        return ValidationResult(
            rule_name=self.name,
            success=exists,
            message=f"Column '{self.column}' {'exists' if exists else 'does not exist'}",
            column=self.column,
            observed_value=list(df.columns) if not exists else None,
        )


class ExpectColumnValuesNotNull(ValidationRule):
    """Expect column values to not be null (within threshold)"""
    
    def __init__(self, column: str, threshold: float = 0.0):
        super().__init__(column=column, threshold=threshold)
        self.column = column
        self.threshold = threshold  # Max allowed null ratio
    
    @property
    def name(self) -> str:
        return f"expect_column_values_not_null({self.column})"
    
    def validate(self, df: pd.DataFrame) -> ValidationResult:
        if self.column not in df.columns:
            return ValidationResult(
                rule_name=self.name,
                success=False,
                message=f"Column '{self.column}' does not exist",
                column=self.column,
            )
        
        null_count = df[self.column].isnull().sum()
        null_ratio = null_count / len(df) if len(df) > 0 else 0
        success = null_ratio <= self.threshold
        
        return ValidationResult(
            rule_name=self.name,
            success=success,
            message=f"Column '{self.column}' has {null_ratio:.2%} nulls (threshold: {self.threshold:.2%})",
            column=self.column,
            observed_value=null_ratio,
            expected_value=f"<= {self.threshold}",
            details={"null_count": int(null_count), "total_count": len(df)},
        )


class ExpectColumnValuesUnique(ValidationRule):
    """Expect column values to be unique"""
    
    def __init__(self, column: str):
        super().__init__(column=column)
        self.column = column
    
    @property
    def name(self) -> str:
        return f"expect_column_values_unique({self.column})"
    
    def validate(self, df: pd.DataFrame) -> ValidationResult:
        if self.column not in df.columns:
            return ValidationResult(
                rule_name=self.name,
                success=False,
                message=f"Column '{self.column}' does not exist",
                column=self.column,
            )
        
        total = len(df)
        unique = df[self.column].nunique()
        duplicates = total - unique
        success = duplicates == 0
        
        return ValidationResult(
            rule_name=self.name,
            success=success,
            message=f"Column '{self.column}' has {duplicates} duplicate values",
            column=self.column,
            observed_value=unique,
            expected_value=total,
            details={"duplicates": duplicates, "unique_ratio": unique / total if total > 0 else 0},
        )


class ExpectColumnValuesInRange(ValidationRule):
    """Expect numeric column values to be within a range"""
    
    def __init__(self, column: str, min_value: float = None, max_value: float = None):
        super().__init__(column=column, min_value=min_value, max_value=max_value)
        self.column = column
        self.min_value = min_value
        self.max_value = max_value
    
    @property
    def name(self) -> str:
        range_str = f"[{self.min_value}, {self.max_value}]"
        return f"expect_column_values_in_range({self.column}, {range_str})"
    
    def validate(self, df: pd.DataFrame) -> ValidationResult:
        if self.column not in df.columns:
            return ValidationResult(
                rule_name=self.name,
                success=False,
                message=f"Column '{self.column}' does not exist",
                column=self.column,
            )
        
        col_data = df[self.column].dropna()
        
        if not pd.api.types.is_numeric_dtype(col_data):
            return ValidationResult(
                rule_name=self.name,
                success=False,
                message=f"Column '{self.column}' is not numeric",
                column=self.column,
            )
        
        violations = 0
        if self.min_value is not None:
            violations += (col_data < self.min_value).sum()
        if self.max_value is not None:
            violations += (col_data > self.max_value).sum()
        
        success = violations == 0
        actual_min = col_data.min() if len(col_data) > 0 else None
        actual_max = col_data.max() if len(col_data) > 0 else None
        
        return ValidationResult(
            rule_name=self.name,
            success=success,
            message=f"Column '{self.column}' has {violations} values outside range",
            column=self.column,
            observed_value=f"[{actual_min}, {actual_max}]",
            expected_value=f"[{self.min_value}, {self.max_value}]",
            details={"violations": int(violations), "min": actual_min, "max": actual_max},
        )


class ExpectColumnValuesInSet(ValidationRule):
    """Expect column values to be in a predefined set"""
    
    def __init__(self, column: str, value_set: List[Any]):
        super().__init__(column=column, value_set=value_set)
        self.column = column
        self.value_set = set(value_set)
    
    @property
    def name(self) -> str:
        return f"expect_column_values_in_set({self.column})"
    
    def validate(self, df: pd.DataFrame) -> ValidationResult:
        if self.column not in df.columns:
            return ValidationResult(
                rule_name=self.name,
                success=False,
                message=f"Column '{self.column}' does not exist",
                column=self.column,
            )
        
        col_data = df[self.column].dropna()
        unique_values = set(col_data.unique())
        unexpected = unique_values - self.value_set
        
        success = len(unexpected) == 0
        
        return ValidationResult(
            rule_name=self.name,
            success=success,
            message=f"Column '{self.column}' has {len(unexpected)} unexpected values",
            column=self.column,
            observed_value=list(unique_values)[:10],
            expected_value=list(self.value_set)[:10],
            details={"unexpected_values": list(unexpected)[:10]},
        )


class ExpectTableRowCountBetween(ValidationRule):
    """Expect table row count to be within a range"""
    
    def __init__(self, min_rows: int = None, max_rows: int = None):
        super().__init__(min_rows=min_rows, max_rows=max_rows)
        self.min_rows = min_rows
        self.max_rows = max_rows
    
    @property
    def name(self) -> str:
        return f"expect_table_row_count_between({self.min_rows}, {self.max_rows})"
    
    def validate(self, df: pd.DataFrame) -> ValidationResult:
        row_count = len(df)
        
        success = True
        if self.min_rows is not None and row_count < self.min_rows:
            success = False
        if self.max_rows is not None and row_count > self.max_rows:
            success = False
        
        return ValidationResult(
            rule_name=self.name,
            success=success,
            message=f"Table has {row_count} rows",
            observed_value=row_count,
            expected_value=f"[{self.min_rows}, {self.max_rows}]",
        )


class ExpectColumnValuesToBeDatetime(ValidationRule):
    """Expect column to contain datetime values"""
    
    def __init__(self, column: str):
        super().__init__(column=column)
        self.column = column
    
    @property
    def name(self) -> str:
        return f"expect_column_values_to_be_datetime({self.column})"
    
    def validate(self, df: pd.DataFrame) -> ValidationResult:
        if self.column not in df.columns:
            return ValidationResult(
                rule_name=self.name,
                success=False,
                message=f"Column '{self.column}' does not exist",
                column=self.column,
            )
        
        try:
            pd.to_datetime(df[self.column])
            success = True
            message = f"Column '{self.column}' can be parsed as datetime"
        except Exception as e:
            success = False
            message = f"Column '{self.column}' cannot be parsed as datetime: {e}"
        
        return ValidationResult(
            rule_name=self.name,
            success=success,
            message=message,
            column=self.column,
            observed_value=str(df[self.column].dtype),
        )
