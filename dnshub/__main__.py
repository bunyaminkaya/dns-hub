"""Başlatıcı: python -m dnshub"""
import sys
from pathlib import Path

# `python dnshub/__main__.py` gibi doğrudan çalıştırılırsa üst klasörü yola ekle
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from dnshub import i18n
from dnshub.ui import theme
from dnshub.ui.controller import Controller
from dnshub.ui.main_window import MainWindow


def main() -> int:
    if sys.platform.startswith("win"):
        try:  # görev çubuğunda Python değil, DNS Hub simgesi ve grubu görünsün
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("bunyaminkaya.DNSHub")
        except Exception:  # noqa: BLE001
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("DNS Hub")
    ctl = Controller()
    i18n.set_language(ctl.settings.get("language"))
    theme.apply_theme(app, ctl.settings.get("theme"))
    win = MainWindow(ctl, app)
    win.show()
    if ctl.settings.get("apply_fastest_on_boot"):
        QTimer.singleShot(3000, ctl.find_fastest)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
