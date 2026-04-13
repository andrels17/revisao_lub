import pandas as pd

ALIASES = {
    "codigo": ["cod_equipamento", "codigo", "id", "cod", "codigo_equipamento"],
    "nome": ["descricao_equipamento", "nome", "descricao", "descricao_equip"],
    "tipo": ["descricaotipoequipamento", "tipo", "tipo_equipamento", "grupo"],
    "setor": ["descricao", "setor", "departamento"],
    "tipo_horimetro": ["tipo_horimetro", "tipo_medidor", "medidor_tipo"],
    "valor_medidor": ["km_atual", "horas_atual", "valor_medidor", "medidor_atual"],
}

def normalizar_colunas(df):
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    rename_map = {}

    for campo, possiveis in ALIASES.items():
        for col in df.columns:
            if col in possiveis and col not in rename_map:
                rename_map[col] = campo

    df = df.rename(columns=rename_map)
    return df

def validar_colunas(df):
    obrigatorias = ["codigo", "nome"]
    faltantes = [c for c in obrigatorias if c not in df.columns]

    if faltantes:
        raise ValueError(f"Colunas obrigatórias ausentes: {', '.join(faltantes)}")

def normalizar_tipo(tipo_original):
    if pd.isna(tipo_original) or str(tipo_original).strip() == "":
        return "Veículos Leves"

    t = str(tipo_original).strip().upper()

    if "CAMINH" in t:
        return "Caminhão"
    if "TRATOR" in t:
        return "Trator"
    if "COLHEIT" in t or "COLHEDOR" in t:
        return "Colheitadeira"
    if "PULVER" in t:
        return "Pulverizador"

    if any(k in t for k in ["IMPLEMENTO", "REBOQUE", "GRADE", "SULCADOR", "SUBSOLADOR", "PIPA", "JULIETA", "TANQUE"]):
        return "Implemento"

    if any(k in t for k in ["CARREGADEIRA", "MAQUINA", "MÁQUINA", "EMPILHADEIRA", "GERADOR", "ELETROBOMBA", "PIVOT", "TURBOMAQ"]):
        return "Máquina"

    if any(k in t for k in ["MOTO", "AUTO", "CARRO", "DRONE", "AVIAO", "AVIÃO", "UTILITARIO", "UTILITÁRIO"]):
        return "Veículos Leves"

    return str(tipo_original).strip().title()

def separar_medidor(df):
    if "tipo_horimetro" not in df.columns or "valor_medidor" not in df.columns:
        return df

    df = df.copy()

    if "km_atual" not in df.columns:
        df["km_atual"] = None
    if "horas_atual" not in df.columns:
        df["horas_atual"] = None

    for i, row in df.iterrows():
        tipo = str(row.get("tipo_horimetro", "")).strip().upper()
        valor = row.get("valor_medidor")

        if pd.isna(valor):
            continue

        if "KM" in tipo or "QUILOMETRO" in tipo or "QUILÔMETRO" in tipo:
            df.at[i, "km_atual"] = valor
        elif "HORA" in tipo:
            df.at[i, "horas_atual"] = valor
        elif "NÃO POSSUI" in tipo or "NAO POSSUI" in tipo:
            pass

    return df

def consolidar_duplicados(df):
    if "codigo" not in df.columns:
        return df

    df = df.copy()
    df["_ordem_importacao"] = range(len(df))
    df = (
        df.sort_values("_ordem_importacao")
          .drop_duplicates(subset=["codigo"], keep="last")
          .drop(columns=["_ordem_importacao"])
    )
    return df

def processar_importacao(caminho_arquivo):
    if str(caminho_arquivo).lower().endswith(".csv"):
        df = pd.read_csv(caminho_arquivo)
    else:
        df = pd.read_excel(caminho_arquivo)

    df = normalizar_colunas(df)
    validar_colunas(df)

    if "tipo" in df.columns:
        df["tipo"] = df["tipo"].apply(normalizar_tipo)

    df = separar_medidor(df)
    df = consolidar_duplicados(df)

    return df
