"""
DB-IP ucretsiz ulke veritabanini indirir (CC BY 4.0, https://db-ip.com).
Docker kurulumunda calisir; indirilemezse uygulama ulkesiz devam eder.
"""
import datetime
import gzip
import os
import sys
import urllib.request

OUT = os.environ.get("GEOIP_DB", os.path.join(os.path.dirname(__file__), "..", "data", "dbip-country.mmdb"))


def main():
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    today = datetime.date.today()
    months = [today, today.replace(day=1) - datetime.timedelta(days=1)]
    for m in months:
        url = f"https://download.db-ip.com/free/dbip-country-lite-{m:%Y-%m}.mmdb.gz"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (HoopLife geoip)"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = gzip.decompress(resp.read())
            with open(OUT, "wb") as fh:
                fh.write(data)
            print(f"geoip: {url} -> {OUT} ({len(data) // 1024} KB)")
            return 0
        except Exception as exc:
            print(f"geoip: {url} failed: {exc}")
    return 0      # kurulumu dusurme


if __name__ == "__main__":
    sys.exit(main())
