"""
Página de gerenciamento de usuários — acessível apenas pelo Admin.
"""
import streamlit as st
from services import auth_service, responsaveis_service


def _badge_role(role: str) -> str:
    cores = {
        "admin":        "🔴",
        "gestor":       "🟠",
        "operador":     "🔵",
        "visualizador": "⚪",
    }
    label = auth_service.ROLE_LABELS.get(role, role)
    return f"{cores.get(role, '⚫')} {label}"


def _form_criar():
    st.subheader("➕ Novo usuário")

    responsaveis = [None] + [
        r for r in responsaveis_service.listar() if r.get("ativo")
    ]

    with st.form("form_criar_usuario", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            nome  = st.text_input("Nome completo *")
            email = st.text_input("E-mail *")
        with col2:
            role  = st.selectbox(
                "Role *",
                list(auth_service.ROLE_LABELS.keys()),
                format_func=lambda r: auth_service.ROLE_LABELS[r],
            )
            resp  = st.selectbox(
                "Vincular a responsável",
                responsaveis,
                format_func=lambda r: "— nenhum —" if r is None
                            else f"{r['nome']} ({r.get('funcao_principal') or 'sem função'})",
                help="Para operadores, vincula o usuário a um responsável e filtra suas pendências.",
            )

        senha   = st.text_input("Senha *", type="password")
        senha2  = st.text_input("Confirmar senha *", type="password")

        _mostrar_permissoes(role)

        submitted = st.form_submit_button("Criar usuário", type="primary")

    if submitted:
        erros = []
        if not nome:  erros.append("Nome obrigatório.")
        if not email: erros.append("E-mail obrigatório.")
        if not senha: erros.append("Senha obrigatória.")
        if senha != senha2: erros.append("As senhas não coincidem.")
        if len(senha) < 6: erros.append("Senha deve ter ao menos 6 caracteres.")

        if erros:
            for e in erros:
                st.error(e)
            return

        ok, msg = auth_service.criar_usuario(
            nome=nome,
            email=email,
            senha=senha,
            role=role,
            responsavel_id=resp["id"] if resp else None,
        )
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)


def _mostrar_permissoes(role: str):
    """Exibe um resumo visual das permissões do role selecionado."""
    paginas = auth_service.ROLE_PAGINAS.get(role, set())
    todas   = auth_service.ROLE_PAGINAS["admin"]

    itens = []
    for p in sorted(todas):
        tick = "✅" if p in paginas else "❌"
        itens.append(f"{tick} {p}")

    with st.expander("Ver permissões deste role"):
        cols = st.columns(2)
        meio = len(itens) // 2
        for i, item in enumerate(itens):
            cols[0 if i < meio else 1].caption(item)


def _form_editar(usuario: dict):
    uid_logado = st.session_state["usuario"]["id"]

    responsaveis = [None] + [
        r for r in responsaveis_service.listar() if r.get("ativo")
    ]
    resp_atual_id = usuario.get("responsavel_id")
    idx_resp = next(
        (i for i, r in enumerate(responsaveis) if r and r["id"] == resp_atual_id),
        0,
    )

    with st.form(f"form_editar_{usuario['id']}", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            nome  = st.text_input("Nome", value=usuario["nome"])
            role  = st.selectbox(
                "Role",
                list(auth_service.ROLE_LABELS.keys()),
                index=list(auth_service.ROLE_LABELS.keys()).index(usuario["role"]),
                format_func=lambda r: auth_service.ROLE_LABELS[r],
                disabled=(usuario["id"] == uid_logado),
            )
        with col2:
            ativo = st.checkbox("Ativo", value=usuario["ativo"],
                                disabled=(usuario["id"] == uid_logado))
            resp  = st.selectbox(
                "Responsável vinculado",
                responsaveis,
                index=idx_resp,
                format_func=lambda r: "— nenhum —" if r is None
                            else f"{r['nome']} ({r.get('funcao_principal') or 'sem função'})",
            )

        nova_senha = st.text_input(
            "Nova senha (deixe em branco para manter)", type="password"
        )

        col_salvar, col_excluir, _ = st.columns([1, 1, 2])
        salvar  = col_salvar.form_submit_button("💾 Salvar", type="primary")
        excluir = col_excluir.form_submit_button(
            "🗑️ Excluir",
            disabled=(usuario["id"] == uid_logado),
        )

    if salvar:
        ok, msg = auth_service.editar_usuario(
            uid=usuario["id"],
            nome=nome,
            role=role,
            ativo=ativo,
            responsavel_id=resp["id"] if resp else None,
            nova_senha=nova_senha or None,
        )
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

    if excluir:
        ok, msg = auth_service.excluir_usuario(usuario["id"], uid_logado)
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)


# ── Render principal ──────────────────────────────────────────────────────────

def render():
    # Somente admin
    auth_service.requer_role("admin")

    st.title("👥 Usuários do sistema")
    st.caption("Gerencie quem acessa o sistema e quais permissões cada um possui.")

    usuarios = auth_service.listar_usuarios()

    # Resumo por role
    col_resumo = st.columns(4)
    for i, (role, label) in enumerate(auth_service.ROLE_LABELS.items()):
        qtd = sum(1 for u in usuarios if u["role"] == role)
        col_resumo[i].metric(label, qtd)

    st.divider()

    tab_lista, tab_novo = st.tabs(["📋 Usuários cadastrados", "➕ Novo usuário"])

    with tab_lista:
        if not usuarios:
            st.info("Nenhum usuário cadastrado.")
        else:
            uid_logado = st.session_state["usuario"]["id"]
            for u in usuarios:
                sufixo = " 👤 (você)" if u["id"] == uid_logado else ""
                status = "✅ Ativo" if u["ativo"] else "⛔ Inativo"
                with st.expander(
                    f"{_badge_role(u['role'])}  |  {u['nome']}  —  {u['email']}{sufixo}  |  {status}"
                ):
                    col_info, _ = st.columns([3, 1])
                    with col_info:
                        st.caption(
                            f"Responsável vinculado: **{u.get('responsavel_nome') or '—'}** | "
                            f"Último login: **{u.get('ultimo_login') or 'nunca'}**"
                        )
                    _form_editar(u)

    with tab_novo:
        _form_criar()
