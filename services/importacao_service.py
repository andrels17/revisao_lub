import io
import pandas as pd
from services import equipamentos_service, setores_service


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

    for col in ["codigo", "nome"]:
        if col not in df.columns:
            return {"erro": f"Coluna obrigatória ausente: '{col}'"}

    erros = []
    for idx, row in df.iterrows():
        linha = idx + 2
        codigo = str(row.get("codigo", "")).strip()
        nome = str(row.get("nome", "")).strip()
        if not codigo or codigo == "nan":
            erros.append(f"Linha {linha}: código vazio")
        elif not nome or nome == "nan":
            erros.append(f"Linha {linha}: nome vazio")

    return {
        "df": df,
        "erros": erros,
        "linhas_ok": len(df) - len(erros),
        "linhas_erro": len(erros),
        "preview": df.head(10),
    }


def importar(df: pd.DataFrame, setor_padrao_id=None) -> dict:
    setores_map = {s["nome"].lower(): s["id"] for s in setores_service.listar()}
    importados = 0
    duplicados = 0
    erros = []

    for idx, row in df.iterrows():
        codigo = str(row.get("codigo", "")).strip()
        nome = str(row.get("nome", "")).strip()
        if not codigo or not nome or codigo == "nan" or nome == "nan":
            continue

        tipo = str(row.get("tipo", "Outro")).strip()
        if not tipo or tipo == "nan":
            tipo = "Outro"

        setor_nome = str(row.get("setor", "")).strip().lower()
        setor_id = setores_map.get(setor_nome) or setor_padrao_id

        try:
            km = float(row.get("km_atual", 0) or 0)
        except (ValueError, TypeError):
            km = 0
        try:
            horas = float(row.get("horas_atual", 0) or 0)
        except (ValueError, TypeError):
            horas = 0

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
                duplicados += 1
            else:
                erros.append(f"Linha {idx + 2} ({codigo}): {msg}")

    return {"importados": importados, "duplicados": duplicados, "erros": erros}
