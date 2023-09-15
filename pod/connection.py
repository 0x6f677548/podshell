import time
import threading
import logging
from enum import StrEnum
import terminal.configuration as configuration


class ConnectorEventTypes(StrEnum):
    ADD_PROFILE = "ADD_PROFILE"
    REMOVE_PROFILE = "REMOVE_PROFILE"
    WARNING = "WARNING"
    STARTING = "STARTING"
    STOPPING = "STOPPING"
    HEALTHY = "HEALTHY"


class ConnectorEvent:
    """Event that is sent to the connector event handler."""

    def __init__(
        self,
        connector_name: str,
        event_type: ConnectorEventTypes,
        event: str,
        terminal_profile: configuration.TerminalProfile = None,
    ):
        """Creates a new instance of the ConnectorEvent class."""
        self.event_type = event_type
        self.event = event
        self.connector_name = connector_name
        self.terminal_profile = terminal_profile


class BaseConnector(threading.Thread):
    """Base class for all connectors.
    A connector is a thread that runs in the background and communicates with
    a pod service or a way to connect to a container, pod or shell
    Connectors should have unique names, like "SSH" or "Docker".
    When inheriting from this class, the _run method should be overridden.
    """

    _logger = logging.getLogger(__name__)

    terminated: bool = False
    """Indicates if the connector has terminated.
    This property is set to True when the stop method is called.
    A connector should check this property in its _run method and terminate if it is True.
    A terminated connector should not be restarted.
    """

    def __init__(
        self,
        name: str,
        connector_event_handler: callable([ConnectorEvent, None]),
    ):
        """Creates a new instance of the BaseConnector class."""
        super().__init__(daemon=True)
        self.terminated = False
        self.name = name
        self.connector_event_handler = connector_event_handler

    def _run(self):
        raise NotImplementedError()

    def health_check(self) -> bool:
        """Checks if the connector is healthy."""
        raise NotImplementedError()

    def run(self):
        """Runs the connector. This method should not be called directly. Use the start method instead."""

        # call the event handler signaling that the connector is starting
        self.connector_event_handler(
            ConnectorEvent(
                connector_name=self.name,
                event_type=ConnectorEventTypes.STARTING,
                event=f"{self.name} connector starting",
            )
        )
        retry_count = 0

        def retry(retry_count, error_message=None):
            retry_count += 1
            sleep_time = 5
            if retry_count > 12:
                event = f"{self.name} {error_message}, too many retries, waiting 30 seconds..."
                sleep_time = 30
            else:
                event = f"{self.name} {error_message}, waiting 5 seconds..."

            # call the event handler signaling that the connector is unhealthy and waiting to retry
            self.connector_event_handler(
                ConnectorEvent(
                    connector_name=self.name,
                    event_type=ConnectorEventTypes.WARNING,
                    event=event,
                )
            )
            time.sleep(sleep_time)
            return retry_count

        while not self.terminated:
            try:
                if self.health_check():
                    retry_count = 0
                    # call the event handler signaling that the connector is healthy
                    self.connector_event_handler(
                        ConnectorEvent(
                            connector_name=self.name,
                            event_type=ConnectorEventTypes.HEALTHY,
                            event=f"{self.name} connector healthy",
                        )
                    )
                    self._run()
                else:
                    self._logger.debug(f"{self.name} connector unhealthy")
                    retry_count = retry(retry_count, "connector unhealthy")
            except Exception as e:
                self._logger.warning(f"{self.name} connector exception", exc_info=e)
                retry_count = retry(retry_count, "connector exception")

    def stop(self, timeout: float = 1):
        """Stops the connector."""

        self.terminated = True

        # call the event handler signaling that the connector is stopping
        self.connector_event_handler(
            ConnectorEvent(
                connector_name=self.name,
                event_type=ConnectorEventTypes.STOPPING,
                event=f"{self.name} connector stopping",
            )
        )
        self.join(timeout)
