"""
Página de login — exibida quando não há usuário autenticado na sessão.
"""
import streamlit as st
from services import auth_service


def render():
    # Centraliza o formulário
    _, col, _ = st.columns([1, 1.6, 1])

    with col:
        st.markdown("<div style='height: 3rem'></div>", unsafe_allow_html=True)
        st.title("🔧 Revisão & Lubrificação")
        st.caption("Sistema de controle de manutenção preventiva")
        st.divider()

        with st.form("form_login", clear_on_submit=False):
            st.subheader("Entrar")
            email = st.text_input(
                "E-mail",
                placeholder="seu@email.com",
                autocomplete="email",
            )
            senha = st.text_input(
                "Senha",
                type="password",
                placeholder="••••••••",
                autocomplete="current-password",
            )
            entrar = st.form_submit_button(
                "Entrar", type="primary", use_container_width=True
            )

        if entrar:
            if not email or not senha:
                st.warning("Preencha e-mail e senha.")
                return

            with st.spinner("Verificando credenciais…"):
                usuario = auth_service.login(email, senha)

            if usuario:
                st.session_state["usuario"] = usuario
                st.session_state.pop("pagina_atual", None)
                st.rerun()
            else:
                st.error("E-mail ou senha incorretos, ou usuário inativo.")

        st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)
        st.caption("Esqueceu sua senha? Contate o administrador do sistema.")
