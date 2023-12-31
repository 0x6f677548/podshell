import logging
import os
from sys import platform
import time
from typing import Callable

import utils
from engine.events import Event, EventType
from engine.terminal import configuration

from .connection import BaseConnector

SSH_COMMAND = "ssh" if platform != "win32" else "ssh.exe"


class SSHConnector(BaseConnector):
    """A connector that subscribes changes to the ssh config file and
    adds/removes profiles based on the changes.
    """

    _logger = logging.getLogger(__name__)

    class SSHProfile:
        """A class that represents an ssh profile from the ssh config file."""

        hostname: str | None = None
        user: str | None = None
        port: str | None = None
        name: str

        def __init__(self, name: str):
            self.name = name

    def __init__(
        self,
        event_handler: Callable[[Event], None],
        ssh_config_file: str = os.path.expanduser(os.path.join("~", ".ssh", "config")),
        poll_interval: int = 5,
        ssh_command: str | None = utils.which(SSH_COMMAND, SSH_COMMAND),
    ):
        """Initializes the SSHConnector."""
        super().__init__(
            name="SSH",
            event_handler=event_handler,
        )

        if ssh_config_file is None:
            ssh_config_file = os.path.expanduser(os.path.join("~", ".ssh", "config"))
        self._ssh_config_file = ssh_config_file
        self._poll_interval = poll_interval
        self._ssh_command = ssh_command

    def _get_ssh_profile_from_config(self) -> list[SSHProfile]:
        profiles = []
        with open(self._ssh_config_file, "r") as file:
            lines = file.readlines()
            current_profile: SSHConnector.SSHProfile | None = None
            for line in lines:
                line = line.strip()
                if line.startswith("Host "):
                    if current_profile:
                        profiles.append(current_profile)
                    parts = line.split()
                    current_profile = SSHConnector.SSHProfile(name=parts[1])
                elif current_profile:
                    if line.startswith("HostName "):
                        current_profile.hostname = line.split()[1]
                    elif line.startswith("User "):
                        current_profile.user = line.split()[1]
                    elif line.startswith("Port "):
                        current_profile.port = line.split()[1]
            if current_profile:
                profiles.append(current_profile)
        return profiles

    def _run(self):
        def trigger_event_handler(
            ssh_profiles: list[SSHConnector.SSHProfile],
        ):
            # create terminal profiles for each ssh profile
            for profile in ssh_profiles:
                if profile.hostname:
                    commandline = f"{self._ssh_command} "
                    if profile.user:
                        commandline += f"{profile.user}@"
                    commandline += profile.hostname
                    if profile.port:
                        commandline += f" -p {profile.port}"

                    terminal_profile = configuration.TerminalProfile(
                        name=profile.name,
                        commandline=commandline,
                    )

                    # call the event handler signaling that a profile has been added
                    self._event_handler(
                        Event(
                            source_name=self.name,
                            event_type=EventType.ADD_PROFILE,
                            event_message=str(terminal_profile),
                            event_data=terminal_profile,
                        )
                    )

        # start watching the ssh config file
        self._logger.info("Watching ssh config file: %s", self._ssh_config_file)

        modified_on = None
        while not self.terminated:
            if (
                not modified_on
                or os.path.getmtime(self._ssh_config_file) != modified_on
            ):
                if modified_on:
                    # call the event handler signaling that the connector is starting
                    # this is actually a restart since the config file has changed
                    self._event_handler(
                        Event(
                            source_name=self.name,
                            event_type=EventType.STARTING,
                            event_message=f"{self.name} connector starting",
                        )
                    )

                modified_on = os.path.getmtime(self._ssh_config_file)
                self._logger.debug("SSH config file modified on: %s", modified_on)
                ssh_profiles = self._get_ssh_profile_from_config()
                trigger_event_handler(ssh_profiles)
            else:
                self._logger.debug("SSH config file not modified")

            time.sleep(self._poll_interval)

    def stop(self, timeout: float = 1):
        """Stops the connector."""
        self.terminated = True
        return super().stop(timeout)

    def health_check(self) -> bool:
        """Checks if the ssh config file exists."""
        return os.path.exists(self._ssh_config_file)
