import logging
import threading
import time
from typing import Callable

from engine.events import Event, EventType


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

    def __init__(self, event_handler: Callable[[Event], None], name: str = ""):
        """Creates a new instance of the BaseConnector class."""
        super().__init__(daemon=True)
        self.terminated = False
        self.name = name
        self._event_handler = event_handler

    def _run(self):
        raise NotImplementedError()

    def health_check(self) -> bool:
        """Checks if the connector is healthy."""
        raise NotImplementedError()

    def run(self):
        """Runs the connector. This method should not be called directly. Use the start method instead."""

        # call the event handler signaling that the connector is starting
        self._event_handler(
            Event(
                source_name=self.name,
                event_type=EventType.STARTING,
                event_message=f"{self.name} connector",
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
            self._event_handler(
                Event(
                    source_name=self.name,
                    event_type=EventType.WARNING,
                    event_message=event,
                )
            )
            time.sleep(sleep_time)
            return retry_count

        while not self.terminated:
            try:
                if self.health_check():
                    retry_count = 0
                    # call the event handler signaling that the connector is healthy
                    self._event_handler(
                        Event(
                            source_name=self.name,
                            event_type=EventType.HEALTHY,
                            event_message=f"{self.name} connector",
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
        self._event_handler(
            Event(
                source_name=self.name,
                event_type=EventType.STOPPING,
                event_message=f"{self.name} connector",
            )
        )
        self.join(timeout)
