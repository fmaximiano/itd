from __future__ import annotations

import os
import re
import uuid


from config.settings import get_settings
from scripts.common.bq import get_bq_client
from pipelines.run_api_pipeline import run_api_pipeline
from scripts.common.logging_utils import get_logger


logger = get_logger(__name__)


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)

    if value is None:
        return None

    return value.strip().strip('"').strip("'")


def _validar_mes_referencia(mes_referencia: str | None) -> str | None:
    if not mes_referencia:
        return None

    if not re.fullmatch(r"\d{4}-\d{2}", mes_referencia):
        raise ValueError(
            "MES_REFERENCIA inválido. Use o formato YYYY-MM. Exemplo: 2026-04"
        )

    ano, mes = mes_referencia.split("-")
    mes_int = int(mes)

    if mes_int < 1 or mes_int > 12:
        raise ValueError(
            "MES_REFERENCIA inválido. O mês deve estar entre 01 e 12."
        )

    return f"{ano}-{mes}"


def main() -> None:
    settings = get_settings()
    client = get_bq_client(settings.gcp_project_id)

    execution_id = _get_env("EXECUTION_ID") or str(uuid.uuid4())

    acao = _get_env("ACAO", "reprocessar")
    mes_referencia = _validar_mes_referencia(
        _get_env("MES_REFERENCIA")
    )

    modo_execucao = _get_env("MODO_EXECUCAO", "manual_github")
    usuario_solicitante = _get_env("USUARIO_SOLICITANTE")
    github_run_id = _get_env("GITHUB_RUN_ID")

    logger.info("Iniciando api.py")
    logger.info("Ação: %s", acao)
    logger.info("Execution ID: %s", execution_id)
    logger.info("Mês referência recebido: %s", mes_referencia or "não informado")
    logger.info("Modo execução: %s", modo_execucao)
    logger.info("Usuário solicitante: %s", usuario_solicitante or "não informado")
    logger.info("GitHub run ID: %s", github_run_id or "não informado")

    if acao == "reprocessar":
        rows_loaded = run_api_pipeline(
            client=client,
            settings=settings,
            execution_id=execution_id,
            mes_referencia=mes_referencia,
            modo_execucao=modo_execucao,
            usuario_solicitante=usuario_solicitante,
            github_run_id=github_run_id,
        )

        logger.info("Pipeline concluído. Linhas carregadas: %s", rows_loaded)
        print(f"OK - Linhas carregadas: {rows_loaded}")
        return

    if acao == "restaurar":
        rows_restored = restore_api_snapshot(
            client=client,
            settings=settings,
            execution_id=execution_id,
            mes_referencia=mes_referencia,
            modo_execucao=modo_execucao,
            usuario_solicitante=usuario_solicitante,
            github_run_id=github_run_id,
        )

        logger.info("Restauração concluída. Linhas restauradas: %s", rows_restored)
        print(f"OK - Linhas restauradas: {rows_restored}")
        return

    raise ValueError(
        f"ACAO inválida: {acao}. Use 'reprocessar' ou 'restaurar'."
    )


if __name__ == "__main__":
    main()