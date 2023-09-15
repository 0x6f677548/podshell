import logging
from pod.connection import BaseConnector, ConnectorEvent, ConnectorEventTypes
from terminal import configuration
import os
import time


class SSHConnector(BaseConnector):
    '''A connector that subscribes changes to the ssh config file and
    adds/removes profiles based on the changes.
    '''

    _logger = logging.getLogger(__name__)

    class SSHProfile:
        '''A class that represents an ssh profile from the ssh config file.'''
        def __init__(self, name, hostname, user, port):
            self.name = name
            self.hostname = hostname
            self.user = user
            self.port = port

    def __init__(
        self,
        connector_event_handler: callable([ConnectorEvent, None]),
        ssh_config_file: str = os.path.expanduser(os.path.join("~", ".ssh", "config")),
        poll_interval: int = 5,
    ):
        '''Initializes the SSHConnector.'''
        super().__init__(
            name="SSH",
            connector_event_handler=connector_event_handler,
        )

        if ssh_config_file is None:
            ssh_config_file = os.path.expanduser(os.path.join("~", ".ssh", "config"))
        self.ssh_config_file = ssh_config_file
        self.poll_interval = poll_interval

    def _get_ssh_profile_from_config(self) -> list[SSHProfile]:
        profiles = []
        with open(self.ssh_config_file, 'r') as file:
            lines = file.readlines()
            current_profile = None
            for line in lines:
                line = line.strip()
                if line.startswith('Host '):
                    if current_profile:
                        profiles.append(current_profile)
                    parts = line.split()
                    current_profile = SSHConnector.SSHProfile(name=parts[1], hostname=None, user=None, port=None)
                elif line.startswith('HostName '):
                    current_profile.hostname = line.split()[1]
                elif line.startswith('User '):
                    current_profile.user = line.split()[1]
                elif line.startswith('Port '):
                    current_profile.port = line.split()[1]
            if current_profile:
                profiles.append(current_profile)
        return profiles

    def _run(self):
        def trigger_connector_event_handler(ssh_profiles):
            # create terminal profiles for each ssh profile            
            for profile in ssh_profiles:
                if profile.hostname:
                    commandline = 'ssh '
                    if profile.user:
                        commandline += f'{profile.user}@'
                    commandline += profile.hostname
                    if profile.port:
                        commandline += f' -p {profile.port}'

                    terminal_profile = configuration.TerminalProfile(
                                name=profile.name,
                                commandline=commandline,
                            )

                    # call the event handler signaling that a profile has been added
                    self.connector_event_handler(
                                ConnectorEvent(
                                    connector_name=self.name,
                                    event_type=ConnectorEventTypes.ADD_PROFILE,
                                    event=terminal_profile,
                                    terminal_profile=terminal_profile,
                                )
                            )

        # start watching the ssh config file
        self._logger.info("Watching ssh config file: %s", self.ssh_config_file)

        modified_on = None
        while not self.terminated:
            if not modified_on or os.path.getmtime(self.ssh_config_file) != modified_on:

                if modified_on:
                    # call the event handler signaling that the connector is starting
                    # this is actually a restart since the config file has changed
                    self.connector_event_handler(
                        ConnectorEvent(
                            connector_name=self.name,
                            event_type=ConnectorEventTypes.STARTING,
                            event=f"{self.name} connector starting",
                        )
                    )

                modified_on = os.path.getmtime(self.ssh_config_file)
                self._logger.debug("SSH config file modified on: %s", modified_on)
                ssh_profiles = self._get_ssh_profile_from_config()
                trigger_connector_event_handler(ssh_profiles)
            else:
                self._logger.debug("SSH config file not modified")

            time.sleep(self.poll_interval)

    def stop(self, timeout: float = 1):
        '''Stops the connector.'''
        self.terminated = True
        return super().stop(timeout)

    def health_check(self) -> bool:
        '''Checks if the ssh config file exists.'''
        return os.path.exists(self.ssh_config_file)
