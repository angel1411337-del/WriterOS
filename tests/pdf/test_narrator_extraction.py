"""
Tests for narrator claims extraction.

Tests:
- Pattern 1: "X claims that Y"
- Pattern 2: "According to X, Y"
- Pattern 3: "X's account states Y"
- Narrator claims in chunk metadata
- Conflicting sources flag
"""
import pytest

from writeros.utils.indexer import VaultIndexer


class TestNarratorExtraction:
    """Test suite for narrator claims detection."""
    
    def test_extract_narrator_claims_pattern_1(self, sample_vault_id, tmp_path):
        """Test 'X claims that Y' pattern."""
        indexer = VaultIndexer(
            vault_path=tmp_path,
            vault_id=sample_vault_id
        )
        
        text = """
        Mushroom claims that Rhaenyra poisoned the King.
        Septon Eustace claims that the King died naturally.
        """
        
        claims = indexer.extract_narrator_claims(text)
        
        # Verify claims extracted
        assert len(claims) >= 2
        
        # Verify Mushroom claim
        mushroom_claims = [c for c in claims if "Mushroom" in c["narrator"]]
        assert len(mushroom_claims) > 0
        assert "poisoned" in mushroom_claims[0]["claim"].lower()
        
        # Verify Septon Eustace claim
        eustace_claims = [c for c in claims if "Eustace" in c["narrator"]]
        assert len(eustace_claims) > 0
        assert "naturally" in eustace_claims[0]["claim"].lower()
    
    def test_extract_narrator_claims_pattern_2(self, sample_vault_id, tmp_path):
        """Test 'According to X, Y' pattern."""
        indexer = VaultIndexer(
            vault_path=tmp_path,
            vault_id=sample_vault_id
        )
        
        text = """
        According to Mushroom, the Queen was furious.
        According to Septon Eustace, the Queen remained calm.
        """
        
        claims = indexer.extract_narrator_claims(text)
        
        # Verify claims extracted
        assert len(claims) >= 2
        
        # Verify pattern detected
        assert any(c["pattern"] == "according_to" for c in claims)
        
        # Verify narrators
        narrators = [c["narrator"] for c in claims]
        assert "Mushroom" in narrators
        assert "Septon Eustace" in narrators
    
    def test_extract_narrator_claims_pattern_3(self, sample_vault_id, tmp_path):
        """Test 'X's account states Y' pattern."""
        indexer = VaultIndexer(
            vault_path=tmp_path,
            vault_id=sample_vault_id
        )
        
        text = """
        Grand Maester Munkun's account states that the battle was fierce.
        Archmaester Gyldayn's account claims the truth is unclear.
        """
        
        claims = indexer.extract_narrator_claims(text)
        
        # Verify claims extracted
        assert len(claims) >= 2
        
        # Verify pattern detected
        assert any(c["pattern"] == "account_states" for c in claims)
        
        # Verify narrators
        narrators = [c["narrator"] for c in claims]
        assert any("Munkun" in n for n in narrators)
        assert any("Gyldayn" in n for n in narrators)
    
    def test_extract_narrator_claims_no_false_positives(self, sample_vault_id, tmp_path):
        """Test that common words don't trigger false positives."""
        indexer = VaultIndexer(
            vault_path=tmp_path,
            vault_id=sample_vault_id
        )
        
        text = """
        He claims that the sword was lost.
        She says that the battle was won.
        It states that the war ended.
        """
        
        claims = indexer.extract_narrator_claims(text)
        
        # Verify no claims extracted (pronouns should be filtered)
        assert len(claims) == 0
    
    def test_extract_narrator_claims_mixed_patterns(self, sample_vault_id, tmp_path):
        """Test extraction with multiple pattern types."""
        indexer = VaultIndexer(
            vault_path=tmp_path,
            vault_id=sample_vault_id
        )
        
        text = """
        Mushroom claims that the King was poisoned.
        According to Septon Eustace, the King died naturally.
        Grand Maester Munkun's account states the truth is unknown.
        """
        
        claims = indexer.extract_narrator_claims(text)
        
        # Verify all patterns detected
        patterns = [c["pattern"] for c in claims]
        assert "claims_that" in patterns
        assert "according_to" in patterns
        assert "account_states" in patterns
        
        # Verify all narrators extracted
        narrators = [c["narrator"] for c in claims]
        assert "Mushroom" in narrators
        assert any("Eustace" in n for n in narrators)
        assert any("Munkun" in n for n in narrators)
