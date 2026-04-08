"""Página de login — exibida quando não há usuário autenticado na sessão."""
import streamlit as st
from services import auth_service


def render():
    st.markdown(
        """
        <style>
        .login-shell{max-width:560px;margin:5vh auto 0 auto;}
        .login-card{
            border:1px solid rgba(148,163,184,.14);
            border-radius:28px;
            padding:1.35rem 1.35rem 1.1rem 1.35rem;
            background:linear-gradient(180deg, rgba(10,19,34,.96), rgba(15,27,45,.96));
            box-shadow:0 32px 80px rgba(0,0,0,.34);
        }
        .login-brand{margin-bottom:1rem;}
        .login-brand h1{margin:0;font-size:1.8rem;font-weight:800;letter-spacing:-0.03em;color:#eef5ff;}
        .login-brand p{margin:.45rem 0 0 0;color:#b9cae2;font-size:.95rem;}
        .login-chip{
            display:inline-block;padding:.26rem .64rem;border-radius:999px;
            background:rgba(79,140,255,.12);border:1px solid rgba(79,140,255,.18);
            color:#dcebff;font-size:.74rem;font-weight:800;margin-bottom:.75rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='login-shell'><div class='login-card'>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class='login-brand'>
            <div class='login-chip'>Acesso ao sistema</div>
            <h1>Revisão &amp; Lubrificação</h1>
            <p>Controle de manutenção preventiva com visual mais moderno, escuro e confortável para o uso diário.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("form_login", clear_on_submit=False):
        email = st.text_input("E-mail", placeholder="seu@email.com", autocomplete="email")
        senha = st.text_input("Senha", type="password", placeholder="••••••••", autocomplete="current-password")
        entrar = st.form_submit_button("Entrar", type="primary", use_container_width=True)

    if entrar:
        if not email or not senha:
            st.warning("Preencha e-mail e senha.")
        else:
            with st.spinner("Verificando credenciais…"):
                usuario = auth_service.login(email, senha)
            if usuario:
                st.session_state["usuario"] = usuario
                st.session_state.pop("pagina_atual", None)
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos, ou usuário inativo.")

    st.caption("Esqueceu sua senha? Contate o administrador do sistema.")
    st.markdown("</div></div>", unsafe_allow_html=True)
