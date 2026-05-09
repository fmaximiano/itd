from __future__ import annotations

import pandas as pd


def load_excel_raw(path: str, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet_name, dtype=object)
    df.columns = [str(c).strip() for c in df.columns]

    # remove linhas totalmente vazias
    df = df.dropna(how="all").copy()

    # remove linhas em que tudo ficou vazio após trim
    def _row_is_effectively_empty(row) -> bool:
        for value in row:
            if value is None:
                continue
            if pd.isna(value):
                continue
            if str(value).strip() != "":
                return False
        return True

    df = df.loc[~df.apply(_row_is_effectively_empty, axis=1)].copy()
    df = df.reset_index(drop=True)

    return df