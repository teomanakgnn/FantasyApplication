import requests
import urllib.parse
import json

# ==========================================
# BURAYI DOLDURUN (Doğrudan yapıştırın)
# ==========================================
LEAGUE_ID = 987023001
# Gizli sekmeden aldığınız espn_s2 (uzun olan):
RAW_ESPN_S2 ="***KALDIRILDI***"
# Gizli sekmeden aldığınız swid ({...} süslü parantezli olan):
RAW_SWID = "***KALDIRILDI***" 

# ==========================================
# TEST KODU
# ==========================================

# 1. Cookie Hazırlığı
cookies = {}
if RAW_ESPN_S2 and RAW_SWID:
    # URL Decode işlemi (Örn: %2B -> +)
    decoded_s2 = urllib.parse.unquote(RAW_ESPN_S2)
    cookies['espn_s2'] = decoded_s2
    cookies['SWID'] = RAW_SWID
    print(f"✅ Cookie Hazırlandı.")
    print(f"   SWID: {RAW_SWID}")
    print(f"   S2 (İlk 20 hane): {decoded_s2[:20]}...")
else:
    print("❌ UYARI: Cookie bilgileri boş! Lütfen dosyanın başındaki alanları doldurun.")
    exit()

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "x-fantasy-filter": '{"players":{"filterStatus":{"value":["FREEAGENT","WAIVERS"]}}}'
}

# 2. Bağlantı Testi (Sırayla 3 Endpoint)
urls = [
    # 1. League History (En Güvenlisi)
    f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/fba/leagueHistory/{LEAGUE_ID}?view=mSettings",
    # 2. 2026 Sezonu
    f"https://fantasy.espn.com/apis/v3/games/fba/seasons/2026/segments/0/leagues/{LEAGUE_ID}?view=mSettings",
]

print(f"\n🚀 Bağlantı Testi Başlıyor (Lig ID: {LEAGUE_ID})...")

success = False
for url in urls:
    print(f"\nTesting URL: {url}")
    try:
        r = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        print(f"   Status Code: {r.status_code}")
        
        if r.status_code == 200:
            try:
                data = r.json()
                
                # History array döner
                if isinstance(data, list) and len(data) > 0:
                    team_count = len(data[0].get('teams', []))
                    print(f"   ✅ BAŞARILI! (History Modu)")
                    print(f"   Takım Sayısı: {team_count}")
                    success = True
                    break
                    
                # Sezon dict döner
                elif isinstance(data, dict):
                    if 'messages' in data and 'No permission' in str(data['messages']):
                         print("   ❌ Yetki Yok (Permission Denied Message)")
                    else:
                        team_count = len(data.get('teams', [])) or len(data.get('settings', {}))
                        print(f"   ✅ BAŞARILI! (Sezon Modu)")
                        print(f"   Veri Tipi: {type(data)}")
                        success = True
                        break
            except json.JSONDecodeError:
                print("   ⚠️ HTML Döndü (Login Sayfası)")
                # HTML'in başını yazdıralım ki ne dediğini görelim
                print(f"   HTML Başlığı: {r.text[:100]}")
        elif r.status_code == 401:
            print("   ⛔ 401 Unauthorized (Cookie Geçersiz)")
        else:
            print(f"   ❌ Hata: {r.status_code}")
            
    except Exception as e:
        print(f"   💥 Bağlantı Hatası: {e}")

if success:
    print("\n🎉 SONUÇ: Cookie'leriniz çalışıyor! Sorun kodun entegrasyonunda.")
else:
    print("\n💀 SONUÇ: Cookie'leriniz geçersiz veya ESPN bu IP'yi engelliyor.")