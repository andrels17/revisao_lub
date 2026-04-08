"""
config.py — mantido para referência, mas não é utilizado em runtime.
As credenciais do banco são carregadas diretamente via st.secrets (Streamlit Cloud)
ou variáveis de ambiente em database/connection.py.

Para configurar localmente, crie um arquivo .streamlit/secrets.toml:
  DATABASE_URL = "postgresql://USUARIO:SENHA@HOST/neondb?sslmode=require"
"""
