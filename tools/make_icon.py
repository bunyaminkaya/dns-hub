"""Uygulama simgesinden assets/icon.png ve çok boyutlu assets/icon.ico üretir.

Kullanım (proje klasöründe): python tools/make_icon.py
Gerekenler: PySide6, Pillow (pip install pillow)
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QGuiApplication  # noqa: E402

from dnshub.ui.widgets import app_pixmap  # noqa: E402

SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> None:
    app = QGuiApplication([])  # noqa: F841  (pixmap için gerekli)
    out = ROOT / "assets"
    out.mkdir(exist_ok=True)
    png = out / "icon.png"
    app_pixmap(1024).save(str(png), "PNG")

    from PIL import Image
    img = Image.open(png).convert("RGBA")
    img.resize((256, 256), Image.LANCZOS).save(out / "icon.ico", format="ICO", sizes=SIZES)
    print("yazıldı:", png, out / "icon.ico")


if __name__ == "__main__":
    main()
