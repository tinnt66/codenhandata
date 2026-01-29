import sys

from PySide6.QtWidgets import QApplication

from .ui.dashboard import Dashboard


def main():
    app = QApplication(sys.argv)
    w = Dashboard()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
