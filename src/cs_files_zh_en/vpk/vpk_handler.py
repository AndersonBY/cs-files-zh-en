"""
VPK file processing for CS:GO Files Downloader
"""

import re
import logging
from pathlib import Path
from typing import List, Set

import vpk

from ..config import Config
from ..utils.file_utils import save_file

logger = logging.getLogger(__name__)


class VPKProcessor:
    """Handles VPK file operations and archive processing"""

    def __init__(self):
        self.vpk_dir = None

    def load_vpk_directory(self, vpk_dir_path: Path):
        """
        Load VPK directory file

        Args:
            vpk_dir_path: Path to pak01_dir.vpk file

        Returns:
            VPK directory object
        """
        logger.info(f"Loading VPK directory from {vpk_dir_path}")

        self.vpk_dir = vpk.open(str(vpk_dir_path))
        file_count = len(list(self.vpk_dir))

        logger.info(f"VPK directory loaded with {file_count} files")
        return self.vpk_dir

    def get_required_archive_indices(self, vpk_dir) -> List[int]:
        """
        Determine which VPK archive indices are needed for target files

        This method uses multiple strategies to extract archive indices,
        including parsing error messages as documented in CLAUDE.md

        Args:
            vpk_dir: VPK directory object

        Returns:
            Sorted list of required archive indices
        """
        logger.info("Determining required VPK archive indices...")
        required_indices: Set[int] = set()

        # Strategy 1: Try to use VPK tree if available
        if hasattr(vpk_dir, "tree") and vpk_dir.tree is not None:
            logger.info(f"Using VPK tree with {len(vpk_dir.tree)} entries")
            required_indices.update(self._extract_indices_from_tree(vpk_dir))
        else:
            logger.info("VPK tree not available, using iteration method")
            required_indices.update(self._extract_indices_from_iteration(vpk_dir))

        result = sorted(list(required_indices))
        logger.info(f"Required archive indices: {result}")

        return result

    def _extract_indices_from_tree(self, vpk_dir) -> Set[int]:
        """Extract archive indices using VPK tree metadata"""
        indices = set()

        for filepath in vpk_dir.tree:
            for target_file in Config.VPK_FILES:
                if filepath.startswith(target_file):
                    logger.info(f"Found target file in tree: {filepath}")

                    try:
                        file_meta = vpk_dir.tree[filepath]
                        archive_index = self._get_archive_index_from_metadata(file_meta)

                        if archive_index is not None and archive_index != 0x7FFF:
                            indices.add(archive_index)
                            logger.info(f"  Archive index: {archive_index}")
                        else:
                            logger.warning(f"  Could not determine archive index for {filepath}")

                    except Exception as e:
                        logger.error(f"  Error accessing metadata for {filepath}: {e}")
                    break

        return indices

    def _extract_indices_from_iteration(self, vpk_dir) -> Set[int]:
        """Extract archive indices using iteration and error message parsing"""
        indices = set()
        file_count = 0

        for filepath in vpk_dir:
            file_count += 1
            if file_count <= 5:  # Log first few files for debugging
                logger.debug(f"  VPK file: {filepath}")

            for target_file in Config.VPK_FILES:
                if filepath.startswith(target_file):
                    logger.info(f"Found target file: {filepath}")
                    archive_index = self._get_archive_index_multiple_methods(vpk_dir, filepath)

                    if archive_index is not None and archive_index != 0x7FFF:
                        indices.add(archive_index)
                        logger.info(f"  ✓ Archive index: {archive_index}")
                    else:
                        logger.warning(f"  ✗ Could not determine archive index for {filepath}")
                    break

        logger.info(f"Processed {file_count} files from VPK")
        return indices

    def _get_archive_index_from_metadata(self, file_meta) -> int | None:
        """Extract archive index from file metadata object"""
        # Try different attribute names
        for attr_name in ["archive_index", "archiveIndex"]:
            if hasattr(file_meta, attr_name):
                return getattr(file_meta, attr_name)

        # Try dictionary access
        if isinstance(file_meta, dict) and "archive_index" in file_meta:
            return file_meta["archive_index"]

        return None

    def _get_archive_index_multiple_methods(self, vpk_dir, filepath: str) -> int | None:
        """Try multiple methods to get archive index for a file"""

        # Method 1: Try get_file_meta if available
        if hasattr(vpk_dir, "get_file_meta"):
            try:
                file_meta = vpk_dir.get_file_meta(filepath)
                if file_meta:
                    index = self._get_archive_index_from_metadata(file_meta)
                    if index is not None:
                        logger.debug(f"  Archive index from meta: {index}")
                        return index
            except Exception as e:
                logger.debug(f"  get_file_meta failed: {e}")

        # Method 2: Error message parsing (the innovative approach from CLAUDE.md)
        try:
            # This will intentionally fail with FileNotFoundError
            vpk_file = vpk_dir.get_vpkfile_instance(filepath, vpk_dir.get_file_meta(filepath))
            if hasattr(vpk_file, "archive_index"):
                index = vpk_file.archive_index
                logger.debug(f"  Archive index from VPKFile: {index}")
                return index
        except FileNotFoundError as e:
            # Extract archive index from error message: "pak01_354.vpk"
            error_msg = str(e)
            if "pak01_" in error_msg and ".vpk" in error_msg:
                match = re.search(r"pak01_(\d+)\.vpk", error_msg)
                if match:
                    index = int(match.group(1))
                    logger.debug(f"  Archive index from error message: {index}")
                    return index
        except Exception as e:
            logger.debug(f"  VPKFile creation failed: {e}")

        return None

    def extract_target_files(self, vpk_dir) -> None:
        """
        Extract target files from VPK directory

        Args:
            vpk_dir: VPK directory object
        """
        logger.info("Extracting target files from VPK...")

        for target_file in Config.VPK_FILES:
            found = False

            for filepath in vpk_dir:
                if filepath.startswith(target_file):
                    logger.info(f"Extracting {filepath}")

                    try:
                        # Get file data
                        vpk_file = vpk_dir[filepath]
                        file_data = vpk_file.read()

                        # Get just the filename for saving
                        filename = target_file.split("/")[-1]
                        static_path = Config.get_static_path() / filename

                        save_file(static_path, file_data)
                        found = True
                        break

                    except Exception as e:
                        logger.error(f"Error extracting {filepath}: {e}")
                        continue

            if not found:
                logger.warning(f"Could not find {target_file} in VPK")
