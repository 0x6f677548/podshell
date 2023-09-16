import logging
from orchestration import Orchestrator, Event, EventType
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
    terminal_actions: list[QAction] = []
    pod_actions: list[QAction] = []

    _logger = logging.getLogger(__name__)

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
        self.orchestrator = Orchestrator(self.handle_event)
        self.orchestrator.start()

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
        """Adds the pod connectors to the menu.
        The pod connectors are added to the menu as checkable actions.
        Checked actions are enabled if the pod connector is alive.
        """

        for pod_connector in self.orchestrator.pod_connectors.values():
            self._logger.debug(f"Adding {pod_connector.name} to the menu")

            def on_trigger(checked, pod_connector_name=pod_connector.name):
                """Triggered when the user clicks on the pod connector action."""
                self._logger.debug(
                    f"Trigger pod connector {pod_connector_name}. State: {checked}"
                )
                self.orchestrator.trigger_pod_connector(pod_connector_name, checked)

            # adds the pod connector to the menu (as a checkable action)
            pod_action = QAction(
                pod_connector.name,
                triggered=on_trigger,
                checkable=True,
                checked=pod_connector.is_alive(),
            )
            self.pod_actions.append(pod_action)

        self.menu.addActions(self.pod_actions)

    def add_terminal_configurator_actions(self):
        """Adds the terminal configurators to the menu.
        The terminal configurators are added to the menu as checkable actions.
        Checked actions are enabled if the terminal connector is available.
        """
        for terminal_configurator in self.orchestrator.terminal_configurators.values():
            self._logger.debug(f"Adding {terminal_configurator.name} to the menu")

            def on_trigger(
                checked, terminal_configurator_name=terminal_configurator.name
            ):
                """Triggered when the user clicks on the terminal connector action."""
                self.orchestrator.trigger_terminal_configurator(
                    terminal_configurator_name, checked
                )

            # add the terminal connector to the menu
            terminal_action = QAction(
                terminal_configurator.name,
                triggered=on_trigger,
                checkable=True,
                checked=terminal_configurator.enabled,
            )
            self.terminal_actions.append(terminal_action)
        self.menu.addActions(self.terminal_actions)

    def show_log(self):
        self.log_window.show()

    def handle_event(self, event: Event):
        self.log_window.append_log(f"({event.event_type}) {event.message}")

        self._logger.info(f"Event: {event.event_type}, {event.message}, {event.data}")

        # update the icon
        if (
            event.event_type == EventType.STARTING
            or event.event_type == EventType.WARNING
            or event.event_type == EventType.ADD_PROFILE
            or event.event_type == EventType.REMOVE_PROFILE
        ):
            self.tray.setIcon(QIcon(":/images/icon_working.png"))
        elif event.event_type == EventType.STOPPING:
            self.tray.setIcon(QIcon(":/images/icon_off.png"))
        elif event.event_type == EventType.HEALTHY:
            self.tray.setIcon(QIcon(":/images/icon_on.png"))

    def run(self):
        # //TODO: add a way to save the terminal configuration
        # self.terminal_configuration.backup()

        self.qapp.exec()
        self.orchestrator.stop()



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    App().run()
