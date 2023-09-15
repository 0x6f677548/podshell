import logging
from terminal import windowsterminal
from pod.docker import DockerConnector
from pod.ssh import SSHConnector
from pod.connection import BaseConnector as PodBaseConnector
from terminal.configuration import BaseConfigurator as TerminalBaseConfigurator
from pod.connection import ConnectorEvent, ConnectorEventTypes
from PySide6.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QWidget,
    QVBoxLayout,
    QTextEdit,
)
from PySide6.QtGui import QIcon, QAction
import datetime
import icon_rc  # noqa: F401


class LogWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Log Window")
        icon = QIcon(":/images/icon_on.png")
        self.setWindowIcon(icon)
        self.setGeometry(100, 100, 400, 300)
        layout = QVBoxLayout()
        self.log_text = QTextEdit(self)
        layout.addWidget(self.log_text)
        self.setLayout(layout)

    def append_log(self, message):
        event_date = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        message = f"{event_date} {message}"
        self.log_text.append(message)


class App:
    pod_connector_types: list[PodBaseConnector] = [DockerConnector, SSHConnector]
    terminal_configurator_types: list[TerminalBaseConfigurator] = [windowsterminal.WindowsTerminalConfigurator]
    pod_connectors = {}
    terminal_configurators = {}
    terminal_actions = []
    pod_actions = []

    logger = logging.getLogger(__name__)

    def __init__(self):
        self.qapp = QApplication([])
        self.qapp.setQuitOnLastWindowClosed(False)

        # Adding an icon
        icon = QIcon(":/images/icon_on.png")

        # Adding item on the menu bar
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(icon)
        self.tray.setVisible(True)
        self.menu = QMenu()
        self.log_window = LogWindow()

        self.add_terminal_configurator_actions()
        # Adding a separator
        self.menu.addSeparator()

        self.add_pod_connector_actions()

        # Adding a separator
        self.menu.addSeparator()

        self.show_log_action = QAction("Show Log", triggered=self.show_log)
        self.menu.addAction(self.show_log_action)

        # Adding a separator
        self.menu.addSeparator()

        # To quit the app
        self.quit_action = QAction("Quit")
        self.quit_action.triggered.connect(self.qapp.quit)
        self.menu.addAction(self.quit_action)

        # Adding options to the System Tray
        self.tray.setContextMenu(self.menu)

    def add_pod_connector_actions(self):
        '''Adds the pod connectors to the menu.
        The pod connectors are added to the menu as checkable actions.
        Checked actions are enabled if the pod connector is available.
        '''

        for pod_connector_type in self.pod_connector_types:
            pod_connector = pod_connector_type(
                connector_event_handler=self.handle_event
            )

            self.logger.debug(f"Adding {pod_connector.name} to the menu")
            # add  the pod connector to the dict  of available connectors
            self.pod_connectors[pod_connector.name] = pod_connector

            def on_trigger(
                checked,
                pod_connector=pod_connector,
                pod_connector_type=pod_connector_type,
            ):
                '''Triggered when the user clicks on the pod connector action.'''
                self.logger.info(
                    f"Trigger pod connector {pod_connector}. State: {checked}"
                )
                if checked:
                    # we'll create a new instance of the pod connector
                    # this is needed because the pod connector is a thread
                    # and we can't restart a thread
                    pod_connector = pod_connector_type(
                        connector_event_handler=self.handle_event
                    )
                    pod_connector.start()
                    self.pod_connectors[pod_connector.name] = pod_connector
                else:
                    pod_connector.stop()

            pod_connector_available = pod_connector.health_check()
            # adds the pod connector to the menu (as a checkable action)
            pod_action = QAction(
                pod_connector.name,
                triggered=on_trigger,
                checkable=True,
                checked=pod_connector_available,
            )
            self.pod_actions.append(pod_action)
            # start the pod connector if it's available (health check passed)
            if pod_connector_available:
                pod_connector.start()

        self.menu.addActions(self.pod_actions)

    def add_terminal_configurator_actions(self):
        '''Adds the terminal configurators to the menu.
        The terminal configurators are added to the menu as checkable actions.
        Checked actions are enabled if the terminal connector is available.
        '''
        for terminal_configurator_type in self.terminal_configurator_types:
            terminal_configurator = terminal_configurator_type()
            self.logger.debug(f"Adding {terminal_configurator.name} to the menu")

            # add  the terminal connector to the dict of available connectors
            self.terminal_configurators[terminal_configurator.name] = terminal_configurator

            def on_trigger(
                checked,
                terminal_configurator=terminal_configurator,
                terminal_configurator_type=terminal_configurator_type,
            ):
                '''Triggered when the user clicks on the terminal connector action.'''

                status = "ENABLE" if checked else "DISABLE"
                log_message = f"({status}) {terminal_configurator.name} connector"
                self.log_window.append_log(log_message)
                self.logger.info(log_message)

                if checked:
                    terminal_configurator = terminal_configurator_type()
                    terminal_configurator.enabled = True
                    self.terminal_configurators[
                        terminal_configurator.name
                    ] = terminal_configurator
                    # since a new terminal connector has been added, we need to restart the pod connectors
                    # otherwise the new terminal connector won't show the connections to the pods
                    self._restart_alive_pod_connectors()
                else:
                    terminal_configurator.enabled = False
                    # if the terminal connector is disabled, we need to remove the groups from the terminal connector
                    # otherwise the terminal connector will show the connections to the pods
                    self._remove_alive_pod_connectors_from_terminal_configurator(
                        terminal_configurator
                    )
            is_available = terminal_configurator_type.is_available()
            # add the terminal connector to the menu
            terminal_action = QAction(
                terminal_configurator.name,
                triggered=on_trigger,
                checkable=True,
                checked=is_available,
            )
            self.terminal_actions.append(terminal_action)
            if is_available:
                terminal_configurator.enabled = True

        self.menu.addActions(self.terminal_actions)

    def show_log(self):
        self.log_window.show()

    def _get_enabled_terminal_configurator(self) -> list[TerminalBaseConfigurator]:
        return [
            terminal_configurator
            for terminal_configurator in self.terminal_configurators.values()
            if terminal_configurator.enabled
        ]

    def _restart_alive_pod_connectors(self):
        for pod_connector in self.pod_connectors.values():
            if pod_connector.is_alive():
                pod_connector.stop()
                pod_connector = pod_connector.__class__(
                    connector_event_handler=self.handle_event
                )
                self.pod_connectors[pod_connector.name] = pod_connector
                pod_connector.start()

    def _remove_alive_pod_connectors_from_terminal_configurator(self, terminal_configurator):
        for pod_connector in self.pod_connectors.values():
            if pod_connector.is_alive():
                terminal_configurator.remove_group(pod_connector.name)

    def handle_event(self, connector_event: ConnectorEvent):
        self.log_window.append_log(
            f"({connector_event.event_type}) {connector_event.event}"
        )

        self.logger.info(
            f"Event: {connector_event.event_type}, {connector_event.event}, {connector_event.terminal_profile}"
        )

        if (
            connector_event.event_type == ConnectorEventTypes.STARTING
            or connector_event.event_type == ConnectorEventTypes.STOPPING
            or connector_event.event_type == ConnectorEventTypes.WARNING
        ):
            # update the icon
            if connector_event.event_type == ConnectorEventTypes.STARTING:
                self.tray.setIcon(QIcon(":/images/icon_working.png"))
            elif connector_event.event_type == ConnectorEventTypes.STOPPING:
                self.tray.setIcon(QIcon(":/images/icon_off.png"))
            elif connector_event.event_type == ConnectorEventTypes.WARNING:
                self.tray.setIcon(QIcon(":/images/icon_working.png"))

            for terminal_configurator in self._get_enabled_terminal_configurator():
                terminal_configurator.remove_group(connector_event.connector_name)

        elif connector_event.event_type == ConnectorEventTypes.ADD_PROFILE:
            self.tray.setIcon(QIcon(":/images/icon_working.png"))
            # add profile to the configuration
            # update terminal connectors with the new configuration
            for terminal_configurator in self._get_enabled_terminal_configurator():
                terminal_configurator.add_profile(
                    connector_event.terminal_profile,
                    connector_event.connector_name,
                )
            self.tray.setIcon(QIcon(":/images/icon_on.png"))
        elif connector_event.event_type == ConnectorEventTypes.REMOVE_PROFILE:
            self.tray.setIcon(QIcon(":/images/icon_working.png"))
            # remove profile from the configuration
            for terminal_configurator in self._get_enabled_terminal_configurator():
                terminal_configurator.remove_profile(connector_event.terminal_profile.name)
            self.tray.setIcon(QIcon(":/images/icon_on.png"))
        elif connector_event.event_type == ConnectorEventTypes.HEALTHY:
            # update the icon
            self.tray.setIcon(QIcon(":/images/icon_on.png"))

    def run(self):
        # //TODO: add a way to save the terminal configuration
        # self.terminal_configuration.backup()

        self.qapp.exec()

        for pod_connector in self.pod_connectors.values():
            if pod_connector.is_alive():
                pod_connector.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    App().run()
