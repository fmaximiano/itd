from __future__ import annotations

import os

import pandas as pd

from scripts.common.dates import now_utc, parse_date_br, parse_int64
from scripts.common.hashing import make_id_linha_hash
from scripts.common.normalize import normalize_text


EXCEL_BASE_RENAME = {
    "data": "data_ref",
    "orgao_responsavel": "orgao_responsavel",
    "nome_servico": "nome_servico",
    "numero_etapa": "numero_etapa",
    "nome_etapa": "nome_etapa",
    "autosservico": "autosservico",
    "digital": "digital",
    "presencial": "presencial",
    "etapa_futura": "etapa_futura",
    "agendamento": "agendamento",
    "peticionamento": "peticionamento",
    "LoginGovbr": "login_govbr",
    "IaGenerativa": "ia_generativa",
    "IntegracaoAutomacao": "integracao_automacao",
    "PagamentoReconhecido": "pagamento_reconhecido",
    "AssinaturaGovbr": "assinatura_govbr",
    "OcrComIa": "ocr_com_ia",
    "ApisConectagov": "apis_conectagov",
    "Bpms": "bpms",
}

EXCEL_BASE_COLUMNS = list(EXCEL_BASE_RENAME.values())


def ensure_columns(df: pd.DataFrame, required_columns: list[str], label: str) -> None:
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        raise ValueError(f"{label}: colunas ausentes: {missing}")


def transform_excel_base(
    df_raw: pd.DataFrame,
    execution_id: str,
    excel_path: str,
) -> pd.DataFrame:
    ensure_columns(df_raw, list(EXCEL_BASE_RENAME.keys()), "Excel base")

    df = df_raw.rename(columns=EXCEL_BASE_RENAME).copy()

    for col in EXCEL_BASE_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = df[EXCEL_BASE_COLUMNS].copy()

    df["data_ref"] = df["data_ref"].apply(parse_date_br)
    df["numero_etapa"] = df["numero_etapa"].apply(parse_int64)

    text_cols = [c for c in EXCEL_BASE_COLUMNS if c not in ("data_ref", "numero_etapa")]
    for col in text_cols:
        df[col] = df[col].apply(normalize_text)

    df["execution_id"] = execution_id
    df["ingestion_ts"] = now_utc()
    df["arquivo_origem"] = os.path.basename(excel_path)
    df["row_num_origem"] = range(2, len(df) + 2)
    df["source_system"] = "excel_hist"

    df["id_linha_hash"] = df.apply(
        lambda r: make_id_linha_hash(
            nid=None,
            nid_1=None,
            numero_etapa=r["numero_etapa"],
            nome_etapa=r["nome_etapa"],
            nome_servico=r["nome_servico"],
            orgao_responsavel=r["orgao_responsavel"],
        ),
        axis=1,
    )

    ordered_cols = [
        "execution_id",
        "ingestion_ts",
        "arquivo_origem",
        "row_num_origem",
        "source_system",
        "data_ref",
        "orgao_responsavel",
        "nome_servico",
        "numero_etapa",
        "nome_etapa",
        "autosservico",
        "digital",
        "presencial",
        "etapa_futura",
        "agendamento",
        "peticionamento",
        "login_govbr",
        "ia_generativa",
        "integracao_automacao",
        "pagamento_reconhecido",
        "assinatura_govbr",
        "ocr_com_ia",
        "apis_conectagov",
        "bpms",
        "id_linha_hash",
    ]
    return df[ordered_cols]