from __future__ import annotations

import html

import streamlit as st


def apply_global_theme() -> None:
    st.markdown(
        """
        <style>
        :root{
            --bg:#07111f;
            --bg-soft:#0b1628;
            --surface:#0f1b2d;
            --surface-2:#13233a;
            --surface-3:#182b45;
            --surface-4:#1c3352;
            --line:rgba(148,163,184,.14);
            --line-strong:rgba(148,163,184,.24);
            --text:#ecf3ff;
            --muted:#9db0c7;
            --muted-2:#7f93ad;
            --brand:#4f8cff;
            --brand-2:#2f6df6;
            --brand-soft:rgba(79,140,255,.14);
            --success:#22c55e;
            --warning:#f59e0b;
            --danger:#ef4444;
            --shadow:0 16px 40px rgba(0,0,0,.24);
            --shadow-strong:0 24px 64px rgba(0,0,0,.34);
            --radius:20px;
        }

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(79,140,255,.12), transparent 24%),
                radial-gradient(circle at top left, rgba(56,189,248,.05), transparent 18%),
                linear-gradient(180deg, #06101d 0%, #091526 100%);
            color: var(--text);
        }

        [data-testid="stAppViewContainer"] { background: transparent; }
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1.35rem !important;
            max-width: 1500px;
        }
        .app-shell{padding:.05rem 0 .7rem 0;}

        .app-topbar{
            display:flex;align-items:center;justify-content:space-between;gap:1rem;
            padding:.8rem .95rem;border:1px solid var(--line);border-radius:22px;
            background: linear-gradient(135deg, rgba(10,20,36,.92), rgba(14,29,48,.9));
            box-shadow:0 14px 32px rgba(0,0,0,.2);color:var(--text);margin-bottom:.75rem;
            backdrop-filter:blur(10px);
        }
        .app-topbar .title-wrap{display:flex;align-items:center;gap:.8rem;min-width:0;}
        .app-topbar .title-icon{
            width:2.4rem;height:2.4rem;border-radius:14px;display:flex;align-items:center;justify-content:center;
            background:linear-gradient(135deg, rgba(79,140,255,.18), rgba(47,109,246,.24));
            border:1px solid rgba(79,140,255,.18);font-size:1.05rem;box-shadow:inset 0 1px 0 rgba(255,255,255,.06);
        }
        .app-topbar .eyebrow{margin:0 0 .12rem 0;color:#8fa4c0;font-size:.72rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;}
        .app-topbar h1{margin:0;font-size:1.08rem;font-weight:800;letter-spacing:-0.02em;line-height:1.1;}
        .app-topbar p{margin:.16rem 0 0 0;color:#b6c7df;font-size:.82rem;line-height:1.2;}

        .app-chip,.section-chip{
            display:inline-block;padding:.24rem .62rem;border-radius:999px;
            background:rgba(79,140,255,.12);border:1px solid rgba(79,140,255,.18);
            color:#dcebff;font-size:.73rem;font-weight:700;margin-right:.38rem;
        }

        .page-hero{
            padding:.95rem 1rem;border:1px solid var(--line);border-radius:22px;
            background:linear-gradient(135deg, rgba(12,24,42,.94), rgba(18,35,58,.9));
            box-shadow:0 14px 28px rgba(0,0,0,.18);margin-bottom:.8rem;
        }
        .page-hero h2{margin:.12rem 0 0 0;font-size:1.15rem;font-weight:800;letter-spacing:-0.02em;line-height:1.15;}
        .page-hero p{margin:.34rem 0 0 0;color:#c0d0e6;font-size:.88rem;line-height:1.4;}

        .section-card{
            border:1px solid var(--line);border-radius:20px;padding:.9rem .95rem .85rem .95rem;
            background:linear-gradient(180deg, rgba(15,27,45,.98), rgba(18,35,58,.98));
            box-shadow:var(--shadow);margin-bottom:.95rem;
        }
        .section-card h3{margin:.1rem 0 .25rem 0;font-size:1.02rem;}
        .section-card p{margin:0;color:var(--muted);font-size:.86rem;}
        .subtle-card{
            border:1px solid var(--line);border-radius:18px;padding:.9rem 1rem;
            background:rgba(12,24,42,.72);box-shadow:0 10px 24px rgba(0,0,0,.14);
        }
        .entity-list-item{
            border:1px solid rgba(148,163,184,.12);border-radius:16px;padding:.75rem .85rem;
            background:rgba(10,19,34,.64);margin-bottom:.55rem;
        }
        .entity-list-item strong{display:block;margin-bottom:.1rem;}
        .entity-list-item small{color:var(--muted);}
        .soft-divider{height:1px;background:linear-gradient(90deg, transparent, rgba(148,163,184,.18), transparent);margin:.65rem 0 .8rem 0;}

        .stSidebar {background: linear-gradient(180deg, #07111f 0%, #0a1525 100%);}
        section[data-testid="stSidebar"] {border-right: 1px solid rgba(255,255,255,.05);}
        section[data-testid="stSidebar"] .block-container{
            padding-top:.9rem !important;padding-left:.9rem !important;padding-right:.9rem !important;
        }

        .sidebar-user{
            padding:.95rem 1rem;border-radius:20px;
            background:linear-gradient(180deg, rgba(255,255,255,.045), rgba(255,255,255,.03));
            border:1px solid rgba(255,255,255,.07);color:var(--text);margin-bottom:.8rem;
            box-shadow:0 14px 34px rgba(0,0,0,.22);
        }
        .sidebar-user .name{font-size:1rem;font-weight:800;margin-bottom:.18rem;}
        .sidebar-user .meta{font-size:.78rem;color:#c0d0e6;}
        .sidebar-section{
            font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;
            color:#8fa4c0;font-weight:800;margin:.9rem .2rem .42rem .2rem;
        }

        section[data-testid="stSidebar"] button[kind],
        section[data-testid="stSidebar"] .stButton > button {
            min-height:2.7rem;border-radius:14px !important;
            border:1px solid rgba(255,255,255,.07) !important;
            background:linear-gradient(180deg, rgba(255,255,255,.035), rgba(255,255,255,.02)) !important;
            color:#e6eefc !important;font-size:.9rem !important;font-weight:600 !important;
            box-shadow:none !important;transition:.18s ease;
        }
        section[data-testid="stSidebar"] .stButton > button:hover {
            transform:translateY(-1px);background:rgba(255,255,255,.07) !important;
            border-color:rgba(255,255,255,.12) !important;
        }
        section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background:linear-gradient(135deg, var(--brand), var(--brand-2)) !important;
            color:white !important;border-color:transparent !important;
            box-shadow:0 12px 24px rgba(47,109,246,.30) !important;
        }

        .stButton > button, .stDownloadButton > button {
            border-radius:14px !important;min-height:2.6rem;
            border:1px solid var(--line-strong) !important;
            box-shadow:0 8px 18px rgba(0,0,0,.18) !important;font-weight:600 !important;
            background:linear-gradient(180deg, rgba(19,35,58,.98), rgba(15,27,45,.98)) !important;
            color:var(--text) !important;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            border-color:rgba(79,140,255,.32) !important;
            background:linear-gradient(180deg, rgba(22,40,66,.98), rgba(16,29,48,.98)) !important;
        }
        .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"]{
            background:linear-gradient(135deg, var(--brand), var(--brand-2)) !important;
            border-color:transparent !important; color:#fff !important;
            box-shadow:0 16px 32px rgba(47,109,246,.28) !important;
        }

        .stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input,
        .stTimeInput input, [data-baseweb="input"] > div {
            border-radius:14px !important;background:rgba(12,24,42,.92) !important;
            color:var(--text) !important;border:1px solid var(--line) !important;
        }
        .stSelectbox div[data-baseweb="select"] > div,
        .stMultiSelect div[data-baseweb="select"] > div {
            border-radius:14px !important;background:rgba(12,24,42,.92) !important;
            color:var(--text) !important;border:1px solid var(--line) !important;
        }
        .stCheckbox label, .stRadio label {color: var(--text) !important;}
        .stForm{
            border:1px solid var(--line);border-radius:22px;padding:1rem 1rem .7rem 1rem;
            background:linear-gradient(180deg, rgba(10,19,34,.92), rgba(15,27,45,.92));
            box-shadow:var(--shadow);
        }

        label, .stMarkdown, p, span, div {color:inherit;}
        h1, h2, h3 {letter-spacing:-0.02em;}

        [data-testid="stMetric"] {
            border:1px solid var(--line);border-radius:18px;padding:.95rem 1rem;
            background:linear-gradient(180deg, rgba(15,27,45,.98), rgba(18,35,58,.98));
            box-shadow:var(--shadow);
        }
        [data-testid="stMetricLabel"], [data-testid="stMetricDelta"] {color:var(--muted) !important;}
        [data-testid="stMetricValue"] {color:var(--text) !important;}

        [data-testid="stDataFrame"] {
            border-radius:18px;overflow:hidden;border:1px solid var(--line);
            box-shadow:var(--shadow);background:var(--surface);
        }
        [data-testid="stDataFrame"] [role="columnheader"] {
            background:linear-gradient(180deg, rgba(24,43,69,.98), rgba(18,35,58,.98)) !important;
            color:#dbe9ff !important;border-bottom:1px solid rgba(148,163,184,.18) !important;
            font-weight:700 !important;
        }
        [data-testid="stDataFrame"] [role="gridcell"] {
            background:rgba(11,22,40,.96) !important;
            color:#e8f1ff !important;border-bottom:1px solid rgba(148,163,184,.08) !important;
        }
        [data-testid="stDataFrame"] [role="row"]:hover [role="gridcell"] {background:rgba(20,36,59,.98) !important;}
        [data-testid="stDataFrameResizable"] {border-radius:18px !important;}

        div[data-testid="stExpander"]{
            border:1px solid var(--line);border-radius:18px !important;
            background:linear-gradient(180deg, rgba(15,27,45,.98), rgba(18,35,58,.98));
            box-shadow:var(--shadow);
        }
        .js-plotly-plot .plotly .main-svg, .js-plotly-plot .plotly .bg {border-radius:18px;}
        [data-testid="stAlert"] {
            border-radius:18px !important;border:1px solid var(--line) !important;
            background:linear-gradient(180deg, rgba(15,27,45,.96), rgba(18,35,58,.96)) !important;
        }
        .stTabs [data-baseweb="tab-list"] {gap:.35rem;}
        .stTabs [data-baseweb="tab"] {border-radius:12px 12px 0 0;background:rgba(255,255,255,.03);}
        .stCaption {color:var(--muted) !important;}

        @media (max-width: 768px) {
            .block-container {padding-left:.9rem !important;padding-right:.9rem !important;}
            [data-testid="column"] {min-width:48% !important;}
            .stDataFrame {font-size:.78rem;}
            .app-topbar,.page-hero{padding:.78rem .85rem;border-radius:18px;}
            .app-topbar .title-icon{width:2.15rem;height:2.15rem;border-radius:12px;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_user(usuario_or_nome, perfil: str | None = None, email: str | None = None) -> None:
    """Compatível com chamadas antigas e novas.

    Aceita:
    - render_sidebar_user(usuario_dict, role_label)
    - render_sidebar_user(nome, perfil, email)
    """
    if isinstance(usuario_or_nome, dict):
        usuario = usuario_or_nome
        nome = usuario.get("nome") or "Usuário"
        email_final = usuario.get("email") or email
        perfil_final = perfil or usuario.get("role_label") or usuario.get("role") or "Usuário"
    else:
        nome = str(usuario_or_nome or "Usuário")
        email_final = email
        perfil_final = perfil or "Usuário"

    nome = html.escape(str(nome))
    perfil_final = html.escape(str(perfil_final))
    email_final = html.escape(str(email_final)) if email_final else ""

    email_html = (
        f"<div class='meta'>{perfil_final} · {email_final}</div>"
        if email_final
        else f"<div class='meta'>{perfil_final}</div>"
    )
    st.sidebar.markdown(
        f"""
        <div class="sidebar-user">
            <div class="name">{nome}</div>
            {email_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_topbar(title_or_usuario, subtitle: str = "") -> None:
    """Compatível com chamadas antigas e novas.

    Aceita:
    - render_topbar(titulo, subtitulo)
    - render_topbar(usuario_dict, pagina_atual)
    """
    if isinstance(title_or_usuario, dict):
        usuario = title_or_usuario
        title = subtitle or "Dashboard"
        nome = usuario.get("nome") or "Usuário"
        role_label = usuario.get("role_label") or usuario.get("role") or "Usuário"
        subtitle = f"{nome} · {role_label}"
    else:
        title = str(title_or_usuario or "")

    title = html.escape(title)
    subtitle = html.escape(subtitle) if subtitle else ""
    subt_html = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f"""
        <div class="app-topbar">
            <div class="title-wrap">
                <div class="title-icon">🧭</div>
                <div>
                    <div class="eyebrow">Área atual</div>
                    <h1>{title}</h1>
                    {subt_html}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_intro(title: str, description: str, chip: str | None = None) -> None:
    title = html.escape(str(title))
    description = html.escape(str(description))
    chip_html = f"<span class='section-chip'>{html.escape(str(chip))}</span>" if chip else ""
    st.markdown(
        f"""
        <div class="page-hero">
            {chip_html}
            <h2>{title}</h2>
            <p>{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_intro(title: str, description: str = "") -> None:
    desc = f"<p>{description}</p>" if description else ""
    st.markdown(
        f"""
        <div class="section-card">
            <h3>{title}</h3>
            {desc}
        </div>
        """,
        unsafe_allow_html=True,
    )
