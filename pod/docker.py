import logging
import docker
from pod.connection import BaseConnector, ConnectorEvent, ConnectorEventTypes
from terminal import configuration


class DockerConnector(BaseConnector):
    def __init__(
        self,
        configuration: configuration.BaseConfiguration,
        f_handle_event: callable([ConnectorEvent, None]) = lambda _: None,
        docker_client: docker.DockerClient = None,
        shell_command: str = "/bin/sh",
    ):
        super().__init__(
            connector_friendly_name="Docker",
            configuration=configuration,
            f_handle_event=f_handle_event,
        )
        self.docker_client = docker_client
        self.shell_command = shell_command

    def _handle_docker_event(self, event):
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("Docker event: %s", str(event))
        if event["Action"] == "start":
            container_name = event["Actor"]["Attributes"]["name"]
            container_profile = configuration.TerminalProfile(
                container_name,
                self._get_command(container_name),
            )

            self.connector_event_handler(
                ConnectorEvent(ConnectorEventTypes.PROFILE_ADDED, container_name)
            )

            self.configuration.add_profile(
                container_profile, self.connector_friendly_name
            )
        elif event["Action"] == "die" or event["Action"] == "stop":
            container_name = event["Actor"]["Attributes"]["name"]
            self.configuration.remove_profile(container_name)
            self.connector_event_handler(
                ConnectorEvent(ConnectorEventTypes.PROFILE_REMOVED, container_name)
            )

    def _get_command(self, container_name):
        return f"docker exec -it {container_name} {self.shell_command}"

    def _get_docker_client(self):
        if self.docker_client is None:
            return docker.from_env()
        else:
            return self.docker_client

    def health_check(self) -> bool:
        docker_client = self._get_docker_client()
        return docker_client.ping()

    def _run(self):
        try:
            docker_client = self._get_docker_client()

            for container in docker_client.containers.list():
                container_profile = configuration.TerminalProfile(
                    container.name, self._get_command(container.name)
                )
                self.configuration.add_profile(
                    container_profile, self.connector_friendly_name
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
            docker_client.close()
        except Exception as e:
            if not isinstance(e, docker.errors.DockerException) and not isinstance(
                e, docker.errors.APIError
            ):
                self._logger.error("Docker connector error", exc_info=e)
            raise
