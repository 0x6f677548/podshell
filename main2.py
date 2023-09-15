import sys
import random
from PySide6.QtCore import Slot, Qt
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QPushButton,
    QSystemTrayIcon,
    QMenu,
    QWidget,
    QVBoxLayout,
)
from PySide6.QtGui import QIcon, QAction


class MyWidget(QWidget):
    def __init__(self):
        QWidget.__init__(self)

        self.hello = ["Hallo Welt", "你好，世界", "Hei maailma", "Hola Mundo", "Привет мир"]

        self.button = QPushButton("Click me!")
        self.text = QLabel("Hello World")
        self.text.setAlignment(Qt.AlignCenter)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.text)
        self.layout.addWidget(self.button)
        self.setLayout(self.layout)

        # Connecting the signal
        self.button.clicked.connect(self.magic)

    @Slot()
    def magic(self):
        self.text.setText(random.choice(self.hello))


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Adding an icon
    icon = QIcon(":/images/icon_on.png")

    # Adding item on the menu bar
    tray = QSystemTrayIcon()
    tray.setIcon(icon)
    tray.setVisible(True)
    menu = QMenu()

    # Adding a separator
    menu.addSeparator()

    # To quit the app
    quit_action = QAction("Quit")
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)

    # Adding options to the System Tray
    tray.setContextMenu(menu)

    widget = MyWidget()
    widget.resize(800, 600)
    widget.show()

    sys.exit(app.exec_())
