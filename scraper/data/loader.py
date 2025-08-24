"""Data loading utilities for CSV and Excel files."""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Union

import aiofiles
import pandas as pd

from scraper.core.config import get_config
from scraper.core.logger import get_logger, LoggerMixin

logger = get_logger(__name__)


class DataLoader(LoggerMixin):
    """Load and normalize data from various file formats."""
    
    def __init__(self, config: Optional[Dict] = None):
        super().__init__()
        self.config = config or get_config()
        
    async def load_file(self, file_path: Union[str, Path]) -> pd.DataFrame:
        """
        Load data from file asynchronously.
        
        Args:
            file_path: Path to the input file
            
        Returns:
            Normalized pandas DataFrame
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        self.log_info(f"Loading data from {file_path}", 
                     file_path=str(file_path),
                     file_size=file_path.stat().st_size)
        
        # Determine file type and load appropriately
        if file_path.suffix.lower() in ['.csv']:
            df = await self._load_csv(file_path)
        elif file_path.suffix.lower() in ['.xlsx', '.xls']:
            df = await self._load_excel(file_path)
        elif file_path.suffix.lower() == '.json':
            df = await self._load_json(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path.suffix}")
        
        # Normalize the DataFrame
        df_normalized = self._normalize_dataframe(df)
        
        self.log_info(f"Loaded {len(df_normalized)} rows", 
                     rows=len(df_normalized),
                     columns=list(df_normalized.columns))
        
        return df_normalized
    
    async def _load_csv(self, file_path: Path) -> pd.DataFrame:
        """Load CSV file asynchronously."""
        def _read_csv():
            # Try different encodings and separators
            encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
            separators = [',', ';', '\t']
            
            for encoding in encodings:
                for sep in separators:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding, sep=sep)
                        if len(df.columns) > 1:  # Multiple columns suggest correct separator
                            return df
                    except (UnicodeDecodeError, pd.errors.ParserError):
                        continue
            
            # Fallback to default pandas behavior
            return pd.read_csv(file_path)
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _read_csv)
    
    async def _load_excel(self, file_path: Path) -> pd.DataFrame:
        """Load Excel file asynchronously."""
        def _read_excel():
            # Try to read the first sheet
            return pd.read_excel(file_path, sheet_name=0)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _read_excel)
    
    async def _load_json(self, file_path: Path) -> pd.DataFrame:
        """Load JSON file asynchronously."""
        async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
            content = await f.read()
            
        # Parse JSON in thread pool
        def _parse_json():
            import json
            data = json.loads(content)
            return pd.DataFrame(data)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _parse_json)
    
    def _normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize DataFrame columns and content."""
        # Make a copy to avoid modifying original
        df = df.copy()
        
        # Normalize column names
        df.columns = [self._normalize_column_name(col) for col in df.columns]
        
        # Remove completely empty rows
        df = df.dropna(how='all')
        
        # Remove duplicate rows
        initial_count = len(df)
        df = df.drop_duplicates()
        duplicates_removed = initial_count - len(df)
        
        if duplicates_removed > 0:
            self.log_info(f"Removed {duplicates_removed} duplicate rows")
        
        # Convert data types
        df = self._infer_data_types(df)
        
        return df
    
    def _normalize_column_name(self, col_name: str) -> str:
        """Normalize a column name."""
        import re
        
        # Convert to lowercase
        normalized = str(col_name).lower().strip()
        
        # Replace spaces and special chars with underscores
        normalized = re.sub(r'[^\w\s]', '_', normalized)
        normalized = re.sub(r'\s+', '_', normalized)
        
        # Remove multiple consecutive underscores
        normalized = re.sub(r'_+', '_', normalized)
        
        # Remove leading/trailing underscores
        normalized = normalized.strip('_')
        
        # Map common column name variations
        column_mappings = {
            'company': 'company_name',
            'company_name': 'company_name',
            'business': 'company_name',
            'organization': 'company_name',
            'org': 'company_name',
            'domain': 'domain',
            'website': 'domain',
            'website_url': 'domain',
            'url': 'domain',
            'site': 'domain',
            'email': 'email',
            'emails': 'email',
            'email_address': 'email',
            'e_mail': 'email',
            'e_mail_address': 'email', 
            'contact_email': 'email',
            'name': 'contact_name',
            'contact': 'contact_name',
            'contact_person': 'contact_name',
            'person': 'contact_name',
            'phone': 'phone',
            'phone_number': 'phone',
            'telephone': 'phone',
            'tel': 'phone',
            'mobile': 'phone',
            'address': 'address',
            'location': 'address',
            'city': 'city',
            'state': 'state',
            'country': 'country',
            'industry': 'industry',
            'sector': 'industry',
            'description': 'description',
            'notes': 'notes',
        }
        
        return column_mappings.get(normalized, normalized)
    
    def _infer_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Infer and convert data types."""
        for col in df.columns:
            # Skip if column is already properly typed
            if df[col].dtype in ['int64', 'float64', 'datetime64[ns]']:
                continue
            
            # Try to convert to numeric if it looks numeric
            if col in ['phone', 'size', 'employees', 'revenue']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Ensure string columns are properly formatted
            elif df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.strip()
                # Replace 'nan' strings with actual NaN
                df[col] = df[col].replace(['nan', 'None', ''], pd.NA)
        
        return df
    
    def get_column_summary(self, df: pd.DataFrame) -> Dict:
        """Get summary information about DataFrame columns."""
        summary = {
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'columns': {},
            'required_columns': {
                'has_company_name': 'company_name' in df.columns,
                'has_domain': 'domain' in df.columns,
                'has_email': 'email' in df.columns,
            }
        }
        
        for col in df.columns:
            col_info = {
                'dtype': str(df[col].dtype),
                'non_null_count': df[col].count(),
                'null_count': df[col].isnull().sum(),
                'unique_count': df[col].nunique(),
            }
            
            # Add sample values for string columns
            if df[col].dtype == 'object':
                non_null_values = df[col].dropna()
                if len(non_null_values) > 0:
                    col_info['sample_values'] = non_null_values.head(3).tolist()
            
            summary['columns'][col] = col_info
        
        return summary


async def load_data_file(file_path: Union[str, Path]) -> pd.DataFrame:
    """Convenience function to load data file."""
    loader = DataLoader()
    return await loader.load_file(file_path)