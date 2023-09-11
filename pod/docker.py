import logging
import docker
from pod.connection import BaseConnector, ConnectorEvent, ConnectorEventTypes
from terminal import configuration


class DockerConnector(BaseConnector):
    '''A connector that subscribes to Docker events '''
    def __init__(
        self,
        connector_event_handler: callable([ConnectorEvent, None]),
        docker_client: docker.DockerClient = None,
        shell_command: str = "/bin/sh",
    ):
        '''Initializes the DockerConnector.'''
        super().__init__(
            connector_friendly_name="Docker",
            connector_event_handler=connector_event_handler,
        )
        self.docker_client = docker_client
        self.shell_command = shell_command

    def health_check(self) -> bool:
        '''Checks if the Docker daemon is running.'''
        docker_client = self._get_docker_client()
        return docker_client.ping()

    def _get_command(self, container_name):
        return f"docker exec -it {container_name} {self.shell_command}"

    def _get_docker_client(self):
        if self.docker_client is None:
            return docker.from_env()
        else:
            return self.docker_client

    def _handle_docker_event(self, event):
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("Docker event: %s", str(event))

        if (
            event["Action"] == "start"
            or event["Action"] == "die"
            or event["Action"] == "stop"
        ):
            # Add or remove container. Create a terminal profile for the container.
            container_name = event["Actor"]["Attributes"]["name"]
            terminal_profile = configuration.TerminalProfile(
                container_name,
                self._get_command(container_name),
            )

            if self._logger.isEnabledFor(logging.DEBUG):
                self._logger.debug(
                    "Docker event: %s, %s", event["Action"], terminal_profile.commandline
                )

            # call the event handler signaling that a container has been added or removed
            self.connector_event_handler(
                ConnectorEvent(
                    connector_friendly_name=self.connector_friendly_name,
                    event_type=ConnectorEventTypes.ADD_PROFILE
                    if event["Action"] == "start"
                    else ConnectorEventTypes.REMOVE_PROFILE,
                    terminal_profile=terminal_profile,
                    event=container_name,
                )
            )

    def _run(self):
        try:
            docker_client = self._get_docker_client()

            # Add existing containers
            for container in docker_client.containers.list():
                terminal_profile = configuration.TerminalProfile(
                    container.name, self._get_command(container.name)
                )

                self.connector_event_handler(
                    ConnectorEvent(
                        connector_friendly_name=self.connector_friendly_name,
                        event_type=ConnectorEventTypes.ADD_PROFILE,
                        terminal_profile=terminal_profile,
                        event=container.name,
                    )
                )

            # Loop over Docker events until terminated
            for event in docker_client.events(
                decode=True,
                filters={"type": ["container"], "event": ["start", "stop", "die"]},
            ):
                if self.terminated:
                    break
                logging.debug("Docker event: %s", str(event))
                self._handle_docker_event(event)

            # close the docker client.
            # If we reach this point, it means that the thread is terminating
            docker_client.close()
        except Exception as e:
            if not isinstance(e, docker.errors.DockerException) and not isinstance(
                e, docker.errors.APIError
            ):
                self._logger.error("Docker connector error", exc_info=e)
            raise
