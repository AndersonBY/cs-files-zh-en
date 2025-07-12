#!/usr/bin/env python3
"""
CS:GO Files Downloader
Fetches items_game.txt and csgo_english.txt from Steam CDN
"""

import sys
import logging

from .config import Config
from .auth.steam_auth import SteamAuthenticator
from .cdn.steam_cdn import SteamCDNManager
from .vpk.vpk_handler import VPKProcessor
from .utils.file_utils import read_manifest_id, save_manifest_id, print_file_summary

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run_demo_mode() -> None:
    """Run demo mode without Steam login"""
    logger.info("Running in demo mode (no Steam login required)")
    from .demo.downloader import download_from_steamcmd_api

    download_from_steamcmd_api()


def download_csgo_files(username: str, password: str, two_factor_code: str | None = None) -> bool:
    """
    Download CS:GO files using Steam CDN

    Args:
        username: Steam username
        password: Steam password
        two_factor_code: Optional 2FA code

    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure directories exist
        Config.ensure_directories()

        # Authenticate with Steam
        with SteamAuthenticator() as auth:
            if not auth.login(username, password, two_factor_code):
                logger.error("Steam authentication failed")
                return False

            # Initialize CDN manager
            cdn_manager = SteamCDNManager(auth.client)

            # Get latest manifest info
            latest_manifest_id, _ = cdn_manager.get_latest_manifest_info()

            # Check if we need to update
            manifest_file = Config.get_manifest_file_path()
            existing_manifest_id = read_manifest_id(manifest_file)

            if existing_manifest_id == latest_manifest_id:
                logger.info("Latest manifest ID matches existing, no update needed")
                return True

            logger.info("Manifest ID differs, downloading game files...")

            # Get manifest
            manifest = cdn_manager.get_manifest(latest_manifest_id)

            # Try direct extraction first
            if cdn_manager.extract_files_directly(manifest):
                logger.info("Files extracted directly from manifest")
            else:
                logger.info("Direct extraction failed, using VPK method...")

                # VPK processing fallback
                vpk_processor = VPKProcessor()

                # Download VPK directory
                vpk_dir_path = cdn_manager.download_vpk_dir(manifest)
                vpk_dir = vpk_processor.load_vpk_directory(vpk_dir_path)

                # Get required archive indices
                required_indices = vpk_processor.get_required_archive_indices(vpk_dir)

                if required_indices:
                    # Download required archives
                    cdn_manager.download_vpk_archives(manifest, required_indices)

                # Extract target files
                vpk_processor.extract_target_files(vpk_dir)

            # Save new manifest ID
            save_manifest_id(manifest_file, latest_manifest_id)

            logger.info("Download completed successfully!")

            # Print summary
            print_file_summary(Config.get_static_path(), Config.get_target_filenames())

            return True

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return False
    except Exception as e:
        logger.error(f"Download failed: {e}", exc_info=True)
        return False


def main() -> None:
    """Main entry point"""
    # Check for demo mode
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ["--demo", "-d"]):
        run_demo_mode()
        return

    # Validate arguments
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print(f"Usage: {sys.argv[0]} <username> <password> [two_factor_code]")
        print(f"       {sys.argv[0]} --demo    (create sample files)")
        print("Downloads CS:GO game files from Steam CDN")
        sys.exit(1)

    # Parse arguments
    username = sys.argv[1]
    password = sys.argv[2]
    two_factor_code = sys.argv[3] if len(sys.argv) == 4 else None

    # Run download
    success = download_csgo_files(username, password, two_factor_code)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
