"""
Metin yardimcilari.

Uygulamanin bircok yeri Streamlit'in ``unsafe_allow_html=True`` yolunu
kullaniyor. Bu yol adi gibi: verilen metin HTML olarak islenir. Kullanici
yazisi (izleme listesi notlari, eposta, kaydedilmis draft adi) oraya duz
gecince yazilan etiket calisiyordu.

Su an her kullanici yalnizca kendi yazdigini gordugu icin bu kendine
zarar kategorisinde; ama paylasilan bir sey eklendigi gun (sıralama
tablosu, paylasilabilir draft linki) oyle kalmaz. Bu yuzden kacis,
kullanilan yerde degil, kaynakta yapiliyor.
"""
import html


def esc(value, default=""):
    """
    Bir degeri HTML icine gomulebilir hale getirir.

    None ve bos degerler icin ``default`` doner; tirnaklar da kacirilir
    ki deger bir oznitelik icine konuldugunda da guvenli olsun.
    """
    if value is None:
        return default
    text = str(value)
    if not text:
        return default
    return html.escape(text, quote=True)
