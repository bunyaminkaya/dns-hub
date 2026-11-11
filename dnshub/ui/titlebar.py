"""Windows başlık çubuğunu uygulama temasına uydurur (Windows 11: renk; Windows 10: koyu/açık mod)."""
from __future__ import annotations

import sys

from . import theme


def _colorref(hex_color: str) -> int:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r | (g << 8) | (b << 16)


def apply_titlebar(widget) -> None:
    """Pencerenin başlık çubuğunu tema rengine boyar. Windows dışında veya desteklenmiyorsa sessizce geçer."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = wintypes.HWND(int(widget.winId()))
        dwm = ctypes.windll.dwmapi

        def put(attr: int, value: int) -> None:
            v = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(hwnd, ctypes.c_uint(attr), ctypes.byref(v), ctypes.sizeof(v))

        dark = 1 if theme.MODE == "dark" else 0
        put(20, dark)                              # DWMWA_USE_IMMERSIVE_DARK_MODE (Win10 20H1+, Win11)
        put(19, dark)                              # eski Windows 10 sürümleri
        put(35, _colorref(theme.P["bg"]))          # DWMWA_CAPTION_COLOR (Win11)
        put(36, _colorref(theme.P["tx"]))          # DWMWA_TEXT_COLOR (Win11)
        put(34, _colorref(theme.P["bg"]))          # DWMWA_BORDER_COLOR (Win11)
    except Exception:  # noqa: BLE001  (görsel iyileştirme, hata uygulamayı durdurmasın)
        pass
