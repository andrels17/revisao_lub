from __future__ import annotations

import streamlit as st


def apply_global_theme() -> None:
    st.markdown(
        """
        <style>
        :root{
            --bg:#f8fafc;
            --surface:#ffffff;
            --surface-soft:#f8fafc;
            --line:rgba(148,163,184,.18);
            --text:#0f172a;
            --muted:#64748b;
            --brand:#2563eb;
            --brand-2:#1d4ed8;
            --shadow:0 12px 30px rgba(15,23,42,.06);
            --shadow-strong:0 22px 60px rgba(2,6,23,.16);
        }

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(37,99,235,.06), transparent 22%),
                linear-gradient(180deg, #f8fafc 0%, #eff6ff 100%);
            color: var(--text);
        }

        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1.2rem !important;
            max-width: 1500px;
        }

        .app-shell{
            padding: .15rem 0 .75rem 0;
        }

        .app-topbar{
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:1rem;
            padding: 1rem 1.1rem;
            border:1px solid var(--line);
            border-radius: 24px;
            background: linear-gradient(135deg, rgba(15,23,42,.98), rgba(30,41,59,.95));
            box-shadow: var(--shadow-strong);
            color:#f8fafc;
            margin-bottom: .9rem;
        }

        .app-topbar h1{
            margin:0;
            font-size:1.35rem;
            font-weight:800;
            letter-spacing:-0.02em;
        }

        .app-topbar p{
            margin:.22rem 0 0 0;
            color:#cbd5e1;
            font-size:.9rem;
        }

        .app-chip{
            display:inline-block;
            padding:.22rem .62rem;
            border-radius:999px;
            background:rgba(255,255,255,.08);
            border:1px solid rgba(255,255,255,.12);
            color:#e2e8f0;
            font-size:.73rem;
            font-weight:700;
            margin-right:.38rem;
        }

        .stSidebar {
            background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
        }

        section[data-testid="stSidebar"] {
            border-right: 1px solid rgba(255,255,255,.06);
        }

        section[data-testid="stSidebar"] .block-container{
            padding-top: .9rem !important;
            padding-left: .9rem !important;
            padding-right: .9rem !important;
        }

        .sidebar-user{
            padding: .95rem 1rem;
            border-radius: 20px;
            background: rgba(255,255,255,.06);
            border:1px solid rgba(255,255,255,.08);
            color:#f8fafc;
            margin-bottom: .8rem;
            box-shadow: 0 12px 30px rgba(0,0,0,.15);
        }

        .sidebar-user .name{
            font-size:1rem;
            font-weight:800;
            margin-bottom:.18rem;
        }

        .sidebar-user .meta{
            font-size:.78rem;
            color:#cbd5e1;
        }

        .sidebar-section{
            font-size:.72rem;
            text-transform:uppercase;
            letter-spacing:.08em;
            color:#94a3b8;
            font-weight:800;
            margin: .85rem .2rem .42rem .2rem;
        }

        section[data-testid="stSidebar"] button[kind],
        section[data-testid="stSidebar"] .stButton > button {
            min-height: 2.65rem;
            border-radius: 14px !important;
            border: 1px solid rgba(255,255,255,.08) !important;
            background: rgba(255,255,255,.04) !important;
            color: #e5e7eb !important;
            font-size: .9rem !important;
            font-weight: 600 !important;
            box-shadow: none !important;
            transition: .18s ease;
        }

        section[data-testid="stSidebar"] .stButton > button:hover {
            transform: translateY(-1px);
            background: rgba(255,255,255,.09) !important;
            border-color: rgba(255,255,255,.14) !important;
        }

        section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, var(--brand), var(--brand-2)) !important;
            color: white !important;
            border-color: transparent !important;
            box-shadow: 0 10px 22px rgba(37,99,235,.28) !important;
        }

        .stButton > button,
        .stDownloadButton > button {
            border-radius: 14px !important;
            min-height: 2.6rem;
            border: 1px solid rgba(148,163,184,.22) !important;
            box-shadow: 0 8px 18px rgba(15,23,42,.05);
            font-weight: 600 !important;
        }

        .stTextInput input,
        .stNumberInput input,
        .stTextArea textarea {
            border-radius: 14px !important;
        }

        .stSelectbox div[data-baseweb="select"] > div,
        .stMultiSelect div[data-baseweb="select"] > div,
        .stDateInput input {
            border-radius: 14px !important;
        }

        [data-testid="stMetric"] {
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: .75rem .9rem;
            background: rgba(255,255,255,.98);
            box-shadow: var(--shadow);
        }

        [data-testid="stDataFrame"] {
            border-radius: 18px;
            overflow: hidden;
            border: 1px solid var(--line);
            box-shadow: var(--shadow);
            background: white;
        }

        div[data-testid="stExpander"]{
            border:1px solid var(--line);
            border-radius: 18px !important;
            background: rgba(255,255,255,.98);
            box-shadow: var(--shadow);
        }

        @media (max-width: 768px) {
            .block-container {
                padding-left: .9rem !important;
                padding-right: .9rem !important;
            }
            [data-testid="column"] { min-width: 48% !important; }
            .stDataFrame { font-size: .78rem; }
            .app-topbar{
                padding: .9rem 1rem;
                border-radius: 20px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_topbar(usuario: dict, pagina_atual: str) -> None:
    role = usuario.get("role_label") or usuario.get("role") or "-"
    nome = usuario.get("nome") or "Usuário"
    st.markdown(
        f"""
        <div class="app-shell">
            <div class="app-topbar">
                <div>
                    <span class="app-chip">Sistema operacional</span>
                    <span class="app-chip">{role}</span>
                    <h1>{pagina_atual}</h1>
                    <p>Bem-vindo, <strong>{nome}</strong>. Navegação mais limpa e identidade visual unificada.</p>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:.78rem;color:#cbd5e1;">Módulo atual</div>
                    <div style="font-size:1rem;font-weight:800;">{pagina_atual}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_user(usuario: dict, role_label: str) -> None:
    nome = usuario.get("nome") or "Usuário"
    email = usuario.get("email") or "-"
    st.markdown(
        f"""
        <div class="sidebar-user">
            <div class="name">{nome}</div>
            <div class="meta">{role_label} · {email}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
