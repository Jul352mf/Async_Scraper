"""Duplicate removal cleaner."""

from typing import Dict, List, Optional

import pandas as pd

from scraper.data.cleaner.base import BaseCleaner


class DuplicateCleaner(BaseCleaner):
    """Remove duplicate rows from DataFrame."""
    
    def __init__(self, 
                 subset: Optional[List[str]] = None,
                 keep: str = 'first',
                 ignore_case: bool = True):
        """
        Initialize duplicate cleaner.
        
        Args:
            subset: Columns to use for duplicate detection. None means all columns.
            keep: Which duplicate to keep ('first', 'last', False for remove all)
            ignore_case: Whether to ignore case when comparing string values
        """
        super().__init__("DuplicateCleaner")
        self.subset = subset
        self.keep = keep
        self.ignore_case = ignore_case
    
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicates from DataFrame."""
        initial_rows = len(df)
        
        # Make a copy to avoid modifying original
        cleaned_df = df.copy()
        
        # Prepare DataFrame for duplicate detection
        if self.ignore_case:
            # Create a temporary DataFrame with lowercase string columns for comparison
            comparison_df = cleaned_df.copy()
            for col in comparison_df.columns:
                if comparison_df[col].dtype == 'object':
                    comparison_df[col] = comparison_df[col].astype(str).str.lower().str.strip()
            
            # Find duplicates using comparison DataFrame
            if self.subset:
                # Ensure subset columns exist
                available_subset = [col for col in self.subset if col in comparison_df.columns]
                if available_subset:
                    duplicates = comparison_df.duplicated(subset=available_subset, keep=self.keep)
                else:
                    duplicates = comparison_df.duplicated(keep=self.keep)
            else:
                duplicates = comparison_df.duplicated(keep=self.keep)
            
            # Apply duplicate mask to original DataFrame
            cleaned_df = cleaned_df[~duplicates]
        else:
            # Standard duplicate removal
            if self.subset:
                available_subset = [col for col in self.subset if col in cleaned_df.columns]
                if available_subset:
                    cleaned_df = cleaned_df.drop_duplicates(subset=available_subset, keep=self.keep)
                else:
                    cleaned_df = cleaned_df.drop_duplicates(keep=self.keep)
            else:
                cleaned_df = cleaned_df.drop_duplicates(keep=self.keep)
        
        final_rows = len(cleaned_df)
        duplicates_removed = initial_rows - final_rows
        
        # Update stats
        self._stats = {
            'initial_rows': initial_rows,
            'final_rows': final_rows,
            'duplicates_removed': duplicates_removed,
            'duplicate_percentage': round((duplicates_removed / initial_rows * 100), 2) if initial_rows > 0 else 0,
            'subset_columns': self.subset,
            'keep_strategy': self.keep,
            'ignore_case': self.ignore_case
        }
        
        self.log_info(f"Removed {duplicates_removed} duplicate rows",
                     duplicates_removed=duplicates_removed,
                     duplicate_percentage=self._stats['duplicate_percentage'])
        
        return cleaned_df


class SmartDuplicateCleaner(BaseCleaner):
    """Smart duplicate cleaner that handles various duplicate scenarios."""
    
    def __init__(self):
        super().__init__("SmartDuplicateCleaner")
    
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Intelligently remove duplicates using multiple strategies."""
        initial_rows = len(df)
        cleaned_df = df.copy()
        
        # Strategy 1: Remove exact duplicates
        exact_duplicates_before = len(cleaned_df)
        cleaned_df = cleaned_df.drop_duplicates()
        exact_duplicates_removed = exact_duplicates_before - len(cleaned_df)
        
        # Strategy 2: Remove duplicates based on key business columns
        if self._has_business_columns(cleaned_df):
            business_duplicates_before = len(cleaned_df)
            cleaned_df = self._remove_business_duplicates(cleaned_df)
            business_duplicates_removed = business_duplicates_before - len(cleaned_df)
        else:
            business_duplicates_removed = 0
        
        # Strategy 3: Remove similar entries (fuzzy matching)
        if self._should_apply_fuzzy_matching(cleaned_df):
            fuzzy_duplicates_before = len(cleaned_df)
            cleaned_df = self._remove_fuzzy_duplicates(cleaned_df)
            fuzzy_duplicates_removed = fuzzy_duplicates_before - len(cleaned_df)
        else:
            fuzzy_duplicates_removed = 0
        
        final_rows = len(cleaned_df)
        total_removed = initial_rows - final_rows
        
        # Update stats
        self._stats = {
            'initial_rows': initial_rows,
            'final_rows': final_rows,
            'total_duplicates_removed': total_removed,
            'exact_duplicates_removed': exact_duplicates_removed,
            'business_duplicates_removed': business_duplicates_removed,
            'fuzzy_duplicates_removed': fuzzy_duplicates_removed,
            'removal_percentage': round((total_removed / initial_rows * 100), 2) if initial_rows > 0 else 0
        }
        
        self.log_info(f"Smart duplicate removal completed",
                     total_removed=total_removed,
                     exact_duplicates=exact_duplicates_removed,
                     business_duplicates=business_duplicates_removed,
                     fuzzy_duplicates=fuzzy_duplicates_removed)
        
        return cleaned_df
    
    def _has_business_columns(self, df: pd.DataFrame) -> bool:
        """Check if DataFrame has business-relevant columns."""
        business_columns = ['company_name', 'domain', 'email']
        return any(col in df.columns for col in business_columns)
    
    def _remove_business_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicates based on business logic."""
        # Priority columns for duplicate detection
        priority_columns = []
        
        # Check for domain column (highest priority)
        if 'domain' in df.columns:
            priority_columns.append('domain')
        
        # Check for company name
        if 'company_name' in df.columns:
            priority_columns.append('company_name')
        
        # Check for email
        if 'email' in df.columns:
            priority_columns.append('email')
        
        if priority_columns:
            # Remove duplicates based on priority columns, keeping first occurrence
            return df.drop_duplicates(subset=priority_columns, keep='first')
        
        return df
    
    def _should_apply_fuzzy_matching(self, df: pd.DataFrame) -> bool:
        """Determine if fuzzy matching should be applied."""
        # Only apply fuzzy matching if:
        # 1. Dataset is not too large (performance consideration)
        # 2. Has string columns that might benefit from fuzzy matching
        
        if len(df) > 10000:  # Skip for large datasets
            return False
        
        string_columns = df.select_dtypes(include=['object']).columns
        business_string_columns = [col for col in string_columns 
                                 if any(term in col.lower() 
                                       for term in ['company', 'name', 'domain'])]
        
        return len(business_string_columns) > 0
    
    def _remove_fuzzy_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove fuzzy duplicates using string similarity."""
        try:
            from rapidfuzz import fuzz
        except ImportError:
            self.log_warning("rapidfuzz not available, skipping fuzzy duplicate removal")
            return df
        
        # Focus on company name column for fuzzy matching
        if 'company_name' not in df.columns:
            return df
        
        # Create a list to store indices to remove
        indices_to_remove = set()
        
        company_names = df['company_name'].dropna().astype(str)
        
        for i, name1 in enumerate(company_names):
            if i in indices_to_remove:
                continue
                
            for j, name2 in enumerate(company_names):
                if i >= j or j in indices_to_remove:
                    continue
                
                # Calculate similarity
                similarity = fuzz.ratio(name1.lower().strip(), name2.lower().strip())
                
                # If very similar (>90% similarity), consider as duplicate
                if similarity > 90:
                    # Keep the one with more information (more non-null columns)
                    row1_info = df.iloc[i].count()
                    row2_info = df.iloc[j].count()
                    
                    if row1_info >= row2_info:
                        indices_to_remove.add(j)
                    else:
                        indices_to_remove.add(i)
        
        # Remove fuzzy duplicates
        if indices_to_remove:
            cleaned_df = df.drop(df.index[list(indices_to_remove)])
            return cleaned_df
        
        return df