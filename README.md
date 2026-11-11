# DNS Hub v0.2

Ücretsiz, reklamsız, açık kaynak DNS değiştirici ve hız testi aracı. Windows için tasarlandı (PySide6).
Arayüz: Türkçe, English, Deutsch. Açık/koyu tema (sistemi takip eder).

## Çalıştırma

```
pip install -r requirements.txt
python run.py
```

(`python -m dnshub` de çalışır. `.exe` derlerken giriş noktası `run.py` olmalı, `dnshub\__main__.py` değil.)

DNS ayarını gerçekten değiştirmek için programı **yönetici olarak** çalıştır.
Windows dışında program "deneme modunda" açılır: arayüz ve testler çalışır, sistem DNS'i değişmez.

Tek `.exe` için: `pip install pyinstaller`, sonra proje klasöründe `build_exe.bat` (yönetici izni ister).
`.exe` simgesi `assets/icon.ico` dosyasından gelir (yoksa `build_exe.bat` kendisi üretir; elle: `python tools/make_icon.py`).
Başlatıcı `run.py`'dir; PyInstaller'a `dnshub\__main__.py` verme, paket içi içe aktarmalar çalışmaz.

## v0.1'de olanlar

- 13 ücretsiz sağlayıcı (Cloudflare, Google, Quad9, AdGuard, CleanBrowsing, Control D, Mullvad, OpenDNS ve filtreli/filtresiz varyantları). Liste `dnshub/providers.json` dosyasında, kolayca güncellenir.
- Hız testi: düz DNS, DoH ve DoT ayrı ayrı. Ortanca gecikme, sapma (jitter), başarı oranı, puan. Olmayan alan adlarını yönlendiren (reklam sayfası döndüren) DNS'leri işaretler.
- "En hızlıyı bul ve uygula": önce şifreli (DoH), olmazsa düz DNS.
- Özel DNS ekleme: IPv4/IPv6, DoH adresi, DoT adı. Kaydetmeden önce 53/443/853 portlarında test eder. Metin/JSON içe ve dışa aktarma.
- Güvenlik sayacı: DNS değişince internet gelmezse 15 saniye içinde eski ayara döner. Eski ayar uygulamadan önce yedeklenir.
- Favoriler, arama, kategori filtreleri, sistem tepsisi, Windows ile başlatma.
- Hakkında sayfası: sürüm, gizlilik, lisans, kullanılan bileşenler ve hata bildirirken kopyalanabilen sistem bilgisi.

## Sonraki sürümler

- v0.2: engel tespiti (ISS DNS'i ile şifreli DNS cevaplarını karşılaştırma), sızıntı testi.
- v0.3: yerel şifreli DNS vekili (DoH → DoT → DoQ → düz DNS yedekleme zinciri, alan adı kuralları).

## Bilinen sınırlar

- Windows 10'da DoH komutu yoktur, DNS düz olarak uygulanır (Windows 11 gerekir).
- Cloudflare gibi bazı sağlayıcılar bazı ülkelerde veya ağlarda engelli olabilir. Bu yüzden program her sunucuyu senin hattında test eder.
- DNS değiştirmek yalnızca alan adı tabanlı engellerde işe yarar. IP veya URL tabanlı engelleri aşmaz.

## Testler

```
python tests/test_core.py          # benchmark, doğrulama, uygulama/geri alma, dil dosyaları
python tests/test_controller.py    # arayüz denetleyicisi (ağ gerekmez)
python tests/screenshots.py out    # başsız çalıştırıp her sayfanın ekran görüntüsünü alır
```

## Lisans

MIT, bkz. `LICENSE`. Hakkında sayfasındaki web sitesi bağlantısı `dnshub/__init__.py` içindeki `WEBSITE` değerinden gelir.
