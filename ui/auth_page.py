"""
Página de login — exibida quando não há usuário autenticado na sessão.
"""
import streamlit as st
from services import auth_service


def _inject_login_styles():
    st.markdown(
        """
        <style>
        .login-shell{padding-top:4vh;}
        .login-wrap{
            padding:1.2rem;
            border-radius:28px;
            border:1px solid rgba(148,163,184,.16);
            background:linear-gradient(180deg, rgba(15,23,42,.88), rgba(17,24,39,.92));
            box-shadow:0 28px 70px rgba(2,6,23,.34);
            backdrop-filter: blur(10px);
        }
        .login-brand{
            padding:1.15rem 1.2rem;
            border-radius:22px;
            background:linear-gradient(135deg, rgba(59,130,246,.18), rgba(15,23,42,.35));
            border:1px solid rgba(59,130,246,.18);
            margin-bottom:1rem;
        }
        .login-brand h1{margin:0 !important;font-size:1.7rem !important;}
        .login-brand p{margin:.38rem 0 0 0;color:#cbd5e1;}
        .login-foot{margin-top:.85rem;color:#8ea2bc;font-size:.82rem;text-align:center;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render():
    _inject_login_styles()
    _, col, _ = st.columns([1, 1.2, 1])

    with col:
        st.markdown('<div class="login-shell"><div class="login-wrap">', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="login-brand">
                <div style="display:inline-block;padding:.24rem .62rem;border-radius:999px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.1);font-size:.72rem;font-weight:700;color:#e2e8f0;">Plataforma operacional</div>
                <h1>🔧 Revisão &amp; Lubrificação</h1>
                <p>Sistema de controle de manutenção preventiva com visual mais moderno, limpo e confortável.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("form_login", clear_on_submit=False):
            st.subheader("Entrar")
            email = st.text_input("E-mail", placeholder="seu@email.com", autocomplete="email")
            senha = st.text_input("Senha", type="password", placeholder="••••••••", autocomplete="current-password")
            entrar = st.form_submit_button("Entrar no sistema", type="primary", use_container_width=True)

        if entrar:
            if not email or not senha:
                st.warning("Preencha e-mail e senha.")
                st.markdown('</div></div>', unsafe_allow_html=True)
                return

            with st.spinner("Verificando credenciais…"):
                usuario = auth_service.login(email, senha)

            if usuario:
                st.session_state["usuario"] = usuario
                st.session_state.pop("pagina_atual", None)
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos, ou usuário inativo.")

        st.markdown('<div class="login-foot">Esqueceu sua senha? Contate o administrador do sistema.</div></div></div>', unsafe_allow_html=True)
