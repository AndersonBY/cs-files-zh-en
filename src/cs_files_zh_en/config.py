"""
Configuration management for CS:GO Files Downloader
"""

from pathlib import Path
from typing import List


class Config:
    """Central configuration for the CS:GO Files Downloader"""
    
    # Steam Application Constants
    APP_ID = 730
    DEPOT_ID = 2347770
    
    # Directory Paths
    STATIC_DIR = "./static"
    TEMP_DIR = "./temp"
    
    # File Names
    MANIFEST_ID_FILE = "manifestId.txt"
    
    # Target Files to Extract from VPK
    VPK_FILES = [
        "resource/csgo_english.txt",
        "resource/csgo_schinese.txt", 
        "scripts/items/items_game.txt",
    ]
    
    # Timeout Settings
    LOGIN_TIMEOUT_SECONDS = 30
    
    @classmethod
    def get_static_path(cls) -> Path:
        """Get static directory path as Path object"""
        return Path(cls.STATIC_DIR)
    
    @classmethod
    def get_temp_path(cls) -> Path:
        """Get temp directory path as Path object"""
        return Path(cls.TEMP_DIR)
    
    @classmethod
    def get_manifest_file_path(cls) -> Path:
        """Get manifest file path"""
        return cls.get_static_path() / cls.MANIFEST_ID_FILE
    
    @classmethod
    def get_target_filenames(cls) -> List[str]:
        """Get list of target filenames (without path)"""
        return [vpk_file.split("/")[-1] for vpk_file in cls.VPK_FILES]
    
    @classmethod
    def ensure_directories(cls) -> None:
        """Create necessary directories if they don't exist"""
        cls.get_static_path().mkdir(exist_ok=True)
        cls.get_temp_path().mkdir(exist_ok=True)