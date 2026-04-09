from __future__ import annotations

import html

import streamlit as st


def apply_global_theme() -> None:
    st.markdown(
        """
        <style>
        /* ── Variáveis ──────────────────────────────────────────────── */
        :root {
            --bg:        #07111f;
            --surface:   #0d1929;
            --surface-2: #111f32;
            --border:    rgba(148,163,184,.12);
            --border-md: rgba(148,163,184,.20);
            --text:      #e8f1ff;
            --muted:     #8fa4c0;
            --muted-2:   #6b84a0;
            --brand:     #4f8cff;
            --brand-2:   #2f6df6;
            --success:   #22c55e;
            --warning:   #f59e0b;
            --danger:    #ef4444;
            --radius:    10px;
            --radius-lg: 14px;
        }

        /* ── Fundo do app ───────────────────────────────────────────── */
        .stApp {
            background: #07111f;
            color: var(--text);
        }
        [data-testid="stAppViewContainer"] { background: transparent; }
        .block-container {
            padding-top: 1.6rem !important;
            padding-bottom: 1.5rem !important;
            max-width: 1440px;
        }

        /* ── Topbar ─────────────────────────────────────────────────── */
        .app-topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: .65rem .9rem;
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            background: var(--surface);
            margin-bottom: .9rem;
        }
        .app-topbar .title-wrap { display: flex; align-items: center; gap: .65rem; }
        .app-topbar .title-icon {
            width: 2rem; height: 2rem; border-radius: 8px;
            display: flex; align-items: center; justify-content: center;
            background: rgba(79,140,255,.12);
            border: 1px solid rgba(79,140,255,.16);
            font-size: .95rem;
        }
        .app-topbar .eyebrow {
            margin: 0 0 .08rem 0; color: var(--muted-2);
            font-size: .68rem; font-weight: 700;
            letter-spacing: .07em; text-transform: uppercase;
        }
        .app-topbar h1  { margin: 0; font-size: 1rem; font-weight: 700; }
        .app-topbar p   { margin: .1rem 0 0; color: var(--muted); font-size: .78rem; }

        /* ── Page hero ──────────────────────────────────────────────── */
        .page-hero {
            margin: .15rem 0 1rem;
        }
        .page-hero h2 {
            margin: .16rem 0 0;
            font-size: 2rem;
            line-height: 1.08;
            font-weight: 800;
            letter-spacing: -.03em;
            color: var(--text);
        }
        .page-hero p {
            margin: .42rem 0 0;
            color: var(--muted);
            font-size: .92rem;
            max-width: 900px;
        }

        /* ── Chip / badge inline ────────────────────────────────────── */
        .app-chip, .section-chip {
            display: inline-block;
            padding: .18rem .5rem;
            border-radius: 999px;
            background: rgba(79,140,255,.10);
            border: 1px solid rgba(79,140,255,.16);
            color: #cde0ff;
            font-size: .70rem;
            font-weight: 700;
            margin-right: .3rem;
        }
        .page-hero .section-chip {
            margin-bottom: .2rem;
        }

        /* ── KPI card ───────────────────────────────────────────────── */
        .status-kpi-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: .65rem;
            margin: .1rem 0 .9rem;
        }
        .status-kpi {
            position: relative; overflow: hidden;
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: .85rem .9rem .8rem;
            background: var(--surface);
        }
        .status-kpi::before {
            content: "";
            position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
            background: var(--accent, var(--brand));
            border-radius: 3px 0 0 3px;
        }
        .status-kpi .label  { font-size: .76rem; color: var(--muted); font-weight: 600; }
        .status-kpi .value  { font-size: 1.7rem; font-weight: 800; margin: .28rem 0 .1rem; color: var(--text); line-height: 1; }
        .status-kpi .sub    { font-size: .72rem; color: var(--muted-2); }
        .status-kpi.status-danger  { --accent: var(--danger); }
        .status-kpi.status-warning { --accent: var(--warning); }
        .status-kpi.status-success { --accent: var(--success); }
        .status-kpi.status-info    { --accent: var(--brand); }

        @media (max-width: 900px) { .status-kpi-grid { grid-template-columns: repeat(2, minmax(0,1fr)); } }
        @media (max-width: 520px) { .status-kpi-grid { grid-template-columns: 1fr; } }

        /* ── Section card ───────────────────────────────────────────── */
        .section-card {
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: .85rem .9rem .8rem;
            background: var(--surface);
            margin-bottom: .8rem;
        }
        .section-card h3 { margin: .05rem 0 .5rem; font-size: .95rem; font-weight: 700; }
        .section-card p  { margin: 0; color: var(--muted); font-size: .82rem; }

        /* ── Entity / list items ────────────────────────────────────── */
        .entity-list-item {
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: .65rem .8rem;
            background: rgba(255,255,255,.025);
            margin-bottom: .45rem;
        }
        .entity-list-item strong { display: block; margin-bottom: .06rem; }
        .entity-list-item small  { color: var(--muted); }

        /* ── Divider ────────────────────────────────────────────────── */
        .soft-divider {
            height: 1px;
            background: var(--border);
            margin: .6rem 0 .75rem;
        }

        /* ── Sidebar ────────────────────────────────────────────────── */
        .stSidebar { background: #060f1c; }
        section[data-testid="stSidebar"] { border-right: 1px solid var(--border); }
        section[data-testid="stSidebar"] .block-container {
            padding-top: .8rem !important;
            padding-left: .75rem !important;
            padding-right: .75rem !important;
        }

        .sidebar-user {
            padding: .8rem .85rem;
            border-radius: var(--radius-lg);
            background: var(--surface-2);
            border: 1px solid var(--border);
            margin-bottom: .7rem;
        }
        .sidebar-user .name { font-size: .92rem; font-weight: 700; margin-bottom: .12rem; }
        .sidebar-user .meta { font-size: .73rem; color: var(--muted); }

        .sidebar-section {
            font-size: .65rem; text-transform: uppercase;
            letter-spacing: .08em; color: var(--muted-2);
            font-weight: 700; margin: .8rem .2rem .3rem;
        }

        /* Botões da sidebar — compactos, sem excessos */
        section[data-testid="stSidebar"] .stButton > button {
            min-height: 2.2rem;
            border-radius: var(--radius) !important;
            border: 1px solid transparent !important;
            background: transparent !important;
            color: var(--muted) !important;
            font-size: .83rem !important;
            font-weight: 500 !important;
            box-shadow: none !important;
            text-align: left !important;
            transition: background .12s, color .12s;
            padding: 0 .6rem !important;
        }
        section[data-testid="stSidebar"] .stButton > button:hover {
            background: rgba(255,255,255,.05) !important;
            color: var(--text) !important;
            border-color: var(--border) !important;
        }
        section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background: rgba(79,140,255,.14) !important;
            color: #a8caff !important;
            border-color: rgba(79,140,255,.22) !important;
        }

        /* ── Botões gerais ──────────────────────────────────────────── */
        .stButton > button, .stDownloadButton > button {
            border-radius: var(--radius) !important;
            min-height: 2.2rem;
            border: 1px solid var(--border-md) !important;
            background: var(--surface-2) !important;
            color: var(--text) !important;
            font-weight: 600 !important;
            font-size: .85rem !important;
            box-shadow: none !important;
            transition: border-color .12s, background .12s;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
            border-color: rgba(79,140,255,.30) !important;
            background: rgba(79,140,255,.08) !important;
        }
        .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
            background: var(--brand) !important;
            border-color: transparent !important;
            color: #fff !important;
        }
        .stButton > button[kind="primary"]:hover {
            background: var(--brand-2) !important;
        }

        /* ── Inputs ─────────────────────────────────────────────────── */
        .stTextInput input, .stNumberInput input, .stTextArea textarea,
        .stDateInput input, .stTimeInput input {
            border-radius: var(--radius) !important;
            background: var(--surface-2) !important;
            color: var(--text) !important;
            border: 1px solid var(--border-md) !important;
            font-size: .87rem !important;
        }
        .stSelectbox div[data-baseweb="select"] > div,
        .stMultiSelect div[data-baseweb="select"] > div {
            border-radius: var(--radius) !important;
            background: var(--surface-2) !important;
            color: var(--text) !important;
            border: 1px solid var(--border-md) !important;
            font-size: .87rem !important;
        }
        .stCheckbox label, .stRadio label { color: var(--text) !important; font-size: .87rem !important; }

        .stForm {
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: .9rem .9rem .65rem;
            background: var(--surface);
        }

        /* ── Métricas nativas ───────────────────────────────────────── */
        [data-testid="stMetric"] {
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: .8rem .85rem;
            background: var(--surface);
        }
        [data-testid="stMetricLabel"] { color: var(--muted) !important; font-size: .78rem !important; }
        [data-testid="stMetricValue"] { color: var(--text) !important; font-size: 1.5rem !important; }
        [data-testid="stMetricDelta"] { color: var(--muted) !important; }

        /* ── DataFrames ─────────────────────────────────────────────── */
        [data-testid="stDataFrame"] {
            border-radius: var(--radius-lg);
            overflow: hidden;
            border: 1px solid var(--border);
            background: var(--surface);
        }
        [data-testid="stDataFrame"] [role="columnheader"] {
            background: var(--surface-2) !important;
            color: var(--muted) !important;
            border-bottom: 1px solid var(--border-md) !important;
            font-weight: 700 !important;
            font-size: .80rem !important;
            text-transform: uppercase;
            letter-spacing: .04em;
        }
        [data-testid="stDataFrame"] [role="gridcell"] {
            background: var(--surface) !important;
            color: var(--text) !important;
            border-bottom: 1px solid var(--border) !important;
            font-size: .85rem !important;
        }
        [data-testid="stDataFrame"] [role="row"]:hover [role="gridcell"] {
            background: var(--surface-2) !important;
        }

        /* ── Expander ───────────────────────────────────────────────── */
        div[data-testid="stExpander"] {
            border: 1px solid var(--border);
            border-radius: var(--radius-lg) !important;
            background: var(--surface);
        }

        /* ── Alertas ────────────────────────────────────────────────── */
        [data-testid="stAlert"] {
            border-radius: var(--radius-lg) !important;
            border: 1px solid var(--border) !important;
            background: var(--surface) !important;
        }

        /* ── Tabs ───────────────────────────────────────────────────── */
        .stTabs [data-baseweb="tab-list"] { gap: .25rem; }
        .stTabs [data-baseweb="tab"] {
            border-radius: 8px 8px 0 0;
            background: transparent;
            font-size: .85rem;
        }

        /* ── Misc ───────────────────────────────────────────────────── */
        .stCaption { color: var(--muted-2) !important; font-size: .78rem !important; }
        label, .stMarkdown, p, span, div { color: inherit; }
        h1, h2, h3 { letter-spacing: -.018em; }

        @media (max-width: 768px) {
            .block-container { padding-left: .8rem !important; padding-right: .8rem !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_user(usuario_or_nome, perfil: str | None = None, email: str | None = None) -> None:
    """Compatível com chamadas antigas e novas."""
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
    """Compatível com chamadas antigas e novas."""
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


def render_page_intro(title: str, description: str, chip: str | None = None, badge: str | None = None) -> None:
    chip = chip or badge
    title = html.escape(str(title))
    description = html.escape(str(description))
    chip_html = f"<span class='section-chip'>{html.escape(str(chip))}</span>" if chip else ""
    desc_html = f"<p>{description}</p>" if description else ""
    st.markdown(
        f"""
        <div class="page-hero">
            {chip_html}
            <h2>{title}</h2>
            {desc_html}
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
