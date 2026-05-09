from __future__ import annotations

import json
import requests
from typing import Any


PAGE_SIZE_ASSUMIDA = 200
MAX_PAGES = 2000


def fetch_api_json(api_url: str, api_key: str, timeout_seconds: int) -> list[dict[str, Any]]:
    if not api_key:
        raise ValueError("API_KEY não informada no ambiente.")

    api_key = api_key.strip().strip('"').strip("'")

    headers = {
        "key": api_key,
    }

    all_items: list[dict[str, Any]] = []
    seen_raw_signatures: set[str] = set()

    page = 0

    while page < MAX_PAGES:
        response = requests.get(
            api_url,
            headers=headers,
            params={"page": page},
            timeout=timeout_seconds,
        )

        if response.status_code != 200:
            body_preview = response.text[:500]
            raise requests.HTTPError(
                f"{response.status_code} ao acessar {response.url}. "
                f"Trecho da resposta: {body_preview}",
                response=response,
            )

        payload: Any = response.json()

        if not isinstance(payload, list):
            raise ValueError(
                f"A API respondeu com JSON que não é lista. Tipo retornado: {type(payload).__name__}"
            )

        if not payload:
            break

        new_items_in_page = 0

        for item in payload:
            raw_signature = json.dumps(item, ensure_ascii=False, sort_keys=True)

            # remove apenas duplicatas físicas idênticas
            if raw_signature in seen_raw_signatures:
                continue

            seen_raw_signatures.add(raw_signature)
            all_items.append(item)
            new_items_in_page += 1

        # se a página não trouxe nada novo, paramos
        if new_items_in_page == 0:
            break

        # se veio menos que 200, provavelmente é a última
        if len(payload) < PAGE_SIZE_ASSUMIDA:
            break

        page += 1

    return all_items