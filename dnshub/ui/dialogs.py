"""Özel DNS ekleme penceresi."""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QDialog, QLineEdit, QMessageBox

from .. import benchmark, storage
from ..i18n import t
from . import theme
from .titlebar import apply_titlebar
from .widgets import Switch, button, card, hbox, label, restyle, svg_icon, vbox


class _Bridge(QObject):
    done = Signal(object)


class CustomDnsDialog(QDialog):
    def __init__(self, parent, controller, prefill: str = ""):
        super().__init__(parent)
        self.ctl = controller
        self.created: dict | None = None
        self._probe: dict | None = None
        self._bridge = _Bridge()
        self._bridge.done.connect(self._probe_done)
        self.setModal(True)
        self.setMinimumWidth(640)

        root = vbox((28, 24, 28, 24), 14)
        self.setLayout(root)
        self.title = label("", "h2")
        self.sub = label("", "muted", wrap=True)
        head = vbox(spacing=4)
        head.addWidget(self.title)
        head.addWidget(self.sub)
        root.addLayout(head)

        self.name = QLineEdit()
        self.v4a = QLineEdit(prefill)
        self.v4b = QLineEdit()
        self.v6 = QLineEdit()
        self.doh = QLineEdit()
        self.dot = QLineEdit()
        self.doh.setPlaceholderText("https://dns.example.com/dns-query")
        self.dot.setPlaceholderText("dns.example.com")
        self.v4a.setPlaceholderText("203.0.113.5")
        self.v4b.setPlaceholderText("8.8.4.4")
        self.v6.setPlaceholderText("2001:4860:4860::8888")
        self.err_a, self.err_b, self.err_6, self.err_doh = (label("", "err") for _ in range(4))
        for e in (self.err_a, self.err_b, self.err_6, self.err_doh):
            e.hide()

        self.l_name, self.l_v4a, self.l_v4b, self.l_v6, self.l_doh, self.l_dot = (label("", "strong") for _ in range(6))
        root.addLayout(self._field(self.l_name, self.name))
        row = hbox(spacing=16)
        row.addLayout(self._field(self.l_v4a, self.v4a, self.err_a))
        row.addLayout(self._field(self.l_v4b, self.v4b, self.err_b))
        root.addLayout(row)
        root.addLayout(self._field(self.l_v6, self.v6, self.err_6))

        self.enc_title = label("", "sec")
        self.enc_sub = label("", "muted", wrap=True)
        enc = vbox(spacing=2)
        enc.addWidget(self.enc_title)
        enc.addWidget(self.enc_sub)
        root.addLayout(enc)
        row2 = hbox(spacing=16)
        a = self._field(self.l_doh, self.doh, self.err_doh)
        b = self._field(self.l_dot, self.dot)
        row2.addLayout(a, 3)
        row2.addLayout(b, 2)
        root.addLayout(row2)

        self.result_card = card(vbox((16, 14, 16, 14), 10))
        self.result_title = label("", "strong")
        self.result_card.layout().addWidget(self.result_title)
        self.lines: dict[str, tuple] = {}
        for proto in benchmark.PROTOCOLS:
            ic, name, val = label(""), label(""), label("", "strong")
            line = hbox(spacing=10)
            line.addWidget(ic)
            line.addWidget(name, 1)
            line.addWidget(val)
            self.result_card.layout().addLayout(line)
            self.lines[proto] = (ic, name, val)
        self.result_card.hide()
        root.addWidget(self.result_card)

        self.fav = Switch(True)
        self.fav_label = label("")
        favrow = hbox(spacing=12)
        favrow.addWidget(self.fav)
        favrow.addWidget(self.fav_label, 1)
        root.addLayout(favrow)

        foot = hbox(spacing=10)
        self.btn_test = button("", "outline", "bolt", theme.P["ac"])
        self.btn_cancel = button("")
        self.btn_save = button("", "primary")
        foot.addWidget(self.btn_test)
        foot.addStretch(1)
        foot.addWidget(self.btn_cancel)
        foot.addWidget(self.btn_save)
        root.addLayout(foot)

        for e in (self.v4a, self.v4b, self.v6, self.doh):
            e.textChanged.connect(self._validate)
        self.btn_test.clicked.connect(self._run_probe)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self._save)
        self.retranslate()
        self._validate()

    def showEvent(self, ev):
        super().showEvent(ev)
        apply_titlebar(self)

    @staticmethod
    def _field(lbl, edit, err=None):
        lay = vbox(spacing=6)
        lay.addWidget(lbl)
        lay.addWidget(edit)
        if err is not None:
            lay.addWidget(err)
        return lay

    def retranslate(self):
        self.setWindowTitle(t("custom.title"))
        self.title.setText(t("custom.title"))
        self.sub.setText(t("custom.sub"))
        self.l_name.setText(t("custom.name"))
        self.name.setPlaceholderText(t("custom.name_ph"))
        self.l_v4a.setText(t("custom.v4a"))
        self.l_v4b.setText(t("custom.v4b"))
        self.l_v6.setText(t("custom.v6"))
        self.enc_title.setText(t("custom.enc"))
        self.enc_sub.setText(t("custom.enc_sub"))
        self.l_doh.setText(t("custom.doh"))
        self.l_dot.setText(t("custom.dot"))
        self.result_title.setText(t("custom.result"))
        self.fav_label.setText(t("custom.fav"))
        self.btn_test.setText(t("custom.test"))
        self.btn_cancel.setText(t("custom.cancel"))
        self.btn_save.setText(t("custom.save"))
        names = {"plain": t("custom.plain"), "doh": t("custom.doh_line"), "dot": t("custom.dot_line")}
        for proto, (_, nm, _) in self.lines.items():
            nm.setText(names[proto])

    # ------------------------------------------------------------ doğrulama
    @staticmethod
    def _mark(edit: QLineEdit, err, state: str, msg: str):
        edit.setProperty("state", state)
        restyle(edit)
        err.setText(msg)
        err.setVisible(bool(msg))

    def _validate(self) -> bool:
        ok = True
        a = self.v4a.text().strip()
        if not a:
            self._mark(self.v4a, self.err_a, "", "")
            ok = False
        elif storage.is_ipv4(a):
            self._mark(self.v4a, self.err_a, "ok", "")
        else:
            self._mark(self.v4a, self.err_a, "bad", t("custom.err_ip"))
            ok = False
        b = self.v4b.text().strip()
        if b and not storage.is_ipv4(b):
            self._mark(self.v4b, self.err_b, "bad", t("custom.err_ip"))
            ok = False
        else:
            self._mark(self.v4b, self.err_b, "ok" if b else "", "")
        v6 = self.v6.text().strip()
        if v6 and not storage.is_ipv6(v6):
            self._mark(self.v6, self.err_6, "bad", t("custom.err_ip6"))
            ok = False
        else:
            self._mark(self.v6, self.err_6, "ok" if v6 else "", "")
        d = self.doh.text().strip()
        if d and not storage.is_doh_url(d):
            self._mark(self.doh, self.err_doh, "bad", t("custom.err_doh"))
            ok = False
        else:
            self._mark(self.doh, self.err_doh, "ok" if d else "", "")
        self.btn_test.setEnabled(ok)
        self.btn_save.setEnabled(ok)
        return ok

    def _draft(self) -> dict:
        v4 = [x.strip() for x in (self.v4a.text(), self.v4b.text()) if x.strip()]
        v6 = [self.v6.text().strip()] if self.v6.text().strip() else []
        return {"id": "draft", "name": self.name.text().strip() or (v4 or v6 or ["?"])[0],
                "v4": v4, "v6": v6, "doh": self.doh.text().strip(), "dot": self.dot.text().strip(), "bootstrap": ""}

    # ------------------------------------------------------------ test
    def _run_probe(self):
        if not self._validate():
            return
        draft = self._draft()
        self.btn_test.setEnabled(False)
        self.result_card.show()
        for proto, (ic, _, val) in self.lines.items():
            ic.clear()
            val.setText(t("custom.testing"))
            val.setProperty("cls", "muted")
            restyle(val)

        def job():
            self._bridge.done.emit(benchmark.probe_provider(draft))

        threading.Thread(target=job, daemon=True).start()

    def _probe_done(self, res: dict):
        self._probe = res
        self.btn_test.setEnabled(self._validate())
        for proto, r in res.items():
            ic, _, val = self.lines[proto]
            if proto != "plain" and not r.supported and r.error == "unsupported":
                # alan boş bırakıldı: ikon yok
                ic.clear()
                val.setText("–")
                val.setProperty("cls", "muted")
            elif r.ok:
                ic.setPixmap(svg_icon("check", theme.P["ok"], 16, 2.4).pixmap(16, 16))
                val.setText(f"{r.median:.0f} {t('common.ms')}")
                val.setProperty("cls", "strong")
            else:
                ic.setPixmap(svg_icon("x", theme.P["wn"], 16, 2.4).pixmap(16, 16))
                val.setText(t("custom.noanswer"))
                val.setProperty("cls", "warn")
            restyle(val)
        # DoH/DoT alanı boşsa ve test yanıt verdiyse, ama sunucu DoH desteklemiyorsa bilgi amaçlı bırak

    def _save(self):
        if not self._validate():
            return
        if self._probe is not None and not any(r.ok for r in self._probe.values()):
            ans = QMessageBox.question(self, t("custom.title"), t("custom.save_anyway"),
                                       QMessageBox.Yes | QMessageBox.No)
            if ans != QMessageBox.Yes:
                return
        d = self._draft()
        item = self.ctl.custom.add(self.name.text(), d["v4"], d["v6"], d["doh"], d["dot"])
        if self.fav.isChecked() and item["id"] not in self.ctl.settings.get("favorites"):
            self.ctl.settings.toggle_favorite(item["id"])
        self.created = item
        self.accept()
