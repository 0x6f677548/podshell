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
        icon = QIcon(":/resources/icon_on.png")
        self.setWindowIcon(icon)
        self.setGeometry(100, 100, 400, 300)
        layout = QVBoxLayout()
        self.log_text = QTextEdit(self)
        layout.addWidget(self.log_text)
        self.setLayout(layout)

    def append_log(self, message):
        event_date = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_text.append(f"{event_date} {message}")


class App:
    """Represents the UI App"""
    _terminal_actions: list[QAction] = []
    _pod_actions: list[QAction] = []
    _logger = logging.getLogger(__name__)

    def __init__(self):
        self._qapp = QApplication([])
        self._qapp.setQuitOnLastWindowClosed(False)

        # Adding an icon
        icon = QIcon(":/resources/icon_on.png")

        # Adding item on the menu bar
        self._tray = QSystemTrayIcon()
        self._tray.setIcon(icon)
        self._tray.setVisible(True)
        self._menu = QMenu()
        self._log_window = LogWindow()

        # create the  orchestrator and start it
        self._orchestrator = Orchestrator(self._handle_orchestrator_event)
        self._orchestrator.start()

        # adding terminal configurators and pod connectors to the menu
        self._add_terminal_configurator_actions()
        self._menu.addSeparator()
        self._add_pod_connector_actions()
        self._menu.addSeparator()
        # Adding a show log action
        self._show_log_action = QAction("Show Log", triggered=self.show_log)
        self._menu.addAction(self._show_log_action)
        self._menu.addSeparator()
        # //TODO: add a enable/disable all action
        # Adding a quit action
        self._quit_action = QAction("Quit")
        self._quit_action.triggered.connect(self._qapp.quit)
        self._menu.addAction(self._quit_action)

        # Adding options to the System Tray
        self._tray.setContextMenu(self._menu)

    def _add_pod_connector_actions(self):
        """Adds the pod connectors to the menu as checkable actions.
        Checked actions are enabled if the pod connector is alive.
        """

        for pod_connector in self._orchestrator.pod_connectors.values():
            if self._logger.isEnabledFor(logging.DEBUG):
                self._logger.debug(f"Adding {pod_connector.name} to the menu")

            def on_trigger(checked, pod_connector_name=pod_connector.name):
                self._orchestrator.trigger_pod_connector(pod_connector_name, checked)

            # adds the pod connector to the menu (as a checkable action)
            self._pod_actions.append(
                QAction(
                    pod_connector.name,
                    triggered=on_trigger,
                    checkable=True,
                    checked=pod_connector.is_alive(),
                )
            )

        self._menu.addActions(self._pod_actions)

    def _add_terminal_configurator_actions(self):
        """Adds the terminal configurators to the menu as checkable actions.
        Checked actions are enabled if the terminal connector is available.
        """
        for terminal_configurator in self._orchestrator.terminal_configurators.values():
            if self._logger.isEnabledFor(logging.DEBUG):
                self._logger.debug(f"Adding {terminal_configurator.name} to the menu")

            def on_trigger(
                checked, terminal_configurator_name=terminal_configurator.name
            ):
                self._orchestrator.trigger_terminal_configurator(
                    terminal_configurator_name, checked
                )

            # add the terminal connector to the menu
            self._terminal_actions.append(
                QAction(
                    terminal_configurator.name,
                    triggered=on_trigger,
                    checkable=True,
                    checked=terminal_configurator.enabled,
                )
            )
        self._menu.addActions(self._terminal_actions)

    def show_log(self):
        self._log_window.show()

    def _handle_orchestrator_event(self, event: Event):
        self._logger.info(f"Event: {event.event_type}, {event.message}, {event.data}")

        # update the icon
        if (
            event.event_type == EventType.STARTING
            or event.event_type == EventType.WARNING
            or event.event_type == EventType.ADD_PROFILE
            or event.event_type == EventType.REMOVE_PROFILE
        ):
            self._tray.setIcon(QIcon(":/resources/icon_working.png"))
        elif event.event_type == EventType.STOPPING:
            self._tray.setIcon(QIcon(":/resources/icon_off.png"))
        elif event.event_type == EventType.HEALTHY:
            self._tray.setIcon(QIcon(":/resources/icon_on.png"))

    def run(self):
        # //TODO: add a way to save the terminal configuration
        # self.terminal_configuration.backup()

        self._qapp.exec()
        self._orchestrator.stop()


if __name__ == "__main__":
    # we'll only log INFO messages when running in windowed mode
    logging.basicConfig(level=logging.INFO)
    App().run()
