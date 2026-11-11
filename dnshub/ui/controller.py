"""Arayüz ile çekirdek arasındaki köprü: arka plan işleri ve sinyaller."""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, Signal

from .. import benchmark, i18n, storage, winnet
from ..i18n import t


class Controller(QObject):
    toast = Signal(str)
    changed = Signal()                 # mevcut DNS değişti
    test_result = Signal(object)       # tek sunucu sonucu (Result)
    test_progress = Signal(int, int)   # biten, toplam
    test_finished = Signal(object)     # sıralı Result listesi
    test_state = Signal(bool)          # çalışıyor mu
    busy = Signal(bool)                # uygulama işlemi sürüyor mu
    latency = Signal(object)           # (ms | None) mevcut DNS gecikmesi

    def __init__(self, manager: winnet.DnsManager | None = None):
        super().__init__()
        self.settings = storage.Settings()
        self.custom = storage.CustomStore()
        self.manager = manager or winnet.DnsManager()
        self._adapters: list[dict] = []
        self._cancel = threading.Event()
        self._testing = False
        self._apply_after = False
        self.last_proto = "doh"
        self.quiet = False        # True: test sayfası bu çalıştırmayı göstermesin (listedeki tek sunucu testi)
        self.results: dict[str, benchmark.Result] = {}   # son test (sağlayıcı kimliği -> sonuç)
        self._load_cached_results()

    # ------------------------------------------------------------ veri
    def providers(self) -> list[dict]:
        return storage.all_providers(self.custom)

    def provider(self, pid: str) -> dict | None:
        return next((p for p in self.providers() if p["id"] == pid), None)

    def _load_cached_results(self) -> None:
        data = storage.load_last_test()
        for pid, d in (data.get("results") or {}).items():
            r = benchmark.Result(pid, d.get("name", pid), d.get("proto", "plain"), median=d.get("median"),
                                 score=d.get("score", 0), success=d.get("success", 0), total=d.get("total", 0))
            self.results[pid] = r

    def last_test_info(self) -> dict:
        d = storage.load_last_test()
        return {"time": d.get("time"), "count": len(d.get("results") or {})}

    # ------------------------------------------------------------ bağdaştırıcı
    def adapters(self, refresh: bool = False) -> list[dict]:
        if refresh or not self._adapters:
            try:
                self._adapters = self.manager.adapters()
            except winnet.DnsError:
                self._adapters = []
        return self._adapters

    @property
    def adapter_index(self) -> int | None:
        ads = self.adapters()
        if not ads:
            return None
        want = self.settings.get("adapter")
        for a in ads:
            if a["Name"] == want:
                return a["InterfaceIndex"]
        return ads[0]["InterfaceIndex"]

    def adapter_name(self) -> str:
        idx = self.adapter_index
        for a in self.adapters():
            if a["InterfaceIndex"] == idx:
                return a["Name"]
        return ""

    def select_adapter(self, name: str) -> None:
        self.settings.set("adapter", name)
        self.changed.emit()

    # ------------------------------------------------------------ mevcut DNS
    def current_info(self) -> dict:
        """{'name', 'addrs', 'encrypted', 'provider', 'auto'}"""
        idx = self.adapter_index
        info = {"name": t("home.unknown"), "addrs": [], "encrypted": False, "provider": None, "auto": False}
        if idx is None:
            return info
        try:
            cur = self.manager.current(idx)
        except winnet.DnsError:
            return info
        v4 = cur.get("v4", [])
        info["addrs"] = v4 or cur.get("v6", [])
        if not info["addrs"]:
            info["name"], info["auto"] = t("home.dhcp"), True
            return info
        match = next((p for p in self.providers() if p.get("v4") and set(p["v4"]) == set(v4)), None)
        if match:
            last = self.settings.get("last_applied") or {}
            info.update(name=match["name"], provider=match,
                        encrypted=bool(last.get("id") == match["id"] and last.get("encrypted")))
        else:
            info["name"] = info["addrs"][0]
        return info

    def measure_current(self) -> None:
        """Mevcut DNS'in gecikmesini arka planda ölçer (latency sinyali)."""
        info = self.current_info()
        ip = info["addrs"][0] if info["addrs"] else None

        def job():
            if not ip:
                self.latency.emit(None)
                return
            r = benchmark.measure(benchmark.PlainTransport(ip), "cur", "cur", "plain", rounds=1,
                                  domains=benchmark.TEST_DOMAINS[:4], check_hijack=False)
            self.latency.emit(r.median if r.ok else None)

        threading.Thread(target=job, daemon=True).start()

    # ------------------------------------------------------------ uygula / geri al
    def _guard(self):
        if self.adapter_index is None:
            self.toast.emit(t("msg.no_adapter"))
            return None
        return self.adapter_index

    def apply(self, provider: dict, encrypted: bool | None = None, announce: bool = True) -> None:
        idx = self._guard()
        if idx is None:
            return
        enc = bool(provider.get("doh")) if encrypted is None else encrypted
        if self.manager.dry and announce:
            self.toast.emit(t("msg.dry"))
        safety = bool(self.settings.get("safety_timer")) and not self.manager.dry

        def job():
            self.busy.emit(True)
            try:
                if safety:
                    # önce uygula, sonra internet gelmezse geri al
                    active = self.manager.apply(idx, provider, encrypted=enc)
                    kept = self.manager._confirm_or_restore(idx, 15.0)
                    if not kept:
                        self.toast.emit(t("msg.auto_reverted"))
                        return
                else:
                    active = self.manager.apply(idx, provider, encrypted=enc)
                self.settings.set("last_applied", {"id": provider["id"], "encrypted": bool(active)})
                if announce:
                    self.toast.emit(t("msg.applied", name=provider["name"]))
            except winnet.NeedAdmin:
                self.toast.emit(t("msg.need_admin"))
            except winnet.DnsError as e:
                self.toast.emit(t("msg.fail", err=str(e)[:120]))
            finally:
                self.busy.emit(False)
                self.changed.emit()

        threading.Thread(target=job, daemon=True).start()

    def apply_addresses(self, addrs: list[str]) -> None:
        idx = self._guard()
        if idx is None:
            return

        def job():
            self.busy.emit(True)
            try:
                self.manager.apply_addresses(idx, addrs)
                self.settings.set("last_applied", {"id": "", "encrypted": False})
                self.toast.emit(t("msg.applied", name=addrs[0]))
            except winnet.NeedAdmin:
                self.toast.emit(t("msg.need_admin"))
            except winnet.DnsError as e:
                self.toast.emit(t("msg.fail", err=str(e)[:120]))
            finally:
                self.busy.emit(False)
                self.changed.emit()

        threading.Thread(target=job, daemon=True).start()

    def restore(self) -> None:
        idx = self._guard()
        if idx is None:
            return

        def job():
            self.busy.emit(True)
            try:
                if self.manager.restore(idx):
                    self.settings.set("last_applied", {"id": "", "encrypted": False})
                    self.toast.emit(t("msg.reverted"))
                else:
                    self.toast.emit(t("home.never"))
            except winnet.NeedAdmin:
                self.toast.emit(t("msg.need_admin"))
            except winnet.DnsError as e:
                self.toast.emit(t("msg.fail", err=str(e)[:120]))
            finally:
                self.busy.emit(False)
                self.changed.emit()

        threading.Thread(target=job, daemon=True).start()

    # ------------------------------------------------------------ test
    @property
    def testing(self) -> bool:
        return self._testing

    def start_test(self, proto: str, providers: list[dict] | None = None, apply_after: bool = False,
                   quiet: bool = False) -> None:
        if self._testing:
            return
        provs = providers if providers is not None else self.providers()
        if proto != "plain":
            key = "doh" if proto == "doh" else "dot"
            provs = [p for p in provs if p.get(key)]
        self._cancel = threading.Event()
        self._testing, self._apply_after, self.last_proto, self.quiet = True, apply_after, proto, quiet
        self.test_state.emit(True)
        total = len(provs)
        done = [0]
        lock = threading.Lock()

        def on_result(r):
            # sayacı artırma ve sinyal gönderme aynı kilit altında: sinyaller sıra dışı ulaşmasın
            with lock:
                done[0] += 1
                self.test_result.emit(r)
                self.test_progress.emit(done[0], total)

        def job():
            results = benchmark.run_benchmark(provs, proto, on_result=on_result, cancel=self._cancel)
            self._finish(proto, results, cancelled=self._cancel.is_set())

        self.test_progress.emit(0, total)
        threading.Thread(target=job, daemon=True).start()

    def stop_test(self) -> None:
        self._cancel.set()

    def _finish(self, proto: str, results: list, cancelled: bool) -> None:
        ok = [r for r in results if r.ok]
        if ok:
            for r in ok:
                self.results[r.provider_id] = r
            storage.save_last_test({
                "time": time.time(), "proto": proto,
                "results": {r.provider_id: {"name": r.name, "proto": r.proto, "median": r.median,
                                            "score": r.score, "success": r.success, "total": r.total}
                            for r in ok},
            })
        self._testing = False
        apply_after, self._apply_after = self._apply_after, False
        self.test_state.emit(False)
        self.test_finished.emit(results)
        if apply_after and not cancelled:
            if ok:
                best = ok[0]
                p = self.provider(best.provider_id)
                if p:
                    self.apply(p, encrypted=(proto == "doh"))
            elif proto == "doh":
                # şifreli DNS hiçbir yerde çalışmadı: düz DNS ile dene
                self.start_test("plain", apply_after=True)
            else:
                self.toast.emit(t("test.nores"))

    def find_fastest(self) -> None:
        """Ana sayfadaki büyük düğme: önce şifreli (DoH), olmazsa düz DNS."""
        self.start_test("doh", apply_after=True)

    # ------------------------------------------------------------ ayarlar
    def set_language(self, code: str) -> None:
        self.settings.set("language", code)
        i18n.set_language(code)

    def set_autostart(self, enabled: bool) -> None:
        self.settings.set("autostart", enabled)
        winnet.set_autostart(enabled)
