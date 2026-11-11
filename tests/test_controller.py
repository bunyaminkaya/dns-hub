"""Denetleyici akışı: iş parçacıkları + Qt sinyalleri + deneme modu DNS uygulama (ağ gerekmez)."""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["DNSHUB_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from dnshub import benchmark, i18n, storage, winnet
from dnshub.ui.controller import Controller

app = QApplication([])
i18n.set_language("en")

# ağ yok: sunuculara sahte, deterministik sonuç ver
FAKE = {"cloudflare": 11.0, "google": 14.0, "quad9": 19.0}


def fake_provider(p, proto, rounds=2, domains=None, check_hijack=True):
    if proto == "doh" and not p.get("doh"):
        return benchmark.Result(p["id"], p["name"], proto, supported=False, error="unsupported")
    ms = FAKE.get(p["id"])
    if ms is None:
        return benchmark.Result(p["id"], p["name"], proto, success=0, total=10, error="Timeout")
    time.sleep(0.05)
    return benchmark.Result(p["id"], p["name"], proto, median=ms, mean=ms, jitter=1.0, success=10, total=10,
                            score=benchmark.compute_score(ms, 1.0, 10, 10), hijack=False)


benchmark.benchmark_provider = fake_provider
winnet.check_connectivity = lambda **k: True


def wait(cond, sec=10):
    end = time.time() + sec
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_find_fastest_applies_winner():
    mgr = winnet.DnsManager(winnet.DryRunBackend())
    mgr.backend.set_dns(1, ["192.168.1.1"])
    ctl = Controller(mgr)
    got, finished, toasts, progress = [], [], [], []
    ctl.test_result.connect(got.append)
    ctl.test_finished.connect(finished.append)
    ctl.toast.connect(toasts.append)
    ctl.test_progress.connect(lambda d, t: progress.append((d, t)))
    ctl.find_fastest()
    assert wait(lambda: bool(finished)), "test bitmedi"
    res = finished[0]
    assert res[0].provider_id == "cloudflare" and res[0].ok          # en hızlı başa geldi
    assert len(got) == len([p for p in ctl.providers() if p.get("doh")])
    assert progress[-1][0] == progress[-1][1]                          # ilerleme tamamlandı
    assert wait(lambda: mgr.current(1)["v4"] == ["1.1.1.1", "1.0.0.1"]), mgr.current(1)
    assert wait(lambda: any("Cloudflare applied" in x for x in toasts)), toasts
    assert ctl.settings.get("last_applied") == {"id": "cloudflare", "encrypted": True}
    # önbellek: sonuçlar kaydedildi ve yeniden yüklenebilir
    assert ctl.results["cloudflare"].median == 11.0
    assert Controller(mgr).results["google"].score > 0
    info = ctl.current_info()
    assert info["name"] == "Cloudflare" and info["encrypted"] is True


def test_restore_after_apply():
    mgr = winnet.DnsManager(winnet.DryRunBackend())
    (Path(os.environ["DNSHUB_HOME"]) / "backup.json").unlink(missing_ok=True)
    mgr.backend.set_dns(1, ["10.1.1.1"])
    ctl = Controller(mgr)
    toasts = []
    ctl.toast.connect(toasts.append)
    ctl.apply(ctl.provider("google"), announce=False)
    assert wait(lambda: mgr.current(1)["v4"] == ["8.8.8.8", "8.8.4.4"])
    ctl.restore()
    assert wait(lambda: mgr.current(1)["v4"] == ["10.1.1.1"]), mgr.current(1)
    assert wait(lambda: any("restored" in x for x in toasts)), toasts


def test_quiet_single_test_and_custom_provider():
    mgr = winnet.DnsManager(winnet.DryRunBackend())
    ctl = Controller(mgr)
    ctl.custom.items.clear()
    item = ctl.custom.add("Mine", ["203.0.113.5"], [], "", "")
    done = []
    ctl.test_finished.connect(done.append)
    ctl.start_test("plain", providers=[ctl.provider(item["id"])], quiet=True)
    assert ctl.quiet is True
    assert wait(lambda: bool(done))
    assert len(done[0]) == 1 and not done[0][0].ok      # sahte ağda yanıt yok
    assert not ctl.testing


def test_apply_addresses_dry():
    mgr = winnet.DnsManager(winnet.DryRunBackend())
    ctl = Controller(mgr)
    ctl.apply_addresses(["9.9.9.9", "149.112.112.112"])
    assert wait(lambda: mgr.current(1)["v4"] == ["9.9.9.9", "149.112.112.112"])
    assert ctl.settings.get("last_applied") == {"id": "", "encrypted": False}


if __name__ == "__main__":
    import traceback
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print("ok  ", name)
            except Exception:  # noqa: BLE001
                failed += 1
                print("FAIL", name)
                traceback.print_exc()
    sys.exit(1 if failed else 0)
