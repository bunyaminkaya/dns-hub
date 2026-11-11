"""DNS hız ve güvenilirlik testi: düz DNS (UDP), DoH ve DoT.

Her ölçüm ilk (ısınma) sorgusunu atar, bağlantı kurulumunu sonuca katmaz.
"""
from __future__ import annotations

import random
import socket
import ssl
import statistics
import string
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from urllib.parse import urlparse

import dns.exception
import dns.message
import dns.query
import dns.rcode
import dns.rdatatype
import httpx

TEST_DOMAINS = [
    "google.com", "youtube.com", "wikipedia.org", "github.com", "cloudflare.com",
    "microsoft.com", "amazon.com", "trendyol.com", "hepsiburada.com", "turkcell.com.tr",
]

PROTOCOLS = ("plain", "doh", "dot")


@dataclass
class Result:
    provider_id: str
    name: str
    proto: str
    supported: bool = True
    median: float | None = None
    mean: float | None = None
    jitter: float | None = None
    success: int = 0
    total: int = 0
    score: int = 0
    hijack: bool | None = None
    error: str = ""
    samples: list = field(default_factory=list)

    @property
    def success_pct(self) -> int:
        return round(100 * self.success / self.total) if self.total else 0

    @property
    def ok(self) -> bool:
        return self.supported and self.success > 0 and self.median is not None


# ----------------------------------------------------------------- puanlama
def compute_score(median: float | None, jitter: float | None, success: int, total: int) -> int:
    if not total or not success or median is None:
        return 0
    fail_rate = 1 - success / total
    score = 100 - median * 0.8 - (jitter or 0) * 0.5 - fail_rate * 100
    return max(0, min(100, round(score)))


def _rand_label(n: int = 14) -> str:
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(n))


def _query(domain: str):
    return dns.message.make_query(domain, dns.rdatatype.A)


def _valid(resp) -> bool:
    return resp.rcode() in (dns.rcode.NOERROR, dns.rcode.NXDOMAIN)


# ----------------------------------------------------------------- taşıyıcılar
class PlainTransport:
    def __init__(self, ip: str, port: int = 53, timeout: float = 2.0):
        self.ip, self.port, self.timeout = ip, port, timeout

    def ask(self, domain: str):
        return dns.query.udp(_query(domain), self.ip, timeout=self.timeout, port=self.port, ignore_unexpected=True)

    def close(self):
        pass


class DohTransport:
    """DoH. `bootstrap` verilirse bağlantı o IP'ye kurulur, sertifika alan adına göre doğrulanır."""

    def __init__(self, url: str, bootstrap: str = "", timeout: float = 3.0):
        u = urlparse(url)
        self.host = u.hostname or ""
        self.timeout = timeout
        self.headers = {"content-type": "application/dns-message", "accept": "application/dns-message"}
        self.ext = {}
        target = url
        if bootstrap:
            ip = f"[{bootstrap}]" if ":" in bootstrap else bootstrap
            netloc = f"{ip}:{u.port}" if u.port else ip
            target = u._replace(netloc=netloc).geturl()
            self.headers["host"] = self.host
            self.ext = {"sni_hostname": self.host}
        self.url = target
        self.client = httpx.Client(http2=(u.scheme == "https"), timeout=timeout, verify=u.scheme == "https")

    def ask(self, domain: str):
        wire = _query(domain).to_wire()
        r = self.client.post(self.url, content=wire, headers=self.headers, extensions=self.ext)
        r.raise_for_status()
        return dns.message.from_wire(r.content)

    def close(self):
        self.client.close()


class DotTransport:
    def __init__(self, ip: str, host: str, port: int = 853, timeout: float = 3.0, verify: bool = True):
        self.ip, self.host, self.port, self.timeout = ip, host, port, timeout
        ctx = ssl.create_default_context()
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        self.ctx = ctx
        self.sock = None

    def _connect(self):
        raw = socket.create_connection((self.ip, self.port), timeout=self.timeout)
        self.sock = self.ctx.wrap_socket(raw, server_hostname=self.host or None)

    def ask(self, domain: str):
        if self.sock is None:
            self._connect()
        try:
            return dns.query.tls(_query(domain), self.ip, timeout=self.timeout, port=self.port,
                                 sock=self.sock, ssl_context=self.ctx, server_hostname=self.host or None)
        except Exception:
            self.close()
            raise

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None


# ----------------------------------------------------------------- ölçüm
def measure(transport, pid: str, name: str, proto: str, rounds: int = 2,
            domains: list[str] | None = None, check_hijack: bool = True) -> Result:
    domains = domains or TEST_DOMAINS
    res = Result(pid, name, proto)
    samples: list[float] = []
    try:
        # ısınma: bağlantıyı kur, süreyi sayma
        try:
            transport.ask(domains[0])
        except Exception as e:  # noqa: BLE001
            res.error = type(e).__name__
        for _ in range(rounds):
            for d in domains:
                res.total += 1
                t0 = time.perf_counter()
                try:
                    resp = transport.ask(d)
                    if _valid(resp):
                        samples.append((time.perf_counter() - t0) * 1000)
                        res.success += 1
                except Exception as e:  # noqa: BLE001
                    res.error = res.error or type(e).__name__
        if check_hijack and res.success:
            try:
                resp = transport.ask(f"{_rand_label()}.com")
                res.hijack = resp.rcode() == dns.rcode.NOERROR and bool(resp.answer)
            except Exception:  # noqa: BLE001
                res.hijack = None
    finally:
        transport.close()
    res.samples = samples
    if samples:
        res.median = statistics.median(samples)
        res.mean = statistics.fmean(samples)
        res.jitter = statistics.pstdev(samples) if len(samples) > 1 else 0.0
    else:
        res.supported = False if not res.error else True
    res.score = compute_score(res.median, res.jitter, res.success, res.total)
    return res


def _unsupported(p: dict, proto: str) -> Result:
    return Result(p["id"], p["name"], proto, supported=False, error="unsupported")


def benchmark_provider(p: dict, proto: str, rounds: int = 2, domains: list[str] | None = None,
                       check_hijack: bool = True) -> Result:
    pid, name = p["id"], p["name"]
    v4 = p.get("v4") or []
    if proto == "plain":
        ip = (v4 or p.get("v6") or [None])[0]
        if not ip:
            return _unsupported(p, proto)
        return measure(PlainTransport(ip), pid, name, proto, rounds, domains, check_hijack)
    if proto == "doh":
        url = p.get("doh") or ""
        if not url:
            return _unsupported(p, proto)
        return measure(DohTransport(url, p.get("bootstrap") or (v4[0] if v4 else "")),
                       pid, name, proto, rounds, domains, check_hijack)
    if proto == "dot":
        host = p.get("dot") or ""
        ip = (v4 or [None])[0]
        if not host or not ip:
            return _unsupported(p, proto)
        return measure(DotTransport(ip, host), pid, name, proto, rounds, domains, check_hijack)
    raise ValueError(proto)


def probe_provider(p: dict, rounds: int = 1) -> dict[str, Result]:
    """Özel DNS ekleme penceresi: üç protokolü de dener (üçü paralel)."""
    out: dict[str, Result] = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {pr: ex.submit(benchmark_provider, p, pr, rounds, TEST_DOMAINS[:4], False) for pr in PROTOCOLS}
        for pr, f in futs.items():
            try:
                out[pr] = f.result()
            except Exception as e:  # noqa: BLE001
                out[pr] = Result(p["id"], p["name"], pr, supported=False, error=type(e).__name__)
    return out


def run_benchmark(providers: list[dict], proto: str, on_result=None, cancel: threading.Event | None = None,
                  rounds: int = 2, workers: int = 4) -> list[Result]:
    """Sağlayıcıları sınırlı paralellikle ölçer; her sonuç bitince on_result(Result) çağrılır."""
    cancel = cancel or threading.Event()
    results: list[Result] = []
    lock = threading.Lock()

    def job(p):
        if cancel.is_set():
            return None
        try:
            r = benchmark_provider(p, proto, rounds)
        except Exception as e:  # noqa: BLE001
            r = Result(p["id"], p["name"], proto, supported=False, error=type(e).__name__)
        with lock:
            results.append(r)
        if on_result:
            on_result(r)
        return r

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(job, providers))
    return rank(results)


def rank(results: list[Result]) -> list[Result]:
    return sorted(results, key=lambda r: (not r.ok, -r.score, r.median if r.median is not None else 1e9))
