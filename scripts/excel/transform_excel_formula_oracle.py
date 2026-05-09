from __future__ import annotations

import pandas as pd

from scripts.common.dates import now_utc, parse_date_br, parse_int64, parse_nullable_int_formula
from scripts.common.hashing import make_id_linha_hash
from scripts.common.normalize import normalize_text


EXCEL_FORMULA_RENAME = {
    "digitalizado": "digitalizado",
    "digitalizado_invertido": "digitalizado_invertido",
    "digitalizacao_futura": "digitalizacao_futura",
    "autosservico_numero": "autosservico_numero",
    "digital_numero": "digital_numero",
    "presencial_numero": "presencial_numero",
    "etapa_futura_presencial": "etapa_futura_presencial",
    "etapa_futura_digital": "etapa_futura_digital",
    "etapa_futura_autosservico": "etapa_futura_autosservico",
    "autosservico_potencial": "autosservico_potencial",
    "servico_presencial": "servico_presencial",
    "etapa_presencial": "etapa_presencial",
    "etapas_digitalizar_2": "etapas_digitalizar_2",
    "etapas_digitalizar": "etapas_digitalizar",
    "LoginGovbr_potencial": "login_govbr_potencial",
    "IaGenerativa_potencial": "ia_generativa_potencial",
    "IntegracaoAutomacao_potencial": "integracao_automacao_potencial",
    "PagamentoReconhecido_potencial": "pagamento_reconhecido_potencial",
    "peticionamento_potencial": "peticionamento_potencial",
    "AssinaturaGovbr_potencial": "assinatura_govbr_potencial",
    "ApisConectagov_potencial": "apis_conectagov_potencial",
    "Bpms_potencial": "bpms_potencial",
    "LoginGovbr_atual": "login_govbr_atual",
    "IaGenerativa_atual": "ia_generativa_atual",
    "IntegracaoAutomacao_atual": "integracao_automacao_atual",
    "PagamentoReconhecido_atual": "pagamento_reconhecido_atual",
    "peticionamento_atual": "peticionamento_atual",
    "AssinaturaGovbr_atual": "assinatura_govbr_atual",
    "ApisConectagov_atual": "apis_conectagov_atual",
    "Bpms_atual": "bpms_atual",
    "etapas_solucao_potencial": "etapas_solucao_potencial",
    "etapas_solucao_atual": "etapas_solucao_atual",
}

EXCEL_FORMULA_COLUMNS = list(EXCEL_FORMULA_RENAME.values())


def ensure_columns(df: pd.DataFrame, required_columns: list[str], label: str) -> None:
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        raise ValueError(f"{label}: colunas ausentes: {missing}")


def transform_excel_formula_oracle(
    df_raw: pd.DataFrame,
    execution_id: str,
) -> pd.DataFrame:
    required = list(EXCEL_FORMULA_RENAME.keys()) + [
        "data",
        "orgao_responsavel",
        "nome_servico",
        "numero_etapa",
        "nome_etapa",
    ]
    ensure_columns(df_raw, required, "Excel fórmulas")

    df = df_raw.rename(columns=EXCEL_FORMULA_RENAME).copy()

    for col in EXCEL_FORMULA_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df["data_ref"] = df_raw["data"].apply(parse_date_br)
    numero_etapa = df_raw["numero_etapa"].apply(parse_int64)
    orgao_responsavel = df_raw["orgao_responsavel"].apply(normalize_text)
    nome_servico = df_raw["nome_servico"].apply(normalize_text)
    nome_etapa = df_raw["nome_etapa"].apply(normalize_text)

    numeric_formula_cols = [
        c for c in EXCEL_FORMULA_COLUMNS
        if c not in ("servico_presencial", "etapa_presencial")
    ]

    for col in numeric_formula_cols:
        df[col] = df[col].apply(parse_nullable_int_formula)

    df["servico_presencial"] = df["servico_presencial"].apply(normalize_text)
    df["etapa_presencial"] = df["etapa_presencial"].apply(normalize_text)

    df["id_linha_hash"] = [
        make_id_linha_hash(
            nid=None,
            nid_1=None,
            numero_etapa=numero_etapa.iloc[i],
            nome_etapa=nome_etapa.iloc[i],
            nome_servico=nome_servico.iloc[i],
            orgao_responsavel=orgao_responsavel.iloc[i],
        )
        for i in range(len(df))
    ]

    df["execution_id"] = execution_id
    df["ingestion_ts"] = now_utc()

    ordered_cols = [
        "execution_id",
        "ingestion_ts",
        "data_ref",
        "id_linha_hash",
        *EXCEL_FORMULA_COLUMNS,
    ]
    return df[ordered_cols]