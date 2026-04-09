create extension if not exists pgcrypto;

create table if not exists public.execucao_manutencao_itens (
    id uuid primary key default gen_random_uuid(),
    execucao_id integer not null references public.execucoes_manutencao(id) on delete cascade,
    item_id_referencia integer,
    item_nome text not null,
    produto text,
    intervalo_valor numeric,
    marcado boolean not null default true,
    created_at timestamptz not null default now()
);

create index if not exists idx_execucao_manutencao_itens_execucao
    on public.execucao_manutencao_itens (execucao_id);
