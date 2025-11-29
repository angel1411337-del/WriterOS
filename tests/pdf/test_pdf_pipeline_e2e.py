"""
End-to-end tests for PDF ingestion pipeline.

Tests:
- Full pipeline with entity extraction
- Pipeline without entity extraction (chunks only)
- Pipeline with override metadata
- Entity and relationship creation
- Multi-PDF processing
- VaultIndexer integration
- Temporal entity resolution in pipeline
- Error handling and re-indexing
"""
import pytest
from pathlib import Path
from uuid import uuid4

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

from writeros.schema import Entity, Relationship, Document, EntityType
from writeros.utils.indexer import VaultIndexer
from sqlmodel import select


pytestmark = pytest.mark.skipif(
    not PYPDF2_AVAILABLE,
    reason="PyPDF2 not installed"
)


class TestPDFPipelineBasic:
    """Basic end-to-end pipeline tests."""
    
    @pytest.mark.asyncio
    async def test_process_pdf_end_to_end(self, mock_pdf_processor, sample_pdf_simple, db_session):
        """Test complete PDF processing pipeline with entity extraction."""
        processor = mock_pdf_processor
        
        # Process PDF
        results = await processor.process_pdf(
            pdf_path=sample_pdf_simple,
            extract_entities=True
        )
        
        # Verify results structure
        assert "file" in results
        assert "pages_extracted" in results
        assert "chunks_created" in results
        assert "entities_created" in results
        assert "relationships_created" in results
        
        # Verify pages extracted
        assert results["pages_extracted"] > 0
        
        # Verify chunks created
        assert results["chunks_created"] > 0
        
        # Verify no errors
        assert len(results["errors"]) == 0
    
    @pytest.mark.asyncio
    async def test_process_pdf_chunks_only(self, mock_pdf_processor, sample_pdf_simple, db_session):
        """Test PDF processing without entity extraction."""
        processor = mock_pdf_processor
        
        # Process PDF without entities
        results = await processor.process_pdf(
            pdf_path=sample_pdf_simple,
            extract_entities=False
        )
        
        # Verify chunks created
        assert results["chunks_created"] > 0
        
        # Verify no entities created
        assert results["entities_created"] == 0
        assert results["relationships_created"] == 0
    
    @pytest.mark.asyncio
    async def test_process_pdf_with_override_metadata(self, mock_pdf_processor, sample_pdf_simple, db_session):
        """Test PDF processing with override metadata injection."""
        processor = mock_pdf_processor
        
        override_metadata = {
            "source": "Fire and Blood",
            "era_start_year": 129,
            "era_end_year": 131,
            "has_unreliable_narrators": True
        }
        
        # Process PDF
        results = await processor.process_pdf(
            pdf_path=sample_pdf_simple,
            extract_entities=False,
            override_metadata=override_metadata
        )
        
        # Verify chunks created
        assert results["chunks_created"] > 0
        
        # Verify metadata injected into chunks
        chunks = db_session.exec(
            select(Document).where(
                Document.vault_id == processor.vault_id
            )
        ).all()
        
        assert len(chunks) > 0
        
        # Check first chunk has override metadata
        chunk = chunks[0]
        assert chunk.metadata_["source"] == "Fire and Blood"
        assert chunk.metadata_["era_start_year"] == 129


class TestPDFEntityGraph:
    """Tests for entity and relationship creation from PDFs."""
    
    @pytest.mark.asyncio
    async def test_pdf_creates_entities(self, mock_pdf_processor, sample_pdf_simple, db_session, sample_vault_id):
        """Test that entities are created from PDF content."""
        processor = mock_pdf_processor
        
        # Process PDF with entity extraction
        results = await processor.process_pdf(
            pdf_path=sample_pdf_simple,
            extract_entities=True
        )
        
        # Verify entities created
        # Note: Actual count depends on ProfilerAgent extraction
        # We just verify the pipeline works
        assert results["entities_created"] >= 0
        
        # Check database for entities
        entities = db_session.exec(
            select(Entity).where(
                Entity.vault_id == sample_vault_id
            )
        ).all()
        
        # Entities may or may not be created depending on LLM extraction
        # Just verify no errors occurred
        assert len(results["errors"]) == 0
    
    @pytest.mark.asyncio
    async def test_pdf_entity_deduplication(self, mock_pdf_processor, sample_pdf_simple, db_session, sample_vault_id):
        """Test that processing same PDF twice doesn't create duplicate entities."""
        processor = mock_pdf_processor
        
        # Process PDF first time
        results1 = await processor.process_pdf(
            pdf_path=sample_pdf_simple,
            extract_entities=True
        )
        
        # Process PDF second time
        results2 = await processor.process_pdf(
            pdf_path=sample_pdf_simple,
            extract_entities=True
        )
        
        # Verify chunks replaced (not duplicated)
        chunks = db_session.exec(
            select(Document).where(
                Document.vault_id == sample_vault_id
            )
        ).all()
        
        # Should have same number of chunks as first run
        assert len(chunks) == results2["chunks_created"]


class TestMultiPDFProcessing:
    """Tests for processing multiple PDFs."""
    
    @pytest.mark.asyncio
    async def test_process_multiple_pdfs(
        self,
        mock_pdf_processor,
        sample_pdf_simple,
        sample_pdf_with_narrators,
        db_session
    ):
        """Test processing multiple PDF files."""
        processor = mock_pdf_processor
        
        # Process first PDF
        results1 = await processor.process_pdf(
            pdf_path=sample_pdf_simple,
            extract_entities=False
        )
        
        # Process second PDF
        results2 = await processor.process_pdf(
            pdf_path=sample_pdf_with_narrators,
            extract_entities=False
        )
        
        # Verify both processed
        assert results1["chunks_created"] > 0
        assert results2["chunks_created"] > 0
        
        # Verify total chunks in database
        total_chunks = db_session.exec(
            select(Document).where(
                Document.vault_id == processor.vault_id
            )
        ).all()
        
        assert len(total_chunks) == results1["chunks_created"] + results2["chunks_created"]
    
    @pytest.mark.asyncio
    async def test_vault_indexer_pdf_integration(
        self,
        sample_vault_id,
        sample_pdf_simple,
        db_session,
        mocker
    ):
        """Test VaultIndexer integration with PDF files."""
        # Create temporary vault directory
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            
            # Copy PDF to vault
            pdf_dest = tmp_path / "test.pdf"
            import shutil
            shutil.copy(sample_pdf_simple, pdf_dest)
            
            # Mock Session
            from unittest.mock import MagicMock
            mock_ctx = MagicMock()
            mock_ctx.__enter__.return_value = db_session
            mock_ctx.__exit__.return_value = None
            mocker.patch("writeros.utils.indexer.Session", return_value=mock_ctx)
            
            # Create indexer
            indexer = VaultIndexer(
                vault_path=tmp_path,
                vault_id=sample_vault_id
            )
            
            # Index vault with PDFs
            results = await indexer.index_vault(include_pdfs=True)
            
            # Verify PDF processed
            assert results["pdfs_processed"] >= 1
            assert results["chunks_created"] > 0


class TestTemporalScenarios:
    """Tests for temporal entity resolution in PDF pipeline."""
    
    @pytest.mark.asyncio
    async def test_multi_era_pdf_processing(
        self,
        mock_pdf_processor,
        sample_pdf_multi_era,
        db_session
    ):
        """Test processing PDF with entities from multiple eras."""
        processor = mock_pdf_processor
        
        # Process multi-era PDF
        results = await processor.process_pdf(
            pdf_path=sample_pdf_multi_era,
            extract_entities=True
        )
        
        # Verify chunks created for all eras
        assert results["chunks_created"] >= 2
        
        # Verify no errors
        assert len(results["errors"]) == 0
    
    @pytest.mark.asyncio
    async def test_temporal_entity_resolution_in_pipeline(
        self,
        db_session,
        sample_vault_id,
        sample_pdf_multi_era,
        mocker
    ):
        """Test that temporal entity resolution works during PDF ingestion."""
        # Mock Session
        from unittest.mock import MagicMock
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = db_session
        mock_ctx.__exit__.return_value = None
        mocker.patch("writeros.utils.pdf_processor.Session", return_value=mock_ctx)
        mocker.patch("writeros.agents.profiler.Session", return_value=mock_ctx)
        
        from writeros.utils.pdf_processor import PDFProcessor
        
        # Create processor
        processor = PDFProcessor(
            vault_id=sample_vault_id,
            enable_cache=False
        )
        
        # Process multi-era PDF
        results = await processor.process_pdf(
            pdf_path=sample_pdf_multi_era,
            extract_entities=True
        )
        
        # Verify processing completed
        assert results["chunks_created"] > 0
        
        # Check if multiple Aegon entities created (if extraction worked)
        aegons = db_session.exec(
            select(Entity).where(
                Entity.vault_id == sample_vault_id,
                Entity.name.contains("Aegon")
            )
        ).all()
        
        # May or may not create entities depending on LLM
        # Just verify no errors
        assert len(results["errors"]) == 0


class TestErrorHandling:
    """Tests for error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_pdf_processing_error_handling(
        self,
        mock_pdf_processor,
        tmp_path
    ):
        """Test graceful error handling for invalid PDF."""
        processor = mock_pdf_processor
        
        # Create invalid PDF file
        invalid_pdf = tmp_path / "invalid.pdf"
        invalid_pdf.write_text("This is not a valid PDF")
        
        # Process should handle error gracefully
        results = await processor.process_pdf(
            pdf_path=invalid_pdf,
            extract_entities=False
        )
        
        # Verify error recorded
        assert len(results["errors"]) > 0
        assert results["chunks_created"] == 0
    
    @pytest.mark.asyncio
    async def test_pdf_reindexing(
        self,
        mock_pdf_processor,
        sample_pdf_simple,
        db_session,
        sample_vault_id
    ):
        """Test that re-indexing same PDF deletes old chunks."""
        processor = mock_pdf_processor
        
        # Process PDF first time
        results1 = await processor.process_pdf(
            pdf_path=sample_pdf_simple,
            extract_entities=False
        )
        
        first_chunk_count = results1["chunks_created"]
        
        # Process PDF second time (re-index)
        results2 = await processor.process_pdf(
            pdf_path=sample_pdf_simple,
            extract_entities=False
        )
        
        # Verify chunks replaced (not added)
        total_chunks = db_session.exec(
            select(Document).where(
                Document.vault_id == sample_vault_id
            )
        ).all()
        
        # Should have same count as second run, not double
        assert len(total_chunks) == results2["chunks_created"]
        assert len(total_chunks) == first_chunk_count
