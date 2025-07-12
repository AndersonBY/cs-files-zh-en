#!/usr/bin/env python3
"""
CS:GO Files Downloader
Fetches items_game.txt and csgo_english.txt from Steam CDN
"""

import sys
import time
import shutil
from pathlib import Path

import vpk
from steam.enums import EResult
from steam.client import SteamClient
from steam.client.cdn import CDNClient


APP_ID = 730
DEPOT_ID = 2347770
STATIC_DIR = "./static"
TEMP_DIR = "./temp"
MANIFEST_ID_FILE = "manifestId.txt"

VPK_FILES = [
    "resource/csgo_english.txt",
    "resource/csgo_schinese.txt",
    "scripts/items/items_game.txt",
]


def download_vpk_dir(cdn, manifest):
    """Download VPK directory file"""
    dir_file = None

    # Find pak01_dir.vpk in manifest using iter_files
    for file_info in manifest.iter_files():
        filename = file_info.filename.replace("\\", "/")
        if filename.endswith("csgo/pak01_dir.vpk"):
            dir_file = file_info
            break

    if not dir_file:
        raise ValueError("Could not find pak01_dir.vpk in manifest")

    print("Downloading vpk dir")

    # Download using Steam CDN
    temp_path = Path(TEMP_DIR) / "pak01_dir.vpk"
    static_path = Path(STATIC_DIR) / "pak01_dir.vpk"

    # Get the depot file
    try:
        # Use the file's read method directly
        file_data = dir_file.read()

        with open(temp_path, "wb") as f:
            f.write(file_data)

        # Copy to static directory
        shutil.copy2(temp_path, static_path)

    except Exception as e:
        print(f"Error downloading VPK dir: {e}")
        # Fallback - try to use existing file if available
        if static_path.exists():
            print("Using existing VPK dir file")
            shutil.copy2(static_path, temp_path)
        else:
            raise

    # Load VPK directory
    vpk_dir = vpk.open(str(temp_path))

    return vpk_dir


def get_required_vpk_files_from_manifest(manifest):
    """Get list of required VPK archive indices by checking which archives contain our target files"""
    print("Searching for target files in manifest...")

    # We'll use a different approach - download all VPK archives first,
    # or use a simplified approach by extracting files directly from manifest

    # For now, let's try to find our target files directly in the manifest
    found_files = []
    for file_info in manifest.iter_files():
        filename = file_info.filename.replace("\\", "/")
        for target_file in VPK_FILES:
            if filename == target_file:
                found_files.append((target_file, file_info))
                print(f"Found target file directly in manifest: {filename}")

    # If we found files directly, we don't need VPK processing
    if found_files:
        print("Files found directly in manifest, skipping VPK processing")
        return []

    # Otherwise, we need to download some VPK archives
    # Let's try a more conservative approach - download commonly used indices
    print("Files not found directly, will need VPK processing")
    return [243]  # Common archive index, we'll expand if needed


def get_required_vpk_files(vpk_dir):
    """Get list of required VPK archive indices by accessing VPK tree metadata"""
    required_indices = set()

    print("Searching VPK tree for target files...")
    print(f"VPK tree type: {type(vpk_dir.tree)}")

    # Check if tree exists and is not None
    if hasattr(vpk_dir, "tree") and vpk_dir.tree is not None:
        print(f"VPK tree has {len(vpk_dir.tree)} entries")

        for filepath in vpk_dir.tree:
            for target_file in VPK_FILES:
                if filepath.startswith(target_file):
                    print(f"Found vpk for {target_file}: {filepath}")

                    try:
                        # Get file metadata from tree without creating VPKFile object
                        file_meta = vpk_dir.tree[filepath]

                        print(f"  File metadata type: {type(file_meta)}")
                        print(f"  File metadata attributes: {[attr for attr in dir(file_meta) if not attr.startswith('_')]}")

                        # Extract archive index from metadata
                        archive_index = None
                        if hasattr(file_meta, "archive_index"):
                            archive_index = file_meta.archive_index
                        elif hasattr(file_meta, "archiveIndex"):
                            archive_index = file_meta.archiveIndex
                        elif isinstance(file_meta, dict) and "archive_index" in file_meta:
                            archive_index = file_meta["archive_index"]

                        if archive_index is not None and archive_index != 0x7FFF:
                            required_indices.add(archive_index)
                            print(f"  Archive index: {archive_index}")
                        else:
                            print("  Could not find archive_index in metadata")

                    except Exception as e:
                        print(f"  Error accessing metadata for {filepath}: {e}")

                    break
    else:
        print("VPK tree is None or not available, using iteration method")
        # Fallback to iteration but with careful error handling
        file_count = 0
        for filepath in vpk_dir:
            file_count += 1
            if file_count <= 5:  # Show first few files for debugging
                print(f"  VPK file: {filepath}")

            for target_file in VPK_FILES:
                if filepath.startswith(target_file):
                    print(f"Found vpk for {target_file}: {filepath}")
                    try:
                        # Try multiple approaches to get archive index
                        archive_index = None

                        # Method 1: get_file_meta
                        if hasattr(vpk_dir, "get_file_meta"):
                            try:
                                file_meta = vpk_dir.get_file_meta(filepath)
                                if file_meta:
                                    print(f"  File meta type: {type(file_meta)}")
                                    print(f"  File meta attributes: {[attr for attr in dir(file_meta) if not attr.startswith('_')]}")
                                    if hasattr(file_meta, "archive_index"):
                                        archive_index = file_meta.archive_index
                                        print(f"  Archive index from meta: {archive_index}")
                            except Exception as e:
                                print(f"  get_file_meta failed: {e}")

                        # Method 2: Try to create VPKFile object but catch the specific error
                        if archive_index is None:
                            try:
                                vpk_file = vpk_dir.get_vpkfile_instance(filepath, vpk_dir.get_file_meta(filepath))
                                if hasattr(vpk_file, "archive_index"):
                                    archive_index = vpk_file.archive_index
                                    print(f"  Archive index from VPKFile: {archive_index}")
                            except FileNotFoundError as e:
                                # This is expected - extract archive index from error message
                                error_msg = str(e)
                                if "pak01_" in error_msg and ".vpk" in error_msg:
                                    import re

                                    match = re.search(r"pak01_(\d+)\.vpk", error_msg)
                                    if match:
                                        archive_index = int(match.group(1))
                                        print(f"  Archive index from error: {archive_index}")
                            except Exception as e:
                                print(f"  VPKFile creation failed: {e}")

                        if archive_index is not None and archive_index != 0x7FFF:
                            required_indices.add(archive_index)
                            print(f"  ✓ Added archive index: {archive_index}")
                        else:
                            print("  ✗ Could not determine archive index")

                    except Exception as e:
                        print(f"  Could not get metadata for {filepath}: {e}")
                    break

        print(f"Total files in VPK: {file_count}")

    print(f"Collected archive indices: {sorted(required_indices)}")
    return sorted(list(required_indices))


def download_vpk_archives(cdn, manifest, required_indices):
    """Download required VPK archive files"""
    print(f"Required VPK files {required_indices}")

    for i, archive_index in enumerate(required_indices):
        # Pad to 3 digits
        padded_index = f"{archive_index:03d}"
        filename = f"pak01_{padded_index}.vpk"

        # Find file in manifest using iter_files
        file_info = None
        for f in manifest.iter_files():
            if f.filename.endswith(filename):
                file_info = f
                break

        if not file_info:
            print(f"Could not find {filename} in manifest")
            continue

        temp_path = Path(TEMP_DIR) / filename
        status = f"[{i + 1}/{len(required_indices)}]"

        print(f"{status} Downloading {filename}")

        try:
            # Download file from Steam CDN using file's read method
            file_data = file_info.read()

            with open(temp_path, "wb") as f:
                f.write(file_data)

        except Exception as e:
            print(f"Error downloading {filename}: {e}")
            continue


def trim_bom(data):
    """Remove BOM from file data"""
    if isinstance(data, bytes) and len(data) >= 3 and data[:3] == b"\xef\xbb\xbf":
        return data[3:]
    return data


def extract_files_from_manifest(manifest):
    """Try to extract target files directly from manifest without VPK processing"""
    print("Attempting to extract files directly from manifest...")

    extracted_count = 0

    for file_info in manifest.iter_files():
        filename = file_info.filename.replace("\\", "/")

        for target_file in VPK_FILES:
            if filename == target_file:
                print(f"Extracting {filename} directly from manifest...")

                try:
                    # Get file data
                    file_data = file_info.read()

                    # Get just the filename for saving
                    save_filename = target_file.split("/")[-1]

                    # Remove BOM
                    file_data = trim_bom(file_data)

                    static_path = Path(STATIC_DIR) / save_filename

                    with open(static_path, "wb") as f:
                        f.write(file_data)
                    print(f"Saved {save_filename} ({len(file_data)} bytes)")

                    extracted_count += 1

                except Exception as e:
                    print(f"Error extracting {filename}: {e}")
                    continue

    print(f"Successfully extracted {extracted_count} files directly from manifest")
    return extracted_count > 0


def extract_vpk_files(vpk_dir):
    """Extract required files from VPK"""
    print("Extracting vpk files")

    for target_file in VPK_FILES:
        found = False

        for filepath in vpk_dir:
            if filepath.startswith(target_file):
                print(f"Extracting {filepath}")

                try:
                    # Get file data
                    vpk_file = vpk_dir[filepath]
                    file_data = vpk_file.read()

                    # Get just the filename
                    filename = target_file.split("/")[-1]

                    # Remove BOM
                    file_data = trim_bom(file_data)

                    static_path = Path(STATIC_DIR) / filename

                    with open(static_path, "wb") as f:
                        f.write(file_data)
                    print(f"Saved {filename} ({len(file_data)} bytes)")

                    found = True
                    break

                except Exception as e:
                    print(f"Error extracting {filepath}: {e}")
                    continue

        if not found:
            print(f"Warning: Could not find {target_file}")


def wait_for_login(client):
    """Wait for Steam client to be logged in"""
    print("Waiting for Steam login...")

    for i in range(30):  # Wait up to 30 seconds
        if client.logged_on:
            return True
        time.sleep(1)
        if i % 5 == 0:
            print(f"Still waiting... ({i + 1}/30 seconds)")

    return False


def main():
    """Main entry point"""
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ["--demo", "-d"]):
        # Demo mode - create sample files
        print("Running in demo mode (no Steam login required)")
        from .downloader import download_from_steamcmd_api

        download_from_steamcmd_api()
        return

    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print(f"Usage: {sys.argv[0]} <username> <password> [two_factor_code]")
        print("       {sys.argv[0]} --demo    (create sample files)")
        print("Downloads CS:GO game files from Steam CDN")
        sys.exit(1)

    # Create directories
    Path(STATIC_DIR).mkdir(exist_ok=True)
    Path(TEMP_DIR).mkdir(exist_ok=True)

    username = sys.argv[1]
    password = sys.argv[2]
    two_factor_code = sys.argv[3] if len(sys.argv) == 4 else None

    client = SteamClient()

    print("Logging into Steam....")

    try:
        # Login to Steam
        if two_factor_code:
            print("Using provided two-factor code...")
            result = client.login(username, password, two_factor_code=two_factor_code)
        else:
            result = client.login(username, password)

        if result == EResult.AccountLogonDenied:
            print("Steam Guard email authentication required.")
            email_code = input("Please enter your Steam Guard email code: ").strip()

            # Retry login with email auth code
            result = client.login(username, password, auth_code=email_code)

        elif result == EResult.AccountLoginDeniedNeedTwoFactor:
            print("Mobile authenticator (2FA) code required.")
            mobile_code = input("Please enter your mobile authenticator code: ").strip()

            # Retry login with 2FA code
            result = client.login(username, password, two_factor_code=mobile_code)

        # result = client.anonymous_login()

        if result != EResult.OK:
            print(f"Login failed with result: {result.name}")
            if result == EResult.InvalidPassword:
                print("Invalid username or password")
            elif result == EResult.AccountLogonDenied:
                print("Invalid Steam Guard email code")
            elif result == EResult.AccountLoginDeniedNeedTwoFactor:
                print("Invalid mobile authenticator (2FA) code")
            elif result == EResult.RateLimitExceeded:
                print("Too many login attempts, please wait and try again")
            sys.exit(1)

        # Wait for login to complete
        if not wait_for_login(client):
            print("Login timeout - Steam connection failed")
            sys.exit(1)

        print("Login successful!")

        # Create CDN client
        print("Initializing CDN client...")
        cdn = CDNClient(client)

        # Get product info for CS:GO
        print("Getting CS:GO product info...")
        app_info = client.get_product_info(apps=[APP_ID])

        if not app_info or "apps" not in app_info or APP_ID not in app_info["apps"]:
            print("Failed to get CS:GO app info")
            sys.exit(1)

        cs_info = app_info["apps"][APP_ID]

        # Get depot info
        if "depots" not in cs_info or str(DEPOT_ID) not in cs_info["depots"]:
            print(f"Depot {DEPOT_ID} not found in app info")
            sys.exit(1)

        depot_info = cs_info["depots"][str(DEPOT_ID)]

        if "manifests" not in depot_info or "public" not in depot_info["manifests"]:
            print("Public manifest not found")
            sys.exit(1)

        latest_manifest_id = depot_info["manifests"]["public"]["gid"]

        print(f"Obtained latest manifest ID: {latest_manifest_id}")

        # Check existing manifest
        manifest_file = Path(STATIC_DIR) / MANIFEST_ID_FILE
        existing_manifest_id = ""

        if manifest_file.exists():
            existing_manifest_id = manifest_file.read_text().strip()

        if existing_manifest_id == str(latest_manifest_id):
            print("Latest manifest Id matches existing manifest Id, exiting")
            sys.exit(0)

        print("Latest manifest Id does not match existing manifest Id, downloading game files")

        # Get manifest request code first
        print("Getting manifest request code...")
        try:
            manifest_request_code = cdn.get_manifest_request_code(APP_ID, DEPOT_ID, latest_manifest_id)
            print(f"Got manifest request code: {manifest_request_code}")
        except Exception as e:
            print(f"Failed to get manifest request code: {e}")
            sys.exit(1)

        # Get manifest
        print("Getting depot manifest...")
        manifest = cdn.get_manifest(APP_ID, DEPOT_ID, latest_manifest_id, manifest_request_code=manifest_request_code)

        if not manifest:
            print("Failed to get depot manifest")
            sys.exit(1)

        # Get files using iter_files method
        files = list(manifest.iter_files())
        print(f"Manifest loaded with {len(files)} files")

        # Try to extract files directly from manifest first
        direct_files = extract_files_from_manifest(manifest)

        if not direct_files:
            print("Files not found directly in manifest, using VPK method...")

            # Download and process VPK files - following the Node.js logic exactly
            vpk_dir = download_vpk_dir(cdn, manifest)
            print(f"VPK directory loaded with {len(list(vpk_dir))} files")

            # Use the VPK directory to determine which archives we need (like Node.js version)
            required_indices = get_required_vpk_files(vpk_dir)

            if required_indices:
                download_vpk_archives(cdn, manifest, required_indices)

            extract_vpk_files(vpk_dir)

        # Save manifest ID
        manifest_file.write_text(str(latest_manifest_id))

        print("Download completed successfully!")

        # List downloaded files
        print("\nDownloaded files:")
        for target_file in VPK_FILES:
            filename = target_file.split("/")[-1]
            file_path = Path(STATIC_DIR) / filename
            if file_path.exists():
                size = file_path.stat().st_size
                print(f"  {filename}: {size:,} bytes")
            else:
                print(f"  {filename}: NOT FOUND")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            if hasattr(client, "logout"):
                client.logout()
        except Exception:
            pass


if __name__ == "__main__":
    main()
