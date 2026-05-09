from __future__ import annotations

import json
from datetime import date
from typing import Any

import pandas as pd

from scripts.common.dates import now_utc, parse_date_br, parse_int64
from scripts.common.hashing import make_chave_negocio_base, make_id_linha_hash, sha256_hex
from scripts.common.normalize import normalize_text


API_RENAME = {
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
    "nid": "nid",
    "nid_1": "nid_1",
    "publicado": "publicado",
    "alterado": "alterado",
    "ExigeDocumentoAut": "exige_documento_aut",
    "ExigeDocumentoAdmPub": "exige_documento_adm_pub",
    "DocumentosEmitidosAdmPub": "documentos_emitidos_adm_pub",
}

API_COLUMNS = list(API_RENAME.values())


def ensure_columns(df: pd.DataFrame, required_columns: list[str], label: str) -> None:
    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        raise ValueError(f"{label}: colunas ausentes: {missing}")


def transform_api(
    data: list[dict[str, Any]],
    execution_id: str,
    snapshot_date: date,
) -> pd.DataFrame:
    df = pd.DataFrame(data)
    df.columns = [str(c).strip() for c in df.columns]

    ensure_columns(df, list(API_RENAME.keys()), "API")

    df = df.rename(columns=API_RENAME).copy()

    for col in API_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = df[API_COLUMNS].copy()

    df["numero_etapa"] = df["numero_etapa"].apply(parse_int64)
    df["publicado"] = df["publicado"].apply(parse_date_br)
    df["alterado"] = df["alterado"].apply(parse_date_br)

    text_cols = [c for c in API_COLUMNS if c not in ("numero_etapa", "publicado", "alterado")]
    for col in text_cols:
        df[col] = df[col].apply(normalize_text)

    df["execution_id"] = execution_id
    df["ingestion_ts"] = now_utc()
    df["snapshot_date"] = snapshot_date
    df["source_system"] = "api"

    raw_payloads = []
    hash_payloads = []
    id_hashes = []
    business_keys = []

    for row in df.to_dict(orient="records"):
        payload_dict = {
            "orgao_responsavel": row["orgao_responsavel"],
            "nome_servico": row["nome_servico"],
            "numero_etapa": row["numero_etapa"],
            "nome_etapa": row["nome_etapa"],
            "autosservico": row["autosservico"],
            "digital": row["digital"],
            "presencial": row["presencial"],
            "etapa_futura": row["etapa_futura"],
            "agendamento": row["agendamento"],
            "peticionamento": row["peticionamento"],
            "login_govbr": row["login_govbr"],
            "ia_generativa": row["ia_generativa"],
            "integracao_automacao": row["integracao_automacao"],
            "pagamento_reconhecido": row["pagamento_reconhecido"],
            "assinatura_govbr": row["assinatura_govbr"],
            "ocr_com_ia": row["ocr_com_ia"],
            "apis_conectagov": row["apis_conectagov"],
            "bpms": row["bpms"],
            "nid": row["nid"],
            "nid_1": row["nid_1"],
            "publicado": row["publicado"].isoformat() if row["publicado"] else None,
            "alterado": row["alterado"].isoformat() if row["alterado"] else None,
            "exige_documento_aut": row["exige_documento_aut"],
            "exige_documento_adm_pub": row["exige_documento_adm_pub"],
            "documentos_emitidos_adm_pub": row["documentos_emitidos_adm_pub"],
        }

        payload_json = json.dumps(payload_dict, ensure_ascii=False, sort_keys=True)
        raw_payloads.append(payload_json)
        hash_payloads.append(sha256_hex(payload_json))

        id_hashes.append(
            make_id_linha_hash(
                nid=row["nid"],
                nid_1=row["nid_1"],
                numero_etapa=row["numero_etapa"],
                nome_etapa=row["nome_etapa"],
                nome_servico=row["nome_servico"],
                orgao_responsavel=row["orgao_responsavel"],
            )
        )

        business_keys.append(
            make_chave_negocio_base(
                nid=row["nid"],
                nid_1=row["nid_1"],
                numero_etapa=row["numero_etapa"],
            )
        )

    df["payload_json"] = raw_payloads
    df["hash_payload"] = hash_payloads
    df["id_linha_hash"] = id_hashes
    df["chave_negocio_base"] = business_keys

    ordered_cols = [
        "execution_id",
        "ingestion_ts",
        "snapshot_date",
        "source_system",
        "payload_json",
        "hash_payload",
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
        "nid",
        "nid_1",
        "publicado",
        "alterado",
        "exige_documento_aut",
        "exige_documento_adm_pub",
        "documentos_emitidos_adm_pub",
        "id_linha_hash",
        "chave_negocio_base",
    ]
    return df[ordered_cols]