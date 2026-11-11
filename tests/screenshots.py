"""Başsız (offscreen) çalıştırıp her sayfanın ekran görüntüsünü alır; arayüzün gerçekten açıldığını doğrular.

Kullanım: python tests/screenshots.py <çıktı klasörü>
"""
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DNSHUB_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication

from dnshub import i18n, storage
from dnshub.ui import theme
from dnshub.ui.controller import Controller
from dnshub.ui.dialogs import CustomDnsDialog
from dnshub.ui.main_window import MainWindow

out = Path(sys.argv[1] if len(sys.argv) > 1 else "shots")
out.mkdir(parents=True, exist_ok=True)

app = QApplication(sys.argv)
ctl = Controller()


def pump(sec=0.3):
    end = time.time() + sec
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def shoot(win, name):
    pump(0.4)
    win.grab().save(str(out / f"{name}.png"))
    print("saved", name)


def run(theme_name, lang):
    ctl.settings.set("theme", theme_name)
    ctl.settings.set("language", lang)
    i18n.set_language(lang)
    theme.apply_theme(app, theme_name)
    win = MainWindow(ctl, app)
    win.resize(1120, 720)
    win.show()
    pump(0.5)
    tag = f"{theme_name}-{lang}"
    for key in ("home", "list", "test", "settings", "about", "block"):
        win.show_page(key)
        shoot(win, f"{tag}-{key}")
    return win


# 1) açık tema, Türkçe: tüm sayfalar
win = run("light", "tr")
# özel DNS ekle penceresi
dlg = CustomDnsDialog(win, ctl, prefill="203.0.113.5")
dlg.doh.setText("https://dns.ornek.com/dns-query")
dlg.show()
pump(0.4)
dlg.grab().save(str(out / "light-tr-custom-dialog.png"))
print("saved dialog")
dlg.close()
win.close()

# 2) koyu tema, İngilizce ve Almanca
for lang in ("en", "de"):
    w = run("dark", lang)
    w.close()

# 3) gerçek akış: yerel sahte sunucuya karşı değil, ağ yoksa bile çökmemeli. Test sayfasını başlat, hemen durdur.
ctl.settings.set("theme", "dark")
ctl.settings.set("language", "tr")
i18n.set_language("tr")
theme.apply_theme(app, "dark")
w = MainWindow(ctl, app)
w.show()
w.show_page("test")
pump(0.2)
w.pages["test"]._toggle()
pump(1.5)
shoot(w, "dark-tr-test-running")
ctl.stop_test()
pump(3)
shoot(w, "dark-tr-test-stopped")
w.close()
print("done")
