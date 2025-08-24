"""Data type inference and cleaning."""

from typing import Dict, List, Optional

import pandas as pd
import numpy as np

from scraper.data.cleaner.base import BaseCleaner


class TypeCleaner(BaseCleaner):
    """Clean and infer appropriate data types."""
    
    def __init__(self, 
                 aggressive_conversion: bool = False,
                 handle_mixed_types: bool = True):
        """
        Initialize type cleaner.
        
        Args:
            aggressive_conversion: Whether to aggressively convert types
            handle_mixed_types: Whether to handle mixed data types in columns
        """
        super().__init__("TypeCleaner")
        self.aggressive_conversion = aggressive_conversion
        self.handle_mixed_types = handle_mixed_types
    
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and infer data types."""
        initial_memory = df.memory_usage(deep=True).sum()
        cleaned_df = df.copy()
        
        type_conversions = {}
        
        for column in cleaned_df.columns:
            original_dtype = cleaned_df[column].dtype
            new_dtype, converted_series = self._infer_and_convert_type(
                cleaned_df[column], column
            )
            
            if new_dtype != original_dtype:
                cleaned_df[column] = converted_series
                type_conversions[column] = {
                    'from': str(original_dtype),
                    'to': str(new_dtype)
                }
        
        final_memory = cleaned_df.memory_usage(deep=True).sum()
        memory_saved = initial_memory - final_memory
        
        # Update stats
        self._stats = {
            'columns_converted': len(type_conversions),
            'type_conversions': type_conversions,
            'initial_memory_bytes': initial_memory,
            'final_memory_bytes': final_memory,
            'memory_saved_bytes': memory_saved,
            'memory_saved_percentage': round((memory_saved / initial_memory * 100), 2) if initial_memory > 0 else 0
        }
        
        self.log_info(f"Type cleaning completed",
                     columns_converted=len(type_conversions),
                     memory_saved_mb=round(memory_saved / 1024 / 1024, 2))
        
        return cleaned_df
    
    def _infer_and_convert_type(self, series: pd.Series, column_name: str) -> tuple:
        """Infer and convert the appropriate type for a series."""
        original_dtype = series.dtype
        
        # Skip if already numeric or datetime
        if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_datetime64_any_dtype(series):
            return original_dtype, series
        
        # Clean the series first
        cleaned_series = self._clean_series_for_type_inference(series, column_name)
        
        # Try different type conversions in order of priority
        converters = [
            self._try_boolean_conversion,
            self._try_numeric_conversion,
            self._try_datetime_conversion,
            self._try_category_conversion,
            self._optimize_string_type
        ]
        
        for converter in converters:
            try:
                result = converter(cleaned_series, column_name)
                if result is not None:
                    new_dtype, converted_series = result
                    if new_dtype != original_dtype:
                        return new_dtype, converted_series
            except Exception as e:
                self.log_debug(f"Type conversion failed for {column_name}",
                             converter=converter.__name__,
                             error=str(e))
                continue
        
        # Return original if no conversion was successful
        return original_dtype, series
    
    def _clean_series_for_type_inference(self, series: pd.Series, column_name: str) -> pd.Series:
        """Clean series data before type inference."""
        # Convert to string first to handle mixed types
        cleaned = series.astype(str)
        
        # Replace common null representations
        null_values = ['nan', 'none', 'null', 'n/a', 'na', '', ' ', 'undefined']
        for null_val in null_values:
            cleaned = cleaned.replace(null_val.lower(), pd.NA)
            cleaned = cleaned.replace(null_val.upper(), pd.NA)
        
        # Strip whitespace
        cleaned = cleaned.str.strip()
        
        # Handle specific column types
        if 'email' in column_name.lower():
            cleaned = self._clean_email_column(cleaned)
        elif 'phone' in column_name.lower():
            cleaned = self._clean_phone_column(cleaned)
        elif 'domain' in column_name.lower() or 'website' in column_name.lower():
            cleaned = self._clean_domain_column(cleaned)
        
        return cleaned
    
    def _try_boolean_conversion(self, series: pd.Series, column_name: str) -> Optional[tuple]:
        """Try to convert to boolean."""
        unique_values = set(series.dropna().str.lower().unique())
        
        # Check if values look boolean-ish
        boolean_values = {'true', 'false', 'yes', 'no', '1', '0', 'y', 'n'}
        
        if unique_values.issubset(boolean_values) and len(unique_values) <= 4:
            # Create mapping
            bool_map = {
                'true': True, 'yes': True, '1': True, 'y': True,
                'false': False, 'no': False, '0': False, 'n': False
            }
            
            converted = series.str.lower().map(bool_map)
            return converted.dtype, converted
        
        return None
    
    def _try_numeric_conversion(self, series: pd.Series, column_name: str) -> Optional[tuple]:
        """Try to convert to numeric."""
        # Clean numeric strings
        numeric_series = series.copy()
        
        # Remove common non-numeric characters
        if numeric_series.dtype == 'object':
            # Remove currency symbols, commas, parentheses
            numeric_series = numeric_series.str.replace(r'[$€£¥,()]', '', regex=True)
            # Handle percentage
            is_percentage = numeric_series.str.contains('%', na=False).any()
            if is_percentage:
                numeric_series = numeric_series.str.replace('%', '')
        
        # Try to convert to numeric
        numeric_converted = pd.to_numeric(numeric_series, errors='coerce')
        
        # Check if conversion was successful (not too many NaNs)
        non_null_original = series.count()
        non_null_converted = numeric_converted.count()
        
        if non_null_converted > 0 and (non_null_converted / non_null_original) > 0.8:
            # Apply percentage conversion if needed
            if is_percentage:
                numeric_converted = numeric_converted / 100
            
            # Choose appropriate numeric type
            if numeric_converted.dtype == 'float64':
                # Check if all values are integers
                if numeric_converted.dropna().apply(lambda x: x.is_integer()).all():
                    # Try to convert to smallest integer type
                    min_val = numeric_converted.min()
                    max_val = numeric_converted.max()
                    
                    if min_val >= 0:  # Unsigned integers
                        if max_val <= 255:
                            return np.dtype('uint8'), numeric_converted.astype('uint8')
                        elif max_val <= 65535:
                            return np.dtype('uint16'), numeric_converted.astype('uint16')
                        elif max_val <= 4294967295:
                            return np.dtype('uint32'), numeric_converted.astype('uint32')
                    else:  # Signed integers
                        if min_val >= -128 and max_val <= 127:
                            return np.dtype('int8'), numeric_converted.astype('int8')
                        elif min_val >= -32768 and max_val <= 32767:
                            return np.dtype('int16'), numeric_converted.astype('int16')
                        elif min_val >= -2147483648 and max_val <= 2147483647:
                            return np.dtype('int32'), numeric_converted.astype('int32')
                
                # Use float32 if values fit, otherwise float64
                if (numeric_converted.abs() < 3.4e+38).all():
                    return np.dtype('float32'), numeric_converted.astype('float32')
            
            return numeric_converted.dtype, numeric_converted
        
        return None
    
    def _try_datetime_conversion(self, series: pd.Series, column_name: str) -> Optional[tuple]:
        """Try to convert to datetime."""
        # Skip if column doesn't look like datetime
        datetime_indicators = ['date', 'time', 'created', 'updated', 'modified', 'timestamp']
        if not any(indicator in column_name.lower() for indicator in datetime_indicators):
            return None
        
        try:
            # Try to parse datetime
            datetime_series = pd.to_datetime(series, errors='coerce', infer_datetime_format=True)
            
            # Check if conversion was successful
            non_null_original = series.count()
            non_null_converted = datetime_series.count()
            
            if non_null_converted > 0 and (non_null_converted / non_null_original) > 0.7:
                return datetime_series.dtype, datetime_series
        
        except Exception:
            pass
        
        return None
    
    def _try_category_conversion(self, series: pd.Series, column_name: str) -> Optional[tuple]:
        """Try to convert to category."""
        # Only convert to category if it would save memory
        unique_count = series.nunique()
        total_count = len(series)
        
        # Convert to category if unique values are less than 50% of total
        if unique_count < total_count * 0.5 and unique_count > 1:
            category_series = series.astype('category')
            return category_series.dtype, category_series
        
        return None
    
    def _optimize_string_type(self, series: pd.Series, column_name: str) -> Optional[tuple]:
        """Optimize string type."""
        if series.dtype == 'object':
            # Try string dtype for better performance (pandas >= 1.0)
            try:
                string_series = series.astype('string')
                return string_series.dtype, string_series
            except Exception:
                pass
        
        return None
    
    def _clean_email_column(self, series: pd.Series) -> pd.Series:
        """Clean email column."""
        return series.str.lower().str.strip()
    
    def _clean_phone_column(self, series: pd.Series) -> pd.Series:
        """Clean phone column."""
        # Remove non-digit characters except +
        return series.str.replace(r'[^\d\+\-\(\)\s]', '', regex=True)
    
    def _clean_domain_column(self, series: pd.Series) -> pd.Series:
        """Clean domain/website column."""
        cleaned = series.str.lower().str.strip()
        # Remove protocol
        cleaned = cleaned.str.replace(r'^https?://', '', regex=True)
        # Remove www.
        cleaned = cleaned.str.replace(r'^www\.', '', regex=True)
        # Remove trailing slash
        cleaned = cleaned.str.rstrip('/')
        return cleaned