"""Uygulama sayfaları. Metinler oluşturulurken t() ile okunur, dil/tema değişince sayfalar yeniden kurulur."""
from __future__ import annotations

import platform
import time
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRectF, Qt, QUrl, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QDesktopServices, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QFileDialog, QFrame,
                               QHeaderView, QLabel, QLineEdit, QProgressBar, QPushButton, QRadioButton,
                               QScrollArea, QTableWidget, QTableWidgetItem, QWidget)

from .. import AUTHOR, WEBSITE, __version__, i18n, storage, winnet
from ..i18n import t
from . import theme
from .dialogs import CustomDnsDialog
from .widgets import (Bar, Ring, Select, Switch, app_pixmap, button, card, hbox, label, restyle, sep, svg_icon,
                      vbox)


def _page_layout(page: QWidget, spacing: int = 20) -> "vbox":
    page.setObjectName("page")
    lay = vbox((16, 12, 32, 28), spacing)
    page.setLayout(lay)
    return lay


def _ms_color(ms: float | None) -> str:
    if ms is None:
        return "er"
    return "ok" if ms < 50 else "wn" if ms < 120 else "er"


def _proto_text(p: dict) -> str:
    parts = []
    if p.get("doh"):
        parts.append("DoH")
    if p.get("dot"):
        parts.append("DoT")
    return " · ".join(parts) if parts else t("list.plain")


def _addr_text(p: dict) -> str:
    return "  ·  ".join((p.get("v4") or p.get("v6") or [])[:2])


def _icon_circle(icon: str, bg: str, fg: str) -> QLabel:
    lb = label()
    lb.setFixedSize(32, 32)
    lb.setAlignment(Qt.AlignCenter)
    lb.setStyleSheet(f"background:{theme.P[bg]}; border-radius:16px;")
    lb.setPixmap(svg_icon(icon, theme.P[fg], 16, 1.9).pixmap(16, 16))
    return lb


# =============================================================== ANA SAYFA
class HomePage(QWidget):
    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        lay = _page_layout(self)

        head = hbox()
        head.addWidget(label(t("home.title"), "h1"))
        head.addStretch(1)
        self.adapter = Select(180)
        self.adapter.setToolTip(t("home.adapter"))
        head.addWidget(self.adapter)
        lay.addLayout(head)

        # durum kartı
        self.name = label("–", "big")
        self.addr = label("", "muted")
        self.pill_proto = label("", "pill")
        self.pill_extra = label("", "pill")
        left = vbox(spacing=10)
        left.addWidget(label(t("home.current"), "muted"))
        left.addWidget(self.name)
        left.addWidget(self.addr)
        pills = hbox(spacing=8)
        pills.addWidget(self.pill_proto)
        pills.addWidget(self.pill_extra)
        pills.addStretch(1)
        left.addSpacing(4)
        left.addLayout(pills)
        self.ring = Ring(128)
        row = hbox((32, 28, 32, 28), 24)
        row.addLayout(left, 1)
        row.addWidget(self.ring)
        lay.addWidget(card(row))

        # ana düğmeler
        btns = hbox(spacing=12)
        self.btn_fast = button(t("home.fastest"), "primary", "bolt")
        self.btn_fast.setProperty("cls", "primary")
        self.btn_fast.setMinimumHeight(56)
        self.btn_fast.setStyleSheet("font-size:16px; border-radius:8px;")
        self.btn_revert = button(t("home.revert"))
        self.btn_revert.setMinimumHeight(56)
        btns.addWidget(self.btn_fast, 1)
        btns.addWidget(self.btn_revert)
        lay.addLayout(btns)
        hint = label(t("home.hint"), "muted", wrap=True)
        lay.addWidget(hint)

        # hızlı giriş
        self.quick = QLineEdit()
        self.quick.setPlaceholderText(t("home.quick_ph"))
        self.btn_quick = button(t("home.apply"), "outline")
        self.btn_save = button(t("home.save"), "ghost")
        qrow = hbox((16, 14, 16, 14), 12)
        qrow.addWidget(self.quick, 1)
        qrow.addWidget(self.btn_quick)
        qrow.addWidget(self.btn_save)
        lay.addWidget(card(qrow))

        # üç kart
        grid = hbox(spacing=16)
        self.card_test = self._info_card("speed", "acs", "ac", t("home.lasttest"))
        self.card_block = self._info_card("shield", "hv", "mu", t("home.block"))
        self.card_leak = self._info_card("lock", "hv", "mu", t("home.leak"))
        for c in (self.card_test, self.card_block, self.card_leak):
            grid.addWidget(c[0], 1)
        lay.addLayout(grid)
        lay.addStretch(1)
        self.card_block[1].setText(t("home.soon"))
        self.card_block[2].setText("v0.2")
        self.card_leak[1].setText(t("home.soon"))
        self.card_leak[2].setText("v0.2")

        # bağlantılar
        for a in ctl.adapters():
            self.adapter.addItem(a["Name"])
        cur = ctl.adapter_name()
        if cur:
            self.adapter.setCurrentText(cur)
        self.adapter.currentTextChanged.connect(ctl.select_adapter)
        self.btn_fast.clicked.connect(ctl.find_fastest)
        self.btn_revert.clicked.connect(ctl.restore)
        self.btn_quick.clicked.connect(self._quick_apply)
        self.quick.returnPressed.connect(self._quick_apply)
        self.btn_save.clicked.connect(self._quick_save)
        ctl.changed.connect(self.refresh)
        ctl.latency.connect(self._latency)
        ctl.test_progress.connect(self._progress)
        ctl.test_state.connect(self._test_state)
        ctl.busy.connect(self._busy)
        self.refresh()

    def _info_card(self, icon, bg, fg, title):
        top = hbox(spacing=10)
        top.addWidget(_icon_circle(icon, bg, fg))
        top.addWidget(label(title, "muted"), 1)
        v1, v2 = label("", "strong"), label("", "muted")
        lay = vbox((18, 18, 18, 18), 6)
        lay.addLayout(top)
        lay.addSpacing(2)
        lay.addWidget(v1)
        lay.addWidget(v2)
        return card(lay), v1, v2

    # ---- durum
    def refresh(self):
        info = self.ctl.current_info()
        self.name.setText(info["name"])
        self.addr.setText("  ·  ".join(info["addrs"][:2]))
        self.pill_proto.setProperty("cls", "pill_ok" if info["encrypted"] else "pill")
        self.pill_proto.setText(t("home.proto_enc") + " · DoH" if info["encrypted"] else t("home.proto_plain"))
        restyle(self.pill_proto)
        self.pill_extra.setVisible(False)
        self.ring.set_value(0, "–", t("common.ms"))
        self.ctl.measure_current()
        li = self.ctl.last_test_info()
        if li["time"]:
            self.card_test[1].setText(t("home.lasttest_n", n=li["count"]))
            self.card_test[2].setText(time.strftime("%d.%m.%Y %H:%M", time.localtime(li["time"])))
        else:
            self.card_test[1].setText(t("home.never"))
            self.card_test[2].setText("")
        self.btn_revert.setEnabled(self.ctl.manager.has_backup())

    def _latency(self, ms):
        if ms is None:
            self.ring.set_value(0, "–", t("common.ms"), "er")
        else:
            self.ring.set_value(1 - ms / 100, f"{ms:.0f}", t("common.ms"), _ms_color(ms))

    def _progress(self, done, total):
        if self.ctl.testing:
            self.btn_fast.setText(f"{done} / {total}")

    def _test_state(self, running):
        self.btn_fast.setEnabled(not running)
        if not running:
            self.btn_fast.setText(t("home.fastest"))

    def _busy(self, b):
        for w in (self.btn_fast, self.btn_revert, self.btn_quick):
            w.setEnabled(not b)
        if not b:
            self.btn_revert.setEnabled(self.ctl.manager.has_backup())

    def _parse_quick(self) -> list[str] | None:
        parts = [p for p in self.quick.text().replace(",", " ").split() if p]
        if parts and all(storage.is_ipv4(p) or storage.is_ipv6(p) for p in parts):
            return parts
        self.ctl.toast.emit(t("msg.bad_addr"))
        return None

    def _quick_apply(self):
        addrs = self._parse_quick()
        if addrs:
            self.ctl.apply_addresses(addrs)

    def _quick_save(self):
        addrs = self._parse_quick()
        if addrs:
            v4 = [a for a in addrs if storage.is_ipv4(a)]
            v6 = [a for a in addrs if storage.is_ipv6(a)]
            self.ctl.custom.add("", v4, v6, "", "")
            self.ctl.toast.emit(t("msg.saved"))


# =============================================================== DNS LİSTESİ
class ListPage(QWidget):
    FILTERS = [("all", "filter.all"), ("fast", "filter.fast"), ("privacy", "filter.privacy"),
               ("adblock", "filter.adblock"), ("family", "filter.family"), ("security", "filter.security"),
               ("mine", "filter.mine")]

    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        self.flt = "all"
        self.sel: dict | None = None
        self.rows: list[dict] = []
        lay = _page_layout(self, 16)

        head = hbox(spacing=10)
        head.addWidget(label(t("list.title"), "h1"))
        head.addStretch(1)
        self.btn_import = button(t("list.import"))
        self.btn_export = button(t("list.export"))
        self.btn_add = button(t("list.add"), "primary", "plus")
        for b in (self.btn_import, self.btn_export, self.btn_add):
            head.addWidget(b)
        lay.addLayout(head)

        self.search = QLineEdit()
        self.search.setPlaceholderText(t("list.search"))
        self.search.addAction(svg_icon("search", theme.P["mu"], 16), QLineEdit.LeadingPosition)
        lay.addWidget(self.search)

        chips = hbox(spacing=8)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for key, tk in self.FILTERS:
            b = button(t(tk), "chip")
            b.setCheckable(True)
            b.setChecked(key == "all")
            b.setProperty("key", key)
            self.group.addButton(b)
            chips.addWidget(b)
        chips.addStretch(1)
        lay.addLayout(chips)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["", t("col.name"), t("col.proto"), t("col.addr"),
                                              t("col.latency"), t("col.score")])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.Fixed)
        hh.setSectionResizeMode(5, QHeaderView.Fixed)
        for col, w in ((0, 48), (2, 130), (4, 96), (5, 64)):
            self.table.setColumnWidth(col, w)
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(52)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        lay.addWidget(self.table, 1)

        self.sel_name = label(t("list.nosel"), "strong")
        self.sel_addr = label("", "small")
        info = vbox(spacing=2)
        info.addWidget(self.sel_name)
        info.addWidget(self.sel_addr)
        self.btn_del = button(t("list.delete"), "ghost")
        self.btn_test = button(t("list.test"))
        self.btn_apply = button(t("list.apply"), "primary")
        bar = hbox((16, 12, 16, 12), 10)
        bar.addLayout(info, 1)
        bar.addWidget(self.btn_del)
        bar.addWidget(self.btn_test)
        bar.addWidget(self.btn_apply)
        lay.addWidget(card(bar))

        self.search.textChanged.connect(self.reload)
        self.group.buttonClicked.connect(self._chip)
        self.table.cellClicked.connect(self._cell)
        self.table.itemSelectionChanged.connect(self._select)
        self.btn_add.clicked.connect(self._add)
        self.btn_import.clicked.connect(self._import)
        self.btn_export.clicked.connect(self._export)
        self.btn_apply.clicked.connect(self._apply)
        self.btn_test.clicked.connect(self._test)
        self.btn_del.clicked.connect(self._delete)
        ctl.changed.connect(self.reload)
        ctl.test_result.connect(self._result)
        self.reload()

    # ---- içerik
    def _visible(self) -> list[dict]:
        q = self.search.text().strip().lower()
        favs = set(self.ctl.settings.get("favorites"))
        out = []
        for i, p in enumerate(self.ctl.providers()):
            if self.flt != "all" and self.flt not in p.get("tags", []):
                continue
            hay = " ".join([p["name"], *p.get("v4", []), *p.get("v6", []), *p.get("tags", [])]).lower()
            if q and q not in hay:
                continue
            r = self.ctl.results.get(p["id"])
            out.append((p["id"] not in favs, -(r.score if r else -1), i, p))
        out.sort(key=lambda x: x[:3])
        return [x[3] for x in out]

    def reload(self, *_):
        keep = self.sel["id"] if self.sel else None
        favs = set(self.ctl.settings.get("favorites"))
        cur = self.ctl.current_info()
        cur_id = cur["provider"]["id"] if cur["provider"] else None
        self.rows = self._visible()
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.rows))
        for r, p in enumerate(self.rows):
            fav = p["id"] in favs
            star = QTableWidgetItem("★" if fav else "☆")
            star.setTextAlignment(Qt.AlignCenter)
            star.setForeground(QColor(theme.P["wn"] if fav else theme.P["mu"]))
            self.table.setItem(r, 0, star)

            nm = label(p["name"], "strong")
            tag_keys = {"fast": "filter.fast", "privacy": "filter.privacy", "adblock": "filter.adblock",
                        "family": "filter.family", "security": "filter.security", "mine": "filter.mine"}
            sub = label(" · ".join(t(tag_keys[x]) for x in p.get("tags", []) if x in tag_keys), "small")
            top = hbox(spacing=8)
            top.addWidget(nm)
            if p["id"] == cur_id:
                top.addWidget(label(t("list.inuse"), "tag_ok"))
            top.addStretch(1)
            col = vbox((6, 0, 0, 0), 1)
            col.addLayout(top)
            col.addWidget(sub)
            w = QWidget()
            w.setLayout(col)
            self.table.setCellWidget(r, 1, w)
            self.table.setItem(r, 2, QTableWidgetItem(_proto_text(p)))
            self.table.setItem(r, 3, QTableWidgetItem(_addr_text(p)))
            res = self.ctl.results.get(p["id"])
            lat = QTableWidgetItem(f"{res.median:.0f} {t('common.ms')}" if res and res.median is not None else "–")
            lat.setForeground(QColor(theme.P[_ms_color(res.median)] if res and res.median is not None
                                     else theme.P["mu"]))
            self.table.setItem(r, 4, lat)
            sc = QTableWidgetItem(str(res.score) if res else "–")
            f = sc.font()
            f.setBold(True)
            sc.setFont(f)
            self.table.setItem(r, 5, sc)
        self.table.blockSignals(False)
        if keep:
            for r, p in enumerate(self.rows):
                if p["id"] == keep:
                    self.table.selectRow(r)
                    break
            else:
                self.sel = None
        self._refresh_bar()

    def _result(self, res):
        self.reload()

    def _chip(self, b):
        self.flt = b.property("key")
        self.reload()

    def _cell(self, row, col):
        if col == 0 and 0 <= row < len(self.rows):
            self.ctl.settings.toggle_favorite(self.rows[row]["id"])
            self.reload()

    def _select(self):
        rows = {i.row() for i in self.table.selectedItems()}
        self.sel = self.rows[min(rows)] if rows and min(rows) < len(self.rows) else None
        self._refresh_bar()

    def _refresh_bar(self):
        p = self.sel
        has = p is not None
        self.sel_name.setText(t("list.selected", name=p["name"]) if has else t("list.nosel"))
        self.sel_addr.setText(f"{_addr_text(p)}  ·  {_proto_text(p)}" if has else "")
        self.btn_apply.setEnabled(has)
        self.btn_test.setEnabled(has)
        self.btn_del.setVisible(bool(has and not p.get("builtin", True)))

    # ---- işlemler
    def _apply(self):
        if self.sel:
            self.ctl.apply(self.sel)

    def _test(self):
        if self.sel and not self.ctl.testing:
            proto = "doh" if self.sel.get("doh") else "plain"
            self.ctl.start_test(proto, providers=[self.sel], quiet=True)

    def _delete(self):
        if self.sel and not self.sel.get("builtin", True):
            self.ctl.custom.remove(self.sel["id"])
            self.sel = None
            self.ctl.toast.emit(t("msg.deleted"))
            self.reload()

    def _add(self):
        dlg = CustomDnsDialog(self, self.ctl)
        if dlg.exec() and dlg.created:
            self.group.buttons()[-1].click()  # "Benim listem"
            self.reload()
            self.ctl.toast.emit(t("msg.saved"))

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, t("list.import"), "", "DNS (*.json *.txt)")
        if not path:
            return
        p = Path(path)
        n = self.ctl.custom.import_json(p) if p.suffix.lower() == ".json" else \
            self.ctl.custom.import_text(p.read_text(encoding="utf-8", errors="ignore"))
        self.ctl.toast.emit(t("msg.imported", n=n))
        self.reload()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, t("list.export"), "dns-hub-list.json", "JSON (*.json)")
        if path:
            self.ctl.custom.export_json(Path(path))


# =============================================================== HIZ TESTİ
ROW_H = 48


class RaceRow(QWidget):
    """Hız testindeki tek satır. Test boyunca yok olmaz; yalnızca içeriği ve konumu değişir."""

    def __init__(self, name: str):
        super().__init__()
        self.setFixedHeight(ROW_H)
        self._flash = 0.0
        self._flash_anim: QVariantAnimation | None = None
        self._move_anim: QPropertyAnimation | None = None
        lay = hbox((20, 0, 20, 0), 16)
        self.setLayout(lay)
        self.rank = label("", "muted")
        self.rank.setFixedWidth(28)
        lay.addWidget(self.rank)
        self.name = label(name, "strong")
        self.tag = label(t("test.tag_best"), "tag_ok")
        self.tag.hide()
        title = hbox(spacing=10)
        title.addWidget(self.name)
        title.addWidget(self.tag)
        title.addStretch(1)
        self.sub = label("", "small")
        col = vbox(spacing=1)
        col.addLayout(title)
        col.addWidget(self.sub)
        lay.addLayout(col, 14)
        self.bar = Bar()
        lay.addWidget(self.bar, 20)
        self.ms = label("", "muted")
        self.ms.setFixedWidth(88)
        self.ms.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(self.ms)

    def set_state(self, rank: str, r, best: bool, animate: bool) -> None:
        self.rank.setText(rank)
        self.tag.setVisible(best)
        if r is None:
            self.sub.setText(t("test.running") + "…")
            self.bar.set_value(0.4, "mu")
            ms, cls = "…", "muted"
        elif not r.supported and r.error == "unsupported":
            self.sub.setText(t("test.no_enc"))
            self.bar.set_value(0, "mu")
            ms, cls = t("test.nores"), "err"
        else:
            proto = {"plain": t("test.plain"), "doh": "DoH", "dot": "DoT"}[r.proto]
            txt = f"{proto} · {r.success_pct}%"
            if r.hijack:
                txt += " · " + t("test.hijack")
            self.sub.setText(txt)
            if r.ok:
                frac, color = min(r.median / 60, 1.0), _ms_color(r.median)
                if animate:
                    self.bar.animate_to(frac, color)
                else:
                    self.bar.set_value(frac, color)
                ms, cls = f"{r.median:.0f} {t('common.ms')}", "strong"
            else:
                self.bar.set_value(0, "mu")
                ms, cls = t("test.nores"), "err"
        self.ms.setText(ms)
        if self.ms.property("cls") != cls:
            self.ms.setProperty("cls", cls)
            restyle(self.ms)

    def slide_to(self, y: int, animate: bool) -> None:
        if self._move_anim is not None:
            self._move_anim.stop()
        if not animate or not self.isVisible() or self.y() == y:
            self.move(self.x(), y)
            return
        a = QPropertyAnimation(self, b"pos", self)
        a.setDuration(420)
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.setStartValue(self.pos())
        a.setEndValue(QPoint(self.x(), y))
        self._move_anim = a
        a.start()

    def flash(self) -> None:
        if self._flash_anim is None:
            self._flash_anim = QVariantAnimation(self)
            self._flash_anim.setDuration(900)
            self._flash_anim.setStartValue(1.0)
            self._flash_anim.setEndValue(0.0)
            self._flash_anim.valueChanged.connect(self._on_flash)
        self._flash_anim.stop()
        self._flash_anim.start()

    def _on_flash(self, v) -> None:
        self._flash = float(v)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        if self._flash > 0.01:
            c = QColor(theme.P["acs"])
            c.setAlphaF(min(1.0, self._flash))
            p.fillRect(self.rect(), c)
        p.setPen(QColor(theme.P["bd"]))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)
        p.end()


class RaceList(QWidget):
    """Satırları elle konumlandırır; sıra değişince satırlar yukarı/aşağı kayar."""

    def __init__(self):
        super().__init__()
        self.setObjectName("scrollInner")
        self.rows: dict[str, RaceRow] = {}
        self.order: list[str] = []

    def clear(self) -> None:
        for w in self.rows.values():
            w.hide()
            w.setParent(None)
            w.deleteLater()
        self.rows, self.order = {}, []
        self.setMinimumHeight(0)

    def add(self, pid: str, name: str) -> RaceRow:
        row = RaceRow(name)
        row.setParent(self)
        row.setFixedWidth(max(self.width(), 100))
        y = len(self.order) * ROW_H
        row.move(0, y)
        row.show()
        self.rows[pid] = row
        self.order.append(pid)
        self.setMinimumHeight(len(self.order) * ROW_H)
        return row

    def reorder(self, new_order: list[str], animate: bool = True) -> None:
        self.order = list(new_order)
        for i, pid in enumerate(self.order):
            self.rows[pid].slide_to(i * ROW_H, animate)

    def resizeEvent(self, e):
        for w in self.rows.values():
            w.setFixedWidth(max(self.width(), 100))
        super().resizeEvent(e)


class TestPage(QWidget):
    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        self.proto = "doh"
        self.entries: dict[str, object] = {}     # sağlayıcı kimliği -> Result | None
        self.best = None
        self.ran = False
        lay = _page_layout(self, 16)

        head = hbox()
        head.addWidget(label(t("test.title"), "h1"))
        head.addStretch(1)
        self.btn_go = button(t("test.start"), "primary", "refresh")
        head.addWidget(self.btn_go)
        lay.addLayout(head)

        seg = QWidget()
        seg.setObjectName("seg")
        sl = hbox((4, 4, 4, 4), 4)
        seg.setLayout(sl)
        self.group = QButtonGroup(self)
        for key, tk in (("plain", "test.plain"), ("doh", "test.doh"), ("dot", "test.dot")):
            b = button(t(tk), "seg")
            b.setCheckable(True)
            b.setChecked(key == self.proto)
            b.setProperty("key", key)
            self.group.addButton(b)
            sl.addWidget(b)
        self.prog_label = label("", "muted")
        self.prog = QProgressBar()
        self.prog.setFixedWidth(180)
        self.prog.setTextVisible(False)
        row = hbox(spacing=24)
        row.addWidget(seg)
        row.addStretch(1)
        row.addWidget(self.prog_label)
        row.addWidget(self.prog)
        lay.addLayout(row)

        box = vbox()
        hdr = hbox((20, 8, 20, 8), 16)
        hdr.addWidget(label("#", "small"), 0)
        hdr.addWidget(label(t("col.name"), "small"), 14)
        hdr.addWidget(label(t("test.col_ms"), "small"), 20)
        hdr.addWidget(label("", "small"), 0)
        box.addLayout(hdr)
        box.addWidget(sep())
        self.empty = label(t("test.empty"), "muted", wrap=True)
        self.empty.setContentsMargins(20, 24, 20, 24)
        box.addWidget(self.empty)
        self.race = RaceList()
        scroll = QScrollArea()
        scroll.setObjectName("scrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self.race)
        self.scroll = scroll
        box.addWidget(scroll, 1)
        scroll.hide()
        lay.addWidget(card(box), 1)

        self.best_title = label(t("test.best"), "muted")
        self.best_line = label("", "sec")
        self.btn_apply = button(t("test.apply"), "primary", "check")
        binfo = vbox(spacing=2)
        binfo.addWidget(self.best_title)
        binfo.addWidget(self.best_line)
        brow = hbox((20, 16, 20, 16), 16)
        brow.addLayout(binfo, 1)
        brow.addWidget(self.btn_apply)
        self.best_card = card(brow, "cardacc")
        self.best_card.hide()
        lay.addWidget(self.best_card)

        self.group.buttonClicked.connect(self._proto)
        self.btn_go.clicked.connect(self._toggle)
        self.btn_apply.clicked.connect(self._apply_best)
        ctl.test_state.connect(self._state)
        ctl.test_progress.connect(self._progress)
        ctl.test_result.connect(self._result)
        ctl.test_finished.connect(self._finished)
        self._sync(animate=False)

    # ---- akış
    def _scope(self) -> list[dict]:
        key = {"plain": None, "doh": "doh", "dot": "dot"}[self.proto]
        return [p for p in self.ctl.providers() if key is None or p.get(key)]

    def _proto(self, b):
        if self.ctl.testing:
            return
        self.proto = b.property("key")
        self.entries, self.best, self.ran = {}, None, False
        self.best_card.hide()
        self.prog.setValue(0)
        self.prog_label.setText("")
        self.btn_go.setText(t("test.start"))
        self._sync(animate=False)

    def _toggle(self):
        if self.ctl.testing:
            self.ctl.stop_test()
        else:
            self.ctl.start_test(self.proto)

    def _state(self, running):
        if self.ctl.quiet:
            return
        if running:
            self.proto = self.ctl.last_proto
            for b in self.group.buttons():
                b.setChecked(b.property("key") == self.proto)
            self.entries = {p["id"]: None for p in self._scope()}
            self.best, self.ran = None, True
            self.best_card.hide()
            self.btn_go.setText(t("test.stop"))
        else:
            self.btn_go.setText(t("test.retest"))
        for b in self.group.buttons():
            b.setEnabled(not running)
        self._sync(animate=False)

    def _progress(self, done, total):
        if self.ctl.quiet:
            return
        self.prog.setMaximum(max(total, 1))
        self.prog.setValue(done)
        self.prog_label.setText(t("test.progress", done=done, total=total))

    def _result(self, r):
        if self.ctl.quiet:
            return
        self.entries[r.provider_id] = r
        self._sync(animate=True, arrived=r.provider_id)

    def _finished(self, results):
        if self.ctl.quiet:
            return
        # iptal edilince hiç çalışmayan sunucular silinmesin, "test edilmedi" olarak altta kalsın
        ok = [r for r in results if r.ok]
        self.best = ok[0] if ok else None
        if self.best:
            self.best_line.setText(t("test.best_line", name=self.best.name, ms=f"{self.best.median:.0f}",
                                     ok=self.best.success_pct))
            self.best_card.show()
        self._sync(animate=True)

    def _apply_best(self):
        if self.best:
            p = self.ctl.provider(self.best.provider_id)
            if p:
                self.ctl.apply(p, encrypted=(self.proto == "doh"))

    # ---- çizim
    @staticmethod
    def _key(item):
        idx, (pid, r) = item
        if r is None:
            return (2, 0, 0, idx)
        if not r.ok:
            return (1, 0, 0, idx)
        return (0, -r.score, r.median if r.median is not None else 1e9, idx)

    def _sync(self, animate: bool, arrived: str | None = None):
        if not self.entries:
            self.race.clear()
            self.scroll.hide()
            self.empty.show()
            return
        self.empty.hide()
        self.scroll.show()
        provs = {p["id"]: p for p in self._scope()}
        if set(self.race.rows) != set(self.entries):
            self.race.clear()
            for pid in self.entries:
                p = provs.get(pid)
                self.race.add(pid, p["name"] if p else pid)
        ranked = sorted(enumerate(self.entries.items()), key=self._key)
        order = [pid for _, (pid, _r) in ranked]
        rank = 0
        for _, (pid, r) in ranked:
            row = self.race.rows[pid]
            if r is not None and r.ok:
                rank += 1
                row.set_state(str(rank), r, best=(rank == 1 and not self.ctl.testing), animate=animate)
            elif r is None:
                row.set_state("", None, False, animate)
                if not self.ctl.testing and self.ran:
                    row.sub.setText(t("test.skipped"))
                    row.ms.setText("–")
            else:
                row.set_state("–", r, False, animate)
        self.race.reorder(order, animate)
        if arrived and arrived in self.race.rows:
            self.race.rows[arrived].flash()


# =============================================================== AYARLAR
class ThemePreview(QPushButton):
    def __init__(self, kind: str):
        super().__init__()
        self.kind = kind
        self.setCheckable(True)
        self.setProperty("cls", "theme")
        self.setFixedHeight(68)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        light, dark = PALETTES_PREVIEW["light"], PALETTES_PREVIEW["dark"]
        p.setPen(Qt.NoPen)
        if self.kind == "system":
            p.setBrush(QColor(light[0]))
            p.drawRoundedRect(r, 5, 5)
            half = QRectF(r.center().x(), r.top(), r.width() / 2, r.height())
            p.setClipRect(half)
            p.setBrush(QColor(dark[0]))
            p.drawRoundedRect(r, 5, 5)
            p.setClipping(False)
        else:
            c = light if self.kind == "light" else dark
            p.setBrush(QColor(c[0]))
            p.drawRoundedRect(r, 5, 5)
        accent = dark[1] if self.kind == "dark" else light[1]
        p.setBrush(QColor(accent))
        p.drawRoundedRect(QRectF(r.center().x() - 18, r.center().y() - 4, 36, 8), 4, 4)


PALETTES_PREVIEW = {"light": ("#F3F3F3", "#0F6CBD"), "dark": ("#202020", "#60CDFF")}


class SettingsPage(QWidget):
    theme_changed = Signal()
    language_changed = Signal()

    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        lay = _page_layout(self, 16)
        lay.addWidget(label(t("settings.title"), "h1"))

        cols = hbox(spacing=16)
        cols.setAlignment(Qt.AlignTop)

        # ---- görünüm
        v = vbox((20, 20, 20, 12), 12)
        v.addWidget(label(t("settings.appearance"), "sec"))
        v.addWidget(label(t("settings.theme"), "muted"))
        tg = hbox(spacing=10)
        self.theme_group = QButtonGroup(self)
        cur = ctl.settings.get("theme")
        for key, tk in (("system", "theme.system"), ("light", "theme.light"), ("dark", "theme.dark")):
            b = ThemePreview(key)
            b.setChecked(key == cur)
            b.setProperty("key", key)
            self.theme_group.addButton(b)
            c = vbox(spacing=8)
            c.addWidget(b)
            lb = label(t(tk), "strong")
            lb.setAlignment(Qt.AlignHCenter)
            c.addWidget(lb)
            tg.addLayout(c, 1)
        v.addLayout(tg)
        v.addSpacing(6)
        v.addWidget(label(t("settings.language"), "muted"))
        self.lang_group = QButtonGroup(self)
        cur_lang = ctl.settings.get("language")
        cur_lang = i18n.current() if cur_lang == "auto" else cur_lang
        for code, name in i18n.LANGS.items():
            rb = QRadioButton(f"{name}")
            rb.setChecked(code == cur_lang)
            rb.setProperty("key", code)
            rb.setCursor(Qt.PointingHandCursor)
            self.lang_group.addButton(rb)
            v.addWidget(rb)
        v.addStretch(1)
        left = card(v)
        cols.addWidget(left, 1)

        # ---- davranış
        v2 = vbox((20, 20, 20, 8), 0)
        v2.addWidget(label(t("settings.behavior"), "sec"))
        v2.addSpacing(8)
        defs = [("autostart", "tg.autostart", "tg.autostart_d"),
                ("apply_fastest_on_boot", "tg.boot_apply", "tg.boot_apply_d"),
                ("safety_timer", "tg.safety", "tg.safety_d"),
                ("fallback_chain", "tg.chain", "tg.chain_d"),
                ("tray", "tg.tray", "tg.tray_d")]
        self.switches: dict[str, Switch] = {}
        for key, tk, dk in defs:
            v2.addWidget(sep())
            row = hbox((0, 14, 0, 14), 16)
            col = vbox(spacing=2)
            col.addWidget(label(t(tk), "strong"))
            col.addWidget(label(t(dk), "small", wrap=True))
            sw = Switch(bool(ctl.settings.get(key)))
            sw.setProperty("key", key)
            sw.toggled.connect(lambda on, k=key: self._toggle(k, on))
            self.switches[key] = sw
            row.addLayout(col, 1)
            row.addWidget(sw)
            v2.addLayout(row)
        right = card(v2)
        cols.addWidget(right, 1)
        lay.addLayout(cols)
        lay.addStretch(1)

        self.theme_group.buttonClicked.connect(self._theme)
        self.lang_group.buttonClicked.connect(self._lang)

    def _theme(self, b):
        self.ctl.settings.set("theme", b.property("key"))
        self.theme_changed.emit()

    def _lang(self, b):
        self.ctl.set_language(b.property("key"))
        self.language_changed.emit()

    def _toggle(self, key, on):
        if key == "autostart":
            self.ctl.set_autostart(on)
        else:
            self.ctl.settings.set(key, on)


# =============================================================== YAKINDA
class SoonPage(QWidget):
    def __init__(self, ctl, kind: str):
        super().__init__()
        lay = _page_layout(self)
        lay.addWidget(label(t("nav.block") if kind == "block" else t("nav.proxy"), "h1"))
        v = vbox((32, 28, 32, 28), 10)
        ic = label()
        ic.setPixmap(svg_icon("shield" if kind == "block" else "proxy", theme.P["ac"], 32, 1.6).pixmap(32, 32))
        v.addWidget(ic)
        v.addWidget(label(t("soon.title"), "sec"))
        v.addWidget(label(t("soon.block" if kind == "block" else "soon.proxy"), "muted", wrap=True))
        lay.addWidget(card(v))
        lay.addStretch(1)


# =============================================================== HAKKINDA
def system_info() -> str:
    """Hata bildirirken yapıştırılabilecek, dilden bağımsız sistem özeti."""
    import dns.version
    import httpx
    from PySide6 import __version__ as pyside_version
    mode = "dry-run (not Windows)" if not winnet.is_windows() else "Windows"
    return "\n".join([
        f"DNS Hub {__version__}",
        f"OS: {platform.platform()}",
        f"Python: {platform.python_version()}",
        f"PySide6: {pyside_version}",
        f"dnspython: {dns.version.version}",
        f"httpx: {httpx.__version__}",
        f"Mode: {mode}",
        f"Administrator: {'yes' if winnet.is_admin() else 'no'}",
        f"Language: {i18n.current()}",
    ])


class AboutPage(QWidget):
    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        self.setObjectName("page")
        outer = vbox((16, 12, 32, 12), 0)
        self.setLayout(outer)
        outer.addWidget(label(t("about.title"), "h1"))
        outer.addSpacing(12)

        inner = QWidget()
        inner.setObjectName("scrollInner")
        lay = vbox((0, 0, 8, 16), 16)
        inner.setLayout(lay)
        scroll = QScrollArea()
        scroll.setObjectName("scrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # ---- üst kart: simge, ad, sürüm, açıklama, düğmeler
        icon = QLabel()
        icon.setPixmap(app_pixmap(176).scaled(88, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon.setFixedSize(88, 88)
        title = hbox(spacing=10)
        title.addWidget(label(t("app.name"), "big"))
        ver = label(t("about.version", v=__version__), "pill")
        title.addWidget(ver, 0, Qt.AlignBottom)
        title.addStretch(1)
        info = vbox(spacing=6)
        info.addLayout(title)
        info.addWidget(label(t("about.tagline"), "strong"))
        info.addWidget(label(t("about.desc"), "muted", wrap=True))
        info.addWidget(label(t("about.developer", name=AUTHOR), "strong"))
        btns = hbox(spacing=10)
        self.btn_web = button(t("about.website"), "primary", "globe")
        self.btn_copy = button(t("about.copy"), "", "copy")
        self.btn_data = button(t("about.open_data"), "", "folder")
        for b in (self.btn_web, self.btn_copy, self.btn_data):
            btns.addWidget(b)
        btns.addStretch(1)
        info.addSpacing(6)
        info.addLayout(btns)
        top = hbox((28, 24, 28, 24), 24)
        top.addWidget(icon, 0, Qt.AlignTop)
        top.addLayout(info, 1)
        lay.addWidget(card(top))

        # ---- iki sütun
        def block(title_key: str, body: str, mono: bool = False) -> QFrame:
            v = vbox((22, 18, 22, 18), 8)
            v.addWidget(label(t(title_key), "sec"))
            body_lb = label(body, "muted", wrap=True)
            if mono:
                body_lb.setTextInteractionFlags(Qt.TextSelectableByMouse)
                body_lb.setStyleSheet("font-family: Consolas, 'Cascadia Mono', monospace; font-size: 12px;")
            v.addWidget(body_lb)
            v.addStretch(1)
            return card(v)

        n = len(storage.builtin_providers())
        left = vbox(spacing=16)
        left.addWidget(block("about.features_t", t("about.features_b", n=n)))
        left.addWidget(block("about.privacy_t", t("about.privacy_b")))
        right = vbox(spacing=16)
        right.addWidget(block("about.license_t", t("about.license_b")))
        self._sys_text = system_info()
        right.addWidget(block("about.sys_t", self._sys_text, mono=True))
        cols = hbox(spacing=16)
        cols.addLayout(left, 1)
        cols.addLayout(right, 1)
        lay.addLayout(cols)

        # ---- alt bilgi
        foot = vbox((4, 4, 4, 4), 4)
        foot.addWidget(label(f"{t('about.credits_t')}: {t('about.credits_b')}", "small", wrap=True))
        foot.addWidget(label(t("about.disclaimer"), "small", wrap=True))
        lay.addLayout(foot)
        lay.addStretch(1)

        self.btn_web.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(WEBSITE)))
        self.btn_copy.clicked.connect(self._copy)
        self.btn_data.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(storage.data_dir()))))

    def _copy(self):
        QApplication.clipboard().setText(self._sys_text)
        self.ctl.toast.emit(t("about.copied"))
