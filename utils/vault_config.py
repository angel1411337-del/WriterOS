"""
Vault configuration management for WriterOS graphs.
Handles vault_id creation and graph directory setup.
"""
from pathlib import Path
from uuid import UUID, uuid4
from datetime import datetime
import json
from typing import Optional


def get_or_create_vault_id(vault_path: Path) -> UUID:
    """
    Get existing vault_id from config or create new one.
    
    Args:
        vault_path: Path to the vault root directory
        
    Returns:
        UUID: The vault identifier
    """
    config_path = vault_path / ".writeros" / "config.json"
    
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding='utf-8'))
        return UUID(config['vault_id'])
    
    # Create new vault_id
    vault_id = uuid4()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    config = {
        'vault_id': str(vault_id),
        'created_at': datetime.utcnow().isoformat(),
        'version': '1.0'
    }
    
    config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
    return vault_id


def ensure_graph_directory(vault_path: Path) -> Path:
    """
    Create .writeros/graphs/ directory if it doesn't exist.
    
    Args:
        vault_path: Path to the vault root directory
        
    Returns:
        Path: The graphs directory
    """
    graph_dir = vault_path / ".writeros" / "graphs"
    graph_dir.mkdir(parents=True, exist_ok=True)
    return graph_dir


def get_vault_config(vault_path: Path) -> dict:
    """
    Read vault configuration.
    
    Args:
        vault_path: Path to the vault root directory
        
    Returns:
        dict: Vault configuration or empty dict if not found
    """
    config_path = vault_path / ".writeros" / "config.json"
    
    if not config_path.exists():
        return {}
    
    return json.loads(config_path.read_text(encoding='utf-8'))


def update_vault_config(vault_path: Path, updates: dict) -> None:
    """
    Update vault configuration with new values.
    
    Args:
        vault_path: Path to the vault root directory
        updates: Dictionary of values to update
    """
    config_path = vault_path / ".writeros" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Get existing config or create new
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding='utf-8'))
    else:
        config = {
            'vault_id': str(uuid4()),
            'created_at': datetime.utcnow().isoformat(),
            'version': '1.0'
        }
    
    # Apply updates
    config.update(updates)
    config['updated_at'] = datetime.utcnow().isoformat()
    
    config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
