import io
import pandas as pd
from services import equipamentos_service, setores_service

COLUNAS_OBRIGATORIAS = ["codigo", "nome"]
COLUNAS_OPCIONAIS = ["tipo", "setor", "km_atual", "horas_atual", "placa", "serie"]

TIPOS_VALIDOS = {
    "caminhão", "trator", "colheitadeira", "pulverizador",
    "implemento", "máquina", "outro",
}


def get_template_csv() -> bytes:
    df = pd.DataFrame(columns=["codigo", "nome", "tipo", "setor", "km_atual", "horas_atual", "placa", "serie"])
    df.loc[0] = {
        "codigo": "EQ001",
        "nome": "Trator John Deere",
        "tipo": "Trator",
        "setor": "Setor Agrícola",
        "km_atual": 0,
        "horas_atual": 1200,
        "placa": "ABC-1234",
        "serie": "JD-2024-001",
    }
    return df.to_csv(index=False).encode("utf-8")


def _parse_numerico(valor, campo: str, linha: int, erros: list) -> float:
    try:
        return float(valor or 0)
    except (ValueError, TypeError):
        erros.append(f"Linha {linha}: valor inválido em '{campo}' — '{valor}' não é numérico")
        return 0.0


def processar_arquivo(file_bytes: bytes, filename: str) -> dict:
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            return {"erro": "Formato não suportado. Use CSV ou XLSX."}
    except Exception as e:
        return {"erro": f"Erro ao ler arquivo: {e}"}

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    ausentes = [col for col in COLUNAS_OBRIGATORIAS if col not in df.columns]
    if ausentes:
        return {"erro": f"Colunas obrigatórias ausentes: {', '.join(ausentes)}"}

    erros = []
    for idx, row in df.iterrows():
        linha = idx + 2
        codigo = str(row.get("codigo", "")).strip()
        nome = str(row.get("nome", "")).strip()
        if not codigo or codigo == "nan":
            erros.append(f"Linha {linha}: código vazio")
        elif not nome or nome == "nan":
            erros.append(f"Linha {linha}: nome vazio")

        tipo = str(row.get("tipo", "")).strip().lower()
        if tipo and tipo != "nan" and tipo not in TIPOS_VALIDOS:
            erros.append(
                f"Linha {linha}: tipo '{row.get('tipo')}' desconhecido — "
                f"use: {', '.join(t.title() for t in sorted(TIPOS_VALIDOS))}"
            )

    return {
        "df": df,
        "erros": erros,
        "linhas_ok": len(df) - len(erros),
        "linhas_erro": len(erros),
        "preview": df.head(10),
    }


def importar(
    df: pd.DataFrame,
    setor_padrao_id=None,
    atualizar_duplicados: bool = False,
    progress_callback=None,
) -> dict:
    """
    Importa equipamentos do DataFrame.
    progress_callback(current, total, codigo) — chamado a cada linha processada.
    """
    setores_map = {s["nome"].lower(): s["id"] for s in setores_service.listar()}
    importados = 0
    atualizados = 0
    duplicados = 0
    erros = []
    total = len(df)

    for idx, row in df.iterrows():
        linha = idx + 2
        codigo = str(row.get("codigo", "")).strip()
        nome = str(row.get("nome", "")).strip()
        if not codigo or not nome or codigo == "nan" or nome == "nan":
            if progress_callback:
                progress_callback(idx + 1, total, codigo or "—")
            continue

        tipo = str(row.get("tipo", "Outro")).strip()
        if not tipo or tipo == "nan":
            tipo = "Outro"

        setor_nome = str(row.get("setor", "")).strip().lower()
        setor_id = setores_map.get(setor_nome) or setor_padrao_id

        km = _parse_numerico(row.get("km_atual", 0), "km_atual", linha, erros)
        horas = _parse_numerico(row.get("horas_atual", 0), "horas_atual", linha, erros)

        try:
            equipamentos_service.criar(
                codigo=codigo,
                nome=nome,
                tipo=tipo,
                setor_id=setor_id,
                km_atual=km,
                horas_atual=horas,
            )
            importados += 1
        except Exception as e:
            msg = str(e)
            if "unique" in msg.lower() or "duplicate" in msg.lower():
                if atualizar_duplicados:
                    try:
                        _atualizar_equipamento(codigo, nome, tipo, setor_id, km, horas)
                        atualizados += 1
                    except Exception as e2:
                        erros.append(f"Linha {linha} ({codigo}): erro ao atualizar — {e2}")
                else:
                    duplicados += 1
            else:
                erros.append(f"Linha {linha} ({codigo}): {msg}")

        if progress_callback:
            progress_callback(idx + 1, total, codigo)

    return {
        "importados": importados,
        "atualizados": atualizados,
        "duplicados": duplicados,
        "erros": erros,
    }


def _atualizar_equipamento(codigo, nome, tipo, setor_id, km, horas):
    from database.connection import get_conn
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            update equipamentos
               set nome = %s,
                   tipo = %s,
                   setor_id = %s,
                   km_atual = greatest(coalesce(km_atual, 0), %s),
                   horas_atual = greatest(coalesce(horas_atual, 0), %s)
             where codigo = %s
            """,
            (nome, tipo, setor_id, km, horas, codigo),
        )
        conn.commit()
    finally:
        conn.close()

