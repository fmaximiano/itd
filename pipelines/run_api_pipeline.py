from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Optional

from google.cloud import bigquery

from config.settings import Settings
from scripts.api.extract_api import fetch_api_json
from scripts.api.load_api_bq import load_api_to_bq
from scripts.api.transform_api import transform_api
from scripts.common.logging_utils import get_logger


logger = get_logger(__name__)


def _mes_anterior_yyyy_mm(hoje: Optional[date] = None) -> str:
    hoje = hoje or date.today()

    if hoje.month == 1:
        return f"{hoje.year - 1}-12"

    return f"{hoje.year}-{hoje.month - 1:02d}"


def _normalizar_mes_referencia(mes_referencia: str) -> str:
    """Normaliza a competência para o formato YYYY-MM.

    Aceita tanto YYYY-MM quanto YYYY-MM-DD, porque o Power BI/Power Automate
    pode enviar a competência como data completa.
    """
    valor = str(mes_referencia).strip()

    if re.fullmatch(r"\d{4}-\d{2}", valor):
        return valor

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
        return valor[:7]

    raise ValueError(
        f"mes_referencia inválido: {mes_referencia!r}. "
        "Use YYYY-MM ou YYYY-MM-DD."
    )


def _snapshot_date_from_mes_referencia(mes_referencia: str) -> date:
    mes_normalizado = _normalizar_mes_referencia(mes_referencia)
    ano, mes = mes_normalizado.split("-")
    return date(int(ano), int(mes), 1)


def _safe_table_suffix(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", value)


def _insert_log(
    client: bigquery.Client,
    settings: Settings,
    *,
    controle_id: str,
    execution_id: str,
    acao: str,
    modo_execucao: str,
    mes_referencia: str,
    snapshot_date: date,
    status: str,
    qtd_linhas: Optional[int] = None,
    backup_id: Optional[str] = None,
    backup_qtd_linhas: Optional[int] = None,
    substituiu_execution_id: Optional[str] = None,
    restaurou_backup_id: Optional[str] = None,
    usuario_solicitante: Optional[str] = None,
    started_at: Optional[datetime] = None,
    finished_at: Optional[datetime] = None,
    github_run_id: Optional[str] = None,
    mensagem: Optional[str] = None,
    erro: Optional[str] = None,
) -> None:
    table_id = f"{settings.gcp_project_id}.{settings.bq_dataset}.controle_execucao_api"

    rows = [
        {
            "controle_id": controle_id,
            "execution_id": execution_id,
            "acao": acao,
            "modo_execucao": modo_execucao,
            "mes_referencia": mes_referencia,
            "snapshot_date": snapshot_date.isoformat(),
            "status": status,
            "qtd_linhas": qtd_linhas,
            "backup_id": backup_id,
            "backup_qtd_linhas": backup_qtd_linhas,
            "substituiu_execution_id": substituiu_execution_id,
            "restaurou_backup_id": restaurou_backup_id,
            "usuario_solicitante": usuario_solicitante,
            "started_at": started_at.isoformat() if started_at else None,
            "finished_at": finished_at.isoformat() if finished_at else None,
            "github_run_id": github_run_id,
            "mensagem": mensagem,
            "erro": erro,
        }
    ]

    errors = client.insert_rows_json(table_id, rows)

    if errors:
        logger.warning("Erro ao gravar log em controle_execucao_api: %s", errors)


def _upsert_controle_execucao_mensal_api(
    client: bigquery.Client,
    settings: Settings,
    *,
    mes_referencia: str,
    execution_id_oficial: str,
    status: str = "oficial",
) -> None:
    """Marca a execução informada como oficial para a competência.

    A raw_api_snapshot guarda as linhas da execução. A tabela
    controle_execucao_mensal_api é quem define qual execution_id deve
    aparecer no Power BI para cada competência.
    """
    competencia_ref = _snapshot_date_from_mes_referencia(mes_referencia)

    query = f"""
        MERGE `{settings.gcp_project_id}.{settings.bq_dataset}.controle_execucao_mensal_api` AS destino
        USING (
          SELECT
            @competencia_ref AS competencia_ref,
            @execution_id_oficial AS execution_id_oficial,
            @status AS status,
            CURRENT_DATETIME("America/Sao_Paulo") AS atualizado_em
        ) AS origem
        ON destino.competencia_ref = origem.competencia_ref

        WHEN MATCHED THEN
          UPDATE SET
            execution_id_oficial = origem.execution_id_oficial,
            status = origem.status,
            atualizado_em = origem.atualizado_em

        WHEN NOT MATCHED THEN
          INSERT (
            competencia_ref,
            execution_id_oficial,
            status,
            atualizado_em
          )
          VALUES (
            origem.competencia_ref,
            origem.execution_id_oficial,
            origem.status,
            origem.atualizado_em
          );
    """

    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(
                    "competencia_ref",
                    "DATE",
                    competencia_ref,
                ),
                bigquery.ScalarQueryParameter(
                    "execution_id_oficial",
                    "STRING",
                    execution_id_oficial,
                ),
                bigquery.ScalarQueryParameter(
                    "status",
                    "STRING",
                    status,
                ),
            ]
        ),
    )

    job.result()

    logger.info(
        "Controle mensal atualizado: competencia_ref=%s | execution_id_oficial=%s | status=%s",
        competencia_ref.isoformat(),
        execution_id_oficial,
        status,
    )


def _count_rows_for_month(
    client: bigquery.Client,
    settings: Settings,
    mes_referencia: str,
) -> int:
    query = f"""
        SELECT COUNT(*) AS qtd
        FROM `{settings.gcp_project_id}.{settings.bq_dataset}.raw_api_snapshot`
        WHERE FORMAT_DATE('%Y-%m', snapshot_date) = @mes_referencia
    """

    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(
                    "mes_referencia",
                    "STRING",
                    mes_referencia,
                )
            ]
        ),
    )

    return list(job.result())[0]["qtd"]


def _replace_month_with_staging(
    client: bigquery.Client,
    settings: Settings,
    *,
    mes_referencia: str,
    staging_table_name: str,
    backup_id: str,
    execution_id: str,
    usuario_solicitante: Optional[str],
) -> int:
    query = f"""
        INSERT INTO `{settings.gcp_project_id}.{settings.bq_dataset}.raw_api_snapshot_backup`
        SELECT
          a.*,
          @backup_id AS backup_id,
          CURRENT_DATETIME("America/Sao_Paulo") AS backup_ts,
          'reprocessamento_api' AS backup_motivo,
          @execution_id AS substituido_por_execution_id,
          @usuario_solicitante AS usuario_solicitante
        FROM `{settings.gcp_project_id}.{settings.bq_dataset}.raw_api_snapshot` a
        WHERE FORMAT_DATE('%Y-%m', a.snapshot_date) = @mes_referencia;

        DELETE FROM `{settings.gcp_project_id}.{settings.bq_dataset}.raw_api_snapshot`
        WHERE FORMAT_DATE('%Y-%m', snapshot_date) = @mes_referencia;

        INSERT INTO `{settings.gcp_project_id}.{settings.bq_dataset}.raw_api_snapshot`
        SELECT *
        FROM `{settings.gcp_project_id}.{settings.bq_dataset}.{staging_table_name}`;
    """

    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("backup_id", "STRING", backup_id),
                bigquery.ScalarQueryParameter("execution_id", "STRING", execution_id),
                bigquery.ScalarQueryParameter("usuario_solicitante", "STRING", usuario_solicitante),
                bigquery.ScalarQueryParameter("mes_referencia", "STRING", mes_referencia),
            ]
        ),
    )

    job.result()

    return _count_rows_for_month(
        client=client,
        settings=settings,
        mes_referencia=mes_referencia,
    )


def _get_latest_backup_for_month(
    client: bigquery.Client,
    settings: Settings,
    mes_referencia: str,
) -> dict | None:
    query = f"""
        SELECT
          backup_id,
          MAX(backup_ts) AS backup_ts,
          COUNT(*) AS qtd_linhas,
          COUNT(DISTINCT execution_id) AS qtd_execution_ids,
          ANY_VALUE(execution_id) AS execution_id_restaurado
        FROM `{settings.gcp_project_id}.{settings.bq_dataset}.raw_api_snapshot_backup`
        WHERE FORMAT_DATE('%Y-%m', snapshot_date) = @mes_referencia
          AND backup_id IS NOT NULL
        GROUP BY backup_id
        ORDER BY backup_ts DESC
        LIMIT 1
    """

    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(
                    "mes_referencia",
                    "STRING",
                    mes_referencia,
                )
            ]
        ),
    )

    rows = list(job.result())

    if not rows:
        return None

    row = rows[0]

    return {
        "backup_id": row["backup_id"],
        "backup_ts": row["backup_ts"],
        "qtd_linhas": row["qtd_linhas"],
        "qtd_execution_ids": row["qtd_execution_ids"],
        "execution_id_restaurado": row["execution_id_restaurado"],
    }


def restore_api_snapshot(
    client: bigquery.Client,
    settings: Settings,
    execution_id: str,
    mes_referencia: Optional[str] = None,
    modo_execucao: str = "manual_github",
    usuario_solicitante: Optional[str] = None,
    github_run_id: Optional[str] = None,
) -> int:
    started_at = datetime.now()
    controle_id = str(uuid.uuid4())

    mes_referencia = _normalizar_mes_referencia(
        mes_referencia or _mes_anterior_yyyy_mm()
    )
    snapshot_date = _snapshot_date_from_mes_referencia(mes_referencia)

    logger.info("Iniciando restauração da API.")
    logger.info("Mês de referência: %s", mes_referencia)

    _insert_log(
        client=client,
        settings=settings,
        controle_id=controle_id,
        execution_id=execution_id,
        acao="restaurar",
        modo_execucao=modo_execucao,
        mes_referencia=mes_referencia,
        snapshot_date=snapshot_date,
        status="iniciado",
        usuario_solicitante=usuario_solicitante,
        started_at=started_at,
        github_run_id=github_run_id,
        mensagem="Restauração iniciada.",
    )

    try:
        backup = _get_latest_backup_for_month(
            client=client,
            settings=settings,
            mes_referencia=mes_referencia,
        )

        if not backup:
            raise ValueError(
                f"Não existe backup disponível para o mês {mes_referencia}."
            )

        backup_id_a_restaurar = backup["backup_id"]
        backup_qtd_linhas = backup["qtd_linhas"]
        execution_id_restaurado = backup["execution_id_restaurado"]

        if backup["qtd_execution_ids"] != 1 or not execution_id_restaurado:
            raise ValueError(
                "Backup inválido para restauração: era esperado exatamente "
                "um execution_id no backup selecionado."
            )

        logger.info(
            "Backup selecionado para restauração: %s | linhas: %s",
            backup_id_a_restaurar,
            backup_qtd_linhas,
        )

        query = f"""
        DELETE FROM `{settings.gcp_project_id}.{settings.bq_dataset}.raw_api_snapshot`
        WHERE FORMAT_DATE('%Y-%m', snapshot_date) = @mes_referencia;

        INSERT INTO `{settings.gcp_project_id}.{settings.bq_dataset}.raw_api_snapshot`
        SELECT
        * EXCEPT(
            backup_id,
            backup_ts,
            backup_motivo,
            substituido_por_execution_id,
            usuario_solicitante
        )
        FROM `{settings.gcp_project_id}.{settings.bq_dataset}.raw_api_snapshot_backup`
        WHERE backup_id = @backup_id_a_restaurar;

        DELETE FROM `{settings.gcp_project_id}.{settings.bq_dataset}.raw_api_snapshot_backup`
        WHERE backup_id = @backup_id_a_restaurar;
        """

        job = client.query(
            query,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter(
                        "backup_id_a_restaurar",
                        "STRING",
                        backup_id_a_restaurar,
                    ),
                    bigquery.ScalarQueryParameter(
                        "execution_id",
                        "STRING",
                        execution_id,
                    ),
                    bigquery.ScalarQueryParameter(
                        "usuario_solicitante",
                        "STRING",
                        usuario_solicitante,
                    ),
                    bigquery.ScalarQueryParameter(
                        "mes_referencia",
                        "STRING",
                        mes_referencia,
                    ),
                ]
            ),
        )

        job.result()

        rows_restored = _count_rows_for_month(
            client=client,
            settings=settings,
            mes_referencia=mes_referencia,
        )

        logger.info("Restauração concluída. Linhas restauradas: %s", rows_restored)

        if rows_restored <= 0:
            raise ValueError(
                "A restauração não gerou linhas ativas. "
                "O controle mensal não será atualizado."
            )

        _upsert_controle_execucao_mensal_api(
            client=client,
            settings=settings,
            mes_referencia=mes_referencia,
            execution_id_oficial=execution_id_restaurado,
            status="oficial",
        )

        _insert_log(
            client=client,
            settings=settings,
            controle_id=str(uuid.uuid4()),
            execution_id=execution_id,
            acao="restaurar",
            modo_execucao=modo_execucao,
            mes_referencia=mes_referencia,
            snapshot_date=snapshot_date,
            status="sucesso",
            qtd_linhas=rows_restored,
            backup_id=None,
            backup_qtd_linhas=backup_qtd_linhas,
            restaurou_backup_id=backup_id_a_restaurar,
            usuario_solicitante=usuario_solicitante,
            started_at=started_at,
            finished_at=datetime.now(),
            github_run_id=github_run_id,
            mensagem="Backup restaurado com sucesso.",
        )

        return rows_restored

    except Exception as exc:
        logger.exception("Erro na restauração da API.")

        _insert_log(
            client=client,
            settings=settings,
            controle_id=str(uuid.uuid4()),
            execution_id=execution_id,
            acao="restaurar",
            modo_execucao=modo_execucao,
            mes_referencia=mes_referencia,
            snapshot_date=snapshot_date,
            status="erro",
            usuario_solicitante=usuario_solicitante,
            started_at=started_at,
            finished_at=datetime.now(),
            github_run_id=github_run_id,
            erro=str(exc),
        )

        raise
    
def _remover_linhas_sem_classificacao(df):
    colunas_classificacao = ["presencial", "digital", "autosservico"]

    for coluna in colunas_classificacao:
        if coluna not in df.columns:
            raise ValueError(
                f"Coluna obrigatória ausente na carga da API: {coluna}"
            )

    def sem_valor(valor) -> bool:
        if valor is None:
            return True

        texto = str(valor).strip()

        return texto == "" or texto == "-"

    sem_classificacao = (
        df["presencial"].apply(sem_valor)
        & df["digital"].apply(sem_valor)
        & df["autosservico"].apply(sem_valor)
    )

    qtd_removidas = int(sem_classificacao.sum())

    if qtd_removidas > 0:
        logger.info(
            "Removendo %s linhas sem classificação: presencial=digital=autosservico ausentes ou '-'.",
            qtd_removidas,
        )

    return df.loc[~sem_classificacao].copy(), qtd_removidas

def run_api_pipeline(
    client: bigquery.Client,
    settings: Settings,
    execution_id: str,
    mes_referencia: Optional[str] = None,
    modo_execucao: str = "manual_github",
    usuario_solicitante: Optional[str] = None,
    github_run_id: Optional[str] = None,
) -> int:
    started_at = datetime.now()
    controle_id = str(uuid.uuid4())
    backup_id = str(uuid.uuid4())

    mes_referencia = _normalizar_mes_referencia(
        mes_referencia or _mes_anterior_yyyy_mm()
    )
    snapshot_date = _snapshot_date_from_mes_referencia(mes_referencia)

    staging_table_name = f"raw_api_snapshot_staging_{_safe_table_suffix(execution_id)}"

    logger.info("Iniciando reprocessamento da API.")
    logger.info("Mês de referência: %s", mes_referencia)
    logger.info("Snapshot date: %s", snapshot_date)
    logger.info("Tabela staging: %s", staging_table_name)

    _insert_log(
        client=client,
        settings=settings,
        controle_id=controle_id,
        execution_id=execution_id,
        acao="reprocessar",
        modo_execucao=modo_execucao,
        mes_referencia=mes_referencia,
        snapshot_date=snapshot_date,
        status="iniciado",
        usuario_solicitante=usuario_solicitante,
        started_at=started_at,
        github_run_id=github_run_id,
        mensagem="Execução iniciada.",
    )

    try:
        logger.info("Buscando dados da API em %s", settings.api_url)
        logger.info(
            "API_KEY carregada? %s | tamanho=%s",
            "sim" if bool(settings.api_key) else "não",
            len(settings.api_key or ""),
        )

        data = fetch_api_json(
            api_url=settings.api_url,
            api_key=settings.api_key,
            timeout_seconds=settings.request_timeout,
        )

        logger.info("API retornou %s registros antes da transformação.", len(data))

        df_api = transform_api(
            data=data,
            execution_id=execution_id,
            snapshot_date=snapshot_date,
        )

        qtd_linhas_antes_filtro = len(df_api)

        df_api, qtd_linhas_removidas_sem_classificacao = _remover_linhas_sem_classificacao(
            df_api
        )

        qtd_linhas = len(df_api)

        logger.info(
            "Linhas após filtro de classificação: %s de %s. Removidas: %s.",
            qtd_linhas,
            qtd_linhas_antes_filtro,
            qtd_linhas_removidas_sem_classificacao,
        )

        if qtd_linhas == 0:
            raise ValueError(
                "A API retornou 0 linhas válidas após remover etapas sem classificação. "
                "A carga ativa não será substituída."
            )

        logger.info("API transformada em DataFrame com %s linhas.", qtd_linhas)

        backup_qtd_linhas = _count_rows_for_month(
            client=client,
            settings=settings,
            mes_referencia=mes_referencia,
        )

        logger.info(
            "Carga ativa atual do mês %s possui %s linhas.",
            mes_referencia,
            backup_qtd_linhas,
        )

        load_api_to_bq(
            df=df_api,
            settings=settings,
            client=client,
            table_name=staging_table_name,
            write_disposition="WRITE_TRUNCATE",
        )

        rows_loaded = _replace_month_with_staging(
            client=client,
            settings=settings,
            mes_referencia=mes_referencia,
            staging_table_name=staging_table_name,
            backup_id=backup_id,
            execution_id=execution_id,
            usuario_solicitante=usuario_solicitante,
        )

        logger.info("Carga ativa substituída com sucesso. Linhas ativas: %s", rows_loaded)

        if rows_loaded <= 0:
            raise ValueError(
                "A carga ativa ficou sem linhas após o reprocessamento. "
                "O controle mensal não será atualizado."
            )

        _upsert_controle_execucao_mensal_api(
            client=client,
            settings=settings,
            mes_referencia=mes_referencia,
            execution_id_oficial=execution_id,
            status="oficial",
        )

        _insert_log(
            client=client,
            settings=settings,
            controle_id=str(uuid.uuid4()),
            execution_id=execution_id,
            acao="reprocessar",
            modo_execucao=modo_execucao,
            mes_referencia=mes_referencia,
            snapshot_date=snapshot_date,
            status="sucesso",
            qtd_linhas=rows_loaded,
            backup_id=backup_id,
            backup_qtd_linhas=backup_qtd_linhas,
            usuario_solicitante=usuario_solicitante,
            started_at=started_at,
            finished_at=datetime.now(),
            github_run_id=github_run_id,
            mensagem="Carga reprocessada com sucesso.",
        )

        return rows_loaded

    except Exception as exc:
        logger.exception("Erro no reprocessamento da API.")

        _insert_log(
            client=client,
            settings=settings,
            controle_id=str(uuid.uuid4()),
            execution_id=execution_id,
            acao="reprocessar",
            modo_execucao=modo_execucao,
            mes_referencia=mes_referencia,
            snapshot_date=snapshot_date,
            status="erro",
            usuario_solicitante=usuario_solicitante,
            started_at=started_at,
            finished_at=datetime.now(),
            github_run_id=github_run_id,
            erro=str(exc),
        )

        raise

    finally:
        client.delete_table(
            f"{settings.gcp_project_id}.{settings.bq_dataset}.{staging_table_name}",
            not_found_ok=True,
        )