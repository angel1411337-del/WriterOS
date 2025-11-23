"""
Agent Tools
Safe tools for agents to interact with the file system.
"""
import shutil
from pathlib import Path
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

ALLOWED_WRITE_DIRECTORIES = [
    "Story_Bible/Characters",
    "Story_Bible/Locations",
    "Story_Bible/Factions",
    "Writing_Bible",
    ".writeros/generated"
]

async def write_file(
    path: str, 
    content: str, 
    vault_path: str,
    overwrite: bool = False
) -> Dict[str, Any]:
    """
    Safely write a file to the vault.
    """
    vault_path_obj = Path(vault_path)
    
    # 1. Validate Directory
    # Normalize path separators
    normalized_path = path.replace("\\", "/")
    
    is_allowed = False
    for allowed_dir in ALLOWED_WRITE_DIRECTORIES:
        if normalized_path.startswith(allowed_dir) or normalized_path.startswith(allowed_dir.replace("/", "\\")):
            is_allowed = True
            break
            
    if not is_allowed:
        return {
            "success": False,
            "error": f"Cannot write to {path}. Allowed directories: {ALLOWED_WRITE_DIRECTORIES}"
        }
    
    full_path = vault_path_obj / path
    
    # 2. Check Overwrite
    if full_path.exists() and not overwrite:
        return {
            "success": False,
            "error": f"File exists. Set overwrite=True to replace.",
            "requires_confirmation": True
        }
    
    # 3. Create Backup
    if full_path.exists():
        backup_path = full_path.with_suffix('.md.bak')
        try:
            shutil.copy(full_path, backup_path)
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")
    
    # 4. Write File
    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding='utf-8')
        
        return {
            "success": True, 
            "path": str(full_path),
            "message": f"Successfully wrote to {path}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to write file: {str(e)}"
        }
