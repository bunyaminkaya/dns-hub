@echo off
REM DNS Hub: tek dosyalık .exe üretir (yönetici izni ister, DNS değiştirmek için gerekli).
REM Bu dosyayı proje klasöründe (run.py ile aynı yerde) çalıştır.
cd /d "%~dp0"

echo [1/3] Paketler kuruluyor (hepsi ayni Python ile)...
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto fail

if not exist "assets\icon.ico" (
  echo Simge dosyasi yok, olusturuluyor...
  python -m pip install pillow
  python tools\make_icon.py
  if errorlevel 1 goto fail
)

echo [2/3] Paketler kontrol ediliyor...
python -c "import dns, httpx, h2, PySide6; print('Paketler tamam:', dns.version.version, httpx.__version__)"
if errorlevel 1 goto fail

echo [3/3] .exe derleniyor...
python -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin --name DNSHub ^
  --icon "assets\icon.ico" ^
  --add-data "dnshub\providers.json;dnshub" ^
  --add-data "dnshub\locales;dnshub\locales" ^
  --collect-submodules dns ^
  --hidden-import h2 --hidden-import hpack --hidden-import hyperframe ^
  run.py
if errorlevel 1 goto fail

echo.
echo Hazir: dist\DNSHub.exe
pause
exit /b 0

:fail
echo.
echo HATA: yukaridaki mesaji kontrol et. "python" komutu Python 3.10+ olmali.
pause
exit /b 1
