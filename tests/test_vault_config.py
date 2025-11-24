import json
from uuid import UUID

from writeros.utils.vault_config import (
    ensure_graph_directory,
    get_or_create_vault_id,
    get_vault_config,
    update_vault_config,
)


def test_get_or_create_vault_id_creates_config(tmp_path):
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    vault_id = get_or_create_vault_id(vault_path)

    config_path = vault_path / ".writeros" / "config.json"
    saved_config = json.loads(config_path.read_text(encoding="utf-8"))

    assert config_path.exists()
    assert UUID(saved_config["vault_id"]) == vault_id


def test_get_or_create_vault_id_reads_existing(tmp_path):
    vault_path = tmp_path / "vault"
    config_path = vault_path / ".writeros" / "config.json"
    config_path.parent.mkdir(parents=True)

    existing_id = UUID(int=1)
    config_path.write_text(
        json.dumps({"vault_id": str(existing_id), "version": "1.0"}),
        encoding="utf-8",
    )

    retrieved_id = get_or_create_vault_id(vault_path)

    assert retrieved_id == existing_id


def test_get_vault_config_missing_returns_empty(tmp_path):
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    assert get_vault_config(vault_path) == {}


def test_update_vault_config_preserves_existing_values(tmp_path):
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    config_path = vault_path / ".writeros" / "config.json"
    config_path.parent.mkdir(parents=True)

    original_id = UUID(int=2)
    config_path.write_text(
        json.dumps({"vault_id": str(original_id), "version": "1.0"}),
        encoding="utf-8",
    )

    update_vault_config(vault_path, {"version": "2.0", "notes": "updated"})
    updated = json.loads(config_path.read_text(encoding="utf-8"))

    assert updated["vault_id"] == str(original_id)
    assert updated["version"] == "2.0"
    assert updated["notes"] == "updated"
    assert "updated_at" in updated


def test_ensure_graph_directory_creates_structure(tmp_path):
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    graph_dir = ensure_graph_directory(vault_path)

    assert graph_dir.exists()
    assert graph_dir.name == "graphs"
    assert graph_dir.parent.name == ".writeros"
