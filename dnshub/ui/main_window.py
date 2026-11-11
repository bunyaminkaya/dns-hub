"""Ana pencere: kenar çubuğu, sayfalar, tema/dil değişince yeniden kurulum, tepsi simgesi."""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QButtonGroup, QMainWindow, QMenu, QSystemTrayIcon, QWidget

from ..i18n import t
from . import theme
from .pages import AboutPage, HomePage, ListPage, SettingsPage, SoonPage, TestPage
from .titlebar import apply_titlebar
from .widgets import Toast, app_icon, button, hbox, svg_icon, vbox

NAV = [("home", "home", "nav.home"), ("list", "list", "nav.list"), ("test", "speed", "nav.test"),
       ("block", "shield", "nav.block"), ("proxy", "proxy", "nav.proxy")]
NAV_BOTTOM = [("settings", "settings", "nav.settings"), ("about", "info", "nav.about")]


class MainWindow(QMainWindow):
    def __init__(self, ctl, app: QApplication):
        super().__init__()
        self.ctl, self.app = ctl, app
        self.current = "home"
        self.setWindowIcon(app_icon())
        self.setWindowTitle(t("app.name"))
        self.resize(1120, 720)
        self.setMinimumSize(960, 640)
        self.toast = Toast(self)
        ctl.toast.connect(self.toast.show_message)
        self.tray = None
        self._quitting = False
        self._build()
        self._setup_tray()
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._system_theme_changed)

    # ------------------------------------------------------------ kurulum
    def _build(self):
        self.setWindowTitle(t("app.name"))
        central = QWidget()
        central.setObjectName("root")
        outer = hbox()
        central.setLayout(outer)

        nav = QWidget()
        nav.setObjectName("nav")
        nav.setFixedWidth(232)
        nl = vbox((12, 16, 12, 16), 4)
        nav.setLayout(nl)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, object] = {}
        for key, icon, tk in NAV:
            nl.addWidget(self._nav_button(key, icon, tk))
        nl.addStretch(1)
        for key, icon, tk in NAV_BOTTOM:
            nl.addWidget(self._nav_button(key, icon, tk))
        outer.addWidget(nav)

        from PySide6.QtWidgets import QStackedWidget
        self.stack = QStackedWidget()
        self.pages = {
            "home": HomePage(self.ctl),
            "list": ListPage(self.ctl),
            "test": TestPage(self.ctl),
            "block": SoonPage(self.ctl, "block"),
            "proxy": SoonPage(self.ctl, "proxy"),
            "settings": SettingsPage(self.ctl),
            "about": AboutPage(self.ctl),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)
        outer.addWidget(self.stack, 1)
        st = self.pages["settings"]
        st.theme_changed.connect(lambda: QTimer.singleShot(0, self.rebuild))
        st.language_changed.connect(lambda: QTimer.singleShot(0, self.rebuild))

        self.setCentralWidget(central)
        self.toast.raise_()
        self.show_page(self.current)

    def _nav_button(self, key: str, icon: str, tk: str):
        b = button(t(tk), "nav")
        b.setCheckable(True)
        b.setIcon(svg_icon(icon, theme.P["tx"], 20, 1.7))
        b.setIconSize(QSize(20, 20))
        b.setProperty("key", key)
        b.clicked.connect(lambda _=False, k=key: self.show_page(k))
        self.nav_group.addButton(b)
        self.nav_buttons[key] = b
        return b

    def show_page(self, key: str):
        self.current = key
        self.stack.setCurrentWidget(self.pages[key])
        for k, b in self.nav_buttons.items():
            b.setChecked(k == key)
            b.setIcon(svg_icon(dict((n[0], n[1]) for n in NAV + NAV_BOTTOM)[k],
                               theme.P["ac"] if k == key else theme.P["tx"], 20, 1.7))
        if key == "home":
            self.pages["home"].refresh()
        elif key == "list":
            self.pages["list"].reload()

    def rebuild(self):
        """Tema veya dil değişti: sayfaları yeniden kur (durum denetleyicide tutulur)."""
        theme.apply_theme(self.app, self.ctl.settings.get("theme"))
        apply_titlebar(self)
        self._build()
        self._refresh_tray_menu()

    def _system_theme_changed(self, *_):
        if self.ctl.settings.get("theme") == "system":
            QTimer.singleShot(0, self.rebuild)

    # ------------------------------------------------------------ tepsi
    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(t("app.name"))
        self.tray.activated.connect(lambda reason: self._show_from_tray()
                                    if reason == QSystemTrayIcon.Trigger else None)
        self._refresh_tray_menu()
        if self.ctl.settings.get("tray"):
            self.tray.show()

    def _refresh_tray_menu(self):
        if not self.tray:
            return
        menu = QMenu()
        act_show = QAction(t("app.name"), menu)
        act_show.triggered.connect(self._show_from_tray)
        act_fast = QAction(t("home.fastest"), menu)
        act_fast.triggered.connect(self.ctl.find_fastest)
        act_rev = QAction(t("home.revert"), menu)
        act_rev.triggered.connect(self.ctl.restore)
        act_quit = QAction(t("common.quit"), menu)
        act_quit.triggered.connect(self.quit)
        for a in (act_show, act_fast, act_rev):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(act_quit)
        self._tray_menu = menu
        self.tray.setContextMenu(menu)
        self.tray.setVisible(bool(self.ctl.settings.get("tray")))

    def _show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit(self):
        self._quitting = True
        self.app.quit()

    def closeEvent(self, ev):
        if (not self._quitting and self.tray and self.tray.isVisible() and self.ctl.settings.get("tray")):
            ev.ignore()
            self.hide()
            return
        ev.accept()
        self.app.quit()

    def showEvent(self, ev):
        super().showEvent(ev)
        apply_titlebar(self)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if self.toast.isVisible():
            self.toast.move((self.width() - self.toast.width()) // 2, self.height() - self.toast.height() - 28)
