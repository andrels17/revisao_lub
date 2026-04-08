"""
Serviço de autenticação com roles.

Roles disponíveis:
  admin        — acesso total + gerenciar usuários
  gestor       — ver tudo, aprovar execuções, relatórios
  operador     — ver suas pendências e registrar execuções
  visualizador — somente leitura (dashboard e relatórios)
"""
from __future__ import annotations

import bcrypt
import streamlit as st

from database.connection import get_conn

# ── Mapa de permissões por role ───────────────────────────────────────────────

ROLE_LABELS = {
    "admin":        "Administrador",
    "gestor":       "Gestor",
    "operador":     "Operador",
    "visualizador": "Visualizador",
}

# Páginas permitidas por role (chaves = nome da página no menu principal)
ROLE_PAGINAS: dict[str, set[str]] = {
    "admin": {
        "📊 Dashboard",
        "🏢 Setores", "🚜 Equipamentos", "👷 Responsáveis",
        "🔗 Vínculos", "📋 Templates",
        "📏 Leituras KM / Horas", "🔧 Controle de Revisões",
        "🛢️ Controle de Lubrificações",
        "📱 Alertas WhatsApp",
        "📥 Importar Equipamentos", "📈 Relatório de Manutenção",
        "⚙️ Configurações",
    },
    "gestor": {
        "📊 Dashboard",
        "🏢 Setores", "🚜 Equipamentos", "👷 Responsáveis",
        "🔗 Vínculos", "📋 Templates",
        "📏 Leituras KM / Horas", "🔧 Controle de Revisões",
        "🛢️ Controle de Lubrificações",
        "📱 Alertas WhatsApp",
        "📈 Relatório de Manutenção",
    },
    "operador": {
        "📊 Dashboard",
        "📏 Leituras KM / Horas",
        "🔧 Controle de Revisões",
        "🛢️ Controle de Lubrificações",
    },
    "visualizador": {
        "📊 Dashboard",
        "📈 Relatório de Manutenção",
    },
}

# ── Helpers de hash ───────────────────────────────────────────────────────────

def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode(), senha_hash.encode())
    except Exception:
        return False


# ── Auth principal ────────────────────────────────────────────────────────────

def login(email: str, senha: str) -> dict | None:
    """
    Verifica credenciais. Retorna dict do usuário ou None.
    Atualiza ultimo_login em caso de sucesso.
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, nome, email, senha_hash, role, ativo, responsavel_id
            FROM usuarios
            WHERE email = %s
            """,
            (email.strip().lower(),),
        )
        row = cur.fetchone()

    if not row:
        return None

    uid, nome, email_db, senha_hash, role, ativo, resp_id = row

    if not ativo:
        return None
    if not verificar_senha(senha, senha_hash):
        return None

    # Atualiza ultimo_login (ignora falha — não bloqueia o login)
    try:
        with get_conn() as conn:
            conn.cursor().execute(
                "UPDATE usuarios SET ultimo_login = NOW() WHERE id = %s", (uid,)
            )
            conn.commit()
    except Exception:
        pass

    return {
        "id":             uid,
        "nome":           nome,
        "email":          email_db,
        "role":           role,
        "responsavel_id": resp_id,
    }


def logout():
    for key in ("usuario", "pagina_atual"):
        st.session_state.pop(key, None)


# ── Getters de sessão ─────────────────────────────────────────────────────────

def usuario_logado() -> dict | None:
    return st.session_state.get("usuario")


def role_atual() -> str | None:
    u = usuario_logado()
    return u["role"] if u else None


def pode_acessar(pagina: str) -> bool:
    role = role_atual()
    if not role:
        return False
    return pagina in ROLE_PAGINAS.get(role, set())


def requer_role(*roles: str):
    """Para a renderização se o usuário não tiver o role necessário."""
    role = role_atual()
    if role not in roles:
        st.error("⛔ Você não tem permissão para acessar este recurso.")
        st.stop()


# ── CRUD de usuários (somente admin) ─────────────────────────────────────────

def listar_usuarios() -> list[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.id, u.nome, u.email, u.role, u.ativo,
                   u.responsavel_id, r.nome AS responsavel_nome,
                   u.ultimo_login, u.created_at
            FROM usuarios u
            LEFT JOIN responsaveis r ON r.id = u.responsavel_id
            ORDER BY u.role, u.nome
            """
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def criar_usuario(
    nome: str,
    email: str,
    senha: str,
    role: str,
    responsavel_id: int | None = None,
) -> tuple[bool, str]:
    try:
        h = hash_senha(senha)
        with get_conn() as conn:
            conn.cursor().execute(
                """
                INSERT INTO usuarios (nome, email, senha_hash, role, responsavel_id)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (nome, email.strip().lower(), h, role, responsavel_id or None),
            )
            conn.commit()
        return True, "Usuário criado com sucesso."
    except Exception as e:
        if "unique" in str(e).lower():
            return False, "E-mail já cadastrado."
        return False, f"Erro ao criar usuário: {e}"


def editar_usuario(
    uid: int,
    nome: str,
    role: str,
    ativo: bool,
    responsavel_id: int | None = None,
    nova_senha: str | None = None,
) -> tuple[bool, str]:
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            if nova_senha:
                cur.execute(
                    """
                    UPDATE usuarios
                    SET nome=%s, role=%s, ativo=%s, responsavel_id=%s, senha_hash=%s
                    WHERE id=%s
                    """,
                    (nome, role, ativo, responsavel_id or None, hash_senha(nova_senha), uid),
                )
            else:
                cur.execute(
                    """
                    UPDATE usuarios
                    SET nome=%s, role=%s, ativo=%s, responsavel_id=%s
                    WHERE id=%s
                    """,
                    (nome, role, ativo, responsavel_id or None, uid),
                )
            conn.commit()
        return True, "Usuário atualizado."
    except Exception as e:
        return False, f"Erro: {e}"


def excluir_usuario(uid: int, uid_logado: int) -> tuple[bool, str]:
    if uid == uid_logado:
        return False, "Você não pode excluir seu próprio usuário."
    try:
        with get_conn() as conn:
            conn.cursor().execute("DELETE FROM usuarios WHERE id = %s", (uid,))
            conn.commit()
        return True, "Usuário removido."
    except Exception as e:
        return False, f"Erro: {e}"
