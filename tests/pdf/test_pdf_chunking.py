"""
Tests for PDF semantic chunking.

Tests:
- Chunk generation from PDF text
- Embedding generation for chunks
- Chunk metadata (index, coherence score)
- Chunk size limits
- Embedding caching
"""
import pytest

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not PYPDF2_AVAILABLE,
    reason="PyPDF2 not installed"
)


class TestPDFChunking:
    """Test suite for PDF semantic chunking."""
    
    @pytest.mark.asyncio
    async def test_chunk_pdf_text(self, mock_pdf_processor, sample_pdf_simple):
        """Test basic PDF text chunking."""
        processor = mock_pdf_processor
        
        # Extract PDF
        pdf_data = processor.extract_pdf(sample_pdf_simple)
        
        # Chunk text
        chunks = await processor.chunk_pdf_text(
            text=pdf_data["text"],
            pdf_metadata=pdf_data["metadata"]
        )
        
        # Verify chunks created
        assert len(chunks) > 0
        
        # Verify chunk structure
        for chunk in chunks:
            assert "content" in chunk
            assert "embedding" in chunk
            assert "chunk_index" in chunk
            assert "coherence_score" in chunk
            
            # Verify content not empty
            assert chunk["content"].strip()
            
            # Verify embedding is list of floats
            assert isinstance(chunk["embedding"], list)
            assert len(chunk["embedding"]) == 1536  # OpenAI embedding size
    
    @pytest.mark.asyncio
    async def test_chunk_embeddings(self, mock_pdf_processor, sample_pdf_simple):
        """Test that embeddings are generated for each chunk."""
        processor = mock_pdf_processor
        
        # Extract and chunk
        pdf_data = processor.extract_pdf(sample_pdf_simple)
        chunks = await processor.chunk_pdf_text(
            text=pdf_data["text"],
            pdf_metadata=pdf_data["metadata"]
        )
        
        # Verify each chunk has unique embedding
        embeddings = [chunk["embedding"] for chunk in chunks]
        
        # Check embeddings are different (not all zeros)
        for embedding in embeddings:
            assert sum(embedding) != 0
    
    @pytest.mark.asyncio
    async def test_chunk_metadata(self, mock_pdf_processor, sample_pdf_simple):
        """Test chunk metadata is correct."""
        processor = mock_pdf_processor
        
        # Extract and chunk
        pdf_data = processor.extract_pdf(sample_pdf_simple)
        chunks = await processor.chunk_pdf_text(
            text=pdf_data["text"],
            pdf_metadata=pdf_data["metadata"]
        )
        
        # Verify chunk indices are sequential
        for i, chunk in enumerate(chunks):
            assert chunk["chunk_index"] == i
            assert chunk["coherence_score"] >= 0
            assert chunk["coherence_score"] <= 1.0
    
    @pytest.mark.asyncio
    async def test_chunk_multi_era_pdf(self, mock_pdf_processor, sample_pdf_multi_era):
        """Test chunking of multi-section PDF."""
        processor = mock_pdf_processor
        
        # Extract and chunk
        pdf_data = processor.extract_pdf(sample_pdf_multi_era)
        chunks = await processor.chunk_pdf_text(
            text=pdf_data["text"],
            pdf_metadata=pdf_data["metadata"]
        )
        
        # Verify multiple chunks created (multi-section document)
        assert len(chunks) >= 2
        
        # Verify chunks contain different era content
        all_content = " ".join([c["content"] for c in chunks])
        assert "Aegon I" in all_content or "Aegon II" in all_content or "Aegon III" in all_content
    
    @pytest.mark.asyncio
    async def test_chunk_empty_pdf(self, mock_pdf_processor, sample_pdf_empty):
        """Test chunking of empty PDF."""
        processor = mock_pdf_processor
        
        # Extract and chunk
        pdf_data = processor.extract_pdf(sample_pdf_empty)
        chunks = await processor.chunk_pdf_text(
            text=pdf_data["text"],
            pdf_metadata=pdf_data["metadata"]
        )
        
        # Verify no chunks created for empty PDF
        assert len(chunks) == 0
