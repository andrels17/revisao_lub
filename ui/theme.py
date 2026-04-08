from __future__ import annotations

import html
import streamlit as st


def apply_global_theme() -> None:
    st.markdown(
        """
        <style>
        :root{
            --bg:#0b1120;
            --bg-2:#111827;
            --surface:#111827;
            --surface-2:#172033;
            --surface-3:#1e293b;
            --surface-soft:rgba(15,23,42,.72);
            --line:rgba(148,163,184,.18);
            --line-strong:rgba(148,163,184,.28);
            --text:#e5edf7;
            --text-soft:#cbd5e1;
            --muted:#94a3b8;
            --brand:#3b82f6;
            --brand-2:#2563eb;
            --accent:#22c55e;
            --danger:#ef4444;
            --warning:#f59e0b;
            --shadow:0 18px 48px rgba(2,6,23,.32);
            --shadow-soft:0 10px 28px rgba(2,6,23,.18);
            --radius:20px;
        }

        html, body, [class*="css"] { color: var(--text); }

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(59,130,246,.16), transparent 24%),
                radial-gradient(circle at top left, rgba(34,197,94,.08), transparent 18%),
                linear-gradient(180deg, #0b1120 0%, #0f172a 50%, #111827 100%);
            color: var(--text);
        }

        .main .block-container {
            padding-top: .95rem !important;
            padding-bottom: 1.25rem !important;
            max-width: 1520px;
        }

        h1, h2, h3, h4, h5, h6 {
            color: #f8fafc !important;
            letter-spacing: -0.02em;
        }

        h1 { font-size: 1.8rem !important; font-weight: 800 !important; }
        h2 { font-size: 1.35rem !important; font-weight: 750 !important; }
        h3 { font-size: 1.08rem !important; font-weight: 700 !important; }

        p, li, label, .stCaption, small, div[data-testid="stMarkdownContainer"] p {
            color: var(--text-soft);
        }

        [data-testid="stHeader"] { background: transparent; }

        .app-shell{ padding:.1rem 0 .65rem 0; }
        .app-topbar{
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:1rem;
            padding:1.05rem 1.15rem;
            border:1px solid rgba(148,163,184,.16);
            border-radius:24px;
            background:linear-gradient(135deg, rgba(15,23,42,.96), rgba(30,41,59,.92));
            box-shadow:var(--shadow);
            margin-bottom:.9rem;
            backdrop-filter: blur(10px);
        }
        .app-topbar h1{margin:0;color:#f8fafc !important;font-size:1.35rem !important;font-weight:800 !important;}
        .app-topbar p{margin:.28rem 0 0 0;color:#cbd5e1;font-size:.9rem;}
        .app-topbar-aside{
            min-width:180px;
            padding:.85rem .95rem;
            border-radius:18px;
            border:1px solid rgba(148,163,184,.14);
            background:rgba(255,255,255,.04);
            text-align:right;
        }
        .app-chip{
            display:inline-block;
            padding:.24rem .65rem;
            border-radius:999px;
            background:rgba(255,255,255,.07);
            border:1px solid rgba(255,255,255,.10);
            color:#dbe7f5;
            font-size:.73rem;
            font-weight:700;
            margin-right:.38rem;
            margin-bottom:.2rem;
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0b1220 0%, #101827 100%);
            border-right: 1px solid rgba(255,255,255,.06);
        }
        section[data-testid="stSidebar"] .block-container{
            padding-top:.9rem !important;
            padding-left:.9rem !important;
            padding-right:.9rem !important;
        }
        .sidebar-user{
            padding:1rem;
            border-radius:20px;
            background:linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.04));
            border:1px solid rgba(255,255,255,.09);
            color:#f8fafc;
            margin-bottom:.85rem;
            box-shadow:0 14px 34px rgba(0,0,0,.18);
        }
        .sidebar-user .name{font-size:1rem;font-weight:800;margin-bottom:.18rem;color:#f8fafc;}
        .sidebar-user .meta{font-size:.78rem;color:#cbd5e1;}
        .sidebar-section{
            font-size:.72rem;
            text-transform:uppercase;
            letter-spacing:.08em;
            color:#8ea2bc;
            font-weight:800;
            margin:.9rem .2rem .45rem .2rem;
        }

        .stButton > button,
        .stDownloadButton > button,
        [data-testid="baseButton-secondary"],
        [data-testid="baseButton-primary"]{
            min-height:2.7rem;
            border-radius:14px !important;
            border:1px solid rgba(148,163,184,.16) !important;
            background:linear-gradient(180deg, rgba(30,41,59,.92), rgba(15,23,42,.92)) !important;
            color:#e8eef7 !important;
            font-size:.92rem !important;
            font-weight:650 !important;
            box-shadow:0 10px 22px rgba(2,6,23,.18) !important;
            transition:all .16s ease;
        }
        .stButton > button:hover,
        .stDownloadButton > button:hover {
            transform:translateY(-1px);
            border-color:rgba(148,163,184,.28) !important;
            background:linear-gradient(180deg, rgba(37,99,235,.18), rgba(15,23,42,.96)) !important;
        }
        .stButton > button[kind="primary"],
        .stDownloadButton > button[kind="primary"],
        [data-testid="baseButton-primary"]{
            background:linear-gradient(135deg, var(--brand), var(--brand-2)) !important;
            color:white !important;
            border-color:transparent !important;
            box-shadow:0 14px 28px rgba(37,99,235,.32) !important;
        }

        section[data-testid="stSidebar"] .stButton > button {
            width:100%;
            justify-content:flex-start;
            background:rgba(255,255,255,.04) !important;
            border:1px solid rgba(255,255,255,.07) !important;
            box-shadow:none !important;
        }
        section[data-testid="stSidebar"] .stButton > button:hover {
            background:rgba(255,255,255,.08) !important;
            border-color:rgba(255,255,255,.14) !important;
        }
        section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background:linear-gradient(135deg, rgba(59,130,246,.92), rgba(37,99,235,.92)) !important;
        }

        .stTextInput > div > div > input,
        .stTextArea textarea,
        .stNumberInput input,
        .stDateInput input,
        .stTimeInput input,
        div[data-baseweb="select"] > div,
        .stMultiSelect div[data-baseweb="select"] > div {
            background:rgba(15,23,42,.82) !important;
            color:#f8fafc !important;
            border:1px solid rgba(148,163,184,.18) !important;
            border-radius:14px !important;
            box-shadow:none !important;
        }
        .stTextInput label, .stTextArea label, .stNumberInput label, .stSelectbox label,
        .stMultiSelect label, .stDateInput label, .stTimeInput label, .stRadio label,
        .stCheckbox label, .stSlider label {
            color:#dbe5f3 !important;
            font-weight:600 !important;
        }
        ::placeholder { color:#8aa0ba !important; opacity:1; }

        div[data-testid="stForm"] {
            border:1px solid var(--line);
            border-radius:22px;
            padding:1rem 1rem .8rem 1rem;
            background:linear-gradient(180deg, rgba(15,23,42,.72), rgba(17,24,39,.76));
            box-shadow:var(--shadow-soft);
        }

        [data-testid="stMetric"] {
            border:1px solid var(--line);
            border-radius:18px;
            padding:.75rem .9rem;
            background:linear-gradient(180deg, rgba(17,24,39,.92), rgba(15,23,42,.96));
            box-shadow:var(--shadow-soft);
        }
        [data-testid="stMetricLabel"] { color:#93a8c2 !important; }
        [data-testid="stMetricValue"] { color:#f8fafc !important; }

        [data-testid="stDataFrame"], div[data-testid="stTable"] {
            border-radius:18px;
            overflow:hidden;
            border:1px solid var(--line);
            box-shadow:var(--shadow-soft);
            background:rgba(15,23,42,.82);
        }

        div[data-testid="stExpander"] {
            border:1px solid var(--line) !important;
            border-radius:18px !important;
            background:linear-gradient(180deg, rgba(15,23,42,.7), rgba(17,24,39,.78)) !important;
            box-shadow:var(--shadow-soft) !important;
        }
        details summary p, details summary span { color:#f8fafc !important; }

        [data-baseweb="tab-list"] {
            gap:.4rem;
            background:transparent !important;
        }
        button[role="tab"] {
            border-radius:12px !important;
            border:1px solid rgba(148,163,184,.14) !important;
            background:rgba(15,23,42,.54) !important;
            color:#cbd5e1 !important;
            padding:.55rem .9rem !important;
        }
        button[role="tab"][aria-selected="true"] {
            background:linear-gradient(135deg, rgba(59,130,246,.18), rgba(37,99,235,.12)) !important;
            color:#f8fafc !important;
            border-color:rgba(59,130,246,.36) !important;
        }

        .stAlert {
            border-radius:16px !important;
            border:1px solid rgba(148,163,184,.16) !important;
            background:rgba(15,23,42,.72) !important;
        }

        hr, .stDivider { border-color: rgba(148,163,184,.12) !important; }

        [data-testid="stRadio"] > div {
            background:rgba(15,23,42,.48);
            padding:.35rem;
            border-radius:14px;
            border:1px solid rgba(148,163,184,.14);
        }

        [data-testid="stFileUploader"] {
            border:1px dashed rgba(148,163,184,.24);
            border-radius:18px;
            background:rgba(15,23,42,.45);
            padding:.35rem;
        }

        .stProgress > div > div > div > div {
            background: linear-gradient(90deg, var(--brand), #60a5fa) !important;
        }

        @media (max-width: 900px) {
            .main .block-container {
                padding-left: .85rem !important;
                padding-right: .85rem !important;
            }
            .app-topbar {
                flex-direction:column;
                align-items:flex-start;
                border-radius:20px;
            }
            .app-topbar-aside { width:100%; text-align:left; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_topbar(usuario: dict, pagina_atual: str) -> None:
    role = html.escape(str(usuario.get("role_label") or usuario.get("role") or "-"))
    nome = html.escape(str(usuario.get("nome") or "Usuário"))
    pagina = html.escape(str(pagina_atual))
    st.markdown(
        f"""
        <div class="app-shell">
            <div class="app-topbar">
                <div>
                    <span class="app-chip">Sistema operacional</span>
                    <span class="app-chip">{role}</span>
                    <h1>{pagina}</h1>
                    <p>Bem-vindo, <strong>{nome}</strong>. Interface padronizada, mais suave e com menos poluição visual.</p>
                </div>
                <div class="app-topbar-aside">
                    <div style="font-size:.76rem;color:#94a3b8;">Módulo atual</div>
                    <div style="font-size:1rem;font-weight:800;color:#f8fafc;">{pagina}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_user(usuario: dict, role_label: str) -> None:
    nome = html.escape(str(usuario.get("nome") or "Usuário"))
    email = html.escape(str(usuario.get("email") or "-"))
    role = html.escape(str(role_label or "-"))
    st.markdown(
        f"""
        <div class="sidebar-user">
            <div class="name">{nome}</div>
            <div class="meta">{role} · {email}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
