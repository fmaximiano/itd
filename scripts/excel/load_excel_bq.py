from __future__ import annotations

import pandas as pd
from google.cloud import bigquery

from config.settings import Settings
from scripts.common.bq import append_to_bq


def load_excel_base_to_bq(
    df: pd.DataFrame,
    settings: Settings,
    client: bigquery.Client,
) -> int:
    return append_to_bq(
        df=df,
        project_id=settings.gcp_project_id,
        dataset=settings.bq_dataset,
        table_name="raw_excel_hist",
        client=client,
        write_disposition="WRITE_TRUNCATE",
    )


def load_excel_formula_to_bq(
    df: pd.DataFrame,
    settings: Settings,
    client: bigquery.Client,
) -> int:
    return append_to_bq(
        df=df,
        project_id=settings.gcp_project_id,
        dataset=settings.bq_dataset,
        table_name="raw_excel_hist_formula_oracle",
        client=client,
        write_disposition="WRITE_TRUNCATE",
    )