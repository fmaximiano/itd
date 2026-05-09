from datetime import datetime, timezone
import pandas as pd
import requests

from scripts.common.config import API_KEY, PROJECT_ID, DATASET_ID, TABLE_RAW_API, API_URL, WRITE_API
from scripts.common.normalize import normalize_columns, clean_strings
from scripts.common.bq import get_client, load_dataframe
from scripts.common.logging_setup import get_logger

logger = get_logger(__name__)

headers = {
  "key": API_KEY
}


def main():
    logger.info("Chamando API: %s", API_URL)
    resp = requests.get(API_URL, headers=headers, timeout=120)
    resp.raise_for_status()

    data = resp.json()
    if not isinstance(data, list):
        raise ValueError("Resposta da API não é uma lista JSON.")

    df = pd.DataFrame(data)
    df = normalize_columns(df)
    df = clean_strings(df)

    now = datetime.now(timezone.utc)
    df["snapshot_at"] = now
    df["snapshot_date"] = now.date()

    df = df.where(pd.notnull(df), None)

    table_id = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_RAW_API}"
    client = get_client(PROJECT_ID)

    logger.info("Enviando %s linhas para %s", len(df), table_id)
    table = load_dataframe(client, df, table_id, WRITE_API)
    logger.info("Carga concluída. Linhas na tabela: %s", table.num_rows)

if __name__ == "__main__":
    main()