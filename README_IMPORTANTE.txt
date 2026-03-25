ARQUIVOS CORRIGIDOS PARA O ERRO DE IMPORT

Ajustes:
1. __init__.py adicionados em services, ui, database e database/repositories
2. connection.py ajustado para Streamlit Cloud + Neon usando st.secrets["DATABASE_URL"]
3. runtime.txt fixado em python-3.11

No Streamlit Cloud > Secrets:
DATABASE_URL = "postgresql://USUARIO:SENHA@HOST/neondb?sslmode=require"
