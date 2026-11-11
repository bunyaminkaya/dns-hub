"""Çok dilli metin sistemi: dnshub/locales/<kod>.json dosyalarından okur."""
from __future__ import annotations

import json
import locale
from pathlib import Path

LOCALE_DIR = Path(__file__).resolve().parent / "locales"
LANGS = {"tr": "Türkçe", "en": "English", "de": "Deutsch"}
FALLBACK = "en"

_current = FALLBACK
_tables: dict[str, dict] = {}
_listeners: list = []


def _table(code: str) -> dict:
    if code not in _tables:
        try:
            _tables[code] = json.loads((LOCALE_DIR / f"{code}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _tables[code] = {}
    return _tables[code]


def detect_system_language() -> str:
    try:
        code = (locale.getlocale()[0] or "").lower()
    except Exception:
        code = ""
    for lang in LANGS:
        if code.startswith(lang) or code.startswith({"tr": "turkish", "de": "german"}.get(lang, lang)):
            return lang
    return FALLBACK


def set_language(code: str) -> str:
    global _current
    if code == "auto" or code not in LANGS:
        code = detect_system_language()
    _current = code
    for fn in list(_listeners):
        fn()
    return code


def current() -> str:
    return _current


def on_change(fn) -> None:
    _listeners.append(fn)


def t(key: str, **kw) -> str:
    text = _table(_current).get(key) or _table(FALLBACK).get(key) or key
    if kw:
        try:
            return text.format(**kw)
        except (KeyError, IndexError):
            return text
    return text
