from __future__ import annotations

from typing import Any, Optional

import pandas as pd
from google.cloud import bigquery


def to_bq_table(project_id: str, dataset: str, table_name: str) -> str:
    return f"{project_id}.{dataset}.{table_name}"


def get_bq_client(project_id: str) -> bigquery.Client:
    return bigquery.Client(project=project_id)


def append_to_bq(
    df: pd.DataFrame,
    project_id: str,
    dataset: str,
    table_name: str,
    client: bigquery.Client,
    write_disposition: str = "WRITE_APPEND",
    date_columns: Optional[set[str]] = None,
    timestamp_columns: Optional[set[str]] = None,
    json_columns: Optional[set[str]] = None,
) -> int:
    if df.empty:
        return 0

    df_to_load = df.copy()

    date_columns = date_columns or {
        "snapshot_date",
        "data_ref",
        "data_referencia",
        "publicado",
        "alterado",
        "dt_carga",
    }

    timestamp_columns = timestamp_columns or {
        "ingestion_ts",
        "started_at",
        "finished_at",
    }

    json_columns = json_columns or {
        "payload_json",
        "metadata",
    }

    for col in df_to_load.columns:
        if col in date_columns:
            df_to_load[col] = pd.to_datetime(
                df_to_load[col],
                errors="coerce"
            ).dt.date

    for col in df_to_load.columns:
        if col in timestamp_columns:
            serie = pd.to_datetime(df_to_load[col], errors="coerce", utc=True)
            serie = serie.dt.floor("us")
            df_to_load[col] = serie.dt.tz_localize(None)

    for col in df_to_load.columns:
        if col in json_columns:
            df_to_load[col] = df_to_load[col].apply(
                lambda x: None if pd.isna(x) else str(x)
            )

    job_config = bigquery.LoadJobConfig(
        write_disposition=write_disposition
    )

    job = client.load_table_from_dataframe(
        df_to_load,
        to_bq_table(project_id, dataset, table_name),
        job_config=job_config,
    )
    job.result()

    return len(df_to_load)


def insert_exec_row(
    client: bigquery.Client,
    project_id: str,
    dataset: str,
    row: dict[str, Any],
) -> None:
    errors = client.insert_rows_json(
        to_bq_table(project_id, dataset, "ctl_execucoes"),
        [row],
    )
    if errors:
        raise RuntimeError(f"Erro ao inserir ctl_execucoes: {errors}")


def insert_exec_start(
    client: bigquery.Client,
    project_id: str,
    dataset: str,
    execution_id: str,
    source_system: str,
    snapshot_date: str,
    started_at: str,
) -> None:
    insert_exec_row(
        client=client,
        project_id=project_id,
        dataset=dataset,
        row={
            "execution_id": execution_id,
            "event_type": "start",
            "source_system": source_system,
            "snapshot_date": snapshot_date,
            "started_at": started_at,
            "finished_at": None,
            "status": "running",
            "rows_read": None,
            "rows_written": None,
            "rows_rejected": None,
            "error_message": None,
        },
    )


def insert_exec_end_success(
    client: bigquery.Client,
    project_id: str,
    dataset: str,
    execution_id: str,
    source_system: str,
    snapshot_date: str,
    started_at: str,
    finished_at: str,
    rows_read: int,
    rows_written: int,
    rows_rejected: int,
) -> None:
    insert_exec_row(
        client=client,
        project_id=project_id,
        dataset=dataset,
        row={
            "execution_id": execution_id,
            "event_type": "end",
            "source_system": source_system,
            "snapshot_date": snapshot_date,
            "started_at": started_at,
            "finished_at": finished_at,
            "status": "success",
            "rows_read": rows_read,
            "rows_written": rows_written,
            "rows_rejected": rows_rejected,
            "error_message": None,
        },
    )


def insert_exec_end_error(
    client: bigquery.Client,
    project_id: str,
    dataset: str,
    execution_id: str,
    source_system: str,
    snapshot_date: str,
    started_at: str,
    finished_at: str,
    error_message: str,
) -> None:
    insert_exec_row(
        client=client,
        project_id=project_id,
        dataset=dataset,
        row={
            "execution_id": execution_id,
            "event_type": "end",
            "source_system": source_system,
            "snapshot_date": snapshot_date,
            "started_at": started_at,
            "finished_at": finished_at,
            "status": "error",
            "rows_read": None,
            "rows_written": None,
            "rows_rejected": None,
            "error_message": error_message[:10000],
        },
    )