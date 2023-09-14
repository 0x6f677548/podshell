import logging
import os
from terminal import windowsterminal
from pod.docker import DockerConnector
from pod.ssh import SSHConnector
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


class LogWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Log Window")
        self.setWindowIcon(QIcon("icon_on.png"))
        self.setGeometry(100, 100, 400, 300)
        layout = QVBoxLayout()
        self.log_text = QTextEdit(self)
        layout.addWidget(self.log_text)
        self.setLayout(layout)

    def append_log(self, message):
        self.log_text.append(message)


class App:
    ssh_connector = None
    docker_connector = None
    logger = logging.getLogger(__name__)

    def __init__(self):
        self.terminal_configuration = windowsterminal.Configuration()
        self.qapp = QApplication([])
        self.qapp.setQuitOnLastWindowClosed(False)

        # Adding an icon
        icon = QIcon("icon_on.png")

        # Adding item on the menu bar
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(icon)
        self.tray.setVisible(True)

        # Creating the options
        self.menu = QMenu()
        self.ssh_option = QAction(
            "SSH", triggered=self.toggle_ssh, checkable=True, checked=True
        )
        self.menu.addAction(self.ssh_option)
        self.docker_option = QAction(
            "Docker", triggered=self.toggle_docker, checkable=True, checked=True
        )
        self.menu.addAction(self.docker_option)
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

        self.log_window = LogWindow()

    def toggle_ssh(self):
        if self.ssh_option.isChecked():
            self.ssh_connector = self._get_ssh_connector()
            self.ssh_connector.start()
        else:
            self.ssh_connector.stop()

    def toggle_docker(self):
        if self.docker_option.isChecked():
            self.docker_connector = self._get_docker_connector()
            self.docker_connector.start()
        else:
            self.docker_connector.stop()

    def show_log(self):
        self.log_window.show()

    def _get_docker_connector(self):
        return DockerConnector(
            connector_event_handler=self.handle_event,
            shell_command="/bin/bash",
        )

    def _get_ssh_connector(self):
        return SSHConnector(
            connector_event_handler=self.handle_event,
            ssh_config_file=os.path.expanduser(os.path.join("~", ".ssh", "config")),
        )

    def handle_event(self, connector_event: ConnectorEvent):
        # date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        event_date = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_window.append_log(
            f"{event_date} ({connector_event.event_type}) {connector_event.event}"
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
                self.tray.setIcon(QIcon("icon_working.png"))
            elif connector_event.event_type == ConnectorEventTypes.STOPPING:
                self.tray.setIcon(QIcon("icon_off.png"))
            elif connector_event.event_type == ConnectorEventTypes.WARNING:
                self.tray.setIcon(QIcon("icon_working.png"))

            # remove profiles from the configuration
            self.terminal_configuration.remove_group(
                connector_event.connector_friendly_name
            )
        elif connector_event.event_type == ConnectorEventTypes.ADD_PROFILE:
            self.tray.setIcon(QIcon("icon_working.png"))
            # add profile to the configuration
            self.terminal_configuration.add_profile(
                connector_event.terminal_profile,
                connector_event.connector_friendly_name,
            )
            self.tray.setIcon(QIcon("icon_on.png"))
        elif connector_event.event_type == ConnectorEventTypes.REMOVE_PROFILE:
            self.tray.setIcon(QIcon("icon_working.png"))
            # remove profile from the configuration
            self.terminal_configuration.remove_profile(
                connector_event.terminal_profile.name
            )
            self.tray.setIcon(QIcon("icon_on.png"))
        elif connector_event.event_type == ConnectorEventTypes.HEALTHY:
            # update the icon
            self.tray.setIcon(QIcon("icon_on.png"))

    def run(self):
        self.terminal_configuration.backup()
        self.toggle_ssh()
        self.toggle_docker()

        self.qapp.exec()
        if not self.ssh_connector.terminated:
            self.ssh_connector.stop()
        if not self.docker_connector.terminated:
            self.docker_connector.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    App().run()
