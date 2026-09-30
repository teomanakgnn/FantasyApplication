"""
Paylasilabilir PNG kartlari.

Alt/ust tahminleri WhatsApp'a, Instagram hikayesine vb. atilabilsin diye
sunucuda tek bir gorsel olarak ciziliyor. Tarayicida ekran goruntusu
almak (html2canvas vb.) ESPN logolarinda CORS yuzunden bos kutu
birakiyordu; burada logolar sunucudan cekilip dogrudan resme basiliyor.

Olcu 1080x1350 (4:5): WhatsApp ve Instagram onizlemede kirpmadan
gosteriyor, telefonda tam ekran okunuyor.

Yazi tipi depoda (assets/fonts, Inter, SIL OFL): sunucudaki sistem
yazi tiplerine guvenilemiyor, Pillow'un varsayilani ise kalin yazamiyor.
"""
import io
import os

import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FONTS = os.path.join(_ROOT, "assets", "fonts")
_BRAND_LOGO = os.path.join(_ROOT, "HoopLifeNBA_logo.png")

WIDTH, HEIGHT = 1080, 1350

BG = (15, 19, 27)
CARD = (23, 28, 39)
LINE = (38, 45, 60)
TEXT = (232, 236, 244)
MUTED = (140, 153, 178)
DIM = (107, 120, 147)
OVER_BG, OVER_FG = (57, 135, 229), (255, 255, 255)
UNDER_BG, UNDER_FG = (230, 103, 103), (255, 255, 255)
NONE_BG, NONE_FG = (40, 46, 60), (140, 153, 178)


def _font(weight, size):
    path = os.path.join(_FONTS, f"Inter-{weight}.otf")
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default(size)


@st.cache_data(ttl=604800, show_spinner=False)
def _logo_bytes(url):
    """Takim logosu (ham PNG baytlari). Ulasilamazsa None."""
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        return resp.content
    except Exception:
        return None


def _logo(url, size):
    data = _logo_bytes(url)
    if not data:
        return None
    try:
        image = Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None
    image.thumbnail((size, size), Image.LANCZOS)
    return image


def _brand(height):
    try:
        image = Image.open(_BRAND_LOGO).convert("RGBA")
    except Exception:
        return None
    ratio = height / image.height
    return image.resize((int(image.width * ratio), height), Image.LANCZOS)


def _pill(draw, box, label, bg, fg, font):
    draw.rounded_rectangle(box, radius=12, fill=bg)
    x0, y0, x1, y1 = box
    draw.text(((x0 + x1) / 2, (y0 + y1) / 2), label, font=font, fill=fg,
              anchor="mm")


def _team_row(canvas, draw, x, y, width, row, pick, look):
    height = 64
    draw.rounded_rectangle((x, y, x + width, y + height - 8), radius=12, fill=CARD)
    logo = _logo(look.get("logo"), 40)
    if logo:
        canvas.paste(logo, (x + 12 + (40 - logo.width) // 2,
                            y + 8 + (40 - logo.height) // 2), logo)
    name = look.get("short") or row["team_name"]
    draw.text((x + 64, y + 28), name, font=_font("Bold", 24), fill=TEXT, anchor="lm")
    draw.text((x + width - 150, y + 28), f"{row['line']:.1f}",
              font=_font("ExtraBold", 26), fill=TEXT, anchor="rm")

    if pick == "over":
        label, bg, fg = "OVER", OVER_BG, OVER_FG
    elif pick == "under":
        label, bg, fg = "UNDER", UNDER_BG, UNDER_FG
    else:
        label, bg, fg = "-", NONE_BG, NONE_FG
    _pill(draw, (x + width - 128, y + 11, x + width - 12, y + 45), label, bg, fg,
          _font("ExtraBold", 19))


def _split(rows):
    """Dogu solda, Bati sagda; konferans bilinmiyorsa baremle ikiye bol."""
    east = [r for r in rows if (r.get("conf") or "").startswith("East")]
    west = [r for r in rows if (r.get("conf") or "").startswith("West")]
    if len(east) + len(west) != len(rows):
        ordered = sorted(rows, key=lambda r: -r["line"])
        half = (len(ordered) + 1) // 2
        return ("", ordered[:half]), ("", ordered[half:])
    key = lambda r: -r["line"]
    return ("EAST", sorted(east, key=key)), ("WEST", sorted(west, key=key))


def over_under_card(season_label, rows, picks, identity, owner=None,
                    site="hooplifenba.com"):
    """
    Kullanicinin 30 takimlik alt/ust tahminlerini tek bir PNG'ye cizer.

    rows: [{team, team_name, line, conf}], picks: {team: 'over'|'under'},
    identity: get_team_identity() ciktisi.

    Returns:
        bytes - PNG.
    """
    canvas = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(canvas)
    margin = 44

    # Baslik
    brand = _brand(58)
    title_x = margin
    if brand:
        canvas.paste(brand, (margin, 40), brand)
        title_x = margin + brand.width + 20
    draw.text((title_x, 46), f"OVER / UNDER {season_label}",
              font=_font("ExtraBold", 44), fill=TEXT)
    who = f"{owner}'s season win total picks" if owner else "Season win total picks"
    draw.text((title_x, 100), who, font=_font("Medium", 24), fill=MUTED)

    # Ozet serit
    overs = sum(1 for v in picks.values() if v == "over")
    unders = sum(1 for v in picks.values() if v == "under")
    y = 162
    stats = [(str(overs), "OVER", OVER_BG), (str(unders), "UNDER", UNDER_BG),
             (f"{len(picks)}/{len(rows)}", "CALLED", MUTED)]
    box_w = (WIDTH - 2 * margin - 2 * 16) / 3
    for i, (value, label, colour) in enumerate(stats):
        x0 = margin + i * (box_w + 16)
        draw.rounded_rectangle((x0, y, x0 + box_w, y + 76), radius=14, fill=CARD)
        draw.rectangle((x0, y + 14, x0 + 4, y + 62), fill=colour)
        draw.text((x0 + 24, y + 38), value, font=_font("ExtraBold", 36),
                  fill=TEXT, anchor="lm")
        draw.text((x0 + box_w - 20, y + 38), label, font=_font("Bold", 18),
                  fill=DIM, anchor="rm")

    # Iki sutun takim
    col_w = (WIDTH - 2 * margin - 24) // 2
    top = 268
    for index, (heading, group) in enumerate(_split(rows)):
        x = margin + index * (col_w + 24)
        if heading:
            draw.text((x + 4, top), heading, font=_font("ExtraBold", 18),
                      fill=DIM, anchor="lm")
        draw.text((x + col_w - 150, top), "LINE", font=_font("Bold", 16),
                  fill=DIM, anchor="rm")
        draw.text((x + col_w - 70, top), "PICK", font=_font("Bold", 16),
                  fill=DIM, anchor="mm")
        y = top + 22
        for row in group:
            _team_row(canvas, draw, x, y, col_w, row, picks.get(row["team"]),
                      identity.get(row["team"], {}))
            y += 64

    # Alt bilgi
    draw.line((margin, HEIGHT - 70, WIDTH - margin, HEIGHT - 70), fill=LINE, width=2)
    draw.text((margin, HEIGHT - 38), "Lines: Las Vegas season win totals",
              font=_font("Medium", 20), fill=DIM, anchor="lm")
    draw.text((WIDTH - margin, HEIGHT - 38), f"Make yours at {site}",
              font=_font("Bold", 22), fill=TEXT, anchor="rm")

    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()
