import logging
from os import path
from sys import platform
import docker
import docker.utils
from .connection import BaseConnector
from engine.events import Event, EventType
from engine.terminal import configuration
import utils


class DockerConnector(BaseConnector):
    """A connector that subscribes to Docker events"""

    def __init__(
        self,
        event_handler: callable([Event, None]),
        docker_client: docker.DockerClient = None,
        shell_command: str = "/bin/sh",
        docker_command: str | None = utils.which("docker", "docker"),
    ):
        """Initializes the DockerConnector."""
        super().__init__(
            name="Docker",
            event_handler=event_handler,
        )
        self._docker_client = docker_client
        self._shell_command = shell_command
        self._docker_command = docker_command

    def health_check(self) -> bool:
        """Checks if the Docker daemon is running.
        It encapsulates the call to the Docker daemon in a try/except block.
        Returns:
            True if the Docker daemon is running, False otherwise.
        """
        try:
            return self._get_docker_client().ping()
        except Exception:
            return False

    def _get_command(self, container_name):
        return f"{self._docker_command} exec -it {container_name} {self._shell_command}"

    def _get_docker_client(self):
        if self._docker_client is None:
            if platform == "win32":
                self._logger.debug("Using docker.from_env()")
                return docker.from_env()
            else:
                kwargs = docker.utils.kwargs_from_env()
                # if the base_url is not set (coming from the environment variables) and we're not
                # on Windows, the docker socket may be configured in the user's home directory
                # let's verify that and set the base_url accordingly if needed
                if "base_url" not in kwargs and not path.exists("/var/run/docker.sock"):
                    socket_path = path.join(
                        path.expanduser("~"), ".docker", "run", "docker.sock"
                    )
                    self._logger.debug(
                        "Could not find docker env vars neither /var/run/docker.sock. "
                        + "Trying to fallback to user's home directory %s",
                        socket_path,
                    )
                    if path.exists(socket_path):
                        self._logger.debug(
                            "Found docker socket in user's home directory"
                        )
                        kwargs["base_url"] = "unix://{}".format(socket_path)
                return docker.DockerClient(**kwargs)
        else:
            return self._docker_client

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
                    "Docker event: %s, %s",
                    event["Action"],
                    terminal_profile.commandline,
                )

            # call the event handler signaling that a container has been added or removed
            self._event_handler(
                Event(
                    source_name=self.name,
                    event_type=EventType.ADD_PROFILE
                    if event["Action"] == "start"
                    else EventType.REMOVE_PROFILE,
                    event_data=terminal_profile,
                    event_message=container_name,
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

                self._event_handler(
                    Event(
                        source_name=self.name,
                        event_type=EventType.ADD_PROFILE,
                        event_data=terminal_profile,
                        event_message=container.name,
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
