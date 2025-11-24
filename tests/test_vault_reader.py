from pathlib import Path

from writeros.utils.vault_reader import VaultRegistry


def build_sample_vault(tmp_path: Path, include_project: bool = False, include_writing: bool = True) -> Path:
    vault_path = tmp_path / "vault"
    story_bible = vault_path / "Story_Bible"
    characters = story_bible / "Characters"
    locations = story_bible / "Locations"

    characters.mkdir(parents=True)
    locations.mkdir(parents=True)

    hero_content = """aliases: [Ace, TheHero]\nRole: Commander\n[[Neo Tokyo]] is the base."""
    location_content = """aliases: [Neo]\nA glittering city. [[Hero]] visits."""

    (characters / "Hero.md").write_text(hero_content, encoding="utf-8")
    (locations / "Neo Tokyo.md").write_text(location_content, encoding="utf-8")

    if include_writing:
        writing_bible = vault_path / "Writing_Bible"
        writing_bible.mkdir()
        (writing_bible / "Rule.md").write_text("Show, don't tell.", encoding="utf-8")

    if include_project:
        project_bible = vault_path / "00_Project_Bible"
        project_bible.mkdir()
        (project_bible / "Roadmap.md").write_text("Plan the arc.", encoding="utf-8")

    return vault_path


def test_refresh_index_collects_entities_and_rules(tmp_path):
    vault_path = build_sample_vault(tmp_path)
    registry = VaultRegistry(str(vault_path))

    assert "Hero" in registry.entities
    assert "Neo Tokyo" in registry.entities
    assert registry.aliases["Ace"] == "Hero"
    assert "Rule" in registry.craft_rules
    assert "Rule" in registry.get_craft_context()


def test_get_relevant_context_matches_aliases(tmp_path):
    vault_path = build_sample_vault(tmp_path)
    registry = VaultRegistry(str(vault_path))

    context = registry.get_relevant_context("Ace travels to Neo Tokyo")

    assert "[Characters]" in context
    assert "[Locations]" in context
    assert "Ace" not in registry.entities


def test_get_relevant_context_without_matches_returns_default(tmp_path):
    vault_path = build_sample_vault(tmp_path)
    registry = VaultRegistry(str(vault_path))

    context = registry.get_relevant_context("No known entities here")

    assert context == "No specific Story Bible entities detected."


def test_get_craft_context_handles_missing_rules(tmp_path):
    vault_path = build_sample_vault(tmp_path, include_writing=False)
    registry = VaultRegistry(str(vault_path))

    assert registry.get_craft_context() == "No custom writing rules found. Use general best practices."


def test_get_global_context_includes_project_and_counts(tmp_path):
    vault_path = build_sample_vault(tmp_path, include_project=True)
    registry = VaultRegistry(str(vault_path))

    context = registry.get_global_context()

    assert "Roadmap.md" in context
    assert "Total Entities: 2" in context


def test_get_global_context_when_project_missing(tmp_path):
    vault_path = build_sample_vault(tmp_path, include_project=False)
    registry = VaultRegistry(str(vault_path))

    context = registry.get_global_context()

    assert "No Project Bible folder" in context


def test_execute_structured_query_filters_by_type_and_value(tmp_path):
    vault_path = build_sample_vault(tmp_path)
    registry = VaultRegistry(str(vault_path))

    results = registry.execute_structured_query("Characters", "Role", "commander")
    all_characters = registry.execute_structured_query("Characters", "", "")

    assert results == ["Hero"]
    assert all_characters == ["Hero"]


def test_get_neighbors_returns_unique_links(tmp_path):
    vault_path = build_sample_vault(tmp_path)
    registry = VaultRegistry(str(vault_path))

    neighbors = registry.get_neighbors("Hero")
    missing_entity_neighbors = registry.get_neighbors("Unknown")

    assert neighbors == ["Neo Tokyo"]
    assert missing_entity_neighbors == []
