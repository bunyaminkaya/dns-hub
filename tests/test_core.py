"""Çekirdek testleri: yerel sahte DNS (UDP) ve sahte DoH (HTTP) sunucusuyla."""
import json
import os
import socketserver
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

os.environ["DNSHUB_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dns.flags
import dns.message
import dns.rrset

from dnshub import benchmark, i18n, storage, winnet


def make_reply(wire: bytes, hijack=False) -> bytes:
    q = dns.message.from_wire(wire)
    r = dns.message.make_response(q)
    name = str(q.question[0].name)
    exists = hijack or not name.split(".")[0].isalnum() or len(name.split(".")[0]) != 14
    if exists:
        r.answer.append(dns.rrset.from_text(q.question[0].name, 60, "IN", "A", "203.0.113.9"))
    else:
        r.set_rcode(3)  # NXDOMAIN
    return r.to_wire()


class UDPHandler(socketserver.BaseRequestHandler):
    hijack = False

    def handle(self):
        data, sock = self.request
        sock.sendto(make_reply(data, self.hijack), self.client_address)


class HijackUDP(UDPHandler):
    hijack = True


class DohHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["content-length"]))
        out = make_reply(body)
        self.send_response(200)
        self.send_header("content-type", "application/dns-message")
        self.send_header("content-length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


def start_udp(handler):
    srv = socketserver.ThreadingUDPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_plain_and_hijack():
    good, bad = start_udp(UDPHandler), start_udp(HijackUDP)
    t = benchmark.PlainTransport("127.0.0.1", port=good.server_address[1])
    r = benchmark.measure(t, "g", "good", "plain", rounds=1)
    assert r.ok and r.success == r.total == len(benchmark.TEST_DOMAINS)
    assert r.hijack is False and 0 < r.score <= 100
    t = benchmark.PlainTransport("127.0.0.1", port=bad.server_address[1])
    r = benchmark.measure(t, "b", "bad", "plain", rounds=1)
    assert r.hijack is True


def test_dead_server():
    t = benchmark.PlainTransport("127.0.0.1", port=1, timeout=0.3)
    r = benchmark.measure(t, "x", "dead", "plain", rounds=1, domains=["a.com", "b.com"])
    assert not r.ok and r.score == 0 and r.success == 0


def test_doh_http():
    srv = HTTPServer(("127.0.0.1", 0), DohHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/dns-query"
    r = benchmark.measure(benchmark.DohTransport(url), "d", "doh", "doh", rounds=1)
    assert r.ok and r.success == r.total and r.hijack is False


def test_ranking_and_score():
    a = benchmark.Result("a", "A", "plain", median=10, jitter=1, success=10, total=10, score=benchmark.compute_score(10, 1, 10, 10))
    b = benchmark.Result("b", "B", "plain", median=40, jitter=5, success=9, total=10, score=benchmark.compute_score(40, 5, 9, 10))
    c = benchmark.Result("c", "C", "plain", supported=False)
    assert [r.provider_id for r in benchmark.rank([c, b, a])] == ["a", "b", "c"]
    assert a.score > b.score > c.score == 0


def test_run_benchmark_unsupported_and_cancel():
    provs = [{"id": "n", "name": "no-doh", "v4": ["127.0.0.1"], "doh": "", "dot": ""}]
    res = benchmark.run_benchmark(provs, "doh")
    assert len(res) == 1 and not res[0].supported
    ev = threading.Event()
    ev.set()
    assert benchmark.run_benchmark(provs, "plain", cancel=ev) == []


def test_providers_valid():
    provs = storage.builtin_providers()
    ids = [p["id"] for p in provs]
    assert len(ids) == len(set(ids)) >= 10
    for p in provs:
        assert p["v4"] and all(storage.is_ipv4(x) for x in p["v4"]), p["id"]
        assert all(storage.is_ipv6(x) for x in p["v6"]), p["id"]
        if p["doh"]:
            assert storage.is_doh_url(p["doh"]), p["id"]


def test_validation():
    assert storage.is_ipv4("8.8.8.8") and not storage.is_ipv4("8.8.8.256") and not storage.is_ipv4("::1")
    assert storage.is_ipv6("2001:4860:4860::8888") and not storage.is_ipv6("1.1.1.1")
    assert storage.is_doh_url("https://dns.google/dns-query") and not storage.is_doh_url("http://x")
    assert storage.is_hostname("dns.google") and not storage.is_hostname("a b")


def test_custom_store_import_export(tmp_path=None):
    cs = storage.CustomStore()
    cs.items.clear()
    cs.add("", ["203.0.113.5"], [], "", "")
    assert cs.items[0]["name"] == "203.0.113.5" and cs.items[0]["tags"] == ["mine"]
    assert cs.import_text("9.9.9.9, 149.112.112.112\nbad line\n2001:db8::1") == 2
    p = Path(os.environ["DNSHUB_HOME"]) / "exp.json"
    cs.export_json(p)
    cs2 = storage.CustomStore()
    cs2.items.clear()
    assert cs2.import_json(p) == 3
    first = cs.items[0]["id"]
    cs.remove(first)
    assert all(i["id"] != first for i in cs.items)
    assert len(storage.all_providers(cs)) == len(storage.builtin_providers()) + len(cs.items)


def test_apply_restore_dry_run():
    mgr = winnet.DnsManager(winnet.DryRunBackend())
    (Path(os.environ["DNSHUB_HOME"]) / "backup.json").unlink(missing_ok=True)
    mgr.backend.set_dns(1, ["192.168.1.1"])
    cf = next(p for p in storage.builtin_providers() if p["id"] == "cloudflare")
    mgr.apply(1, cf)
    assert mgr.current(1)["v4"] == ["1.1.1.1", "1.0.0.1"] and mgr.backend.state["doh"]
    mgr.apply(1, next(p for p in storage.builtin_providers() if p["id"] == "google"))
    assert mgr.restore(1)  # ilk yedeğe döner, araya giren ikinci uygulama yedeği ezmez
    assert mgr.current(1)["v4"] == ["192.168.1.1"]


def test_safety_timer_reverts_when_offline(monkeypatch=None):
    mgr = winnet.DnsManager(winnet.DryRunBackend())
    (Path(os.environ["DNSHUB_HOME"]) / "backup.json").unlink(missing_ok=True)
    mgr.backend.set_dns(1, ["10.0.0.1"])
    orig = winnet.check_connectivity
    try:
        winnet.check_connectivity = lambda **k: False
        kept = mgr.apply_with_safety(1, storage.builtin_providers()[0], wait=2.0)
        assert kept is False and mgr.current(1)["v4"] == ["10.0.0.1"]
        (Path(os.environ["DNSHUB_HOME"]) / "backup.json").unlink(missing_ok=True)
        winnet.check_connectivity = lambda **k: True
        assert mgr.apply_with_safety(1, storage.builtin_providers()[0], wait=2.0) is True
        assert mgr.current(1)["v4"] == storage.builtin_providers()[0]["v4"]
    finally:
        winnet.check_connectivity = orig


def test_i18n_keys_complete():
    base = set(json.loads((i18n.LOCALE_DIR / "en.json").read_text(encoding="utf-8")))
    for code in i18n.LANGS:
        keys = set(json.loads((i18n.LOCALE_DIR / f"{code}.json").read_text(encoding="utf-8")))
        assert keys == base, (code, base ^ keys)
    i18n.set_language("de")
    assert i18n.t("nav.home") == "Startseite" and i18n.t("nope.key") == "nope.key"
    assert i18n.t("test.progress", done=2, total=5) == "2 / 5 Server getestet"
    i18n.set_language("tr")
    assert i18n.t("nav.home") == "Ana Sayfa"


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
