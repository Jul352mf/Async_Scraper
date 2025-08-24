"""Data saving utilities for various output formats."""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Union

import aiofiles
import pandas as pd

from scraper.core.config import get_config
from scraper.core.logger import get_logger, LoggerMixin

logger = get_logger(__name__)


class DataSaver(LoggerMixin):
    """Save data to various file formats."""
    
    def __init__(self, config: Optional[Dict] = None):
        super().__init__()
        self.config = config or get_config()
        
    async def save_file(self, 
                       df: pd.DataFrame, 
                       file_path: Union[str, Path],
                       format: Optional[str] = None) -> None:
        """
        Save DataFrame to file asynchronously.
        
        Args:
            df: DataFrame to save
            file_path: Output file path
            format: Output format (csv, xlsx, json). Auto-detected if None.
        """
        file_path = Path(file_path)
        
        # Create directory if it doesn't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Determine format
        if format is None:
            format = file_path.suffix.lower().lstrip('.')
        
        self.log_info(f"Saving {len(df)} rows to {file_path}",
                     rows=len(df),
                     columns=len(df.columns),
                     format=format,
                     file_path=str(file_path))
        
        # Save based on format
        if format == 'csv':
            await self._save_csv(df, file_path)
        elif format in ['xlsx', 'excel']:
            await self._save_excel(df, file_path)
        elif format == 'json':
            await self._save_json(df, file_path)
        else:
            raise ValueError(f"Unsupported output format: {format}")
        
        # Log file info
        if file_path.exists():
            file_size = file_path.stat().st_size
            self.log_info(f"File saved successfully",
                         file_size_bytes=file_size,
                         file_size_mb=round(file_size / 1024 / 1024, 2))
        
    async def _save_csv(self, df: pd.DataFrame, file_path: Path) -> None:
        """Save DataFrame as CSV."""
        def _write_csv():
            df.to_csv(file_path, index=False, encoding='utf-8')
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _write_csv)
    
    async def _save_excel(self, df: pd.DataFrame, file_path: Path) -> None:
        """Save DataFrame as Excel."""
        def _write_excel():
            # Ensure .xlsx extension
            if file_path.suffix.lower() != '.xlsx':
                actual_path = file_path.with_suffix('.xlsx')
            else:
                actual_path = file_path
                
            with pd.ExcelWriter(actual_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Data', index=False)
                
                # Auto-adjust column widths
                worksheet = writer.sheets['Data']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    
                    adjusted_width = min(max_length + 2, 50)  # Cap at 50
                    worksheet.column_dimensions[column_letter].width = adjusted_width
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _write_excel)
    
    async def _save_json(self, df: pd.DataFrame, file_path: Path) -> None:
        """Save DataFrame as JSON."""
        # Convert DataFrame to JSON string
        json_str = df.to_json(orient='records', indent=2)
        
        # Write asynchronously
        async with aiofiles.open(file_path, mode='w', encoding='utf-8') as f:
            await f.write(json_str)
    
    async def save_results_summary(self, 
                                  results: Dict,
                                  summary_path: Union[str, Path]) -> None:
        """Save a summary of scraping results."""
        summary_path = Path(summary_path)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create summary content
        summary_content = {
            'timestamp': pd.Timestamp.now().isoformat(),
            'total_companies': results.get('total_companies', 0),
            'companies_processed': results.get('companies_processed', 0),
            'total_emails_found': results.get('total_emails_found', 0),
            'unique_emails_found': results.get('unique_emails_found', 0),
            'domains_scraped': results.get('domains_scraped', 0),
            'pages_scraped': results.get('pages_scraped', 0),
            'processing_time_seconds': results.get('processing_time_seconds', 0),
            'average_time_per_domain': results.get('average_time_per_domain', 0),
            'success_rate': results.get('success_rate', 0),
            'errors': results.get('errors', []),
            'configuration': results.get('configuration', {}),
        }
        
        # Save as JSON
        import json
        async with aiofiles.open(summary_path, mode='w', encoding='utf-8') as f:
            await f.write(json.dumps(summary_content, indent=2, default=str))
        
        self.log_info(f"Results summary saved to {summary_path}")


class BatchSaver(LoggerMixin):
    """Save data in batches for large datasets."""
    
    def __init__(self, batch_size: int = 1000):
        super().__init__()
        self.batch_size = batch_size
        self.saver = DataSaver()
    
    async def save_in_batches(self,
                             df: pd.DataFrame,
                             file_path: Union[str, Path],
                             format: str = 'csv') -> List[Path]:
        """
        Save large DataFrame in batches.
        
        Returns:
            List of saved file paths
        """
        file_path = Path(file_path)
        saved_files = []
        
        total_batches = (len(df) + self.batch_size - 1) // self.batch_size
        self.log_info(f"Saving {len(df)} rows in {total_batches} batches",
                     total_rows=len(df),
                     batch_size=self.batch_size,
                     total_batches=total_batches)
        
        for i in range(0, len(df), self.batch_size):
            batch_df = df.iloc[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            
            # Create batch file name
            batch_file_path = file_path.parent / f"{file_path.stem}_batch_{batch_num:03d}{file_path.suffix}"
            
            await self.saver.save_file(batch_df, batch_file_path, format)
            saved_files.append(batch_file_path)
            
            self.log_info(f"Saved batch {batch_num}/{total_batches}",
                         batch_num=batch_num,
                         batch_rows=len(batch_df))
        
        return saved_files


class IncrementalSaver(LoggerMixin):
    """Save data incrementally as it's processed."""
    
    def __init__(self, file_path: Union[str, Path], format: str = 'csv'):
        super().__init__()
        self.file_path = Path(file_path)
        self.format = format
        self.saver = DataSaver()
        self._buffer = []
        self._buffer_size = 100
        self._total_saved = 0
        
    async def add_record(self, record: Dict) -> None:
        """Add a record to the buffer."""
        self._buffer.append(record)
        
        if len(self._buffer) >= self._buffer_size:
            await self.flush()
    
    async def add_records(self, records: List[Dict]) -> None:
        """Add multiple records to the buffer."""
        self._buffer.extend(records)
        
        if len(self._buffer) >= self._buffer_size:
            await self.flush()
    
    async def flush(self) -> None:
        """Flush buffer to file."""
        if not self._buffer:
            return
        
        df = pd.DataFrame(self._buffer)
        
        # If file doesn't exist, create it
        if not self.file_path.exists():
            await self.saver.save_file(df, self.file_path, self.format)
        else:
            # Append to existing file
            if self.format == 'csv':
                def _append_csv():
                    df.to_csv(self.file_path, mode='a', header=False, index=False)
                
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _append_csv)
            else:
                # For non-CSV formats, we need to read existing data and combine
                existing_df = pd.read_csv(self.file_path) if self.format == 'csv' else pd.DataFrame()
                combined_df = pd.concat([existing_df, df], ignore_index=True)
                await self.saver.save_file(combined_df, self.file_path, self.format)
        
        self._total_saved += len(self._buffer)
        self.log_info(f"Flushed {len(self._buffer)} records to file",
                     flushed_records=len(self._buffer),
                     total_saved=self._total_saved)
        
        self._buffer.clear()
    
    async def close(self) -> None:
        """Close the saver and flush any remaining data."""
        await self.flush()
        self.log_info(f"IncrementalSaver closed, total records saved: {self._total_saved}")


# Convenience functions
async def save_dataframe(df: pd.DataFrame, 
                        file_path: Union[str, Path],
                        format: Optional[str] = None) -> None:
    """Convenience function to save DataFrame."""
    saver = DataSaver()
    await saver.save_file(df, file_path, format)


async def save_results(results_df: pd.DataFrame,
                      output_path: Union[str, Path],
                      summary_data: Optional[Dict] = None) -> None:
    """Save scraping results with optional summary."""
    output_path = Path(output_path)
    
    # Save main results
    await save_dataframe(results_df, output_path)
    
    # Save summary if provided
    if summary_data:
        summary_path = output_path.parent / f"{output_path.stem}_summary.json"
        saver = DataSaver()
        await saver.save_results_summary(summary_data, summary_path)