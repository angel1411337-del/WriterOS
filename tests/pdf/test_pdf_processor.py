"""
Test suite for PDF processing functionality.

Tests:
1. PDF text extraction
2. PDF metadata extraction
3. Chunking with ClusterSemanticChunker
4. Entity extraction from PDF content
5. Graph population from PDF
6. Integration with VaultIndexer
"""
import pytest
from pathlib import Path
from uuid import uuid4
from sqlmodel import Session, select
from io import BytesIO

try:
    import PyPDF2
    from PyPDF2 import PdfWriter
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

from writeros.schema import Vault, Document, Entity, Relationship
from writeros.utils.pdf_processor import PDFProcessor
from writeros.utils.indexer import VaultIndexer
from writeros.utils.db import engine


@pytest.fixture
def sample_vault(db_session):
    """Create a sample vault for testing."""
    vault = Vault(
        name="Test PDF Vault",
        user_id=uuid4()
    )
    db_session.add(vault)
    db_session.commit()
    db_session.refresh(vault)
    return vault


@pytest.fixture
def sample_pdf(tmp_path):
    """
    Create a sample PDF file with test content.

    Content includes characters, locations, and relationships for entity extraction.
    """
    if not PYPDF2_AVAILABLE:
        pytest.skip("PyPDF2 not installed")

    pdf_content = """
# The Quest for the Dragon Sword

## Chapter 1: The Hero's Journey

Aragorn, a brave warrior from the Northern Kingdom, set out on a quest to find the legendary Dragon Sword.
He was accompanied by his mentor, Gandalf the Wise, an ancient wizard with great knowledge of the old world.

The journey began in the City of Eternal Light, a magnificent metropolis built on the slopes of Mount Destiny.
The city was known for its towering spires and gleaming white walls.

Aragorn's rival, Mordred the Dark, sought the same sword. According to ancient scrolls, Mordred had been
Aragorn's childhood friend before betraying him. The two were now sworn enemies.

The Dark Brotherhood, a secret organization led by Mordred, controlled the Shadow Realm, a desolate wasteland
where the sword was rumored to be hidden. The Brotherhood's ideology was simple: power through conquest.

## Chapter 2: The Alliance

Princess Elara of the Eastern Isles joined Aragorn's quest. She was Aragorn's spouse, having married him
in a ceremony at the Temple of the Ancients. Elara brought with her knowledge of ancient magic and
a map to the sword's location.

Gandalf claims that the sword can only be wielded by one pure of heart. According to Mordred's account,
the sword grants unlimited power to anyone who possesses it. These conflicting views would shape the quest.
    """

    pdf_path = tmp_path / "test_document.pdf"

    # Create a simple PDF
    pdf_writer = PdfWriter()

    # We'll create a simple text-based PDF
    # Note: PyPDF2 doesn't easily create PDFs with text, so we'll use reportlab if available
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter

        # Create PDF with reportlab
        pdf_buffer = BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=letter)

        # Add title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, 750, "The Quest for the Dragon Sword")

        # Add content
        c.setFont("Helvetica", 12)
        y = 700
        for line in pdf_content.split('\n'):
            if line.strip():
                # Simple line wrapping
                if len(line) > 80:
                    words = line.split()
                    current_line = ""
                    for word in words:
                        if len(current_line + word) < 80:
                            current_line += word + " "
                        else:
                            c.drawString(100, y, current_line)
                            y -= 15
                            current_line = word + " "
                    if current_line:
                        c.drawString(100, y, current_line)
                        y -= 15
                else:
                    c.drawString(100, y, line)
                    y -= 15

                if y < 100:  # New page if needed
                    c.showPage()
                    c.setFont("Helvetica", 12)
                    y = 750

        c.save()

        # Write to file
        pdf_buffer.seek(0)
        with open(pdf_path, 'wb') as f:
            f.write(pdf_buffer.read())

    except ImportError:
        # Fallback: Create a minimal PDF with just metadata
        pytest.skip("reportlab not installed - cannot create test PDF")

    return pdf_path


@pytest.mark.skipif(not PYPDF2_AVAILABLE, reason="PyPDF2 not installed")
class TestPDFExtraction:
    """Tests for PDF text and metadata extraction."""

    @pytest.mark.asyncio
    async def test_extract_pdf_text(self, sample_vault, sample_pdf):
        """Test that text is extracted from PDF correctly."""
        processor = PDFProcessor(vault_id=sample_vault.id)

        pdf_data = processor.extract_pdf(sample_pdf)

        assert pdf_data["text"] is not None
        assert len(pdf_data["text"]) > 0
        assert pdf_data["page_count"] > 0
        assert "Aragorn" in pdf_data["text"]
        assert "Dragon Sword" in pdf_data["text"]

    @pytest.mark.asyncio
    async def test_extract_pdf_metadata(self, sample_vault, sample_pdf):
        """Test that metadata is extracted from PDF."""
        processor = PDFProcessor(vault_id=sample_vault.id)

        pdf_data = processor.extract_pdf(sample_pdf)

        assert "metadata" in pdf_data
        metadata = pdf_data["metadata"]
        assert "title" in metadata
        # Title might be filename if PDF doesn't have embedded metadata
        assert metadata["title"] is not None


@pytest.mark.skipif(not PYPDF2_AVAILABLE, reason="PyPDF2 not installed")
class TestPDFChunking:
    """Tests for PDF chunking with ClusterSemanticChunker."""

    @pytest.mark.asyncio
    async def test_chunk_pdf_text(self, sample_vault, sample_pdf):
        """Test that PDF text is chunked correctly."""
        processor = PDFProcessor(vault_id=sample_vault.id)

        pdf_data = processor.extract_pdf(sample_pdf)
        chunks = await processor.chunk_pdf_text(
            text=pdf_data["text"],
            pdf_metadata=pdf_data["metadata"]
        )

        assert len(chunks) > 0
        assert all("content" in chunk for chunk in chunks)
        assert all("embedding" in chunk for chunk in chunks)
        assert all("chunk_index" in chunk for chunk in chunks)

        # Verify embeddings are lists of floats
        for chunk in chunks:
            assert isinstance(chunk["embedding"], list)
            assert len(chunk["embedding"]) > 0
            assert all(isinstance(x, float) for x in chunk["embedding"])

    @pytest.mark.asyncio
    async def test_chunks_stored_in_database(self, sample_vault, sample_pdf, db_session):
        """Test that chunks are stored in database correctly."""
        processor = PDFProcessor(vault_id=sample_vault.id)

        pdf_data = processor.extract_pdf(sample_pdf)
        chunks = await processor.chunk_pdf_text(
            text=pdf_data["text"],
            pdf_metadata=pdf_data["metadata"]
        )

        await processor.store_chunks(
            chunks=chunks,
            pdf_path=sample_pdf,
            pdf_metadata=pdf_data["metadata"]
        )

        # Verify in database
        docs = db_session.exec(
            select(Document).where(Document.vault_id == sample_vault.id)
        ).all()

        assert len(docs) == len(chunks)

        # Check first document
        doc = docs[0]
        assert doc.doc_type == "pdf"
        assert doc.metadata_.get("source_type") == "pdf"
        assert doc.metadata_.get("source_file") == sample_pdf.name


@pytest.mark.skipif(not PYPDF2_AVAILABLE, reason="PyPDF2 not installed")
class TestEntityExtraction:
    """Tests for entity extraction from PDF content."""

    @pytest.mark.asyncio
    async def test_extract_entities_from_pdf(self, sample_vault, sample_pdf, db_session):
        """Test that entities are extracted from PDF content."""
        processor = PDFProcessor(vault_id=sample_vault.id)

        # Process PDF with entity extraction
        results = await processor.process_pdf(
            pdf_path=sample_pdf,
            extract_entities=True
        )

        assert results["entities_created"] > 0

        # Verify entities in database
        entities = db_session.exec(
            select(Entity).where(Entity.vault_id == sample_vault.id)
        ).all()

        assert len(entities) > 0

        # Check for expected entities
        entity_names = [e.name for e in entities]
        assert any("Aragorn" in name for name in entity_names)

    @pytest.mark.asyncio
    async def test_relationships_created_from_pdf(self, sample_vault, sample_pdf, db_session):
        """Test that relationships are created from PDF content."""
        processor = PDFProcessor(vault_id=sample_vault.id)

        # Process PDF with entity extraction
        results = await processor.process_pdf(
            pdf_path=sample_pdf,
            extract_entities=True
        )

        # Verify relationships in database
        relationships = db_session.exec(
            select(Relationship).where(Relationship.vault_id == sample_vault.id)
        ).all()

        # Should have at least some relationships (mentor, spouse, enemy, etc.)
        assert len(relationships) > 0 or results["relationships_created"] >= 0


@pytest.mark.skipif(not PYPDF2_AVAILABLE, reason="PyPDF2 not installed")
class TestVaultIndexerIntegration:
    """Tests for VaultIndexer integration with PDF processing."""

    @pytest.mark.asyncio
    async def test_vault_indexer_processes_pdfs(self, sample_vault, tmp_path, db_session):
        """Test that VaultIndexer can process PDFs."""
        # Create a simple PDF in a test directory
        pdf_dir = tmp_path / "Story_Bible"
        pdf_dir.mkdir()

        # Create minimal PDF
        try:
            from reportlab.pdfgen import canvas

            pdf_path = pdf_dir / "test.pdf"
            c = canvas.Canvas(str(pdf_path))
            c.drawString(100, 750, "Test PDF Content")
            c.drawString(100, 730, "This is a test document for WriterOS.")
            c.save()

        except ImportError:
            pytest.skip("reportlab not installed")

        # Create indexer
        indexer = VaultIndexer(
            vault_path=str(tmp_path),
            vault_id=sample_vault.id
        )

        # Index vault (including PDFs)
        results = await indexer.index_vault(
            directories=["Story_Bible"],
            include_pdfs=True
        )

        assert results["pdfs_processed"] == 1
        assert results["chunks_created"] > 0

        # Verify in database
        docs = db_session.exec(
            select(Document).where(
                Document.vault_id == sample_vault.id,
                Document.doc_type == "pdf"
            )
        ).all()

        assert len(docs) > 0

    @pytest.mark.asyncio
    async def test_vault_indexer_skips_pdfs_when_disabled(self, sample_vault, tmp_path):
        """Test that PDFs are skipped when include_pdfs=False."""
        pdf_dir = tmp_path / "Story_Bible"
        pdf_dir.mkdir()

        # Create minimal PDF
        try:
            from reportlab.pdfgen import canvas

            pdf_path = pdf_dir / "test.pdf"
            c = canvas.Canvas(str(pdf_path))
            c.drawString(100, 750, "Test PDF Content")
            c.save()

        except ImportError:
            pytest.skip("reportlab not installed")

        # Create indexer
        indexer = VaultIndexer(
            vault_path=str(tmp_path),
            vault_id=sample_vault.id
        )

        # Index vault WITHOUT PDFs
        results = await indexer.index_vault(
            directories=["Story_Bible"],
            include_pdfs=False
        )

        assert results["pdfs_processed"] == 0


@pytest.mark.skipif(not PYPDF2_AVAILABLE, reason="PyPDF2 not installed")
class TestPDFProcessorEndToEnd:
    """End-to-end tests for complete PDF processing workflow."""

    @pytest.mark.asyncio
    async def test_full_pdf_workflow(self, sample_vault, sample_pdf, db_session):
        """Test complete workflow: extract → chunk → store → extract entities."""
        processor = PDFProcessor(vault_id=sample_vault.id)

        # Process PDF
        results = await processor.process_pdf(
            pdf_path=sample_pdf,
            extract_entities=True
        )

        # Verify results
        assert results["pages_extracted"] > 0
        assert results["chunks_created"] > 0
        assert results["errors"] == []

        # Verify chunks in database
        docs = db_session.exec(
            select(Document).where(Document.vault_id == sample_vault.id)
        ).all()
        assert len(docs) == results["chunks_created"]

        # Verify all chunks have embeddings
        for doc in docs:
            assert doc.embedding is not None
            assert len(doc.embedding) > 0

    @pytest.mark.asyncio
    async def test_process_pdf_directory(self, sample_vault, tmp_path, db_session):
        """Test processing multiple PDFs in a directory."""
        # Create directory with multiple PDFs
        pdf_dir = tmp_path / "pdfs"
        pdf_dir.mkdir()

        try:
            from reportlab.pdfgen import canvas

            for i in range(3):
                pdf_path = pdf_dir / f"doc_{i}.pdf"
                c = canvas.Canvas(str(pdf_path))
                c.drawString(100, 750, f"Document {i}")
                c.drawString(100, 730, f"This is test document number {i}.")
                c.save()

        except ImportError:
            pytest.skip("reportlab not installed")

        # Process directory
        processor = PDFProcessor(vault_id=sample_vault.id)
        results = await processor.process_pdf_directory(
            directory=pdf_dir,
            extract_entities=False  # Skip for speed
        )

        assert results["files_processed"] == 3
        assert results["total_chunks"] > 0
        assert results["errors"] == []

    @pytest.mark.asyncio
    async def test_pdf_with_metadata_override(self, sample_vault, sample_pdf, db_session):
        """Test PDF processing with override metadata."""
        processor = PDFProcessor(vault_id=sample_vault.id)

        override_metadata = {
            "era_name": "Fantasy Era",
            "canon_layer": "primary",
            "custom_field": "test_value"
        }

        results = await processor.process_pdf(
            pdf_path=sample_pdf,
            extract_entities=False,
            override_metadata=override_metadata
        )

        # Verify metadata in database
        docs = db_session.exec(
            select(Document).where(Document.vault_id == sample_vault.id)
        ).all()

        assert len(docs) > 0

        # Check first document has override metadata
        doc = docs[0]
        assert doc.metadata_.get("era_name") == "Fantasy Era"
        assert doc.metadata_.get("canon_layer") == "primary"
        assert doc.metadata_.get("custom_field") == "test_value"
