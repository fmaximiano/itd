from __future__ import annotations

import hashlib
from typing import Optional

from scripts.common.normalize import normalize_text


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_id_linha_hash(
    nid: Optional[str],
    nid_1: Optional[str],
    numero_etapa: Optional[int],
    nome_etapa: Optional[str],
    nome_servico: Optional[str],
    orgao_responsavel: Optional[str],
) -> str:
    parts = [
        normalize_text(nid) or "",
        normalize_text(nid_1) or "",
        str(numero_etapa) if numero_etapa is not None else "",
        normalize_text(nome_etapa) or "",
        normalize_text(nome_servico) or "",
        normalize_text(orgao_responsavel) or "",
    ]
    return sha256_hex("|".join(parts))


def make_chave_negocio_base(
    nid: Optional[str],
    nid_1: Optional[str],
    numero_etapa: Optional[int],
) -> Optional[str]:
    nid_norm = normalize_text(nid)
    nid_1_norm = normalize_text(nid_1)

    if nid_norm is None and nid_1_norm is None and numero_etapa is None:
        return None

    return f"{nid_norm or ''}|{nid_1_norm or ''}|{numero_etapa if numero_etapa is not None else ''}"