"""
Konsol çıktısı için güvenli kodlama ayarı.

Windows'ta terminal varsayılan olarak cp1252/cp1254 gibi tek baytlık bir
kod sayfası kullanıyor. Kod tabanındaki log satırlarında ✓, ❌, 📊 gibi
karakterler var ve bunlar print edilince UnicodeEncodeError fırlatıp
uygulamayı komple düşürüyor (sadece logu bozmakla kalmıyor).

Bu modül stdout/stderr'i UTF-8'e çevirir; çeviremediği karakter olursa
hata fırlatmak yerine yerine koyma yapar. Uygulama açılışında bir kez
çağrılır ve tekrar çağrılması zararsızdır.
"""

import sys

_CONFIGURED = False


def configure_console_encoding():
    """stdout/stderr'i UTF-8 + errors='replace' yapar. Idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            # Bazı ortamlar stdout'u sarmalayıp yeniden yapılandırmaya izin
            # vermiyor; orada zaten UTF-8 olma ihtimali yüksek, sessizce geç.
            pass

    _CONFIGURED = True
