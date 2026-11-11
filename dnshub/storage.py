"""Ayarlar, özel DNS listesi ve sağlayıcı verisi (JSON dosyaları)."""
from __future__ import annotations

import ipaddress
import json
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

PKG_DIR = Path(__file__).resolve().parent

DEFAULT_SETTINGS = {
    "language": "auto",      # auto | tr | en | de
    "theme": "system",       # system | light | dark
    "autostart": False,
    "apply_fastest_on_boot": False,
    "safety_timer": True,
    "fallback_chain": True,
    "tray": True,
    "favorites": [],
    "adapter": "",
}


def data_dir() -> Path:
    override = os.environ.get("DNSHUB_HOME")
    if override:
        base = Path(override)
    elif sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", str(Path.home()))) / "DNSHub"
    else:
        base = Path.home() / ".config" / "dnshub"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------- doğrulama
def is_ipv4(value: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(value.strip()), ipaddress.IPv4Address)
    except ValueError:
        return False


def is_ipv6(value: str) -> bool:
    try:
        return isinstance(ipaddress.ip_address(value.strip()), ipaddress.IPv6Address)
    except ValueError:
        return False


def is_doh_url(value: str) -> bool:
    u = urlparse(value.strip())
    return u.scheme == "https" and bool(u.netloc)


def is_hostname(value: str) -> bool:
    v = value.strip()
    if not v or len(v) > 253 or " " in v:
        return False
    return all(p and len(p) <= 63 for p in v.split("."))


# ---------------------------------------------------------------- ayarlar
class Settings:
    def __init__(self) -> None:
        self.path = data_dir() / "settings.json"
        self.data = dict(DEFAULT_SETTINGS)
        self.data.update(_read(self.path, {}))

    def get(self, key):
        return self.data.get(key, DEFAULT_SETTINGS.get(key))

    def set(self, key, value) -> None:
        self.data[key] = value
        self.save()

    def save(self) -> None:
        _write(self.path, self.data)

    def toggle_favorite(self, pid: str) -> bool:
        favs = list(self.get("favorites"))
        if pid in favs:
            favs.remove(pid)
            state = False
        else:
            favs.append(pid)
            state = True
        self.set("favorites", favs)
        return state


# ---------------------------------------------------------------- sağlayıcılar
def builtin_providers() -> list[dict]:
    raw = _read(PKG_DIR / "providers.json", {"providers": []})
    out = []
    for p in raw["providers"]:
        p = dict(p)
        p["builtin"] = True
        p.setdefault("bootstrap", "")
        out.append(p)
    return out


class CustomStore:
    """Kullanıcının eklediği DNS'ler."""

    def __init__(self) -> None:
        self.path = data_dir() / "custom.json"
        self.items: list[dict] = _read(self.path, [])

    def all(self) -> list[dict]:
        return [dict(i, builtin=False) for i in self.items]

    def add(self, name, v4, v6, doh, dot, bootstrap="") -> dict:
        item = {
            "id": "custom-" + uuid.uuid4().hex[:8],
            "name": name.strip() or (list(v4) + list(v6) + [""])[0].strip(),
            "tags": ["mine"],
            "v4": [x.strip() for x in v4 if x.strip()],
            "v6": [x.strip() for x in v6 if x.strip()],
            "doh": doh.strip(),
            "dot": dot.strip(),
            "bootstrap": bootstrap.strip(),
        }
        self.items.append(item)
        self.save()
        return item

    def remove(self, pid: str) -> None:
        self.items = [i for i in self.items if i["id"] != pid]
        self.save()

    def save(self) -> None:
        _write(self.path, self.items)

    def export_json(self, path: Path) -> None:
        _write(Path(path), self.items)

    def import_json(self, path: Path) -> int:
        data = _read(Path(path), [])
        n = 0
        for d in data if isinstance(data, list) else []:
            v4 = [x for x in d.get("v4", []) if is_ipv4(x)]
            v6 = [x for x in d.get("v6", []) if is_ipv6(x)]
            if not v4 and not v6:
                continue
            doh = d.get("doh", "")
            self.add(d.get("name", ""), v4, v6, doh if is_doh_url(doh) else "", d.get("dot", ""))
            n += 1
        return n

    def import_text(self, text: str) -> int:
        """Her satırda bir IP (virgül/boşlukla ayrılmış iki IP de olur)."""
        n = 0
        for line in text.splitlines():
            parts = [p for p in line.replace(",", " ").split() if p]
            v4 = [p for p in parts if is_ipv4(p)]
            v6 = [p for p in parts if is_ipv6(p)]
            if v4 or v6:
                self.add((v4 or v6)[0], v4, v6, "", "")
                n += 1
        return n


def all_providers(custom: CustomStore) -> list[dict]:
    return builtin_providers() + custom.all()


# ---------------------------------------------------------------- yedek ve son test
def save_backup(data: dict) -> None:
    _write(data_dir() / "backup.json", data)


def load_backup() -> dict:
    return _read(data_dir() / "backup.json", {})


def save_last_test(data: dict) -> None:
    _write(data_dir() / "last_test.json", data)


def load_last_test() -> dict:
    return _read(data_dir() / "last_test.json", {})
