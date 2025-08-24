"""Base classes for data cleaning operations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from scraper.core.logger import get_logger, LoggerMixin


class BaseCleaner(ABC, LoggerMixin):
    """Abstract base class for data cleaners."""
    
    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self._stats = {}
    
    @abstractmethod
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean the DataFrame and return the result."""
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cleaning statistics."""
        return self._stats.copy()
    
    def reset_stats(self) -> None:
        """Reset cleaning statistics."""
        self._stats = {}


class CleaningPipeline(LoggerMixin):
    """Pipeline for applying multiple cleaning operations."""
    
    def __init__(self, cleaners: Optional[List[BaseCleaner]] = None):
        super().__init__()
        self.cleaners = cleaners or []
        self._pipeline_stats = {}
    
    def add_cleaner(self, cleaner: BaseCleaner) -> "CleaningPipeline":
        """Add a cleaner to the pipeline."""
        self.cleaners.append(cleaner)
        return self
    
    def clean(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Apply all cleaners in sequence.
        
        Returns:
            Tuple of (cleaned_dataframe, cleaning_stats)
        """
        self.log_info(f"Starting cleaning pipeline with {len(self.cleaners)} cleaners",
                     initial_rows=len(df),
                     initial_columns=len(df.columns))
        
        current_df = df.copy()
        initial_rows = len(current_df)
        
        # Reset stats
        self._pipeline_stats = {
            'initial_rows': initial_rows,
            'initial_columns': len(df.columns),
            'cleaners_applied': [],
            'final_rows': 0,
            'final_columns': 0,
            'total_rows_removed': 0,
            'cleaning_summary': {}
        }
        
        # Apply each cleaner
        for cleaner in self.cleaners:
            rows_before = len(current_df)
            
            self.log_info(f"Applying cleaner: {cleaner.name}",
                         cleaner=cleaner.name,
                         rows_before=rows_before)
            
            # Apply cleaner
            current_df = cleaner.clean(current_df)
            
            rows_after = len(current_df)
            rows_removed = rows_before - rows_after
            
            # Record stats
            cleaner_stats = {
                'rows_before': rows_before,
                'rows_after': rows_after,
                'rows_removed': rows_removed,
                'cleaner_stats': cleaner.get_stats()
            }
            
            self._pipeline_stats['cleaners_applied'].append({
                'name': cleaner.name,
                'stats': cleaner_stats
            })
            
            self._pipeline_stats['cleaning_summary'][cleaner.name] = cleaner_stats
            
            self.log_info(f"Cleaner {cleaner.name} completed",
                         rows_removed=rows_removed,
                         rows_remaining=rows_after)
        
        # Final stats
        final_rows = len(current_df)
        self._pipeline_stats['final_rows'] = final_rows
        self._pipeline_stats['final_columns'] = len(current_df.columns)
        self._pipeline_stats['total_rows_removed'] = initial_rows - final_rows
        
        self.log_info("Cleaning pipeline completed",
                     total_rows_removed=self._pipeline_stats['total_rows_removed'],
                     final_rows=final_rows,
                     cleaners_count=len(self.cleaners))
        
        return current_df, self._pipeline_stats
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        return self._pipeline_stats.copy()


class DataValidator(LoggerMixin):
    """Validate data quality and structure."""
    
    def __init__(self):
        super().__init__()
    
    def validate_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Validate DataFrame structure and content.
        
        Returns:
            Validation report with issues and recommendations
        """
        report = {
            'is_valid': True,
            'issues': [],
            'warnings': [],
            'recommendations': [],
            'statistics': {
                'total_rows': len(df),
                'total_columns': len(df.columns),
                'empty_rows': 0,
                'duplicate_rows': 0,
                'columns_with_nulls': 0,
                'memory_usage_mb': 0
            }
        }
        
        # Check for empty DataFrame
        if df.empty:
            report['issues'].append("DataFrame is empty")
            report['is_valid'] = False
            return report
        
        # Check for empty rows
        empty_rows = df.isnull().all(axis=1).sum()
        report['statistics']['empty_rows'] = empty_rows
        if empty_rows > 0:
            report['warnings'].append(f"{empty_rows} completely empty rows found")
        
        # Check for duplicate rows
        duplicate_rows = df.duplicated().sum()
        report['statistics']['duplicate_rows'] = duplicate_rows
        if duplicate_rows > 0:
            report['warnings'].append(f"{duplicate_rows} duplicate rows found")
            report['recommendations'].append("Consider using DuplicateCleaner")
        
        # Check for columns with high null percentage
        null_percentages = df.isnull().mean()
        high_null_columns = null_percentages[null_percentages > 0.8].index.tolist()
        if high_null_columns:
            report['warnings'].append(f"Columns with >80% null values: {high_null_columns}")
            report['recommendations'].append("Consider removing columns with excessive null values")
        
        report['statistics']['columns_with_nulls'] = (null_percentages > 0).sum()
        
        # Memory usage
        memory_usage = df.memory_usage(deep=True).sum() / 1024 / 1024  # Convert to MB
        report['statistics']['memory_usage_mb'] = round(memory_usage, 2)
        
        # Check for required columns for scraping
        required_columns = ['company_name', 'domain']
        missing_required = [col for col in required_columns if col not in df.columns]
        if missing_required:
            if 'company_name' in missing_required and 'domain' in missing_required:
                report['issues'].append("Neither 'company_name' nor 'domain' column found")
                report['is_valid'] = False
            else:
                report['warnings'].append(f"Missing recommended columns: {missing_required}")
        
        # Check data types
        object_columns = df.select_dtypes(include=['object']).columns
        if len(object_columns) == len(df.columns):
            report['recommendations'].append("Consider type inference for better performance")
        
        self.log_info("Data validation completed",
                     is_valid=report['is_valid'],
                     issues_count=len(report['issues']),
                     warnings_count=len(report['warnings']))
        
        return report
    
    def suggest_cleaning_pipeline(self, df: pd.DataFrame) -> List[str]:
        """Suggest appropriate cleaners based on data analysis."""
        suggestions = []
        
        # Always suggest duplicate removal
        if df.duplicated().any():
            suggestions.append("DuplicateCleaner")
        
        # Suggest null handling if there are nulls
        if df.isnull().any().any():
            suggestions.append("NullCleaner")
        
        # Suggest type cleaning if all columns are objects
        object_columns = df.select_dtypes(include=['object']).columns
        if len(object_columns) > len(df.columns) * 0.5:
            suggestions.append("TypeCleaner")
        
        # Suggest email cleaning if email column exists
        if any('email' in col.lower() for col in df.columns):
            suggestions.append("EmailCleaner")
        
        # Suggest domain cleaning if domain/website columns exist
        domain_cols = [col for col in df.columns if any(term in col.lower() 
                      for term in ['domain', 'website', 'url', 'site'])]
        if domain_cols:
            suggestions.append("DomainCleaner")
        
        return suggestions


# Factory function for common cleaning pipelines
def create_standard_pipeline() -> CleaningPipeline:
    """Create a standard cleaning pipeline."""
    from scraper.data.cleaner.duplicates import DuplicateCleaner
    from scraper.data.cleaner.datatypes import TypeCleaner
    
    pipeline = CleaningPipeline([
        DuplicateCleaner(),
        TypeCleaner(),
    ])
    
    return pipeline