import time
import threading
import logging
from enum import StrEnum
import terminal.configuration as configuration


class ConnectorEventTypes(StrEnum):
    PROFILE_ADDED = "PROFILE_ADDED"
    PROFILE_REMOVED = "PROFILE_REMOVED"
    WARNING = "WARNING"
    STARTING = "STARTING"
    STOPPING = "STOPPING"
    HEALTHY = "HEALTHY"


class ConnectorEvent:
    def __init__(self, event_type: ConnectorEventTypes, event: str):
        self.event_type = event_type
        self.event = event


class BaseConnector(threading.Thread):
    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        connector_friendly_name: str,
        configuration: configuration.BaseConfiguration,
        f_handle_event: callable([ConnectorEvent, None]) = lambda _: None,
    ):
        super().__init__(daemon=True)
        self.terminated = False
        self.connector_friendly_name = connector_friendly_name
        self.configuration = configuration
        self.connector_event_handler = f_handle_event

    def _run(self):
        raise NotImplementedError()

    def health_check(self) -> bool:
        raise NotImplementedError()

    def run(self):
        self.connector_event_handler(
            ConnectorEvent(
                ConnectorEventTypes.STARTING,
                f"{self.connector_friendly_name} connector starting",
            )
        )
        retry_count = 0

        # reset the status
        self.configuration.remove_group(self.connector_friendly_name)

        while not self.terminated:
            try:
                if self.health_check():
                    retry_count = 0
                    self.connector_event_handler(
                        ConnectorEvent(
                            ConnectorEventTypes.HEALTHY,
                            f"{self.connector_friendly_name} connector healthy",
                        )
                    )

                self._run()
            except Exception as e:
                self._logger.warning(
                    f"{self.connector_friendly_name} connector exception", exc_info=e
                )
                self.configuration.remove_group(self.connector_friendly_name)
                retry_count += 1
                sleep_time = 5
                if retry_count > 12:
                    connector_event = ConnectorEvent(
                        ConnectorEventTypes.WARNING,
                        f"{self.connector_friendly_name} connector error, too many retries, waiting 30 seconds...",
                    )
                    sleep_time = 30
                else:
                    connector_event = ConnectorEvent(
                        ConnectorEventTypes.WARNING,
                        f"{self.connector_friendly_name} connector error, waiting 5 seconds...",
                    )
                self.connector_event_handler(connector_event)
                time.sleep(sleep_time)

    def stop(self, timeout: float = 1):
        self.connector_event_handler(
            ConnectorEvent(
                ConnectorEventTypes.STOPPING,
                f"{self.connector_friendly_name} connector stopping",
            )
        )
        self.configuration.remove_group(self.connector_friendly_name)
        self.terminated = True
        self.join(timeout)
