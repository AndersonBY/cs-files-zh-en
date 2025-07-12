"""
File processing utilities for CS:GO Files Downloader
"""

import logging
from pathlib import Path
from typing import Dict, List, Union

logger = logging.getLogger(__name__)


def trim_bom(data: Union[bytes, str]) -> Union[bytes, str]:
    """
    Remove UTF-8 BOM from file data for compatibility

    Args:
        data: Raw file data (bytes or string)

    Returns:
        Data with BOM removed if present
    """
    if isinstance(data, bytes) and len(data) >= 3 and data[:3] == b"\xef\xbb\xbf":
        return data[3:]
    elif isinstance(data, str) and data.startswith("\ufeff"):
        return data[1:]
    return data


def save_file(file_path: Path, data: bytes, remove_bom: bool = True) -> int:
    """
    Save file data to disk with optional BOM removal

    Args:
        file_path: Path to save the file
        data: File data to save
        remove_bom: Whether to remove UTF-8 BOM

    Returns:
        Number of bytes written
    """
    if remove_bom:
        data = trim_bom(data)  # type: ignore

    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "wb") as f:
        f.write(data)

    logger.info(f"Saved {file_path.name}: {len(data):,} bytes")
    return len(data)


def get_file_sizes(directory: Path, filenames: List[str]) -> Dict[str, int]:
    """
    Get file sizes for a list of files in a directory

    Args:
        directory: Directory to check
        filenames: List of filenames to check

    Returns:
        Dictionary mapping filename to size in bytes
    """
    sizes = {}
    for filename in filenames:
        file_path = directory / filename
        if file_path.exists():
            sizes[filename] = file_path.stat().st_size
        else:
            sizes[filename] = 0
    return sizes


def print_file_summary(directory: Path, filenames: List[str]) -> None:
    """
    Print a formatted summary of downloaded files

    Args:
        directory: Directory containing the files
        filenames: List of filenames to summarize
    """
    print("\nDownloaded files:")
    sizes = get_file_sizes(directory, filenames)

    for filename, size in sizes.items():
        if size > 0:
            print(f"  {filename}: {size:,} bytes")
        else:
            print(f"  {filename}: NOT FOUND")


def read_manifest_id(manifest_file: Path) -> str:
    """
    Read existing manifest ID from file

    Args:
        manifest_file: Path to manifest file

    Returns:
        Manifest ID as string, empty if file doesn't exist
    """
    if manifest_file.exists():
        return manifest_file.read_text().strip()
    return ""


def save_manifest_id(manifest_file: Path, manifest_id: str) -> None:
    """
    Save manifest ID to file

    Args:
        manifest_file: Path to manifest file
        manifest_id: Manifest ID to save
    """
    manifest_file.write_text(str(manifest_id))
    logger.info(f"Saved manifest ID: {manifest_id}")
