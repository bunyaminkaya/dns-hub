"""PyInstaller ve doğrudan çalıştırma için başlatıcı (paket dışından olduğu için içe aktarmalar sorunsuz)."""
import sys

from dnshub.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
