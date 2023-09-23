import json
import logging
import os
import re
import shutil
import threading
from datetime import datetime, timedelta
from sys import platform

from utils import APP_NAME

from .configuration import BaseConfigurator, TerminalProfile

_logger: logging.Logger = logging.getLogger(__name__)


class ITerm2Configurator(BaseConfigurator):
    """Configuration class for Windows Terminal"""

    # https://iterm2.com/documentation-dynamic-profiles.html
    # ~/Library/Application Support/iTerm2/DynamicProfiles/
    SETTINGS_DIR = os.path.join(
        os.path.expanduser("~"),
        "Library",
        "Application Support",
        "iTerm2",
        "DynamicProfiles",
    )

    @staticmethod
    def is_available() -> bool:
        """Returns true if this terminal is installed/available."""

        # check if the OS is macOS. if not, return False
        if platform != "darwin":
            _logger.info("This is not a macOS system. iTerm2 is not available.")
            return False
        # check if the settings directory exists
        elif not os.path.exists(ITerm2Configurator.SETTINGS_DIR):
            _logger.info(
                "iTerm2 settings directory not found. iTerm2 is not available."
            )
            return False
        return True

    def __init__(self, settings_file_path: str | None = None):
        """Initializes a new instance of the Configuration class"""
        if settings_file_path is None:
            settings_file_path = os.path.join(
                ITerm2Configurator.SETTINGS_DIR, APP_NAME + ".json"
            )
        self._settings_file_path = settings_file_path
        self._lock = threading.Lock()
        self.name = "iTerm2 Terminal"

    def _profile_exists(self, settings: dict, profile_name: str) -> bool:
        return (
            next(
                (p for p in settings["Profiles"] if p.get("Name") == profile_name),
                None,
            )
            is not None
        )

    # region add profiles

    def add_profiles(
        self, profiles: list[TerminalProfile], group_name: str | None = None
    ) -> None:
        """Adds the specified profiles to the settings file
        format of the profile:
        {
            "Tags" : [
                "ssh"
            ],
            "Name": "foo.example.com",
            "Guid": "1a2b3c4d5e6f",
            "Custom Command" : "Yes",
            "Command" : "ssh foo.example.com"
        }


        """
        with self._lock:
            settings = self._get_settings()
            for profile in profiles:
                # check if profile already exists. if not, add it
                if not self._profile_exists(settings, profile.name):
                    # Title Components:544 -> Profile name + job with arguments
                    settings["Profiles"].append(
                        {
                            "Name": profile.name,
                            "Custom Command": "Yes",
                            "Command": profile.commandline,
                            "Guid": profile.guid,
                            "Tags": [APP_NAME, group_name],
                            "Title Components": 544,
                        }
                    )
                elif _logger.isEnabledFor(logging.DEBUG):
                    _logger.debug(f"Profile {profile.name} already exists")

            self._save(settings)

    # endregion

    # region remove profiles

    def remove_profiles(self, profile_names: list[str]) -> None:
        """Removes the specified profiles from the settings file"""
        with self._lock:
            settings = self._get_settings()

            profiles_to_keep = []
            for profile in settings["Profile"]:
                if profile["name"] not in profile_names:
                    profiles_to_keep.append(profile)

            settings["Profiles"] = profiles_to_keep
            self._save(settings)

    # endregion

    # region remove group
    def remove_group(self, group_name: str) -> None:
        """Removes the specified group from the settings.json file"""
        with self._lock:
            settings = self._get_settings()

            profiles_to_keep = []
            for profile in settings["Profiles"]:
                # let's look to tags and if we find the group name,
                # this profile should be removed
                if group_name not in profile["Tags"]:
                    profiles_to_keep.append(profile)

            settings["Profiles"] = profiles_to_keep
            self._save(settings)

    # end region

    def backup(self) -> None:
        """Backup the settings.json file and deletes backups longer than 7 days"""

        # check if the settings file exists. if not, return
        if not os.path.exists(self._settings_file_path):
            _logger.debug(
                f"Settings file not found at {self._settings_file_path}. Backup not created."
            )
            return

        # backup_folder will be ~/Library/Application Support/iTerm2/DynamicProfilesBackup
        backup_folder = os.path.join(
            os.path.expanduser("~"),
            "Library",
            "Application Support",
            "iTerm2",
            "DynamicProfilesBackup",
        )

        # Generate the backup file name
        backup_file_path = re.sub(
            r"\.json$",
            f".backup.{datetime.now().strftime('%Y%m%d%H%M%S')}.json",
            self._settings_file_path,
        )
        # Create the backup folder if it doesn't exist
        if not os.path.exists(backup_folder):
            os.makedirs(backup_folder)
        # Copy the settings file to the backup location
        shutil.copy(
            self._settings_file_path,
            os.path.join(backup_folder, os.path.basename(backup_file_path)),
        )

        # Delete backup files older than 7 days
        for filename in os.listdir(backup_folder):
            file_path = os.path.join(backup_folder, filename)
            file_creation_time = datetime.fromtimestamp(os.path.getctime(file_path))
            if datetime.now() - file_creation_time > timedelta(days=7):
                os.remove(file_path)
                _logger.debug(f"Deleted backup file: {filename}")

    def _save(self, settings) -> None:
        # Convert the settings object to JSON and write it to the file
        with open(self._settings_file_path, "w") as settings_file:
            json.dump(settings, settings_file, indent=4)

    def _get_settings(self) -> dict:
        # check if the settings file exists. if not, create it
        if not os.path.exists(self._settings_file_path):
            _logger.debug(
                f"Settings file not found. Creating new file at {self._settings_file_path}"
            )
            with open(self._settings_file_path, "w") as settings_file:
                settings_file.write('{"Profiles": []}')

        # Read the current JSON content
        with open(self._settings_file_path, "r") as settings_file:
            current_settings = json.load(settings_file)
        return current_settings
