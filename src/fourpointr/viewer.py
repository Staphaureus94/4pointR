from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QToolButton,
    QFileDialog,
    QDockWidget
)

from PyQt5.QtGui import QIcon

class ViewerWindow(QMainWindow):
    def __init__(self):
        super().__init__()

    def setup_dock(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        dir_line = DirLineEdit()
        layout.addWidget(dir_line)

        dock = QDockWidget('Settings')
        dock.setWidget(widget)
        dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.addDockWidget()









class DirLineEdit(QWidget):
    def __init__(self):
        super().__init__()

        # Layout
        layout = QHBoxLayout(self)

        # Line edit to show selected directory
        self.line_edit = QLineEdit(self)
        self.line_edit.setPlaceholderText("Select a directory...")

        # Button to open the file dialog
        self.button = QToolButton(self)
        self.button.setIcon(QIcon.fromTheme("folder"))  # Uses system folder icon
        self.button.clicked.connect(self.choose_directory)

        # Add widgets to layout
        layout.addWidget(self.line_edit)
        layout.addWidget(self.button)

    def choose_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory", self.line_edit.text())
        if directory:
            self.line_edit.setText(directory) 
