from __future__ import annotations

from google.cloud import bigquery

from config.settings import Settings
from scripts.excel.extract_excel import load_excel_raw
from scripts.excel.load_excel_bq import load_excel_base_to_bq, load_excel_formula_to_bq
from scripts.excel.transform_excel_base import transform_excel_base
from scripts.excel.transform_excel_formula_oracle import transform_excel_formula_oracle


def run_excel_pipeline(
    client: bigquery.Client,
    settings: Settings,
    execution_id: str,
) -> tuple[int, int]:
    df_raw = load_excel_raw(settings.excel_path)

    df_excel_base = transform_excel_base(
        df_raw=df_raw,
        execution_id=execution_id,
        excel_path=settings.excel_path,
    )

    df_excel_formula = transform_excel_formula_oracle(
        df_raw=df_raw,
        execution_id=execution_id,
    )

    rows_hist = load_excel_base_to_bq(
        df=df_excel_base,
        settings=settings,
        client=client,
    )

    rows_formula = load_excel_formula_to_bq(
        df=df_excel_formula,
        settings=settings,
        client=client,
    )

    return rows_hist, rows_formula