ARQUIVOS CORRIGIDOS PARA O ERRO DE IMPORT

Ajustes:
1. __init__.py adicionados em services, ui, database e database/repositories
2. connection.py ajustado para Streamlit Cloud + Neon usando st.secrets["DATABASE_URL"]
3. runtime.txt fixado em python-3.11

No Streamlit Cloud > Secrets:
DATABASE_URL = "postgresql://USUARIO:SENHA@HOST/neondb?sslmode=require"


AJUSTE UUID (08/04/2026)
- O projeto da Fase 1 foi alinhado para bancos Neon/Supabase que usam UUID nos IDs principais.
- As tabelas novas compatíveis são: configuracoes_sistema, log_auditoria, vinculos_equipamento e vinculos_setor.
- Antes de subir, garanta: CREATE EXTENSION IF NOT EXISTS pgcrypto;
- Em banco já existente, evite recriar tabelas legadas. Rode apenas os trechos novos/ajustados do schema.


FASE 2.1
- novo módulo de comentários/log por equipamento (tabela comentarios_equipamento)
- painel de setores prioritários no dashboard
- exportação do Painel 360° em PDF (requer reportlab)


Fase 2.2: automação assistida de alertas
- fila sugerida com prioridade, cooldown e cobertura
- registro em lote de alertas disparados fora do sistema
- novas configurações: alerta_cooldown_horas e fila_alertas_limite
