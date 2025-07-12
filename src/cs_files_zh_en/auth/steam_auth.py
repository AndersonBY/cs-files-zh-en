"""
Steam authentication handling for CS:GO Files Downloader
"""

import time
import logging

from steam.client import SteamClient
from steam.enums import EResult

from ..config import Config

logger = logging.getLogger(__name__)


class SteamAuthenticator:
    """Handles Steam authentication with multiple 2FA methods"""

    def __init__(self):
        self.client = SteamClient()
        self._logged_in = False

    @property
    def is_logged_in(self) -> bool:
        """Check if client is logged in"""
        return self._logged_in and self.client.logged_on

    def login(self, username: str, password: str, two_factor_code: str | None = None) -> bool:
        """
        Login to Steam with support for multiple authentication methods

        Args:
            username: Steam username
            password: Steam password
            two_factor_code: Optional 2FA code for automated login

        Returns:
            True if login successful, False otherwise
        """
        logger.info("Logging into Steam...")

        try:
            # Initial login attempt
            if two_factor_code:
                logger.info("Using provided two-factor code...")
                result = self.client.login(username, password, two_factor_code=two_factor_code)
            else:
                result = self.client.login(username, password)

            # Handle Steam Guard email authentication
            if result == EResult.AccountLogonDenied:
                logger.info("Steam Guard email authentication required.")
                email_code = input("Please enter your Steam Guard email code: ").strip()
                result = self.client.login(username, password, auth_code=email_code)

            # Handle mobile authenticator (2FA)
            elif result == EResult.AccountLoginDeniedNeedTwoFactor:
                logger.info("Mobile authenticator (2FA) code required.")
                mobile_code = input("Please enter your mobile authenticator code: ").strip()
                result = self.client.login(username, password, two_factor_code=mobile_code)

            # Check final result
            if result != EResult.OK:
                self._log_login_error(result)
                return False

            # Wait for login to complete
            if not self._wait_for_login():
                logger.error("Login timeout - Steam connection failed")
                return False

            self._logged_in = True
            logger.info("Login successful!")
            return True

        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    def logout(self) -> None:
        """Logout from Steam"""
        try:
            if hasattr(self.client, "logout"):
                self.client.logout()
                self._logged_in = False
                logger.info("Logged out from Steam")
        except Exception as e:
            logger.warning(f"Logout error: {e}")

    def _wait_for_login(self) -> bool:
        """
        Wait for Steam client to complete login

        Returns:
            True if login completed within timeout, False otherwise
        """
        logger.info("Waiting for Steam login to complete...")

        for i in range(Config.LOGIN_TIMEOUT_SECONDS):
            if self.client.logged_on:
                return True

            time.sleep(1)

            if i % 5 == 0 and i > 0:
                logger.info(f"Still waiting... ({i + 1}/{Config.LOGIN_TIMEOUT_SECONDS} seconds)")

        return False

    def _log_login_error(self, result: EResult) -> None:
        """Log detailed error message based on login result"""
        error_messages = {
            EResult.InvalidPassword: "Invalid username or password",
            EResult.AccountLogonDenied: "Invalid Steam Guard email code",
            EResult.AccountLoginDeniedNeedTwoFactor: "Invalid mobile authenticator (2FA) code",
            EResult.RateLimitExceeded: "Too many login attempts, please wait and try again",
        }

        specific_message = error_messages.get(result, f"Unknown error: {result.name}")
        logger.error(f"Login failed: {specific_message}")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - automatically logout"""
        self.logout()
