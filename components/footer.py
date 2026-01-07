import streamlit as st
from services.injuries import get_latest_injuries

def render_injury_footer(scroll_duration=20):
    injuries = get_latest_injuries()
    if not injuries:
        return

    # Injury item html
    items_html = ""
    for i in injuries:
        items_html += f"""
        <div class="injury-item">
            <span class="status-dot {i['status'].lower()}"></span>
            <b>{i['player']}</b> — {i['reason']} ({i['date']})
        </div>
        """

    st.markdown(
        f"""
        <style>
        /* Toggle button as chevron */
        .injury-toggle {{
            position: fixed;
            bottom: 0;
            left: 50%;
            transform: translateX(-50%);
            cursor: pointer;
            font-size: 16px;
            color: #fff;
            background: #1a1d23;
            padding: 6px 12px;
            border-radius: 8px 8px 0 0;
            border: 2px solid #fff; /* Kalın beyaz çizgi */
            z-index: 9999;
            text-align: center;
            font-family: "Inter", sans-serif;
        }}

        /* Footer container hidden by default */
        .injury-footer {{
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            max-height: 200px;
            background: #0e1117;
            color: white;
            padding: 10px 0;
            overflow: hidden;
            font-family: "Inter", sans-serif;
            transform: translateY(100%);
            transition: transform 0.4s ease;
            z-index: 9998;
            border-top: 1px solid #333;
        }}

        /* Show footer on toggle hover */
        .injury-toggle:hover + .injury-footer {{
            transform: translateY(0);
        }}

        /* Horizontal scroll track */
        .injury-track {{
            display: inline-block;
            white-space: nowrap;
            padding-left: 20px;
            animation: scroll-left {scroll_duration}s linear infinite;
        }}

        .injury-footer:hover .injury-track {{
            animation-play-state: paused;
        }}

        .injury-item {{
            margin-right: 50px;
            font-size: 14px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}

        .status-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
        }}

        .status-dot.out {{ background: #ff4b4b; }}
        .status-dot.questionable {{ background: #ffa500; }}
        .status-dot.probable {{ background: #2ecc71; }}

        @keyframes scroll-left {{
            from {{ transform: translateX(100%); }}
            to {{ transform: translateX(-100%); }}
        }}
        </style>

        <!-- Toggle button -->
        <div class="injury-toggle">&#9650; Injury List</div>

        <!-- Footer container -->
        <div class="injury-footer">
            <div class="injury-track">
                {items_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
