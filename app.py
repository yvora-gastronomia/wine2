import hashlib
import io
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import pandas as pd
import requests
import streamlit as st

# ======================================================
# CONFIG
# ======================================================

APP_TITLE = "YVORA Wine Pairing"

def _get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

# ======================================================
# UTILS
# ======================================================

def norm_text(x) -> str:
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass
    return str(x).strip()

def _decode_csv_bytes(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("cp1252", errors="replace")

# ======================================================
# GOOGLE SHEETS EXTRACTION
# ======================================================

def _extract_sheet_id_and_gid(url: str) -> Tuple[str, str]:
    u = norm_text(url)

    parsed = urlparse(u)

    gid = "0"

    if parsed.fragment:
        frag_qs = parse_qs(parsed.fragment)
        gid = (frag_qs.get("gid", [gid]) or [gid])[0]

    qs = parse_qs(parsed.query)
    if "gid" in qs:
        gid = qs["gid"][0]

    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", u)
    if not m:
        return "", gid

    return m.group(1), gid


def _candidate_sheet_csv_urls(url: str) -> List[str]:
    sheet_id, gid = _extract_sheet_id_and_gid(url)

    if not sheet_id:
        raise ValueError("Não foi possível identificar o ID da planilha.")

    gid = gid or "0"

    return [
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}",
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}",
    ]

# ======================================================
# LOAD CSV (COM FALLBACK REAL)
# ======================================================

@st.cache_data(ttl=45)
def load_csv_from_url(url: str, source_name: str = "SHEET") -> pd.DataFrame:
    original_url = norm_text(url)

    candidate_urls = _candidate_sheet_csv_urls(original_url)

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/csv,*/*",
    }

    last_error = None

    for idx, export_url in enumerate(candidate_urls, start=1):
        try:
            r = requests.get(export_url, headers=headers, timeout=30)
            r.raise_for_status()

            csv_text = _decode_csv_bytes(r.content)

            if not csv_text.strip():
                last_error = ValueError(
                    f"[{source_name}] tentativa {idx} retornou vazio\n{export_url}"
                )
                continue

            if "<html" in csv_text.lower():
                last_error = ValueError(
                    f"[{source_name}] tentativa {idx} retornou HTML\n{export_url}"
                )
                continue

            return pd.read_csv(io.StringIO(csv_text), dtype=str, keep_default_na=False)

        except Exception as e:
            last_error = ValueError(
                f"[{source_name}] tentativa {idx} falhou\nURL: {export_url}\nErro: {e}"
            )

    raise last_error

# ======================================================
# NORMALIZAÇÃO
# ======================================================

def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.lower().strip() for c in df.columns]
    return df

# ======================================================
# LOAD DATA
# ======================================================

def load_all_data():
    menu_url = _get_secret("MENU_SHEET_URL")
    wines_url = _get_secret("WINES_SHEET_URL")
    pairings_url = _get_secret("PAIRINGS_SHEET_URL")

    if not menu_url:
        raise ValueError("MENU_SHEET_URL não configurado")

    if not wines_url:
        raise ValueError("WINES_SHEET_URL não configurado")

    if not pairings_url:
        raise ValueError("PAIRINGS_SHEET_URL não configurado")

    menu = normalize_cols(load_csv_from_url(menu_url, "MENU"))
    wines = normalize_cols(load_csv_from_url(wines_url, "WINES"))
    pairings = normalize_cols(load_csv_from_url(pairings_url, "PAIRINGS"))

    return menu, wines, pairings

# ======================================================
# UI
# ======================================================

def main():
    st.set_page_config(layout="wide")
    st.title("Wine Pairing")

    try:
        menu, wines, pairings = load_all_data()
        st.success("Dados carregados com sucesso")

        st.write("MENU:", len(menu))
        st.write("WINES:", len(wines))
        st.write("PAIRINGS:", len(pairings))

    except Exception as e:
        st.error("Erro ao carregar dados:")
        st.code(str(e))

# ======================================================
# RUN
# ======================================================

if __name__ == "__main__":
    main()
