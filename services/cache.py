"""
Sureli bellek onbellegi (Streamlit'in st.cache_data'sinin yerine).

Ayni argumanlarla gelen cagriyi, sure dolana kadar ilk sonucla yanitlar.
Ayni anahtar icin ayni anda gelen iki istek, pahali islemi iki kez
calistirmaz: ikincisi birincinin bitmesini bekler (ESPN'e ayni anda
otuz istek yagmasin diye).

Donen deger paylasilir. pandas DataFrame gibi degistirilebilir nesneler
cagiran tarafta degistirilecekse once kopyalanmali; st.cache_data
her seferinde kopya donduruyordu, bu yuzden kopyalama burada da
varsayilan olarak acik.
"""
import copy
import functools
import threading
import time

_REGISTRY = []


def _key(args, kwargs):
    try:
        return (args, tuple(sorted(kwargs.items())))
    except TypeError:
        return repr((args, sorted(kwargs.items())))


def cache_data(ttl=None, show_spinner=None, copy_result=True, max_entries=256):
    """
    Dekorator. ``ttl`` saniye cinsinden (None = surec boyunca).

    ``show_spinner`` Streamlit uyumlulugu icin kabul edilip yok sayilir.
    ``_`` ile baslayan anahtar kelime argumanlari da Streamlit'teki gibi
    anahtara girmez.
    """
    def wrap(func):
        store = {}
        locks = {}
        guard = threading.Lock()

        @functools.wraps(func)
        def inner(*args, **kwargs):
            visible = {k: v for k, v in kwargs.items() if not k.startswith("_")}
            key = _key(args, visible)
            now = time.time()
            hit = store.get(key)
            if hit is not None and (ttl is None or now - hit[0] < ttl):
                return copy.deepcopy(hit[1]) if copy_result else hit[1]

            with guard:
                lock = locks.setdefault(key, threading.Lock())
            with lock:
                hit = store.get(key)
                if hit is not None and (ttl is None or time.time() - hit[0] < ttl):
                    return copy.deepcopy(hit[1]) if copy_result else hit[1]
                value = func(*args, **kwargs)
                if len(store) >= max_entries:
                    oldest = min(store, key=lambda k: store[k][0])
                    store.pop(oldest, None)
                store[key] = (time.time(), value)
                return copy.deepcopy(value) if copy_result else value

        def clear():
            store.clear()

        inner.clear = clear
        _REGISTRY.append(inner)
        return inner

    return wrap


def clear_all():
    for func in _REGISTRY:
        func.clear()
