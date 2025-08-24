"""Tests for data loading and cleaning functionality."""

import asyncio
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from scraper.data.loader import DataLoader, load_data_file
from scraper.data.saver import DataSaver, save_dataframe
from scraper.data.cleaner.base import CleaningPipeline, DataValidator
from scraper.data.cleaner.duplicates import DuplicateCleaner
from scraper.data.cleaner.datatypes import TypeCleaner


class TestDataLoader:
    """Test data loading functionality."""
    
    @pytest.mark.asyncio
    async def test_load_csv(self):
        """Test CSV loading."""
        # Create test CSV
        test_data = {
            'Company Name': ['Acme Corp', 'Beta LLC', 'Gamma Inc'],
            'Website': ['acme.com', 'beta.org', 'gamma.net'],
            'Email': ['info@acme.com', 'contact@beta.org', 'hello@gamma.net']
        }
        df = pd.DataFrame(test_data)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f.name, index=False)
            csv_path = f.name
        
        try:
            loader = DataLoader()
            loaded_df = await loader.load_file(csv_path)
            
            # Check normalization
            assert 'company_name' in loaded_df.columns
            assert 'domain' in loaded_df.columns  # Website -> domain
            assert 'email' in loaded_df.columns
            assert len(loaded_df) == 3
            
        finally:
            Path(csv_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_load_excel(self):
        """Test Excel loading."""
        # Create test Excel file
        test_data = {
            'Company': ['Test Corp'],
            'Site': ['test.com'],
            'Contact Email': ['test@test.com']
        }
        df = pd.DataFrame(test_data)
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            df.to_excel(f.name, index=False)
            excel_path = f.name
        
        try:
            loaded_df = await load_data_file(excel_path)
            
            assert 'company_name' in loaded_df.columns  # Company -> company_name
            assert 'domain' in loaded_df.columns  # Site -> domain
            assert 'email' in loaded_df.columns  # Contact Email -> email
            
        finally:
            Path(excel_path).unlink(missing_ok=True)
    
    def test_column_normalization(self):
        """Test column name normalization."""
        loader = DataLoader()
        
        test_cases = [
            ('Company Name', 'company_name'),
            ('Website URL', 'domain'),
            ('E-mail Address', 'email'),
            ('Contact Person', 'contact_name'),
            ('Phone Number', 'phone'),
        ]
        
        for original, expected in test_cases:
            normalized = loader._normalize_column_name(original)
            assert normalized == expected


class TestDataSaver:
    """Test data saving functionality."""
    
    @pytest.mark.asyncio
    async def test_save_csv(self):
        """Test CSV saving."""
        test_data = {
            'company_name': ['Test Corp'],
            'domain': ['test.com'],
            'email': ['test@test.com']
        }
        df = pd.DataFrame(test_data)
        
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            csv_path = f.name
        
        try:
            await save_dataframe(df, csv_path)
            
            # Verify file exists and content
            assert Path(csv_path).exists()
            loaded_df = pd.read_csv(csv_path)
            assert len(loaded_df) == 1
            assert list(loaded_df.columns) == ['company_name', 'domain', 'email']
            
        finally:
            Path(csv_path).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_save_excel(self):
        """Test Excel saving."""
        test_data = {
            'company_name': ['Test Corp'],
            'domain': ['test.com']
        }
        df = pd.DataFrame(test_data)
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            excel_path = f.name
        
        try:
            saver = DataSaver()
            await saver.save_file(df, excel_path, 'xlsx')
            
            # Verify file exists
            assert Path(excel_path).exists()
            
        finally:
            Path(excel_path).unlink(missing_ok=True)


class TestCleaners:
    """Test data cleaning functionality."""
    
    def test_duplicate_cleaner(self):
        """Test duplicate removal."""
        test_data = {
            'company_name': ['Acme Corp', 'acme corp', 'Beta LLC', 'Beta LLC'],
            'domain': ['acme.com', 'acme.com', 'beta.org', 'beta.org'],
            'email': ['info@acme.com', 'INFO@acme.com', 'contact@beta.org', 'contact@beta.org']
        }
        df = pd.DataFrame(test_data)
        
        cleaner = DuplicateCleaner(ignore_case=True)
        cleaned_df = cleaner.clean(df)
        
        # Should remove case-insensitive duplicates
        assert len(cleaned_df) == 2  # Only unique companies
        
        stats = cleaner.get_stats()
        assert stats['duplicates_removed'] == 2
        assert stats['ignore_case'] is True
    
    def test_type_cleaner(self):
        """Test type inference and cleaning."""
        test_data = {
            'company_name': ['Acme Corp', 'Beta LLC'],
            'employee_count': ['100', '50'],
            'is_public': ['yes', 'no'],
            'revenue': ['1000000', '500000']
        }
        df = pd.DataFrame(test_data)
        
        cleaner = TypeCleaner()
        cleaned_df = cleaner.clean(df)
        
        # Check type conversions
        assert pd.api.types.is_numeric_dtype(cleaned_df['employee_count'])
        assert cleaned_df['is_public'].dtype == 'bool'
        assert pd.api.types.is_numeric_dtype(cleaned_df['revenue'])
        
        stats = cleaner.get_stats()
        assert stats['columns_converted'] >= 2  # At least employee_count and revenue
    
    def test_cleaning_pipeline(self):
        """Test cleaning pipeline."""
        test_data = {
            'company_name': ['Acme Corp', 'Acme Corp', 'Beta LLC'],  # Has duplicate
            'employee_count': ['100', '100', '25'],  # String numbers, first two identical
            'domain': ['acme.com', 'acme.com', 'beta.org']  # Same domain for duplicate
        }
        df = pd.DataFrame(test_data)
        
        pipeline = CleaningPipeline([
            DuplicateCleaner(),
            TypeCleaner()
        ])
        
        cleaned_df, stats = pipeline.clean(df)
        
        # Should have removed duplicate and converted types
        assert len(cleaned_df) == 2  # Duplicate removed
        assert pd.api.types.is_numeric_dtype(cleaned_df['employee_count'])  # Type converted
        
        assert stats['total_rows_removed'] == 1
        assert len(stats['cleaners_applied']) == 2
    
    def test_data_validator(self):
        """Test data validation."""
        # Valid data
        valid_data = {
            'company_name': ['Acme Corp', 'Beta LLC'],
            'domain': ['acme.com', 'beta.org'],
            'email': ['info@acme.com', 'contact@beta.org']
        }
        valid_df = pd.DataFrame(valid_data)
        
        validator = DataValidator()
        report = validator.validate_dataframe(valid_df)
        
        assert report['is_valid'] is True
        assert len(report['issues']) == 0
        
        # Invalid data (empty DataFrame)
        empty_df = pd.DataFrame()
        report = validator.validate_dataframe(empty_df)
        
        assert report['is_valid'] is False
        assert len(report['issues']) > 0


if __name__ == "__main__":
    pytest.main([__file__])