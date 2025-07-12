"""
Steam CDN client operations for CS:GO Files Downloader
"""

import logging
from pathlib import Path
from typing import Tuple, List

from steam.client import SteamClient
from steam.client.cdn import CDNClient

from ..config import Config
from ..utils.file_utils import save_file

logger = logging.getLogger(__name__)


class SteamCDNManager:
    """Manages Steam CDN operations for downloading game files"""

    def __init__(self, steam_client: SteamClient):
        self.steam_client = steam_client
        self.cdn_client = CDNClient(steam_client)

    def get_latest_manifest_info(self) -> Tuple[str, dict]:
        """
        Get latest manifest ID and app info for CS:GO

        Returns:
            Tuple of (manifest_id, app_info)

        Raises:
            ValueError: If unable to get manifest info
        """
        logger.info("Getting CS:GO product info...")

        app_info = self.steam_client.get_product_info(apps=[Config.APP_ID])

        if not app_info or "apps" not in app_info or Config.APP_ID not in app_info["apps"]:
            raise ValueError("Failed to get CS:GO app info")

        cs_info = app_info["apps"][Config.APP_ID]

        # Get depot info
        if "depots" not in cs_info or str(Config.DEPOT_ID) not in cs_info["depots"]:
            raise ValueError(f"Depot {Config.DEPOT_ID} not found in app info")

        depot_info = cs_info["depots"][str(Config.DEPOT_ID)]

        if "manifests" not in depot_info or "public" not in depot_info["manifests"]:
            raise ValueError("Public manifest not found")

        latest_manifest_id = depot_info["manifests"]["public"]["gid"]

        logger.info(f"Latest manifest ID: {latest_manifest_id}")
        return str(latest_manifest_id), cs_info

    def get_manifest(self, manifest_id: str):
        """
        Download and return manifest for given ID

        Args:
            manifest_id: Manifest ID to download

        Returns:
            Manifest object

        Raises:
            ValueError: If unable to get manifest
        """
        logger.info("Getting manifest request code...")

        try:
            manifest_request_code = self.cdn_client.get_manifest_request_code(Config.APP_ID, Config.DEPOT_ID, manifest_id)
            logger.info(f"Got manifest request code: {manifest_request_code}")
        except Exception as e:
            raise ValueError(f"Failed to get manifest request code: {e}")

        logger.info("Getting depot manifest...")
        manifest = self.cdn_client.get_manifest(Config.APP_ID, Config.DEPOT_ID, manifest_id, manifest_request_code=manifest_request_code)

        if not manifest:
            raise ValueError("Failed to get depot manifest")

        files = list(manifest.iter_files())
        logger.info(f"Manifest loaded with {len(files)} files")

        return manifest

    def extract_files_directly(self, manifest) -> bool:
        """
        Try to extract target files directly from manifest without VPK processing

        Args:
            manifest: Steam manifest object

        Returns:
            True if files were successfully extracted, False otherwise
        """
        logger.info("Attempting to extract files directly from manifest...")

        extracted_count = 0

        for file_info in manifest.iter_files():
            filename = file_info.filename.replace("\\", "/")

            for target_file in Config.VPK_FILES:
                if filename == target_file:
                    logger.info(f"Extracting {filename} directly from manifest...")

                    try:
                        # Get file data
                        file_data = file_info.read()

                        # Get just the filename for saving
                        save_filename = target_file.split("/")[-1]
                        static_path = Config.get_static_path() / save_filename

                        save_file(static_path, file_data)
                        extracted_count += 1

                    except Exception as e:
                        logger.error(f"Error extracting {filename}: {e}")
                        continue

        logger.info(f"Successfully extracted {extracted_count} files directly from manifest")
        return extracted_count > 0

    def download_vpk_dir(self, manifest) -> Path:
        """
        Download VPK directory file from manifest

        Args:
            manifest: Steam manifest object

        Returns:
            Path to downloaded VPK directory file

        Raises:
            ValueError: If VPK directory file not found or download fails
        """
        logger.info("Downloading VPK directory file...")

        # Find pak01_dir.vpk in manifest
        dir_file = None
        for file_info in manifest.iter_files():
            filename = file_info.filename.replace("\\", "/")
            if filename.endswith("csgo/pak01_dir.vpk"):
                dir_file = file_info
                break

        if not dir_file:
            raise ValueError("Could not find pak01_dir.vpk in manifest")

        temp_path = Config.get_temp_path() / "pak01_dir.vpk"
        static_path = Config.get_static_path() / "pak01_dir.vpk"

        try:
            # Download using Steam CDN
            file_data = dir_file.read()
            save_file(temp_path, file_data, remove_bom=False)
            save_file(static_path, file_data, remove_bom=False)

            return temp_path

        except Exception as e:
            # Fallback - try to use existing file if available
            if static_path.exists():
                logger.warning(f"Download failed ({e}), using existing VPK dir file")
                import shutil

                shutil.copy2(static_path, temp_path)
                return temp_path
            else:
                raise ValueError(f"Error downloading VPK dir: {e}")

    def download_vpk_archives(self, manifest, required_indices: List[int]) -> None:
        """
        Download required VPK archive files

        Args:
            manifest: Steam manifest object
            required_indices: List of archive indices to download
        """
        logger.info(f"Downloading {len(required_indices)} VPK archive files...")

        for i, archive_index in enumerate(required_indices):
            # Pad to 3 digits
            padded_index = f"{archive_index:03d}"
            filename = f"pak01_{padded_index}.vpk"

            # Find file in manifest
            file_info = None
            for f in manifest.iter_files():
                if f.filename.endswith(filename):
                    file_info = f
                    break

            if not file_info:
                logger.warning(f"Could not find {filename} in manifest")
                continue

            temp_path = Config.get_temp_path() / filename
            status = f"[{i + 1}/{len(required_indices)}]"

            logger.info(f"{status} Downloading {filename}")

            try:
                # Download file from Steam CDN
                file_data = file_info.read()
                save_file(temp_path, file_data, remove_bom=False)

            except Exception as e:
                logger.error(f"Error downloading {filename}: {e}")
                continue
