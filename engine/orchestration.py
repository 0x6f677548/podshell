import logging
from .pod.connection import BaseConnector as PodBaseConnector
from .terminal.configuration import BaseConfigurator as TerminalBaseConfigurator
from .terminal import windowsterminal, iterm2
from .pod.docker import DockerConnector
from .pod.ssh import SSHConnector
from .events import Event, EventType


class Orchestrator:
    """Represents the orchestrator between the pod connectors and the terminal configurators"""
    _pod_connector_types: list[PodBaseConnector] = [DockerConnector, SSHConnector]
    _terminal_configurator_types: list[TerminalBaseConfigurator] = [
        windowsterminal.WindowsTerminalConfigurator, iterm2.ITerm2Configurator
    ]
    # a dictionary (key: pod connector name, value: pod connector instance)
    pod_connectors: dict[str, PodBaseConnector] = {}
    """A dictionary (key: pod connector name, value: pod connector instance)"""

    # a dictionary (key: terminal configurator name, value: terminal configurator instance)
    terminal_configurators: dict[str, TerminalBaseConfigurator] = {}
    """A dictionary (key: terminal configurator name, value: terminal configurator instance)"""

    _logger = logging.getLogger(__name__)

    def __init__(self, event_handler: callable([Event, None])):
        self._event_handler = event_handler
        self._init_terminal_configurators()
        self._init_pod_connectors()

    def _init_terminal_configurators(self):
        """Inits the terminal configurators list"""
        for terminal_configurator_type in self._terminal_configurator_types:
            terminal_configurator: TerminalBaseConfigurator = (
                terminal_configurator_type()
            )
            self._logger.debug(
                f"Adding {terminal_configurator.name} to the available terminal configurators"
            )

            # add  the terminal connector to the dict of available connectors
            self.terminal_configurators[
                terminal_configurator.name
            ] = terminal_configurator

    def _init_pod_connectors(self):
        """Inits the pod connectors list"""
        for pod_connector_type in self._pod_connector_types:
            pod_connector: PodBaseConnector = pod_connector_type(
                event_handler=self._handle_connector_event
            )

            self._logger.debug(
                f"Adding {pod_connector.name} to the available pod connectors"
            )
            # add  the pod connector to the dict  of available connectors
            self.pod_connectors[pod_connector.name] = pod_connector

    def trigger_terminal_configurator(
        self, terminal_configurator_name: str, enable: bool
    ):
        """Triggers a terminal configurator by its name"""
        status = "ENABLE" if enable else "DISABLE"
        event_message = f"{terminal_configurator_name} connector"
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug(f"({status}) {event_message}")

        self._event_handler(
            Event(
                source_name=terminal_configurator_name,
                event_type=EventType.STARTING if enable else EventType.STOPPING,
                event_message=event_message,
            )
        )
        
        self.terminal_configurators[terminal_configurator_name].enabled = enable
        if enable:
            # since a new terminal connector has been enabled, we need to restart the pod connectors
            # otherwise the new terminal connector won't show the connections to the pods
            self._restart_alive_pod_connectors()
        else:
            # if the terminal connector is disabled, we need to remove the groups from the terminal connector
            # otherwise the terminal connector will show the connections to the pods
            self._remove_alive_pod_connectors_from_terminal_configurator(
                self.terminal_configurators[terminal_configurator_name]
            )

        self._send_healthy_event(terminal_configurator_name)

    def trigger_pod_connector(self, pod_connector_name: str, enable: bool):
        """Triggers a pod connector by its name"""
        self._logger.debug(
            f"Trigger pod connector {pod_connector_name}. State: {enable}"
        )
        self.pod_connectors[pod_connector_name].enabled = enable
        if enable:
            self._start_pod_connector(pod_connector_name)
        else:
            self._logger.debug(f"Stopping pod connector {pod_connector_name}")
            self.pod_connectors[pod_connector_name].stop()
        self._send_healthy_event(pod_connector_name)

    def _send_healthy_event(self, source_name: str):
        self._event_handler(
            Event(
                source_name=source_name,
                event_type=EventType.HEALTHY,
                event_message="Last operation completed successfully",
            )
        )

    def _start_pod_connector(self, pod_connector_name: str):
        """Starts a pod connector by its name"""
        self._logger.debug(f"Starting pod connector {pod_connector_name}")
        pod_connector = self.pod_connectors[pod_connector_name]
        if pod_connector.terminated:
            # create a new instance of the same type of the pod connector
            pod_connector = pod_connector.__class__(
                event_handler=self._handle_connector_event
            )
            self.pod_connectors[pod_connector_name] = pod_connector
        pod_connector.start()

    def _restart_alive_pod_connectors(self):
        for pod_connector in self.pod_connectors.values():
            if pod_connector.is_alive() and not pod_connector.terminated:
                pod_connector.stop()
                pod_connector = pod_connector.__class__(
                    event_handler=self._handle_connector_event
                )
                self.pod_connectors[pod_connector.name] = pod_connector
                pod_connector.start()

    def _remove_alive_pod_connectors_from_terminal_configurator(
        self, terminal_configurator: TerminalBaseConfigurator
    ):
        for pod_connector in self.pod_connectors.values():
            if pod_connector.is_alive():
                terminal_configurator.remove_group(pod_connector.name)

    def _get_enabled_terminal_configurator(self) -> list[TerminalBaseConfigurator]:
        return [
            terminal_configurator
            for terminal_configurator in self.terminal_configurators.values()
            if terminal_configurator.enabled
        ]

    def _handle_connector_event(self, event: Event):
        # notify event subscribers
        self._event_handler(event)

        self._logger.debug(f"Event: {event.event_type}, {event.message}")

        if (
            event.event_type == EventType.STARTING
            or event.event_type == EventType.STOPPING
            or event.event_type == EventType.WARNING
        ):
            for terminal_configurator in self._get_enabled_terminal_configurator():
                terminal_configurator.remove_group(event.source_name)

        elif event.event_type == EventType.ADD_PROFILE:
            # add profile to the configuration
            # update terminal connectors with the new configuration
            for terminal_configurator in self._get_enabled_terminal_configurator():
                terminal_configurator.add_profile(
                    event.data,
                    event.source_name,
                )
            # signaled that we're done (healthy)
            self._send_healthy_event(event.source_name)

        elif event.event_type == EventType.REMOVE_PROFILE:
            # remove profile from the configuration
            for terminal_configurator in self._get_enabled_terminal_configurator():
                terminal_configurator.remove_profile(event.data.name)
            self._send_healthy_event(event.source_name)

    def stop(self):
        """Stops all the pod connectors and terminal configurators"""
        for pod_connector in self.pod_connectors.values():
            if pod_connector.is_alive():
                pod_connector.stop()
        for terminal_configurator in self.terminal_configurators.values():
            terminal_configurator.enabled = False

    def start(self):
        """Starts all the pod connectors and terminal configurators.
        It also backs up the terminal configurators.
        """
        for terminal_configurator in self.terminal_configurators.values():
            if terminal_configurator.is_available():
                terminal_configurator.backup()
                terminal_configurator.enabled = True
        for pod_connector in self.pod_connectors.values():
            if pod_connector.health_check():
                self._start_pod_connector(pod_connector.name)
