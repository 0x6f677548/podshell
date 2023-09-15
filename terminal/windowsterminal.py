import os
import subprocess
import shutil
import re
from datetime import datetime, timedelta
import json
import logging
from terminal.configuration import BaseConfigurator, TerminalProfile

_logger: logging.Logger = logging.getLogger(__name__)


class WindowsTerminalConfigurator(BaseConfigurator):
    """Configuration class for Windows Terminal"""

    @staticmethod
    def is_available() -> bool:
        '''Returns true if this terminal is installed/available.'''
        return WindowsTerminalConfigurator._get_settings_file_path() is not None

    @staticmethod
    def _get_settings_file_path() -> str:
        '''
        Returns the path to the settings.json file for Windows Terminal
        Returns None if the settings.json file is not found
        '''
        # from https://learn.microsoft.com/en-us/windows/terminal/install#settings-json-file
        # Terminal (stable / general release):
        #  %LOCALAPPDATA%\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json
        # Terminal (preview release):
        #  %LOCALAPPDATA%\Packages\Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe\LocalState\settings.json
        # Terminal (unpackaged: Scoop, Chocolately, etc):
        # %LOCALAPPDATA%\Microsoft\Windows Terminal\settings.json

        # a function that checks if a file exists and returns true or false
        # logs a debug message if the file is found
        def file_exists(path: str) -> bool:
            found = os.path.exists(path)
            if found and _logger.isEnabledFor(logging.DEBUG):
                _logger.debug(f"Found settings file at {path}")
            return found

        # try to find the settings.json file in the default locations
        settings_file_path = os.path.join(
            os.environ["LOCALAPPDATA"],
            "packages",
            "Microsoft.WindowsTerminal_8wekyb3d8bbwe",
            "LocalState",
            "settings.json",
        )

        if file_exists(settings_file_path):
            return settings_file_path

        settings_file_path = os.path.join(
            os.environ["LOCALAPPDATA"],
            "packages",
            "Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe",
            "LocalState",
            "settings.json",
        )

        if file_exists(settings_file_path):
            return settings_file_path

        settings_file_path = os.path.join(
            os.environ["LOCALAPPDATA"], "Microsoft", "Windows Terminal", "settings.json"
        )

        if file_exists(settings_file_path):
            return settings_file_path

        # if the settings.json file is not found in the default locations,
        #  try to find the Windows Terminal package family name
        try:
            package_family_name = (
                subprocess.check_output(
                    [
                        "powershell",
                        "Get-AppxPackage",
                        "Microsoft.WindowsTerminal*",
                        "|",
                        "Select-Object",
                        "-ExpandProperty",
                        "PackageFamilyName",
                    ]
                )
                .decode("utf-8")
                .strip()
            )
            # Get the path to the settings.json file
            settings_file_path = os.path.join(
                os.environ["LOCALAPPDATA"],
                "packages",
                package_family_name,
                "LocalState",
                "settings.json")

            if file_exists(settings_file_path):
                return settings_file_path

        except subprocess.CalledProcessError as e:
            raise Exception(
                "Windows Terminal settings file not found"
                "and package family name could not be determined"
            ) from e

        # if we get here, the settings.json file was not found
        return None

    def __init__(self, settings_file_path: str = _get_settings_file_path()):
        '''Initializes a new instance of the Configuration class'''
        self.settings_file_path = settings_file_path
        self.name = "Windows Terminal"

    # region group management

    def _is_profile_in_group(self, group: dict, profile_name: str) -> bool:
        return (
            next(
                (e for e in group.get("entries") if e.get("name") == profile_name), None
            )
            is not None
        )

    def _get_group(self, settings: dict, group_name: str) -> bool:
        return (
            next(
                (g for g in settings["newTabMenu"] if g.get("name") == group_name), None
            )
        )

    def _profile_exists(self, settings: dict, profile_name: str) -> bool:
        return (
            next(
                (p for p in settings["profiles"]["list"] if p.get("name") == profile_name), None
            )
            is not None
        )

    def _upsert_group(
        self, settings: dict, group_name: str, profiles: list[TerminalProfile]
    ) -> dict:
        # check if group exists. if not, create it
        group = self._get_group(settings, group_name)
        if group is None:
            group = {
                "name": group_name,
                "allowEmpty": False,
                "type": "folder",
                "entries": [],
            }
            settings["newTabMenu"].append(group)

        # add profiles to group if not already in group
        for profile in profiles:
            if not self._is_profile_in_group(group, profile.name):
                group["entries"].append({"profile": profile.guid, "type": "profile"})

        return settings

    # end region

    # region add profiles

    def add_profiles(self, profiles: list[TerminalProfile], group_name: str = None) -> None:
        '''Adds the specified profiles to the settings.json file'''
        settings = self._get_settings()
        for profile in profiles:
            # check if profile already exists. if not, add it
            if not self._profile_exists(settings, profile.name):
                settings["profiles"]["list"].append(
                    {
                        "name": profile.name,
                        "commandline": profile.commandline,
                        "guid": profile.guid,
                        "suppressApplicationTitle": True,
                    }
                )
            elif _logger.isEnabledFor(logging.DEBUG):
                _logger.debug(f"Profile {profile.name} already exists")

        if group_name is not None:
            self._upsert_group(settings, group_name, profiles)
        self._save(settings)

    # endregion

    # region remove profiles

    def remove_profiles(self, profile_names: list[str]) -> None:
        '''Removes the specified profiles from the settings.json file'''
        settings = self._get_settings()

        # remove all profiles from the list, but keep the guid of each profile for later
        profile_guids = []
        profiles_to_keep = []
        for profile in settings["profiles"]["list"]:
            if profile["name"] in profile_names:
                profile_guids.append(profile["guid"])
            else:
                profiles_to_keep.append(profile)

        settings["profiles"]["list"] = profiles_to_keep

        # check for all entries in all groups and remove them
        for group in settings["newTabMenu"]:
            if group.get("type") == "folder":
                group["entries"] = [
                    e
                    for e in group["entries"]
                    if e["type"] == "profile" and e["profile"] not in profile_guids
                ]

        self._save(settings)

    # endregion

    # region remove group
    def remove_group(self, group_name: str) -> None:
        '''Removes the specified group from the settings.json file'''
        settings = self._get_settings()

        # keep the guid of each profile for later
        profile_guids = []

        # remove all entries in the group
        for group in settings["newTabMenu"]:
            if group.get("type") == "folder" and group["name"] == group_name:
                for entry in group["entries"]:
                    if entry["type"] == "profile":
                        profile_guids.append(entry["profile"])

                group["entries"] = []

        # remove all profiles from the list
        settings["profiles"]["list"] = [
            p for p in settings["profiles"]["list"] if p["guid"] not in profile_guids
        ]

        # remove all profile entries from all groups
        for group in settings["newTabMenu"]:
            if group.get("type") == "folder":
                group["entries"] = [
                    e
                    for e in group["entries"]
                    if e["type"] == "profile" and e["profile"] not in profile_guids
                ]

        self._save(settings)

    # end region

    def backup(self) -> None:
        """Backup the settings.json file and deletes backups longer than 7 days"""
        backup_folder = (
            "backup_folder"  # Change this to your desired backup folder path
        )

        # Create the backup folder if it doesn't exist
        if not os.path.exists(backup_folder):
            os.makedirs(backup_folder)

        # Generate the backup file path
        backup_file_path = re.sub(
            r"\.json$",
            f".backup.{datetime.now().strftime('%Y%m%d%H%M%S')}.json",
            self.settings_file_path,
        )
        # Copy the settings file to the backup location
        shutil.copy(
            self.settings_file_path,
            os.path.join(backup_folder, os.path.basename(backup_file_path)),
        )

        # Delete backup files older than 7 days
        for filename in os.listdir(backup_folder):
            if filename.startswith("settings.backup.") and filename.endswith(".json"):
                file_path = os.path.join(backup_folder, filename)
                file_creation_time = datetime.fromtimestamp(os.path.getctime(file_path))
                if datetime.now() - file_creation_time > timedelta(days=7):
                    os.remove(file_path)
                    print(f"Deleted backup file: {filename}")

    def _save(self, settings) -> None:
        # Convert the settings object to JSON and write it to the file
        with open(self.settings_file_path, "w") as settings_file:
            json.dump(settings, settings_file, indent=4)

    def _get_settings(self) -> dict:
        # Read the current JSON content
        with open(self.settings_file_path, "r") as settings_file:
            current_settings = json.load(settings_file)
        return current_settings
