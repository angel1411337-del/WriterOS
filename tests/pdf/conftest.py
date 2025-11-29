"""
Shared fixtures for PDF ingestion tests.

Provides:
- Sample PDF files (synthetic)
- Mock PDF processor
- Database fixtures
"""
import pytest
from pathlib import Path
from uuid import uuid4
from io import BytesIO

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from writeros.utils.pdf_processor import PDFProcessor
from writeros.preprocessing import ChunkingStrategy
from writeros.agents.profiler import ProfilerAgent


def create_pdf_with_content(path: Path, content: str, metadata: dict = None):
    """
    Create a synthetic PDF file with given content.
    
    Args:
        path: Path to save PDF
        content: Text content to include
        metadata: Optional metadata (title, author)
    """
    if not REPORTLAB_AVAILABLE:
        pytest.skip("reportlab not installed")
    
    metadata = metadata or {}
    
    c = canvas.Canvas(str(path), pagesize=letter)
    
    # Set metadata
    if "title" in metadata:
        c.setTitle(metadata["title"])
    if "author" in metadata:
        c.setAuthor(metadata["author"])
    
    # Write content
    text_object = c.beginText(50, 750)
    text_object.setFont("Helvetica", 12)
    
    for line in content.split("\n"):
        if line.strip():
            text_object.textLine(line)
    
    c.drawText(text_object)
    c.save()


@pytest.fixture
def sample_pdf_simple(tmp_path):
    """
    Create a simple PDF with basic text content.
    """
    pdf_path = tmp_path / "simple_test.pdf"
    
    content = """
The Dance of Dragons began in year 129 AC.
Aegon II claimed the throne after his father's death.
Rhaenyra contested his claim, leading to civil war.
The conflict lasted for two years and devastated the realm.
"""
    
    metadata = {
        "title": "Simple Test Document",
        "author": "Test Author"
    }
    
    create_pdf_with_content(pdf_path, content, metadata)
    
    return pdf_path


@pytest.fixture
def sample_pdf_with_narrators(tmp_path):
    """
    Create a PDF with narrator claims for testing unreliable narrator detection.
    """
    pdf_path = tmp_path / "narrator_test.pdf"
    
    content = """
The events of the Dance are disputed by historians.

Mushroom claims that Rhaenyra poisoned King Viserys to hasten her claim.
According to Septon Eustace, the King died peacefully of natural causes.
Grand Maester Munkun's account states that the truth remains unclear.

Mushroom also claims that Aegon II was a drunkard and unfit to rule.
Septon Eustace writes that Aegon was a pious and just king.
"""
    
    metadata = {
        "title": "Conflicting Accounts of the Dance",
        "author": "Various Chroniclers"
    }
    
    create_pdf_with_content(pdf_path, content, metadata)
    
    return pdf_path


@pytest.fixture
def sample_pdf_multi_era(tmp_path):
    """
    Create a PDF with entities from different time periods.
    """
    pdf_path = tmp_path / "multi_era_test.pdf"
    
    content = """
PART I: THE CONQUEST (1-37 AC)

Aegon I Targaryen conquered Westeros in year 1 AC with his dragons.
He ruled for 37 years, establishing the Targaryen dynasty.
His sister-wives were Visenya and Rhaenys.

PART II: THE DANCE OF DRAGONS (129-131 AC)

Aegon II Targaryen ascended to the throne in year 129 AC.
His reign was marked by the Dance of Dragons civil war.
He fought against his half-sister Rhaenyra for the throne.

PART III: THE BROKEN KING (131-157 AC)

Aegon III Targaryen became king at age 11 in year 131 AC.
Known as the Broken King, he ruled for 26 years.
His reign saw the last of the dragons die.
"""
    
    metadata = {
        "title": "The Three Aegons",
        "author": "Archmaester Gyldayn"
    }
    
    create_pdf_with_content(pdf_path, content, metadata)
    
    return pdf_path


@pytest.fixture
def sample_pdf_empty(tmp_path):
    """
    Create an empty PDF for error handling tests.
    """
    pdf_path = tmp_path / "empty_test.pdf"
    
    content = ""
    metadata = {"title": "Empty Document"}
    
    create_pdf_with_content(pdf_path, content, metadata)
    
    return pdf_path


@pytest.fixture
def mock_pdf_processor(db_session, sample_vault_id, mocker):
    """
    Create a PDFProcessor with mocked database session.
    """
    # Patch Session to use test db_session
    from unittest.mock import MagicMock
    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db_session
    mock_ctx.__exit__.return_value = None
    mocker.patch("writeros.utils.pdf_processor.Session", return_value=mock_ctx)
    
    # Patch ProfilerAgent Session as well
    mocker.patch("writeros.agents.profiler.Session", return_value=mock_ctx)
    
    # Create processor
    processor = PDFProcessor(
        vault_id=sample_vault_id,
        chunking_strategy=ChunkingStrategy.AUTO,
        enable_cache=False  # Disable cache for tests
    )
    
    return processor

@pytest.fixture
def mock_profiler(db_session, mocker):
    """
    Create a ProfilerAgent with mocked database session.
    Ensures it shares the same transaction as the test.
    """
    # Patch Session to use test db_session
    from unittest.mock import MagicMock
    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = db_session
    mock_ctx.__exit__.return_value = None
    
    # Patch Session in profiler module
    mocker.patch("writeros.agents.profiler.Session", return_value=mock_ctx)
    
    return ProfilerAgent()
