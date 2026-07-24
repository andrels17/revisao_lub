"""
Servico de autenticacao com roles.
Todos os IDs são UUID — lidos como str (::text) e escritos com cast ::uuid.
"""
from __future__ import annotations
import bcrypt
import streamlit as st
from database.connection import get_conn, release_conn

ROLE_LABELS = {
    "admin":        "Administrador",
    "gestor":       "Gestor",
    "operador":     "Operador",
    "visualizador": "Visualizador",
}

ROLE_PAGINAS: dict[str, set[str]] = {
    "admin": {
        "Dashboard",
        "Setores", "Equipamentos", "Responsaveis",
        "Vinculos", "Templates",
        "Leituras KM / Horas", "Controle de Revisoes",
        "Controle de Lubrificacoes",
        "Alertas WhatsApp",
        "Importar Equipamentos", "Relatorio de Manutencao",
        "Configuracoes",
    },
    "gestor": {
        "Dashboard",
        "Setores", "Equipamentos", "Responsaveis",
        "Vinculos", "Templates",
        "Leituras KM / Horas", "Controle de Revisoes",
        "Controle de Lubrificacoes",
        "Alertas WhatsApp",
        "Relatorio de Manutencao",
    },
    "operador": {
        "Dashboard",
        "Leituras KM / Horas",
        "Controle de Revisoes",
        "Controle de Lubrificacoes",
    },
    "visualizador": {
        "Dashboard",
        "Relatorio de Manutencao",
    },
}

ROLE_PAGINAS["admin"] = {
    "🧭 Painel Operacional",
    "🧠 Painel Executivo",
    "🏢 Setores", "🗂️ Grupos", "🚜 Equipamentos", "👷 Responsáveis",
    "🔗 Vínculos", "📋 Templates",
    "📏 Leituras KM / Horas", "🔧 Controle de Revisões",
    "🛢️ Controle de Lubrificações",
    "📱 Alertas WhatsApp",
    "📥 Importar Equipamentos", "📈 Relatório de Manutenção",
    "📄 Relatórios PDF",
    "⚙️ Configurações",
    "🔥 Prioridades do Dia",
    "📋 Log de Auditoria",
}
ROLE_PAGINAS["gestor"] = {
    "🧭 Painel Operacional",
    "🧠 Painel Executivo",
    "🏢 Setores", "🗂️ Grupos", "🚜 Equipamentos", "👷 Responsáveis",
    "🔗 Vínculos", "📋 Templates",
    "📏 Leituras KM / Horas", "🔧 Controle de Revisões",
    "🛢️ Controle de Lubrificações",
    "📱 Alertas WhatsApp",
    "📈 Relatório de Manutenção",
    "📄 Relatórios PDF",
    "🔥 Prioridades do Dia",
}
ROLE_PAGINAS["operador"] = {
    "🧭 Painel Operacional",
    "🧠 Painel Executivo",
    "📏 Leituras KM / Horas",
    "🔧 Controle de Revisões",
    "🛢️ Controle de Lubrificações",
    "🔥 Prioridades do Dia",
}
ROLE_PAGINAS["visualizador"] = {
    "🧭 Painel Operacional",
    "🧠 Painel Executivo",
    "📈 Relatório de Manutenção",
    "📄 Relatórios PDF",
    "🔥 Prioridades do Dia",
}

def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()

def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode(), senha_hash.encode())
    except Exception:
        return False

def _validar_senha(senha: str) -> tuple[bool, str]:
    """Valida requisitos mínimos de segurança para senhas."""
    if not senha or len(senha) < 8:
        return False, "Senha deve ter ao menos 8 caracteres."
    if not any(c.isupper() for c in senha):
        return False, "Senha deve conter ao menos uma letra maiúscula."
    if not any(c.isdigit() for c in senha):
        return False, "Senha deve conter ao menos um número."
    return True, ""

MAX_TENTATIVAS = 5
BLOQUEIO_MINUTOS = 15


def _garantir_tabela_tentativas() -> None:
    """Cria a tabela de tentativas de login se não existir."""
    try:
        with get_conn() as conn:
            conn.cursor().execute(
                """
                CREATE TABLE IF NOT EXISTS public.tentativas_login (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    ip VARCHAR(45),
                    sucesso BOOLEAN NOT NULL DEFAULT FALSE,
                    tentativa_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_tentativas_login_email_em
                    ON public.tentativas_login(email, tentativa_em);
                """
            )
            conn.commit()
    except Exception:
        pass


def _registrar_tentativa(email: str, sucesso: bool) -> None:
    """Registra uma tentativa de login no banco."""
    try:
        with get_conn() as conn:
            conn.cursor().execute(
                "INSERT INTO public.tentativas_login (email, sucesso) VALUES (%s, %s)",
                (email.strip().lower(), sucesso),
            )
            conn.commit()
    except Exception:
        pass


def verificar_bloqueio(email: str) -> tuple[bool, int]:
    """
    Verifica se o email está bloqueado por excesso de tentativas.
    Retorna (bloqueado: bool, minutos_restantes: int).
    """
    try:
        _garantir_tabela_tentativas()
        janela = f"NOW() - INTERVAL '{BLOQUEIO_MINUTOS} minutes'"
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT COUNT(*) FROM public.tentativas_login
                WHERE email = %s
                  AND sucesso = FALSE
                  AND tentativa_em >= {janela}
                """,
                (email.strip().lower(),),
            )
            count = cur.fetchone()[0]
            if count >= MAX_TENTATIVAS:
                cur.execute(
                    f"""
                    SELECT MAX(tentativa_em) FROM public.tentativas_login
                    WHERE email = %s AND sucesso = FALSE AND tentativa_em >= {janela}
                    """,
                    (email.strip().lower(),),
                )
                ultima = cur.fetchone()[0]
                if ultima:
                    import datetime as _dt
                    agora = _dt.datetime.now(_dt.timezone.utc)
                    try:
                        delta = agora - ultima
                    except TypeError:
                        delta = agora.replace(tzinfo=None) - ultima
                    restante = max(0, BLOQUEIO_MINUTOS * 60 - int(delta.total_seconds()))
                    return True, restante // 60
    except Exception:
        pass
    return False, 0


def login(email: str, senha: str) -> dict | None:
    _garantir_tabela_tentativas()
    bloqueado, minutos = verificar_bloqueio(email)
    if bloqueado:
        raise PermissionError(f"BLOQUEADO:{minutos}")

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id::text, nome, email, senha_hash, role, ativo,
                   responsavel_id::text
            FROM usuarios
            WHERE email = %s
            """,
            (email.strip().lower(),),
        )
        row = cur.fetchone()
    if not row:
        _registrar_tentativa(email, False)
        return None
    uid, nome, email_db, senha_hash, role, ativo, resp_id = row
    if not ativo:
        _registrar_tentativa(email, False)
        return None
    if not verificar_senha(senha, senha_hash):
        _registrar_tentativa(email, False)
        return None
    _registrar_tentativa(email, True)
    try:
        with get_conn() as conn:
            conn.cursor().execute(
                "UPDATE usuarios SET ultimo_login = NOW() WHERE id = %s::uuid", (uid,)
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
    role = role_atual()
    if role not in roles:
        st.error("Voce nao tem permissao para acessar este recurso.")
        st.stop()

def listar_usuarios() -> list[dict]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.id, u.nome, u.email, u.role, u.ativo,
                   u.responsavel_id::text, r.nome AS responsavel_nome,
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
    responsavel_id: str | None = None,
) -> tuple[bool, str]:
    try:
        ok_pwd, msg_pwd = _validar_senha(senha)
        if not ok_pwd:
            return False, msg_pwd
        h = hash_senha(senha)
        with get_conn() as conn:
            conn.cursor().execute(
                """
                INSERT INTO usuarios (nome, email, senha_hash, role, responsavel_id)
                VALUES (%s, %s, %s, %s, %s::uuid)
                """,
                (nome, email.strip().lower(), h, role, responsavel_id or None),
            )
            conn.commit()
        return True, "Usuario criado com sucesso."
    except Exception as e:
        if "unique" in str(e).lower():
            return False, "E-mail ja cadastrado."
        return False, f"Erro ao criar usuario: {e}"

def editar_usuario(
    uid: int,
    nome: str,
    role: str,
    ativo: bool,
    responsavel_id: str | None = None,
    nova_senha: str | None = None,
) -> tuple[bool, str]:
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            if nova_senha:
                ok_pwd, msg_pwd = _validar_senha(nova_senha)
                if not ok_pwd:
                    return False, msg_pwd
                cur.execute(
                    """
                    UPDATE usuarios
                    SET nome=%s, role=%s, ativo=%s,
                        responsavel_id=%s::uuid, senha_hash=%s
                    WHERE id=%s
                    """,
                    (nome, role, ativo, responsavel_id or None,
                     hash_senha(nova_senha), uid),
                )
            else:
                cur.execute(
                    """
                    UPDATE usuarios
                    SET nome=%s, role=%s, ativo=%s, responsavel_id=%s::uuid
                    WHERE id=%s
                    """,
                    (nome, role, ativo, responsavel_id or None, uid),
                )
            conn.commit()
        return True, "Usuario atualizado."
    except Exception as e:
        return False, f"Erro: {e}"

def excluir_usuario(uid: int, uid_logado: int) -> tuple[bool, str]:
    if uid == uid_logado:
        return False, "Voce nao pode excluir seu proprio usuario."
    try:
        with get_conn() as conn:
            conn.cursor().execute(
                "DELETE FROM usuarios WHERE id = %s", (uid,)
            )
            conn.commit()
        return True, "Usuario removido."
    except Exception as e:
        return False, f"Erro: {e}"
