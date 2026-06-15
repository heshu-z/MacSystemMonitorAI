"""
MacSystemMonitorAI - macOS 系统监控工具
Application entry point.
"""
import sys

from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
