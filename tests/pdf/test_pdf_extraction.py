"""
Tests for PDF text extraction and metadata.

Tests:
- Basic PDF extraction
- Metadata extraction (title, author, page count)
- Multi-page PDF handling
- Empty PDF handling
- Error handling for malformed PDFs
"""
import pytest
from pathlib import Path

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

from writeros.utils.pdf_processor import PDFProcessor


pytestmark = pytest.mark.skipif(
    not PYPDF2_AVAILABLE,
    reason="PyPDF2 not installed"
)


class TestPDFExtraction:
    """Test suite for PDF text extraction."""
    
    def test_extract_pdf_basic(self, mock_pdf_processor, sample_pdf_simple):
        """Test basic PDF text extraction."""
        processor = mock_pdf_processor
        
        # Extract PDF
        result = processor.extract_pdf(sample_pdf_simple)
        
        # Verify text extracted
        assert result["text"]
        assert "Dance of Dragons" in result["text"]
        assert "Aegon II" in result["text"]
        assert "Rhaenyra" in result["text"]
        
        # Verify page count
        assert result["page_count"] == 1
        
        # Verify pages list
        assert len(result["pages"]) == 1
        assert result["pages"][0]["page_num"] == 1
    
    def test_extract_pdf_metadata(self, mock_pdf_processor, sample_pdf_simple):
        """Test PDF metadata extraction."""
        processor = mock_pdf_processor
        
        # Extract PDF
        result = processor.extract_pdf(sample_pdf_simple)
        
        # Verify metadata
        metadata = result["metadata"]
        assert metadata["title"] == "Simple Test Document"
        assert metadata["author"] == "Test Author"
    
    def test_extract_pdf_multi_era(self, mock_pdf_processor, sample_pdf_multi_era):
        """Test extraction of multi-section PDF."""
        processor = mock_pdf_processor
        
        # Extract PDF
        result = processor.extract_pdf(sample_pdf_multi_era)
        
        # Verify all eras present
        text = result["text"]
        assert "Aegon I" in text
        assert "Aegon II" in text
        assert "Aegon III" in text
        
        # Verify era markers
        assert "PART I" in text
        assert "PART II" in text
        assert "PART III" in text
    
    def test_extract_pdf_empty(self, mock_pdf_processor, sample_pdf_empty):
        """Test extraction of empty PDF."""
        processor = mock_pdf_processor
        
        # Extract PDF
        result = processor.extract_pdf(sample_pdf_empty)
        
        # Verify empty text
        assert result["text"].strip() == ""
        assert result["page_count"] >= 0
    
    def test_extract_pdf_with_narrators(self, mock_pdf_processor, sample_pdf_with_narrators):
        """Test extraction of PDF with narrator claims."""
        processor = mock_pdf_processor
        
        # Extract PDF
        result = processor.extract_pdf(sample_pdf_with_narrators)
        
        # Verify narrator text extracted
        text = result["text"]
        assert "Mushroom claims" in text
        assert "Septon Eustace" in text
        assert "Grand Maester Munkun" in text
    
    def test_extract_pdf_nonexistent_file(self, mock_pdf_processor, tmp_path):
        """Test error handling for nonexistent PDF."""
        processor = mock_pdf_processor
        
        nonexistent_path = tmp_path / "nonexistent.pdf"
        
        # Should raise exception
        with pytest.raises(Exception):
            processor.extract_pdf(nonexistent_path)
