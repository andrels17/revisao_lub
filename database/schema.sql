CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- SCHEMA COMPLETO - Sistema de Revisão e Lubrificação
-- Execute este script no seu banco Neon para criar as tabelas novas
-- ============================================================

-- Setores (já existe, mantido como referência)
CREATE TABLE IF NOT EXISTS setores (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    tipo_nivel VARCHAR(50) DEFAULT 'setor',
    setor_pai_id INTEGER REFERENCES setores(id),
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Responsáveis (já existe)
CREATE TABLE IF NOT EXISTS responsaveis (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    funcao_principal VARCHAR(100),
    telefone VARCHAR(30),
    email VARCHAR(200),
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Templates de Revisão (já existe)
CREATE TABLE IF NOT EXISTS templates_revisao (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    tipo_controle VARCHAR(20) NOT NULL CHECK (tipo_controle IN ('horas', 'km')),
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Etapas dos Templates de Revisão (já existe)
CREATE TABLE IF NOT EXISTS etapas_template_revisao (
    id SERIAL PRIMARY KEY,
    template_id INTEGER NOT NULL REFERENCES templates_revisao(id) ON DELETE CASCADE,
    nome_etapa VARCHAR(200) NOT NULL,
    gatilho_valor NUMERIC(12,2) NOT NULL,
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Equipamentos (já existe, mantido)
CREATE TABLE IF NOT EXISTS equipamentos (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    nome VARCHAR(200) NOT NULL,
    descricao TEXT,
    tipo VARCHAR(100),
    grupo VARCHAR(100),
    placa VARCHAR(30),
    serie VARCHAR(100),
    setor_id INTEGER REFERENCES setores(id),
    km_atual NUMERIC(12,2) DEFAULT 0,
    horas_atual NUMERIC(12,2) DEFAULT 0,
    template_revisao_id INTEGER REFERENCES templates_revisao(id),
    template_lubrificacao_id INTEGER,  -- referência criada abaixo
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── NOVAS TABELAS ──────────────────────────────────────────

-- Templates de Lubrificação
CREATE TABLE IF NOT EXISTS templates_lubrificacao (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    tipo_controle VARCHAR(20) NOT NULL CHECK (tipo_controle IN ('horas', 'km')),
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- FK da coluna template_lubrificacao_id (caso ainda não exista)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_equipamentos_template_lub'
    ) THEN
        ALTER TABLE equipamentos
            ADD CONSTRAINT fk_equipamentos_template_lub
            FOREIGN KEY (template_lubrificacao_id) REFERENCES templates_lubrificacao(id);
    END IF;
END $$;

-- Itens dos Templates de Lubrificação
CREATE TABLE IF NOT EXISTS itens_template_lubrificacao (
    id SERIAL PRIMARY KEY,
    template_id INTEGER NOT NULL REFERENCES templates_lubrificacao(id) ON DELETE CASCADE,
    nome_item VARCHAR(200) NOT NULL,
    tipo_produto VARCHAR(100),
    intervalo_valor NUMERIC(12,2) NOT NULL,
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Vínculos Responsável × Equipamento (operacional)
CREATE TABLE IF NOT EXISTS vinculos_equipamento (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipamento_id UUID NOT NULL REFERENCES equipamentos(id) ON DELETE CASCADE,
    responsavel_id UUID NOT NULL REFERENCES responsaveis(id) ON DELETE CASCADE,
    tipo_vinculo VARCHAR(100) DEFAULT 'lubrificador',
    principal BOOLEAN DEFAULT FALSE,
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (equipamento_id, responsavel_id, tipo_vinculo)
);

-- Vínculos Responsável × Setor (gestão)
CREATE TABLE IF NOT EXISTS vinculos_setor (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    setor_id UUID NOT NULL REFERENCES setores(id) ON DELETE CASCADE,
    responsavel_id UUID NOT NULL REFERENCES responsaveis(id) ON DELETE CASCADE,
    tipo_responsabilidade VARCHAR(100) DEFAULT 'gestor',
    principal BOOLEAN DEFAULT FALSE,
    ativo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (setor_id, responsavel_id, tipo_responsabilidade)
);

-- Leituras (histórico de KM/Horas)
CREATE TABLE IF NOT EXISTS leituras (
    id SERIAL PRIMARY KEY,
    equipamento_id INTEGER NOT NULL REFERENCES equipamentos(id) ON DELETE CASCADE,
    tipo_leitura VARCHAR(20) NOT NULL CHECK (tipo_leitura IN ('km', 'horas', 'ambos')),
    km_valor NUMERIC(12,2),
    horas_valor NUMERIC(12,2),
    data_leitura DATE NOT NULL DEFAULT CURRENT_DATE,
    responsavel_id INTEGER REFERENCES responsaveis(id),
    observacoes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Execuções de Manutenção (revisões)
CREATE TABLE IF NOT EXISTS execucoes_manutencao (
    id SERIAL PRIMARY KEY,
    equipamento_id INTEGER NOT NULL REFERENCES equipamentos(id),
    responsavel_id INTEGER REFERENCES responsaveis(id),
    tipo VARCHAR(50) NOT NULL CHECK (tipo IN ('revisao', 'lubrificacao')),
    data_execucao DATE NOT NULL,
    km_execucao NUMERIC(12,2) DEFAULT 0,
    horas_execucao NUMERIC(12,2) DEFAULT 0,
    observacoes TEXT,
    status VARCHAR(30) DEFAULT 'concluida' CHECK (status IN ('concluida', 'pendente')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Execuções de Lubrificação (por item)
CREATE TABLE IF NOT EXISTS execucoes_lubrificacao (
    id SERIAL PRIMARY KEY,
    equipamento_id INTEGER NOT NULL REFERENCES equipamentos(id),
    item_id INTEGER REFERENCES itens_template_lubrificacao(id),
    responsavel_id INTEGER REFERENCES responsaveis(id),
    nome_item VARCHAR(200),
    tipo_produto VARCHAR(100),
    data_execucao DATE NOT NULL,
    km_execucao NUMERIC(12,2) DEFAULT 0,
    horas_execucao NUMERIC(12,2) DEFAULT 0,
    observacoes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Registro de alertas enviados
CREATE TABLE IF NOT EXISTS alertas_enviados (
    id SERIAL PRIMARY KEY,
    equipamento_id INTEGER REFERENCES equipamentos(id),
    responsavel_id INTEGER REFERENCES responsaveis(id),
    tipo_alerta VARCHAR(50),
    perfil VARCHAR(30),
    mensagem TEXT,
    enviado_em TIMESTAMPTZ DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_vinculos_equipamento_eqp ON vinculos_equipamento(equipamento_id);
CREATE INDEX IF NOT EXISTS idx_vinculos_setor_set ON vinculos_setor(setor_id);
CREATE INDEX IF NOT EXISTS idx_execucoes_lub_eqp ON execucoes_lubrificacao(equipamento_id);
CREATE INDEX IF NOT EXISTS idx_leituras_eqp ON leituras(equipamento_id);


-- ============================================================
-- FASE 1 — Auditoria e configurações persistentes
-- ============================================================

CREATE TABLE IF NOT EXISTS configuracoes_sistema (
    chave VARCHAR(100) PRIMARY KEY,
    valor VARCHAR(500) NOT NULL,
    descricao TEXT,
    atualizado_em TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS log_auditoria (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id UUID NULL,
    acao VARCHAR(100) NOT NULL,
    entidade VARCHAR(100) NOT NULL,
    entidade_id TEXT,
    valor_antigo JSONB,
    valor_novo JSONB,
    criado_em TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_log_auditoria_entidade ON log_auditoria(entidade, entidade_id);
CREATE INDEX IF NOT EXISTS idx_log_auditoria_data ON log_auditoria(criado_em DESC);


-- ============================================================
-- Compatibilidade com bancos existentes em UUID
-- ============================================================
-- Observação: em bancos já existentes, aplique somente as tabelas novas
-- da Fase 1 e as tabelas de vínculo ajustadas para UUID. Não é necessário
-- recriar as tabelas legadas se elas já existirem em produção.


-- Comentários / log por equipamento
CREATE TABLE IF NOT EXISTS public.comentarios_equipamento (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipamento_id UUID NOT NULL REFERENCES public.equipamentos(id) ON DELETE CASCADE,
    usuario_id UUID NULL,
    autor_nome TEXT,
    comentario TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comentarios_equipamento_eqp
    ON public.comentarios_equipamento (equipamento_id, created_at DESC);


-- Configurações adicionais para automação assistida de alertas
-- Inserir manualmente, se desejar:
-- insert into configuracoes_sistema (chave, valor, descricao) values ('alerta_cooldown_horas', '24', 'Cooldown entre alertas do mesmo equipamento/tipo em horas') on conflict (chave) do nothing;
-- insert into configuracoes_sistema (chave, valor, descricao) values ('fila_alertas_limite', '200', 'Limite padrão da fila sugerida de alertas por tipo') on conflict (chave) do nothing;
