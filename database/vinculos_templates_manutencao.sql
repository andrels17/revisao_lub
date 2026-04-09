create table if not exists public.vinculos_templates_manutencao (
    id uuid primary key default gen_random_uuid(),
    template_revisao_id uuid not null references public.templates_revisao(id) on delete cascade,
    template_lubrificacao_id uuid not null references public.templates_lubrificacao(id) on delete cascade,
    observacoes text,
    ativo boolean not null default true,
    created_at timestamptz not null default now(),
    unique (template_revisao_id, template_lubrificacao_id)
);
