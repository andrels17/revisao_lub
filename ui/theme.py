from __future__ import annotations

from html import escape

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
            --success-soft:rgba(34,197,94,.14);
            --warning-soft:rgba(245,158,11,.14);
            --danger-soft:rgba(239,68,68,.14);
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
        .app-shell{padding:.15rem 0 .85rem 0;}

        @keyframes fadeSlideIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
        @keyframes skeletonShimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}

        .app-topbar{
            animation:fadeSlideIn .35s ease;
            display:flex;align-items:center;justify-content:space-between;gap:1rem;
            padding:1rem 1.1rem;border:1px solid var(--line);border-radius:24px;
            background: linear-gradient(135deg, rgba(12,24,42,.96), rgba(18,35,58,.94));
            box-shadow:var(--shadow-strong);color:var(--text);margin-bottom:.95rem;
        }
        .app-topbar h1{margin:0;font-size:1.35rem;font-weight:800;letter-spacing:-0.02em;}
        .app-topbar p{margin:.22rem 0 0 0;color:#c0d0e6;font-size:.9rem;}

        .app-chip,.section-chip{
            display:inline-block;padding:.24rem .62rem;border-radius:999px;
            background:rgba(79,140,255,.12);border:1px solid rgba(79,140,255,.18);
            color:#dcebff;font-size:.73rem;font-weight:700;margin-right:.38rem;
        }

        .page-hero{
            animation:fadeSlideIn .4s ease;
            padding:1.1rem 1.15rem;border:1px solid var(--line);border-radius:24px;
            background:linear-gradient(135deg, rgba(12,24,42,.96), rgba(18,35,58,.94));
            box-shadow:var(--shadow);margin-bottom:1rem;
        }
        .page-hero h2{margin:0;font-size:1.3rem;font-weight:800;letter-spacing:-0.02em;}
        .page-hero p{margin:.42rem 0 0 0;color:#c0d0e6;font-size:.92rem;}

        .section-card{
            animation:fadeSlideIn .45s ease;
            border:1px solid var(--line);border-radius:22px;padding:1rem 1rem .95rem 1rem;
            background:linear-gradient(180deg, rgba(15,27,45,.98), rgba(18,35,58,.98));
            box-shadow:var(--shadow);margin-bottom:.95rem;
        }
        .section-card h3{margin:.1rem 0 .25rem 0;font-size:1.02rem;}
        .section-card p{margin:0;color:var(--muted);font-size:.86rem;}
        .subtle-card{
            animation:fadeSlideIn .45s ease;
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
            position:relative;overflow:hidden;
            border:1px solid var(--line);border-radius:18px;padding:.95rem 1rem;
            background:linear-gradient(180deg, rgba(15,27,45,.98), rgba(18,35,58,.98));
            box-shadow:var(--shadow);
        }
        [data-testid="stMetricLabel"], [data-testid="stMetricDelta"] {color:var(--muted) !important;}
        [data-testid="stMetric"]:hover {transform:translateY(-2px);border-color:rgba(79,140,255,.24);}
        [data-testid="stMetric"] [data-testid="stMetricValue"] {font-weight:800 !important;}
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

        
        .status-badge{display:inline-flex;align-items:center;gap:.4rem;padding:.26rem .62rem;border-radius:999px;font-size:.75rem;font-weight:700;border:1px solid var(--line);} 
        .status-badge.status-em-dia{background:var(--success-soft);color:#b8f7cd;border-color:rgba(34,197,94,.22);} 
        .status-badge.status-proximo{background:var(--warning-soft);color:#fde3ae;border-color:rgba(245,158,11,.24);} 
        .status-badge.status-vencido{background:var(--danger-soft);color:#fecaca;border-color:rgba(239,68,68,.24);} 
        .status-badge.status-realizado{background:rgba(79,140,255,.14);color:#d7e8ff;border-color:rgba(79,140,255,.24);} 
        .skeleton-row{display:grid;grid-template-columns:repeat(4,1fr);gap:.85rem;margin:.15rem 0 1rem 0;animation:fadeSlideIn .2s ease;} 
        .skeleton-card{height:110px;border-radius:18px;border:1px solid rgba(148,163,184,.10);background:linear-gradient(90deg, rgba(15,27,45,.95) 0%, rgba(23,40,63,.98) 50%, rgba(15,27,45,.95) 100%);background-size:200% 100%;animation:skeletonShimmer 1.35s linear infinite;box-shadow:var(--shadow);} 
        .plot-shell{border:1px solid var(--line);border-radius:20px;padding:.8rem;background:linear-gradient(180deg, rgba(15,27,45,.98), rgba(18,35,58,.98));box-shadow:var(--shadow);} 
        .plot-caption{font-size:.78rem;color:var(--muted);margin-top:.2rem;} 

        @media (max-width: 768px) {
            .block-container {padding-left:.9rem !important;padding-right:.9rem !important;}
            [data-testid="column"] {min-width:48% !important;}
            .stDataFrame {font-size:.78rem;}
            .app-topbar,.page-hero{
            animation:fadeSlideIn .4s ease;padding:.9rem 1rem;border-radius:20px;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_user(nome: str, perfil: str, email: str | None = None) -> None:
    email_html = f"<div class='meta'>{perfil} · {email}</div>" if email else f"<div class='meta'>{perfil}</div>"
    st.sidebar.markdown(
        f"""
        <div class="sidebar-user">
            <div class="name">{nome}</div>
            {email_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_topbar(title: str, subtitle: str = "") -> None:
    subt_html = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(
        f"""
        <div class="app-topbar">
            <div>
                <h1>{title}</h1>
                {subt_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page_intro(title: str, description: str, chip: str | None = None) -> None:
    chip_html = f"<span class='section-chip'>{chip}</span>" if chip else ""
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



def render_loading_skeleton(cards: int = 4) -> None:
    cards = max(1, int(cards or 1))
    st.markdown("<div class='skeleton-row'>" + "".join(["<div class='skeleton-card'></div>" for _ in range(cards)]) + "</div>", unsafe_allow_html=True)


def get_status_tone(status: str | None) -> str:
    status = (status or "").strip().upper()
    return {"EM DIA": "em-dia", "PROXIMO": "proximo", "VENCIDO": "vencido", "REALIZADO": "realizado"}.get(status, "realizado")


def render_status_badge(status: str, label: str | None = None) -> str:
    tone = get_status_tone(status)
    text = escape(label or status or "-")
    return f"<span class='status-badge status-{tone}'>{text}</span>"


def apply_plotly_dark_figure(fig, *, height: int = 320):
    fig.update_layout(
        height=height,
        margin=dict(t=18, b=18, l=18, r=18),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#dbe9ff", size=13),
        hoverlabel=dict(bgcolor="#0b1628", bordercolor="rgba(79,140,255,.28)", font=dict(color="#ecf3ff")),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#9db0c7")),
    )
    try:
        fig.update_xaxes(showgrid=True, gridcolor="rgba(157,176,199,.10)", zeroline=False, linecolor="rgba(157,176,199,.18)", tickfont=dict(color="#9db0c7"))
        fig.update_yaxes(showgrid=True, gridcolor="rgba(157,176,199,.10)", zeroline=False, linecolor="rgba(157,176,199,.18)", tickfont=dict(color="#9db0c7"))
    except Exception:
        pass
    return fig
