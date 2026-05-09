from pathlib import Path
import pandas as pd

from scripts.common.config import PROJECT_ID, DATASET_ID, TABLE_RAW_EXCEL, EXCEL_PATH, WRITE_EXCEL
from scripts.common.normalize import normalize_columns, clean_strings
from scripts.common.bq import get_client, load_dataframe
from scripts.common.logging_setup import get_logger

logger = get_logger(__name__)

REQUIRED_COLUMNS = [
    "data_ref",
    "orgao_responsavel",
    "nome_servico",
    "numero_etapa",
    "nome_etapa",
]

def main():
    if not EXCEL_PATH:
        raise ValueError("EXCEL_PATH não definido no .env")

    path = Path(EXCEL_PATH)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    logger.info("Lendo Excel: %s", path)
    df = pd.read_excel(path, dtype=object)

    df = normalize_columns(df)
    df = clean_strings(df)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes: {missing}")

    df["data_ref"] = pd.to_datetime(df["data_ref"], errors="coerce", dayfirst=True).dt.date
    df = df.where(pd.notnull(df), None)

    table_id = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_RAW_EXCEL}"
    client = get_client(PROJECT_ID)

    logger.info("Enviando %s linhas para %s", len(df), table_id)
    table = load_dataframe(client, df, table_id, WRITE_EXCEL)
    logger.info("Carga concluída. Linhas na tabela: %s", table.num_rows)

if __name__ == "__main__":
    main()