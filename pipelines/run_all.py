from __future__ import annotations

import uuid
from datetime import date

from config.settings import get_settings
from pipelines.run_api_pipeline import run_api_pipeline
from pipelines.run_excel_pipeline import run_excel_pipeline
from scripts.common.bq import (
    get_bq_client,
    insert_exec_end_error,
    insert_exec_end_success,
    insert_exec_start,
)
from scripts.common.dates import now_utc
from scripts.common.logging_utils import get_logger


logger = get_logger(__name__)


def run_all() -> None:
    settings = get_settings()
    client = get_bq_client(settings.gcp_project_id)

    execution_id = str(uuid.uuid4())
    source_system = "excel_hist+api"
    snapshot_date = date.today().isoformat()
    started_at = now_utc().isoformat()

    insert_exec_start(
        client=client,
        project_id=settings.gcp_project_id,
        dataset=settings.bq_dataset,
        execution_id=execution_id,
        source_system=source_system,
        snapshot_date=snapshot_date,
        started_at=started_at,
    )

    try:
        logger.info("Iniciando pipeline do Excel.")
        rows_hist, rows_formula = run_excel_pipeline(
            client=client,
            settings=settings,
            execution_id=execution_id,
        )
        logger.info(
            "Excel concluído. raw_excel_hist=%s | raw_excel_hist_formula_oracle=%s",
            rows_hist,
            rows_formula,
        )

        logger.info("Iniciando pipeline da API.")
        rows_api = run_api_pipeline(
            client=client,
            settings=settings,
            execution_id=execution_id,
        )
        logger.info("API concluída. raw_api_snapshot=%s", rows_api)

        finished_at = now_utc().isoformat()
        total_rows = rows_hist + rows_formula + rows_api

        insert_exec_end_success(
            client=client,
            project_id=settings.gcp_project_id,
            dataset=settings.bq_dataset,
            execution_id=execution_id,
            source_system=source_system,
            snapshot_date=snapshot_date,
            started_at=started_at,
            finished_at=finished_at,
            rows_read=total_rows,
            rows_written=total_rows,
            rows_rejected=0,
        )

        logger.info(
            "Execução concluída com sucesso. execution_id=%s | total=%s",
            execution_id,
            total_rows,
        )

    except Exception as exc:
        finished_at = now_utc().isoformat()

        insert_exec_end_error(
            client=client,
            project_id=settings.gcp_project_id,
            dataset=settings.bq_dataset,
            execution_id=execution_id,
            source_system=source_system,
            snapshot_date=snapshot_date,
            started_at=started_at,
            finished_at=finished_at,
            error_message=str(exc),
        )

        logger.exception("Execução falhou. execution_id=%s", execution_id)
        raise