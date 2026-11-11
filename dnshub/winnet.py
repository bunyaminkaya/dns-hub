"""DNS ayarını okuma/uygulama/geri alma.

Windows'ta PowerShell (NetAdapter ve DnsClient modülleri) kullanır. Diğer sistemlerde
gerçek ayar değiştirilmez, `DryRunBackend` ile aynı akış denenebilir.
"""
from __future__ import annotations

import ctypes
import json
import socket
import subprocess
import sys
import time

from . import storage

CREATE_NO_WINDOW = 0x08000000 if sys.platform.startswith("win") else 0


class DnsError(Exception):
    pass


class NeedAdmin(DnsError):
    pass


def is_windows() -> bool:
    return sys.platform.startswith("win")


def is_admin() -> bool:
    if not is_windows():
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


# ----------------------------------------------------------------- Windows
class WindowsBackend:
    dry = False

    def _ps(self, script: str, timeout: int = 30) -> str:
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
               "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.Encoding]::UTF8; " + script]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                               creationflags=CREATE_NO_WINDOW, encoding="utf-8", errors="replace")
        except (OSError, subprocess.TimeoutExpired) as e:
            raise DnsError(str(e)) from e
        if p.returncode != 0:
            err = (p.stderr or p.stdout).strip()
            if "denied" in err.lower() or "yetki" in err.lower() or "0x80041003" in err:
                raise NeedAdmin(err)
            raise DnsError(err)
        return p.stdout.strip()

    def adapters(self) -> list[dict]:
        out = self._ps("Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and -not $_.Virtual} | "
                       "Select-Object Name,InterfaceDescription,InterfaceIndex | ConvertTo-Json -Compress")
        if not out:
            return []
        data = json.loads(out)
        return data if isinstance(data, list) else [data]

    def get_dns(self, index: int) -> dict:
        out = self._ps(f"Get-DnsClientServerAddress -InterfaceIndex {int(index)} | "
                       "Select-Object AddressFamily,ServerAddresses | ConvertTo-Json -Compress")
        data = json.loads(out) if out else []
        data = data if isinstance(data, list) else [data]
        v4 = next((d["ServerAddresses"] for d in data if d["AddressFamily"] == 2), []) or []
        v6 = next((d["ServerAddresses"] for d in data if d["AddressFamily"] == 23), []) or []
        return {"v4": list(v4), "v6": list(v6)}

    def set_dns(self, index: int, servers: list[str], doh: str = "") -> bool:
        """DNS'i uygular. Dönüş: DoH gerçekten etkinleştirildi mi (Windows 11 gerekir)."""
        servers = [s for s in servers if s]
        if not servers:
            self._ps(f"Set-DnsClientServerAddress -InterfaceIndex {int(index)} -ResetServerAddresses")
            return False
        doh_ok = False
        if doh:
            try:
                for s in servers:
                    if ":" in s:
                        continue
                    self._ps(f"if (-not (Get-DnsClientDohServerAddress -ServerAddress '{s}' -ErrorAction SilentlyContinue)) "
                             f"{{ Add-DnsClientDohServerAddress -ServerAddress '{s}' -DohTemplate '{doh}' "
                             f"-AllowFallbackToUdp $false -AutoUpgrade $true }}")
                doh_ok = True
            except NeedAdmin:
                raise
            except DnsError:
                doh_ok = False  # Windows 10: DoH komutu yok, düz DNS ile devam
        addr = ",".join(f"'{s}'" for s in servers)
        self._ps(f"Set-DnsClientServerAddress -InterfaceIndex {int(index)} -ServerAddresses ({addr})")
        self._ps("Clear-DnsClientCache")
        return doh_ok


# ----------------------------------------------------------------- deneme modu
class DryRunBackend:
    """Windows dışında: ayarlar bir dosyada tutulur, sisteme dokunulmaz."""
    dry = True

    def __init__(self) -> None:
        self.path = storage.data_dir() / "dryrun_dns.json"
        try:
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.state = {"v4": [], "v6": [], "doh": ""}

    def adapters(self):
        return [{"Name": "Ethernet (deneme)", "InterfaceDescription": "Dry-run", "InterfaceIndex": 1}]

    def get_dns(self, index):
        return {"v4": list(self.state["v4"]), "v6": list(self.state["v6"])}

    def set_dns(self, index, servers, doh="") -> bool:
        self.state = {"v4": [s for s in servers if ":" not in s], "v6": [s for s in servers if ":" in s], "doh": doh}
        self.path.write_text(json.dumps(self.state), encoding="utf-8")
        return bool(doh and servers)


def default_backend():
    return WindowsBackend() if is_windows() else DryRunBackend()


# ----------------------------------------------------------------- üst düzey
def check_connectivity(domains=("www.msftconnecttest.com", "one.one.one.one", "wikipedia.org"),
                       timeout: float = 4.0) -> bool:
    """Sistem çözücüsüyle en az bir alan adı çözülüyor mu?"""
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        for d in domains:
            try:
                socket.getaddrinfo(d, 443)
                return True
            except OSError:
                continue
        return False
    finally:
        socket.setdefaulttimeout(old)


def set_autostart(enabled: bool) -> bool:
    """Windows açılışında başlat (kullanıcı kaydı, yönetici gerekmez). Windows dışında hiçbir şey yapmaz."""
    if not is_windows():
        return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_SET_VALUE)
        with key:
            if enabled:
                exe = sys.executable if getattr(sys, "frozen", False) else f'"{sys.executable}" -m dnshub'
                winreg.SetValueEx(key, "DNSHub", 0, winreg.REG_SZ, exe)
            else:
                try:
                    winreg.DeleteValue(key, "DNSHub")
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


class DnsManager:
    """Uygulama, yedekleme ve geri alma."""

    def __init__(self, backend=None):
        self.backend = backend or default_backend()

    @property
    def dry(self) -> bool:
        return self.backend.dry

    def adapters(self) -> list[dict]:
        return self.backend.adapters()

    def current(self, index: int) -> dict:
        return self.backend.get_dns(index)

    def apply(self, index: int, provider: dict, encrypted: bool = True, ipv6: bool = False) -> bool:
        """Mevcut ayarı yedekler (daha önce yedek yoksa) ve sağlayıcıyı uygular.

        Dönüş: şifreli DNS (DoH) gerçekten etkin mi."""
        if not storage.load_backup():
            storage.save_backup({"index": index, "dns": self.backend.get_dns(index)})
        servers = list(provider.get("v4") or [])
        if ipv6:
            servers += list(provider.get("v6") or [])
        if not servers:
            servers = list(provider.get("v6") or [])
        doh = provider.get("doh", "") if encrypted else ""
        return bool(self.backend.set_dns(index, servers, doh))

    def apply_addresses(self, index: int, addresses: list[str]) -> None:
        if not storage.load_backup():
            storage.save_backup({"index": index, "dns": self.backend.get_dns(index)})
        self.backend.set_dns(index, addresses, "")

    def has_backup(self) -> bool:
        return bool(storage.load_backup())

    def restore(self, index: int | None = None) -> bool:
        b = storage.load_backup()
        if not b:
            return False
        idx = index if index is not None else b.get("index", 1)
        dns_ = b.get("dns", {})
        self.backend.set_dns(idx, list(dns_.get("v4", [])) + list(dns_.get("v6", [])), "")
        return True

    def apply_with_safety(self, index: int, provider: dict, wait: float = 15.0, **kw) -> bool:
        """Uygular, internet gelmezse `wait` saniye içinde geri alır. True: DNS kalıcı."""
        self.apply(index, provider, **kw)
        return self._confirm_or_restore(index, wait)

    def _confirm_or_restore(self, index: int, wait: float) -> bool:
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            if check_connectivity(timeout=3.0):
                return True
            time.sleep(1.0)
        self.restore(index)
        return False
