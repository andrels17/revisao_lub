"""
Relatório de Manutenção por Período
Exporta revisões e lubrificações realizadas em um intervalo de datas.
"""
import datetime
import re

import pandas as pd
import streamlit as st

from database.connection import get_conn, release_conn
from services import prioridades_service
from ui.exportacao import botao_exportar_excel, botao_exportar_pdf_relatorio_manutencao

try:
    import psycopg2
except Exception:  # pragma: no cover
    psycopg2 = None


PLOTLY_COLORS = {
    "rev": "#4f8cff",
    "lub": "#22c55e",
    "axis": "rgba(157,176,199,.36)",
    "grid": "rgba(157,176,199,.12)",
    "font": "#dbe9ff",
    "muted": "#9db0c7",
}


@st.cache_data(ttl=180, show_spinner=False)
def _carregar_revisoes(data_ini, data_fim, setor_id=None, equipamento_id=None):
    conn = get_conn()
    cur = conn.cursor()
    try:
        filtros = ["em.tipo = 'revisao'", "em.data_execucao >= %s", "em.data_execucao <= %s"]
        params = [data_ini, data_fim]
        if setor_id:
            filtros.append("e.setor_id = %s")
            params.append(setor_id)
        if equipamento_id:
            filtros.append("em.equipamento_id = %s")
            params.append(equipamento_id)

        cur.execute(
            f"""
            select em.id,
                   em.data_execucao,
                   em.equipamento_id,
                   e.setor_id,
                   coalesce(e.tipo, '-')                as tipo_equipamento,
                   e.codigo,
                   e.nome                               as equipamento,
                   coalesce(s.nome, '-')               as setor,
                   em.km_execucao,
                   em.horas_execucao,
                   coalesce(r.nome, '-')               as responsavel,
                   coalesce(em.status, 'concluida')    as status,
                   em.observacoes
            from execucoes_manutencao em
            join equipamentos e on e.id = em.equipamento_id
            left join setores s      on s.id = e.setor_id
            left join responsaveis r on r.id = em.responsavel_id
            where {' and '.join(filtros)}
            order by em.data_execucao desc, e.codigo
            """,
            params,
        )
        rows = cur.fetchall()
        return pd.DataFrame(
            rows,
            columns=[
                "ID",
                "Data",
                "Equipamento ID",
                "Setor ID",
                "Tipo Equipamento",
                "Código",
                "Equipamento",
                "Setor",
                "KM",
                "Horas",
                "Responsável",
                "Status",
                "Observações",
            ],
        )
    finally:
        release_conn(conn)


@st.cache_data(ttl=180, show_spinner=False)
def _carregar_lubrificacoes(data_ini, data_fim, setor_id=None, equipamento_id=None):
    conn = get_conn()
    cur = conn.cursor()
    try:
        filtros = ["el.data_execucao >= %s", "el.data_execucao <= %s"]
        params = [data_ini, data_fim]
        if setor_id:
            filtros.append("e.setor_id = %s")
            params.append(setor_id)
        if equipamento_id:
            filtros.append("el.equipamento_id = %s")
            params.append(equipamento_id)

        try:
            cur.execute(
                f"""
                select el.id,
                       el.data_execucao,
                       el.equipamento_id,
                       e.setor_id,
                       coalesce(e.tipo, '-')            as tipo_equipamento,
                       e.codigo,
                       e.nome                           as equipamento,
                       coalesce(s.nome, '-')            as setor,
                       el.nome_item,
                       coalesce(el.tipo_produto, '-')   as tipo_produto,
                       el.km_execucao,
                       el.horas_execucao,
                       coalesce(r.nome, '-')            as responsavel,
                       el.observacoes
                from execucoes_lubrificacao el
                join equipamentos e on e.id = el.equipamento_id
                left join setores s      on s.id = e.setor_id
                left join responsaveis r on r.id = el.responsavel_id
                where {' and '.join(filtros)}
                order by el.data_execucao desc, e.codigo
                """,
                params,
            )
            rows = cur.fetchall()
        except Exception as exc:
            if not psycopg2 or not isinstance(
                exc,
                (
                    psycopg2.errors.UndefinedTable,
                    psycopg2.errors.UndefinedColumn,
                    psycopg2.errors.UndefinedObject,
                ),
            ):
                raise
            conn.rollback()
            rows = []

        return pd.DataFrame(
            rows,
            columns=[
                "ID",
                "Data",
                "Equipamento ID",
                "Setor ID",
                "Tipo Equipamento",
                "Código",
                "Equipamento",
                "Setor",
                "Item",
                "Produto",
                "KM",
                "Horas",
                "Responsável",
                "Observações",
            ],
        )
    finally:
        release_conn(conn)


def _carregar_setores():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("select id, nome from setores where ativo = true order by nome")
        return cur.fetchall()
    finally:
        release_conn(conn)


def _carregar_equipamentos(setor_id=None):
    conn = get_conn()
    cur = conn.cursor()
    try:
        if setor_id:
            cur.execute(
                "select id, codigo, nome from equipamentos where ativo = true and setor_id = %s order by codigo",
                (setor_id,),
            )
        else:
            cur.execute("select id, codigo, nome from equipamentos where ativo = true order by codigo")
        return cur.fetchall()
    finally:
        release_conn(conn)


def _normalizar_datas(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
    out = df.copy()
    if "Data" in out.columns:
        out["Data"] = pd.to_datetime(out["Data"], errors="coerce")
        out = out.sort_values(["Data", "Código"], ascending=[False, True], na_position="last")
    return out


def _filtrar_busca(df: pd.DataFrame, termo: str, colunas: list[str]) -> pd.DataFrame:
    if df.empty or not termo:
        return df
    termo = termo.strip().lower()
    if not termo:
        return df

    mascara = pd.Series(False, index=df.index)
    for coluna in colunas:
        if coluna in df.columns:
            mascara = mascara | df[coluna].fillna("").astype(str).str.lower().str.contains(termo, regex=False)
    return df.loc[mascara].copy()


def _formatar_datas_exibicao(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if "Data" in out.columns:
        out["Data"] = pd.to_datetime(out["Data"], errors="coerce").dt.strftime("%d/%m/%Y")
        out["Data"] = out["Data"].fillna("-")
    return out


ETAPA_REGEX = re.compile(r"^Etapa:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def _extrair_etapa_observacao(obs: str) -> str | None:
    if not obs:
        return None
    match = ETAPA_REGEX.search(str(obs))
    return match.group(1).strip() if match else None


@st.cache_data(ttl=180, show_spinner=False)
def _carregar_hierarquia_setores() -> dict:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("select id, nome, setor_pai_id from setores order by nome")
        rows = cur.fetchall()
    finally:
        release_conn(conn)

    itens = [{"id": r[0], "nome": r[1], "setor_pai_id": r[2]} for r in rows]
    mapa = {str(s["id"]): s for s in itens}
    hier = {}
    for s in itens:
        atual = s
        caminho = [s.get("nome") or "-"]
        while atual.get("setor_pai_id"):
            pai = mapa.get(str(atual["setor_pai_id"]))
            if not pai:
                break
            caminho.append(pai.get("nome") or "-")
            atual = pai
        caminho = list(reversed(caminho))
        depto = caminho[0] if caminho else (s.get("nome") or "-")
        grupo = caminho[1] if len(caminho) > 1 else "—"
        hier[str(s["id"])] = {"Departamento": depto, "Grupo": grupo, "Setor": s.get("nome") or "-"}
    return hier


@st.cache_data(ttl=180, show_spinner=False)
def _carregar_mapa_etapas_revisao() -> dict:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select e.id as equipamento_id,
                   coalesce(e.tipo, '-') as tipo_equipamento,
                   e.setor_id,
                   coalesce(tr.tipo_controle, 'km') as tipo_controle,
                   et.nome_etapa,
                   coalesce(et.gatilho_valor, 0) as gatilho_valor,
                   max(coalesce(et.gatilho_valor, 0)) over (partition by tr.id) as ciclo_maximo
            from equipamentos e
            join templates_revisao tr on tr.id = e.template_revisao_id
            join etapas_template_revisao et on et.template_id = tr.id and et.ativo = true
            """
        )
        rows = cur.fetchall()
    except Exception:
        conn.rollback()
        rows = []
    finally:
        release_conn(conn)

    mapa = {}
    for equipamento_id, tipo_equipamento, setor_id, tipo_controle, nome_etapa, gatilho_valor, ciclo_maximo in rows:
        chave = (str(equipamento_id), str(nome_etapa or '').strip().lower())
        mapa[chave] = {
            "Tipo Controle": (tipo_controle or 'km').lower(),
            "Valor Base": float(gatilho_valor or 0),
            "Ciclo Máximo": float(ciclo_maximo or gatilho_valor or 0),
            "Tipo Equipamento": tipo_equipamento or '-',
            "Setor ID": setor_id,
        }
    return mapa


@st.cache_data(ttl=180, show_spinner=False)
def _carregar_mapa_itens_lubrificacao() -> dict:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            select e.id as equipamento_id,
                   coalesce(e.tipo, '-') as tipo_equipamento,
                   e.setor_id,
                   coalesce(tl.tipo_controle, 'km') as tipo_controle,
                   itl.nome_item,
                   coalesce(itl.intervalo_valor, 0) as intervalo_valor
            from equipamentos e
            join templates_lubrificacao tl on tl.id = e.template_lubrificacao_id
            join itens_template_lubrificacao itl on itl.template_id = tl.id and coalesce(itl.ativo, true) = true
            """
        )
        rows = cur.fetchall()
    except Exception:
        conn.rollback()
        rows = []
    finally:
        release_conn(conn)

    mapa = {}
    for equipamento_id, tipo_equipamento, setor_id, tipo_controle, nome_item, intervalo_valor in rows:
        chave = (str(equipamento_id), str(nome_item or '').strip().lower())
        mapa[chave] = {
            "Tipo Controle": (tipo_controle or 'km').lower(),
            "Intervalo Base": float(intervalo_valor or 0),
            "Tipo Equipamento": tipo_equipamento or '-',
            "Setor ID": setor_id,
        }
    return mapa


def _fmt_intervalo(valor: float, controle: str) -> str:
    valor = float(valor or 0)
    controle = 'horas' if str(controle).lower().startswith('h') else 'km'
    if controle == 'horas':
        return f"{valor:,.0f} h".replace(',', '.')
    return f"{valor:,.0f} km".replace(',', '.')


def _fmt_atraso(valor: float, controle: str) -> str:
    valor = max(float(valor or 0), 0.0)
    controle = 'horas' if str(controle).lower().startswith('h') else 'km'
    sufixo = 'h' if controle == 'horas' else 'km'
    return f"{valor:,.0f} {sufixo}".replace(',', '.')


def _calcular_previsto_revisao(leitura_execucao: float, etapa_valor: float, ciclo_maximo: float) -> float:
    leitura_execucao = float(leitura_execucao or 0)
    etapa_valor = float(etapa_valor or 0)
    ciclo_maximo = float(ciclo_maximo or 0)
    if etapa_valor <= 0:
        return leitura_execucao
    if ciclo_maximo <= 0:
        return etapa_valor
    if leitura_execucao <= etapa_valor:
        return etapa_valor
    indice = int((leitura_execucao - etapa_valor) // ciclo_maximo)
    previsto = etapa_valor + (indice * ciclo_maximo)
    if previsto <= 0:
        previsto = etapa_valor
    while previsto + ciclo_maximo <= leitura_execucao and ciclo_maximo > 0:
        previsto += ciclo_maximo
    return previsto


def _calcular_previsto_lubrificacao(leitura_execucao: float, intervalo_base: float) -> float:
    leitura_execucao = float(leitura_execucao or 0)
    intervalo_base = float(intervalo_base or 0)
    if intervalo_base <= 0:
        return leitura_execucao
    if leitura_execucao <= intervalo_base:
        return intervalo_base
    previsto = int(leitura_execucao // intervalo_base) * intervalo_base
    if previsto <= 0:
        previsto = intervalo_base
    return previsto


def _enriquecer_macro_revisoes(df_rev: pd.DataFrame) -> pd.DataFrame:
    if df_rev is None or df_rev.empty:
        return pd.DataFrame()
    out = _normalizar_datas(df_rev)
    mapa_etapas = _carregar_mapa_etapas_revisao()
    hier = _carregar_hierarquia_setores()

    out['Etapa'] = out['Observações'].apply(_extrair_etapa_observacao)
    out['Etapa Chave'] = out['Etapa'].fillna('').astype(str).str.strip().str.lower()
    out['Equipamento Chave'] = out['Equipamento ID'].astype(str)

    metas = out.apply(lambda row: mapa_etapas.get((row['Equipamento Chave'], row['Etapa Chave']), {}), axis=1)
    out['Controle'] = metas.apply(lambda d: d.get('Tipo Controle') if d else None)
    out['Valor Base'] = metas.apply(lambda d: d.get('Valor Base') if d else None)
    out['Ciclo Máximo'] = metas.apply(lambda d: d.get('Ciclo Máximo') if d else None)
    out['Tipo Equipamento'] = out['Tipo Equipamento'].fillna(metas.apply(lambda d: d.get('Tipo Equipamento') if d else '-')).replace('', '-')
    out['Setor ID'] = out['Setor ID'].fillna(metas.apply(lambda d: d.get('Setor ID') if d else None))

    out['Controle'] = out['Controle'].fillna(out.apply(lambda row: 'horas' if pd.notna(row.get('Horas')) and pd.isna(row.get('KM')) else 'km', axis=1))
    out['Leitura Execução'] = out.apply(lambda row: float(row['Horas'] or 0) if str(row['Controle']).startswith('h') else float(row['KM'] or 0), axis=1)
    out['Valor Base'] = pd.to_numeric(out['Valor Base'], errors='coerce')
    out['Ciclo Máximo'] = pd.to_numeric(out['Ciclo Máximo'], errors='coerce')
    out['Previsto'] = out.apply(lambda row: _calcular_previsto_revisao(row['Leitura Execução'], row['Valor Base'], row['Ciclo Máximo']), axis=1)
    out['Atraso'] = (out['Leitura Execução'] - out['Previsto']).clip(lower=0)
    out['Prazo'] = out['Atraso'].apply(lambda v: 'Atrasada' if float(v or 0) > 0 else 'No prazo')
    out['Referência'] = out.apply(lambda row: _fmt_intervalo(row['Valor Base'], row['Controle']) if pd.notna(row['Valor Base']) else '-', axis=1)
    out['Etapa Macro'] = out.apply(lambda row: row['Etapa'] if row['Etapa'] else row['Referência'], axis=1)

    def _hier(row):
        return hier.get(str(row['Setor ID']), {'Departamento': row.get('Setor') or '-', 'Grupo': '—', 'Setor': row.get('Setor') or '-'})

    info_h = out.apply(_hier, axis=1)
    out['Departamento'] = info_h.apply(lambda d: d['Departamento'])
    out['Grupo'] = info_h.apply(lambda d: d['Grupo'])
    return out


def _enriquecer_macro_lubrificacoes(df_lub: pd.DataFrame) -> pd.DataFrame:
    if df_lub is None or df_lub.empty:
        return pd.DataFrame()
    out = _normalizar_datas(df_lub)
    mapa_itens = _carregar_mapa_itens_lubrificacao()
    hier = _carregar_hierarquia_setores()

    out['Item Chave'] = out['Item'].fillna('').astype(str).str.strip().str.lower()
    out['Equipamento Chave'] = out['Equipamento ID'].astype(str)
    metas = out.apply(lambda row: mapa_itens.get((row['Equipamento Chave'], row['Item Chave']), {}), axis=1)
    out['Controle'] = metas.apply(lambda d: d.get('Tipo Controle') if d else None)
    out['Intervalo Base'] = metas.apply(lambda d: d.get('Intervalo Base') if d else None)
    out['Tipo Equipamento'] = out['Tipo Equipamento'].fillna(metas.apply(lambda d: d.get('Tipo Equipamento') if d else '-')).replace('', '-')
    out['Setor ID'] = out['Setor ID'].fillna(metas.apply(lambda d: d.get('Setor ID') if d else None))

    out['Controle'] = out['Controle'].fillna(out.apply(lambda row: 'horas' if pd.notna(row.get('Horas')) and pd.isna(row.get('KM')) else 'km', axis=1))
    out['Leitura Execução'] = out.apply(lambda row: float(row['Horas'] or 0) if str(row['Controle']).startswith('h') else float(row['KM'] or 0), axis=1)
    out['Intervalo Base'] = pd.to_numeric(out['Intervalo Base'], errors='coerce')
    out['Previsto'] = out.apply(lambda row: _calcular_previsto_lubrificacao(row['Leitura Execução'], row['Intervalo Base']), axis=1)
    out['Atraso'] = (out['Leitura Execução'] - out['Previsto']).clip(lower=0)
    out['Prazo'] = out['Atraso'].apply(lambda v: 'Atrasada' if float(v or 0) > 0 else 'No prazo')
    out['Referência'] = out.apply(lambda row: _fmt_intervalo(row['Intervalo Base'], row['Controle']) if pd.notna(row['Intervalo Base']) else '-', axis=1)

    def _hier(row):
        return hier.get(str(row['Setor ID']), {'Departamento': row.get('Setor') or '-', 'Grupo': '—', 'Setor': row.get('Setor') or '-'})

    info_h = out.apply(_hier, axis=1)
    out['Departamento'] = info_h.apply(lambda d: d['Departamento'])
    out['Grupo'] = info_h.apply(lambda d: d['Grupo'])
    return out


def _resumir_macro(df: pd.DataFrame, modo: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    chaves = ['Departamento', 'Grupo', 'Tipo Equipamento']
    if modo == 'rev':
        chaves += ['Etapa Macro', 'Referência', 'Controle']
    else:
        chaves += ['Item', 'Referência', 'Controle']

    resumo = (
        df.groupby(chaves, dropna=False)
        .agg(
            Equipamentos=('Código', pd.Series.nunique),
            Execuções=('ID', 'count'),
            NoPrazo=('Prazo', lambda s: int((s == 'No prazo').sum())),
            Atrasadas=('Prazo', lambda s: int((s == 'Atrasada').sum())),
            AtrasoMedio=('Atraso', lambda s: float(pd.Series(s)[pd.Series(s) > 0].mean()) if (pd.Series(s) > 0).any() else 0.0),
            MaiorAtraso=('Atraso', 'max'),
        )
        .reset_index()
    )
    resumo['Controle'] = resumo['Controle'].fillna('km')
    resumo['Atraso médio'] = resumo.apply(lambda row: _fmt_atraso(row['AtrasoMedio'], row['Controle']), axis=1)
    resumo['Maior atraso'] = resumo.apply(lambda row: _fmt_atraso(row['MaiorAtraso'], row['Controle']), axis=1)
    resumo['No prazo'] = resumo['NoPrazo']
    resumo['Atrasadas'] = resumo['Atrasadas']
    resumo['Equipamentos'] = resumo['Equipamentos'].astype(int)
    resumo['Execuções'] = resumo['Execuções'].astype(int)
    resumo['Tipo'] = resumo['Tipo Equipamento'].fillna('-')
    if modo == 'rev':
        resumo = resumo.rename(columns={'Etapa Macro': 'Etapa'})
        colunas = ['Departamento', 'Grupo', 'Tipo', 'Etapa', 'Referência', 'Equipamentos', 'Execuções', 'No prazo', 'Atrasadas', 'Atraso médio', 'Maior atraso']
    else:
        colunas = ['Departamento', 'Grupo', 'Tipo', 'Item', 'Referência', 'Equipamentos', 'Execuções', 'No prazo', 'Atrasadas', 'Atraso médio', 'Maior atraso']
    return resumo[colunas].sort_values(['Departamento', 'Grupo', 'Tipo', 'Referência'])


def _render_macro_hierarquico(df_macro: pd.DataFrame, modo: str, titulo: str, descricao: str) -> None:
    st.markdown(f"<div class='section-card'><h3>{titulo}</h3><p>{descricao}</p></div>", unsafe_allow_html=True)
    resumo = _resumir_macro(df_macro, modo)
    if resumo.empty:
        st.info('Sem dados suficientes para consolidar a visão macro neste período.')
        return

    top_cols = st.columns(4)
    top_cols[0].metric('Departamentos', int(resumo['Departamento'].nunique()))
    top_cols[1].metric('Grupos', int(resumo['Grupo'].nunique()))
    top_cols[2].metric('Execuções', int(resumo['Execuções'].sum()))
    top_cols[3].metric('Atrasadas', int(resumo['Atrasadas'].sum()))

    st.dataframe(resumo, use_container_width=True, hide_index=True)

    for departamento, df_dep in resumo.groupby('Departamento', dropna=False):
        atrasadas = int(df_dep['Atrasadas'].sum())
        execucoes = int(df_dep['Execuções'].sum())
        label = f"{departamento} · {execucoes} execução(ões) · {atrasadas} atrasada(s)"
        with st.expander(label, expanded=False):
            for grupo, df_grp in df_dep.groupby('Grupo', dropna=False):
                st.markdown(f"**Grupo: {grupo}**")
                st.dataframe(df_grp.drop(columns=['Departamento', 'Grupo']), use_container_width=True, hide_index=True)


def _colunas_publicas_revisoes(df: pd.DataFrame) -> pd.DataFrame:
    colunas = ['Data', 'Código', 'Equipamento', 'Setor', 'Tipo Equipamento', 'Etapa', 'Referência', 'Prazo', 'Atraso', 'Responsável', 'Status', 'Observações']
    base = df.copy()
    if 'Atraso' in base.columns:
        base['Atraso'] = base.apply(lambda row: _fmt_atraso(row['Atraso'], row.get('Controle', 'km')), axis=1)
    for coluna in colunas:
        if coluna not in base.columns:
            base[coluna] = '-'
    return base[colunas]


def _colunas_publicas_lubrificacoes(df: pd.DataFrame) -> pd.DataFrame:
    colunas = ['Data', 'Código', 'Equipamento', 'Setor', 'Tipo Equipamento', 'Item', 'Produto', 'Referência', 'Prazo', 'Atraso', 'Responsável', 'Observações']
    base = df.copy()
    if 'Atraso' in base.columns:
        base['Atraso'] = base.apply(lambda row: _fmt_atraso(row['Atraso'], row.get('Controle', 'km')), axis=1)
    for coluna in colunas:
        if coluna not in base.columns:
            base[coluna] = '-'
    return base[colunas]




def _render_sem_movimentacao(setor_id=None, equipamento_id=None) -> None:
    resumo = prioridades_service.resumo_sem_movimentacao(setor_id=setor_id, equipamento_id=equipamento_id, limite=10)
    total = int(resumo.get("quantidade", 0))
    threshold = int(resumo.get("threshold", 0))
    top10 = resumo.get("top10") or []
    st.markdown("<div class='section-card'><h3>Sem movimentação / sem leitura</h3><p>Leitura operacional para destacar equipamentos acima da janela configurada sem atualização de KM/Horas.</p></div>", unsafe_allow_html=True)
    k1, k2 = st.columns(2)
    k1.metric("Equipamentos acima da janela", total)
    k2.metric("Janela configurada", f"{threshold} dia(s)")
    if not top10:
        st.success("Nenhum equipamento acima da janela configurada para o recorte atual.")
        return
    st.dataframe(pd.DataFrame(top10), use_container_width=True, hide_index=True)

def _render_page_header() -> None:
    st.markdown(
        """
        <div class="page-header-card">
            <div class="eyebrow">📈 Ferramentas</div>
            <h2>Relatório de manutenção</h2>
            <p>Consolide revisões e lubrificações por período, enxergue a distribuição operacional e exporte o resultado em um formato mais executivo.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_kpi_cards(df_rev: pd.DataFrame, df_lub: pd.DataFrame) -> None:
    total = len(df_rev) + len(df_lub)
    equipamentos = len(set(df_rev.get("Código", pd.Series(dtype=str)).dropna().astype(str).tolist() + df_lub.get("Código", pd.Series(dtype=str)).dropna().astype(str).tolist()))
    cards = [
        ("status-info", "📦 Total de registros", total, "Execuções no período"),
        ("status-danger", "🔧 Revisões", len(df_rev), "Itens concluídos"),
        ("status-success", "🛢️ Lubrificações", len(df_lub), "Itens concluídos"),
        ("status-warning", "🚜 Equipamentos impactados", equipamentos, "Base com execução"),
    ]
    html_cards = []
    for css, label, value, sub in cards:
        html_cards.append(
            f"<div class='status-kpi {css}'><div class='label'>{label}</div><div class='value'>{int(value)}</div><div class='sub'>{sub}</div></div>"
        )
    st.markdown(f"<div class='status-kpi-grid'>{''.join(html_cards)}</div>", unsafe_allow_html=True)


def _apply_plotly_theme(fig, height: int = 340):
    fig.update_layout(
        height=height,
        margin=dict(t=22, b=10, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=PLOTLY_COLORS["font"], size=13),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=PLOTLY_COLORS["muted"]),
        ),
        xaxis=dict(
            showgrid=False,
            linecolor=PLOTLY_COLORS["axis"],
            tickfont=dict(color=PLOTLY_COLORS["muted"]),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=PLOTLY_COLORS["grid"],
            zeroline=False,
            tickfont=dict(color=PLOTLY_COLORS["muted"]),
        ),
        hoverlabel=dict(bgcolor="#0f1b2d", font_color="#eef5ff", bordercolor="#1f3350"),
    )
    return fig


def _render_distribution_chart(df_rev: pd.DataFrame, df_lub: pd.DataFrame) -> None:
    base = []
    if not df_rev.empty:
        rev = df_rev.copy()
        rev["Tipo"] = "Revisões"
        base.append(rev[["Setor", "Tipo"]])
    if not df_lub.empty:
        lub = df_lub.copy()
        lub["Tipo"] = "Lubrificações"
        base.append(lub[["Setor", "Tipo"]])

    if not base:
        st.info("Sem dados suficientes para gerar a visão executiva.")
        return

    df = pd.concat(base, ignore_index=True)
    resumo = df.groupby(["Setor", "Tipo"]).size().reset_index(name="Qtd")

    try:
        import plotly.express as px

        fig = px.bar(
            resumo,
            x="Setor",
            y="Qtd",
            color="Tipo",
            barmode="group",
            color_discrete_map={"Revisões": PLOTLY_COLORS["rev"], "Lubrificações": PLOTLY_COLORS["lub"]},
        )
        _apply_plotly_theme(fig, 360)
        fig.update_traces(marker_line_width=0, opacity=0.95, hovertemplate="%{x}<br>%{fullData.name}: %{y}<extra></extra>")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    except Exception:
        pivot = resumo.pivot(index="Setor", columns="Tipo", values="Qtd").fillna(0)
        st.bar_chart(pivot, use_container_width=True)


def _safe_datetime_series(df: pd.DataFrame, col: str = "Data") -> pd.Series:
    if df is None or df.empty or col not in df.columns:
        return pd.Series(dtype="datetime64[ns]")
    return pd.to_datetime(df[col], errors="coerce")


def _render_timeline_chart(df_rev: pd.DataFrame, df_lub: pd.DataFrame) -> None:
    base = []
    if not df_rev.empty:
        rev = df_rev[["Data"]].copy()
        rev["Data"] = _safe_datetime_series(df_rev, "Data")
        rev["Tipo"] = "Revisões"
        base.append(rev)
    if not df_lub.empty:
        lub = df_lub[["Data"]].copy()
        lub["Data"] = _safe_datetime_series(df_lub, "Data")
        lub["Tipo"] = "Lubrificações"
        base.append(lub)
    if not base:
        st.info("Sem dados suficientes para gerar evolução diária.")
        return

    df = pd.concat(base, ignore_index=True)
    df = df.dropna(subset=["Data"])
    if df.empty:
        st.info("Sem datas válidas para montar a série temporal.")
        return

    df["DiaData"] = df["Data"].dt.floor("D")
    resumo = (
        df.groupby(["DiaData", "Tipo"])
        .size()
        .reset_index(name="Qtd")
        .sort_values("DiaData")
    )
    resumo["Dia"] = resumo["DiaData"].dt.strftime("%d/%m")

    try:
        import plotly.express as px

        fig = px.line(
            resumo,
            x="Dia",
            y="Qtd",
            color="Tipo",
            markers=True,
            color_discrete_map={"Revisões": PLOTLY_COLORS["rev"], "Lubrificações": PLOTLY_COLORS["lub"]},
        )
        _apply_plotly_theme(fig, 320)
        fig.update_traces(mode="lines+markers", hovertemplate="%{x}<br>%{fullData.name}: %{y}<extra></extra>")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    except Exception:
        pivot = resumo.pivot(index="Dia", columns="Tipo", values="Qtd").fillna(0)
        st.line_chart(pivot, use_container_width=True)


def _render_evolucao_diaria(df_rev: pd.DataFrame, df_lub: pd.DataFrame) -> None:
    _render_timeline_chart(df_rev, df_lub)


def _render_responsaveis_summary(df_rev: pd.DataFrame, df_lub: pd.DataFrame) -> None:
    frames = []
    if not df_rev.empty:
        r = df_rev[["Responsável"]].copy()
        r["Tipo"] = "Revisão"
        frames.append(r)
    if not df_lub.empty:
        l = df_lub[["Responsável"]].copy()
        l["Tipo"] = "Lubrificação"
        frames.append(l)

    if not frames:
        st.info("Nenhum responsável registrado no período selecionado.")
        return

    df = pd.concat(frames, ignore_index=True)
    resumo = (
        df.groupby(["Responsável", "Tipo"])
        .size()
        .reset_index(name="Qtd")
        .sort_values("Qtd", ascending=False)
    )
    st.dataframe(resumo, use_container_width=True, hide_index=True)


def _render_highlights(df_rev: pd.DataFrame, df_lub: pd.DataFrame) -> None:
    frases = []
    total = len(df_rev) + len(df_lub)
    if total == 0:
        st.info("Nenhuma execução encontrada no período atual.")
        return

    frames = []
    if not df_rev.empty:
        rev = df_rev.copy()
        rev["Tipo"] = "Revisão"
        frames.append(rev[["Setor", "Responsável", "Código", "Tipo"]])
    if not df_lub.empty:
        lub = df_lub.copy()
        lub["Tipo"] = "Lubrificação"
        frames.append(lub[["Setor", "Responsável", "Código", "Tipo"]])
    df = pd.concat(frames, ignore_index=True)

    top_setor = df.groupby("Setor").size().sort_values(ascending=False)
    if not top_setor.empty:
        frases.append(f"<b>Setor líder:</b> {top_setor.index[0]} com {int(top_setor.iloc[0])} execução(ões).")

    top_resp = df.groupby("Responsável").size().sort_values(ascending=False)
    if not top_resp.empty:
        frases.append(f"<b>Maior volume por responsável:</b> {top_resp.index[0]} com {int(top_resp.iloc[0])} registro(s).")

    top_eq = df.groupby("Código").size().sort_values(ascending=False)
    if not top_eq.empty:
        frases.append(f"<b>Equipamento mais recorrente:</b> {top_eq.index[0]} apareceu {int(top_eq.iloc[0])} vez(es).")

    pct_rev = round((len(df_rev) / total) * 100) if total else 0
    pct_lub = round((len(df_lub) / total) * 100) if total else 0
    frases.append(f"<b>Mix operacional:</b> {pct_rev}% revisões e {pct_lub}% lubrificações.")

    html = "".join([f"<div class='highlight-pill'>{frase}</div>" for frase in frases])
    st.markdown(f"<div class='highlights-grid'>{html}</div>", unsafe_allow_html=True)


def render():
    head_l, head_r = st.columns([6, 1], vertical_alignment="center")
    with head_l:
        _render_page_header()
    with head_r:
        st.markdown("<div style='height:.35rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 Atualizar", help="Recarrega os dados do banco", use_container_width=True):
            _carregar_revisoes.clear()
            _carregar_lubrificacoes.clear()
            st.rerun()

    st.markdown(
        "<div class='section-caption'>Filtre por período, setor e equipamento para montar uma visão executiva do que foi realizado e exportar o resultado em segundos.</div>",
        unsafe_allow_html=True,
    )

    hoje = datetime.date.today()
    st.markdown("<div class='filters-shell'><div class='filters-title'>Recorte do relatório</div>", unsafe_allow_html=True)
    col0, col1, col2, col3, col4 = st.columns([1.1, 1, 1, 1.1, 1.3])
    with col0:
        atalho = st.selectbox("Período rápido", ["Mês atual", "Últimos 7 dias", "Últimos 30 dias", "Hoje", "Personalizado"], key="rel_periodo_rapido")
    default_ini = hoje.replace(day=1)
    if atalho == "Últimos 7 dias":
        default_ini = hoje - datetime.timedelta(days=6)
    elif atalho == "Últimos 30 dias":
        default_ini = hoje - datetime.timedelta(days=29)
    elif atalho == "Hoje":
        default_ini = hoje

    with col1:
        data_ini = st.date_input("Data inicial", value=default_ini, key="rel_ini")
    with col2:
        data_fim = st.date_input("Data final", value=hoje, key="rel_fim")
    with col3:
        setores = _carregar_setores()
        setor_opts = [None] + list(setores)
        setor_sel = st.selectbox(
            "Setor",
            setor_opts,
            format_func=lambda s: "Todos" if s is None else s[1],
            key="rel_setor",
        )
        setor_id = setor_sel[0] if setor_sel else None
    with col4:
        equipamentos = _carregar_equipamentos(setor_id)
        eqp_opts = [None] + list(equipamentos)
        eqp_sel = st.selectbox(
            "Equipamento",
            eqp_opts,
            format_func=lambda e: "Todos" if e is None else f"{e[1]} — {e[2]}",
            key="rel_eqp",
        )
        eqp_id = eqp_sel[0] if eqp_sel else None
    busca = st.text_input("Busca rápida", placeholder="Código, equipamento, setor, responsável...", key="rel_busca")
    st.markdown("</div>", unsafe_allow_html=True)

    if data_ini > data_fim:
        st.error("A data inicial deve ser anterior à data final.")
        return

    setor_nome = setor_sel[1] if setor_sel else None
    equipamento_nome = f"{eqp_sel[1]} — {eqp_sel[2]}" if eqp_sel else None

    df_rev = _normalizar_datas(_carregar_revisoes(data_ini, data_fim, setor_id, eqp_id))
    df_lub = _normalizar_datas(_carregar_lubrificacoes(data_ini, data_fim, setor_id, eqp_id))

    df_rev = _filtrar_busca(df_rev, busca, ["Código", "Equipamento", "Setor", "Responsável", "Status", "Observações"])
    df_lub = _filtrar_busca(df_lub, busca, ["Código", "Equipamento", "Setor", "Responsável", "Item", "Produto", "Observações"])

    df_rev_macro = _enriquecer_macro_revisoes(df_rev)
    df_lub_macro = _enriquecer_macro_lubrificacoes(df_lub)

    _render_kpi_cards(df_rev, df_lub)

    action_l, action_m, action_r = st.columns([4, 1.2, 1.2])
    with action_l:
        st.markdown("<div class='section-caption' style='margin-top:.2rem'>Use o PDF executivo para compartilhar uma leitura mais limpa com gestão e supervisão.</div>", unsafe_allow_html=True)
    with action_m:
        combinado = pd.concat([
            _formatar_datas_exibicao(df_rev.assign(Tipo='Revisão')) if not df_rev.empty else pd.DataFrame(),
            _formatar_datas_exibicao(df_lub.assign(Tipo='Lubrificação')) if not df_lub.empty else pd.DataFrame(),
        ], ignore_index=True)
        if not combinado.empty:
            botao_exportar_excel(combinado, "relatorio_manutencao_geral", label="⬇️ Excel geral", key="exp_rel_geral")
    with action_r:
        botao_exportar_pdf_relatorio_manutencao(
            df_rev,
            df_lub,
            data_ini,
            data_fim,
            setor_nome=setor_nome,
            equipamento_nome=equipamento_nome,
            setor_id=setor_id,
            equipamento_id=eqp_id,
            key="exp_rel_pdf_exec",
        )

    tab_exec, tab_rev, tab_lub = st.tabs(["Visão executiva", "Revisões", "Lubrificações"])

    with tab_exec:
        st.markdown("<div class='section-card'><h3>Highlights do período</h3><p>Leitura rápida para gestão com foco em volume, concentração e responsáveis.</p></div>", unsafe_allow_html=True)
        _render_highlights(df_rev, df_lub)
        _render_sem_movimentacao(setor_id=setor_id, equipamento_id=eqp_id)

        macro_rev_tab, macro_lub_tab = st.tabs(["Macro de revisões", "Macro de lubrificações"])
        with macro_rev_tab:
            _render_macro_hierarquico(
                df_rev_macro,
                'rev',
                'Etapas de revisão realizadas',
                'Visão macro por departamento e grupo, mostrando quantos equipamentos executaram cada etapa, se foi no prazo ou atrasada, e quanto passou do previsto.',
            )
        with macro_lub_tab:
            _render_macro_hierarquico(
                df_lub_macro,
                'lub',
                'Lubrificações realizadas',
                'Consolidado por item e intervalo, com leitura por departamento, grupo e tipo de equipamento, incluindo atraso médio e maior atraso.',
            )

        col_chart, col_table = st.columns([1.2, 1], vertical_alignment="top")
        with col_chart:
            st.markdown("<div class='section-card'><h3>Distribuição por setor</h3><p>Comparativo entre revisões e lubrificações realizadas dentro do período filtrado.</p></div>", unsafe_allow_html=True)
            _render_distribution_chart(df_rev, df_lub)
        with col_table:
            st.markdown("<div class='section-card'><h3>Resumo por responsável</h3><p>Volume executado por pessoa considerando os dois tipos de manutenção.</p></div>", unsafe_allow_html=True)
            _render_responsaveis_summary(df_rev, df_lub)

        st.markdown("<div class='section-card'><h3>Evolução diária</h3><p>Ritmo de execução ao longo do período para apoiar leitura operacional.</p></div>", unsafe_allow_html=True)
        _render_evolucao_diaria(df_rev, df_lub)

    with tab_rev:
        st.markdown("<div class='section-card'><h3>Revisões realizadas</h3><p>Consulte o histórico detalhado e exporte quando precisar compartilhar ou auditar.</p></div>", unsafe_allow_html=True)
        if df_rev.empty:
            st.info("Nenhuma revisão encontrada para o período e filtros selecionados.")
        else:
            col_exp = st.columns([5, 1])[1]
            with col_exp:
                botao_exportar_excel(_formatar_datas_exibicao(_colunas_publicas_revisoes(df_rev_macro)), "relatorio_revisoes", label="⬇️ Excel", key="exp_rel_rev")
            st.dataframe(_formatar_datas_exibicao(_colunas_publicas_revisoes(df_rev_macro)), use_container_width=True, hide_index=True)
            with st.expander("Resumo macro por etapa"):
                _render_macro_hierarquico(
                    df_rev_macro,
                    'rev',
                    'Etapas de revisão realizadas',
                    'Consolidado por departamento, grupo, tipo de equipamento e etapa executada.',
                )
            with st.expander("Resumo por responsável"):
                resumo = (
                    df_rev.groupby("Responsável")
                    .agg(Qtd=("ID", "count"))
                    .reset_index()
                    .sort_values("Qtd", ascending=False)
                )
                st.dataframe(resumo, use_container_width=True, hide_index=True)

    with tab_lub:
        st.markdown("<div class='section-card'><h3>Lubrificações realizadas</h3><p>Visualize o consolidado por item lubrificado e faça a exportação com o mesmo padrão do sistema.</p></div>", unsafe_allow_html=True)
        if df_lub.empty:
            st.info("Nenhuma lubrificação encontrada para o período e filtros selecionados.")
        else:
            col_exp = st.columns([5, 1])[1]
            with col_exp:
                botao_exportar_excel(_formatar_datas_exibicao(_colunas_publicas_lubrificacoes(df_lub_macro)), "relatorio_lubrificacoes", label="⬇️ Excel", key="exp_rel_lub")
            st.dataframe(_formatar_datas_exibicao(_colunas_publicas_lubrificacoes(df_lub_macro)), use_container_width=True, hide_index=True)
            with st.expander("Resumo macro por item"):
                _render_macro_hierarquico(
                    df_lub_macro,
                    'lub',
                    'Lubrificações realizadas',
                    'Consolidado por departamento, grupo, tipo de equipamento e item lubrificado.',
                )
            with st.expander("Resumo por item lubrificado"):
                resumo = (
                    df_lub.groupby("Item")
                    .agg(Qtd=("ID", "count"))
                    .reset_index()
                    .sort_values("Qtd", ascending=False)
                )
                st.dataframe(resumo, use_container_width=True, hide_index=True)
