"""Küçük yeniden kullanılabilir bileşenler."""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QEasingCurve, QPoint, QPointF, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from . import theme

ICONS = {
    "home": '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/>',
    "speed": '<path d="M4 18a8 8 0 1116 0"/><path d="M12 18l4-6"/>',
    "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    "proxy": '<circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M8.5 6H15a3 3 0 010 6H9a3 3 0 000 6h6.5"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>',
    "bolt": '<path d="M13 3L5 14h6l-1 7 8-11h-6z"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "lock": '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 018 0v3"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "refresh": '<path d="M20 11a8 8 0 10-2.3 5.7"/><path d="M20 4v7h-7"/>',
    "search": '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4-4"/>',
    "monitor": '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    "chevron": '<path d="M6 9l6 6 6-6"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
    "copy": '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 012-2h9"/>',
    "folder": '<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>',
}

APP_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect width="24" height="24" rx="6" fill="#0F6CBD"/>'
           '<g fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="6.5"/>'
           '<path d="M5.5 12h13M12 5.5c2.2 2.2 2.2 10.8 0 13M12 5.5c-2.2 2.2-2.2 10.8 0 13"/></g></svg>')


def app_pixmap(size: int = 256) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    QSvgRenderer(QByteArray(APP_SVG.encode())).render(p)
    p.end()
    return pm


def app_icon() -> QIcon:
    return QIcon(app_pixmap(256))


def svg_icon(name: str, color: str | None = None, size: int = 20, width: float = 1.8) -> QIcon:
    color = color or theme.P["tx"]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
           f'stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')
    r = QSvgRenderer(QByteArray(svg.encode()))
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    r.render(p)
    p.end()
    pm.setDevicePixelRatio(2)
    return QIcon(pm)


def set_cls(w: QWidget, cls: str) -> QWidget:
    w.setProperty("cls", cls)
    return w


def label(text: str = "", cls: str = "", wrap: bool = False) -> QLabel:
    lb = QLabel(text)
    if cls:
        lb.setProperty("cls", cls)
    lb.setWordWrap(wrap)
    return lb


def button(text: str = "", cls: str = "", icon: str | None = None, icon_color: str | None = None) -> QPushButton:
    b = QPushButton(text)
    if cls:
        b.setProperty("cls", cls)
    if icon:
        b.setIcon(svg_icon(icon, icon_color or (theme.P["acx"] if cls == "primary" else None), 18))
        b.setIconSize(QSize(18, 18))
    b.setCursor(Qt.PointingHandCursor)
    return b


def restyle(w: QWidget) -> None:
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def card(layout: QVBoxLayout | QHBoxLayout | None = None, name: str = "card") -> QFrame:
    f = QFrame()
    f.setObjectName(name)
    if layout is not None:
        f.setLayout(layout)
    return f


def vbox(margins=(0, 0, 0, 0), spacing=0) -> QVBoxLayout:
    lay = QVBoxLayout()
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return lay


def hbox(margins=(0, 0, 0, 0), spacing=0) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return lay


def sep() -> QFrame:
    f = QFrame()
    f.setObjectName("sep")
    f.setFixedHeight(1)
    return f


class Ring(QWidget):
    """Gecikme halkası: ortada değer ve birim."""

    def __init__(self, size: int = 128):
        super().__init__()
        self.setFixedSize(size, size)
        self.frac = 0.0
        self.text = "–"
        self.unit = "ms"
        self.color = "ok"

    def set_value(self, frac: float, text: str, unit: str, color: str = "ok") -> None:
        self.frac, self.text, self.unit, self.color = max(0.0, min(1.0, frac)), text, unit, color
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(7, 7, -7, -7)
        pen = QPen(QColor(theme.P["hv"]), 10)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(r, 0, 360 * 16)
        if self.frac > 0:
            pen.setColor(QColor(theme.P[self.color]))
            p.setPen(pen)
            p.drawArc(r, 90 * 16, int(-self.frac * 360 * 16))
        p.setPen(QColor(theme.P["tx"]))
        f = p.font()
        f.setPixelSize(30)
        f.setWeight(f.Weight.DemiBold)
        p.setFont(f)
        p.drawText(QRectF(0, self.height() / 2 - 26, self.width(), 34), Qt.AlignCenter, self.text)
        f.setPixelSize(13)
        f.setWeight(f.Weight.Normal)
        p.setFont(f)
        p.setPen(QColor(theme.P["mu"]))
        p.drawText(QRectF(0, self.height() / 2 + 6, self.width(), 20), Qt.AlignCenter, self.unit)


class Bar(QWidget):
    """İnce yatay çubuk (hız testi)."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(8)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.frac = 0.0
        self.color = "ok"
        self._anim: QVariantAnimation | None = None

    def set_value(self, frac: float, color: str) -> None:
        if self._anim is not None:
            self._anim.stop()
        self.frac, self.color = max(0.0, min(1.0, frac)), color
        self.update()

    def animate_to(self, frac: float, color: str, ms: int = 380) -> None:
        """Çubuğu yumuşakça yeni değere uzatır/kısaltır."""
        frac = max(0.0, min(1.0, frac))
        self.color = color
        if self._anim is None:
            self._anim = QVariantAnimation(self)
            self._anim.setEasingCurve(QEasingCurve.OutCubic)
            self._anim.valueChanged.connect(self._step)
        self._anim.stop()
        if abs(frac - self.frac) < 0.002 or not self.isVisible():
            self.set_value(frac, color)
            return
        self._anim.setDuration(ms)
        self._anim.setStartValue(float(self.frac))
        self._anim.setEndValue(float(frac))
        self._anim.start()

    def _step(self, v) -> None:
        self.frac = float(v)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.P["hv"]))
        p.drawRoundedRect(self.rect(), 4, 4)
        if self.frac > 0:
            p.setBrush(QColor(theme.P[self.color]))
            p.drawRoundedRect(QRectF(0, 0, self.width() * self.frac, self.height()), 4, 4)


class Switch(QAbstractButton):
    """Windows tarzı açma/kapama anahtarı."""

    def __init__(self, checked: bool = False):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(44, 24)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        track = QColor(theme.P["ac"] if on else theme.P["mu"])
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setBrush(track if on else Qt.NoBrush)
        pen = QPen(track, 1.5)
        p.setPen(pen)
        p.drawRoundedRect(r, 11, 11)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.P["acx"] if on else theme.P["mu"]))
        d = 14
        x = self.width() - 5 - d if on else 5
        p.drawEllipse(QPointF(x + d / 2, self.height() / 2), d / 2, d / 2)

    def sizeHint(self):
        return QSize(44, 24)


class Select(QPushButton):
    """Temaya uyumlu açılır seçici (QComboBox yerine): metin + ok, tıklayınca temalı menü açar."""

    currentTextChanged = Signal(str)

    def __init__(self, min_width: int = 180):
        super().__init__()
        self.setProperty("cls", "select")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(min_width)
        self._items: list[str] = []
        self._text = ""
        lay = hbox((12, 0, 10, 0), 8)
        self.setLayout(lay)
        self._lbl = QLabel()
        self._lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        arrow = QLabel()
        arrow.setAttribute(Qt.WA_TransparentForMouseEvents)
        arrow.setPixmap(svg_icon("chevron", theme.P["mu"], 14, 2.2).pixmap(14, 14))
        lay.addWidget(self._lbl, 1)
        lay.addWidget(arrow)
        self.clicked.connect(self._popup)

    def addItem(self, text: str) -> None:
        self._items.append(text)
        if not self._text:
            self.setCurrentText(text, emit=False)

    def currentText(self) -> str:
        return self._text

    def setCurrentText(self, text: str, emit: bool = True) -> None:
        if text == self._text:
            return
        self._text = text
        self._lbl.setText(text)
        if emit:
            self.currentTextChanged.emit(text)

    def _popup(self) -> None:
        if not self._items:
            return
        menu = QMenu(self)
        menu.setMinimumWidth(self.width())
        active = None
        for it in self._items:
            act = menu.addAction(it.replace("&", "&&"))
            act.setData(it)
            if it == self._text:
                active = act
        if active:
            menu.setActiveAction(active)
        chosen = menu.exec(self.mapToGlobal(QPoint(0, self.height() + 4)))
        if chosen is not None:
            self.setCurrentText(chosen.data())


class Toast(QLabel):
    """Pencerenin altında kısa bildirim."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("toast")
        self.hide()
        from PySide6.QtCore import QTimer
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def show_message(self, text: str, ms: int = 4000) -> None:
        self.setText(text)
        self.adjustSize()
        p = self.parentWidget()
        self.move((p.width() - self.width()) // 2, p.height() - self.height() - 28)
        self.raise_()
        self.show()
        self.timer.start(ms)
