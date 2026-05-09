from __future__ import annotations

import pandas as pd
from google.cloud import bigquery

from config.settings import Settings
from scripts.common.bq import append_to_bq


def load_api_to_bq(
    df: pd.DataFrame,
    settings: Settings,
    client: bigquery.Client,
    table_name: str = "raw_api_snapshot",
    write_disposition: str = "WRITE_APPEND",
) -> int:
    return append_to_bq(
        df=df,
        project_id=settings.gcp_project_id,
        dataset=settings.bq_dataset,
        table_name=table_name,
        client=client,
        write_disposition=write_disposition,
    )