"""
HoopLife NBA - tek kaynaklı tasarım sistemi.

Önceden her sayfa kendi CSS'ini ve kendi arka plan fotoğrafını yüklüyordu
(11 dosyada 21 ayrı <style> bloğu, 4 farklı arka plan görseli). Sonuç
her sayfanın başka bir siteymiş gibi durmasıydı.

Burada tanımlanan token'lar (renk, boşluk, yarıçap, tipografi) ve temel
bileşen stilleri bütün sayfalar için ortak zemini kurar. Sayfalar kendi
özel bileşenlerini yine tanımlayabilir ama renk/boşluk değerlerini
buradaki değişkenlerden almalıdır:

    var(--bg-page)      sayfa zemini
    var(--bg-panel)     ana içerik paneli
    var(--bg-card)      kart / kutu
    var(--bg-raised)    kart üstü vurgulu yüzey
    var(--border)       standart kenarlık
    var(--text)         ana metin
    var(--text-dim)     ikincil metin
    var(--accent)       marka kırmızısı
    var(--space-1..5)   boşluk ölçeği
    var(--radius-sm/md/lg)
"""

import streamlit as st


def load_styles():
    st.markdown("""
    <style>

    /* ===============================================================
       1. TASARIM TOKEN'LARI
       =============================================================== */
    :root {
        /* Yüzeyler - koyu, nötr, mavi-gri bir skala */
        --bg-page:    #0B0E14;
        --bg-panel:   #12161F;
        --bg-card:    #171C27;
        --bg-raised:  #1E2430;
        --bg-input:   #1A1F2B;

        --border:       #262D3A;
        --border-soft:  #1E2430;
        --border-focus: #3B4657;

        --text:      #E8EAED;
        --text-dim:  #9BA3B0;
        --text-mute: #6B7280;

        --accent:       #C8102E;   /* marka kırmızısı */
        --accent-hover: #A50D26;
        --accent-soft:  rgba(200, 16, 46, 0.14);
        --info:    #4DA6FF;
        --success: #3FBF7F;
        --warn:    #E5A93C;
        --danger:  #E5544B;

        /* Boşluk ölçeği - tüm sayfalar bunları kullanır */
        --space-1: 4px;
        --space-2: 8px;
        --space-3: 14px;
        --space-4: 22px;
        --space-5: 34px;

        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;

        --shadow-sm: 0 1px 2px rgba(0,0,0,.34);
        --shadow-md: 0 6px 20px rgba(0,0,0,.30);

        --font: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI",
                system-ui, sans-serif;
    }

    /* ===============================================================
       2. ZEMİN
       Önceden her sayfa kendi basketbol sahası fotoğrafını yüklüyordu
       (4 farklı görsel) ve metinler fotoğrafın üstünde okunmuyordu.
       Artık tek, sakin ve markalı bir zemin var.
       =============================================================== */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
        background:
            radial-gradient(1100px 620px at 18% -8%,  rgba(200,16,46,.11), transparent 62%),
            radial-gradient(900px  560px at 88% 108%, rgba(77,166,255,.09), transparent 60%),
            var(--bg-page) !important;
        background-attachment: fixed !important;
        color: var(--text);
        font-family: var(--font);
        font-size: 15px;
    }

    /* Sayfaların .stApp arka planını kendi fotoğraflarıyla ezmesini
       engelle - tasarım sistemi tek zemin kullanır. */
    .stApp { background-image: none !important; }
    .stApp::before { background-image: none !important; }

    /* ===============================================================
       3. ANA İÇERİK PANELİ
       =============================================================== */
    [data-testid="stMainBlockContainer"],
    section.main > div {
        background-color: var(--bg-panel);
        border: 1px solid var(--border-soft);
        border-radius: var(--radius-lg);
        padding: var(--space-5) calc(var(--space-5) - 4px);
        margin: var(--space-3) var(--space-4);
        box-shadow: var(--shadow-md);
    }

    [data-testid="stMain"] { background: transparent; }

    /* ===============================================================
       4. TİPOGRAFİ
       =============================================================== */
    h1, h2, h3, h4 { color: var(--text); font-family: var(--font); }
    h1 { font-size: 1.55rem; font-weight: 750; letter-spacing: -.2px;
         margin: 0 0 var(--space-2) 0; }
    h2 { font-size: 1.18rem; font-weight: 700; letter-spacing: -.1px;
         margin: var(--space-4) 0 var(--space-2) 0;
         padding-bottom: var(--space-2);
         border-bottom: 1px solid var(--border-soft); }
    h3 { font-size: 1.02rem; font-weight: 650;
         margin: var(--space-3) 0 var(--space-1) 0; }
    p, li { color: var(--text); line-height: 1.55; }
    a { color: var(--info); text-decoration: none; }
    a:hover { text-decoration: underline; }
    [data-testid="stCaptionContainer"], .stCaption, small {
        color: var(--text-dim) !important;
    }
    hr { border-color: var(--border-soft); margin: var(--space-4) 0; }

    /* ===============================================================
       5. SIDEBAR
       =============================================================== */
    section[data-testid="stSidebar"] {
        background-color: var(--bg-panel);
        border-right: 1px solid var(--border);
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1.1px;
        color: var(--text-mute);
        text-transform: uppercase;
        border: none;
        margin-top: var(--space-3);
    }
    header[data-testid="stHeader"] { display: none; }
    [data-testid="stAppViewContainer"] { padding-top: 0; }

    /* ===============================================================
       6. BUTONLAR
       =============================================================== */
    [data-testid="stButton"] button,
    [data-testid="stFormSubmitButton"] button,
    [data-testid="stDownloadButton"] button {
        border-radius: var(--radius-sm);
        font-weight: 600;
        letter-spacing: .2px;
        min-height: 40px;
        transition: background-color .16s ease, border-color .16s ease,
                    transform .06s ease;
    }
    [data-testid="stButton"] button:active { transform: translateY(1px); }

    button[kind="primary"], button[data-testid="baseButton-primary"] {
        background-color: var(--accent) !important;
        color: #fff !important;
        border: 1px solid var(--accent) !important;
    }
    button[kind="primary"]:hover, button[data-testid="baseButton-primary"]:hover {
        background-color: var(--accent-hover) !important;
        border-color: var(--accent-hover) !important;
    }
    button[kind="secondary"], button[data-testid="baseButton-secondary"] {
        background-color: var(--bg-card) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
    }
    button[kind="secondary"]:hover {
        background-color: var(--bg-raised) !important;
        border-color: var(--border-focus) !important;
    }

    /* ===============================================================
       7. GİRDİLER
       =============================================================== */
    input, textarea,
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    [data-testid="stNumberInput"] input,
    [data-testid="stTextInput"] input,
    [data-testid="stDateInput"] input {
        background-color: var(--bg-input) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
    }
    input:focus, textarea:focus { border-color: var(--border-focus) !important; }
    [data-testid="stWidgetLabel"] label,
    [data-testid="stWidgetLabel"] p {
        color: var(--text-dim) !important;
        font-size: .86rem !important;
        font-weight: 600 !important;
    }

    /* ===============================================================
       8. KAPSAYICILAR / KARTLAR / TABLOLAR
       =============================================================== */
    [data-testid="stDataFrame"],
    [data-testid="stTable"] {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: var(--radius-md);
        overflow: hidden;
    }

    /* st.container(border=True) */
    [data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"] {
        gap: var(--space-2);
    }
    div[data-testid="stExpander"] details {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: var(--radius-md);
    }
    div[data-testid="stExpander"] summary {
        color: var(--text-dim);
        font-size: .9rem;
        font-weight: 600;
    }

    [data-testid="stMetric"] {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: var(--radius-md);
        padding: var(--space-3);
    }
    [data-testid="stMetricLabel"] { color: var(--text-dim) !important; }

    /* Uyarı / bilgi kutuları */
    [data-testid="stAlert"] {
        border-radius: var(--radius-md);
        border: 1px solid var(--border);
    }

    /* Sekmeler */
    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: var(--space-1);
        border-bottom: 1px solid var(--border-soft);
    }
    [data-testid="stTabs"] button[data-baseweb="tab"] {
        color: var(--text-dim);
        font-weight: 600;
    }
    [data-testid="stTabs"] button[aria-selected="true"] { color: var(--text); }

    /* ===============================================================
       9. KAYDIRMA ÇUBUĞU
       =============================================================== */
    ::-webkit-scrollbar { width: 9px; height: 9px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb {
        background-color: var(--border);
        border-radius: 6px;
    }
    ::-webkit-scrollbar-thumb:hover { background-color: var(--border-focus); }

    /* ===============================================================
       10. MOBİL
       =============================================================== */
    @media (max-width: 768px) {
        html, body, [data-testid="stAppViewContainer"] { font-size: 15px; }
        [data-testid="stMainBlockContainer"],
        section.main > div {
            margin: 0 !important;
            border-radius: 0 !important;
            border-left: none !important;
            border-right: none !important;
            padding: var(--space-3) var(--space-3) var(--space-5) !important;
            box-shadow: none !important;
        }
        h1 { font-size: 1.3rem; }
        h2 { font-size: 1.08rem; margin-top: var(--space-3); }
        h3 { font-size: 1rem; }
    }

    </style>
    """, unsafe_allow_html=True)
