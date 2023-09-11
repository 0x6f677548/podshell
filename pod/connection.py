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
    '''Event that is sent to the connector event handler.'''
    def __init__(
        self,
        connector_friendly_name: str,
        event_type: ConnectorEventTypes,
        event: str,
        terminal_profile: configuration.TerminalProfile = None,
    ):
        '''Creates a new instance of the ConnectorEvent class.'''
        self.event_type = event_type
        self.event = event
        self.connector_friendly_name = connector_friendly_name
        self.terminal_profile = terminal_profile


class BaseConnector(threading.Thread):
    '''Base class for all connectors.'''
    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        connector_friendly_name: str,
        connector_event_handler: callable([ConnectorEvent, None]),
    ):
        '''Creates a new instance of the BaseConnector class.'''
        super().__init__(daemon=True)
        self.terminated = False
        self.connector_friendly_name = connector_friendly_name
        self.connector_event_handler = connector_event_handler

    def _run(self):
        raise NotImplementedError()

    def health_check(self) -> bool:
        '''Checks if the connector is healthy.'''
        raise NotImplementedError()

    def run(self):
        '''Runs the connector. This method should not be called directly. Use the start method instead.'''

        # call the event handler signaling that the connector is starting
        self.connector_event_handler(
            ConnectorEvent(
                connector_friendly_name=self.connector_friendly_name,
                event_type=ConnectorEventTypes.STARTING,
                event=f"{self.connector_friendly_name} connector starting",
            )
        )
        retry_count = 0

        while not self.terminated:
            try:
                if self.health_check():
                    retry_count = 0
                    # call the event handler signaling that the connector is healthy
                    self.connector_event_handler(
                        ConnectorEvent(
                            connector_friendly_name=self.connector_friendly_name,
                            event_type=ConnectorEventTypes.HEALTHY,
                            event=f"{self.connector_friendly_name} connector healthy",
                        )
                    )

                self._run()
            except Exception as e:
                self._logger.warning(
                    f"{self.connector_friendly_name} connector exception", exc_info=e
                )
                retry_count += 1
                sleep_time = 5
                if retry_count > 12:
                    event = f"{self.connector_friendly_name} connector error, too many retries, waiting 30 seconds..."
                    sleep_time = 30
                else:
                    event = f"{self.connector_friendly_name} connector error, waiting 5 seconds..."

                # call the event handler signaling that the connector is unhealthy and waiting to retry
                self.connector_event_handler(
                    ConnectorEvent(
                        connector_friendly_name=self.connector_friendly_name,
                        event_type=ConnectorEventTypes.WARNING,
                        event=event,
                    )
                )
                time.sleep(sleep_time)

    def stop(self, timeout: float = 1):
        '''Stops the connector.'''

        # call the event handler signaling that the connector is stopping
        self.connector_event_handler(
            ConnectorEvent(
                connector_friendly_name=self.connector_friendly_name,
                event_type=ConnectorEventTypes.STOPPING,
                event=f"{self.connector_friendly_name} connector stopping"
            )
        )
        self.terminated = True
        self.join(timeout)
