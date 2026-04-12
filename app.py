# ===============================
# YVORA WINE PAIRING - FIX FINAL
# ===============================

import io
import re
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
import requests
import streamlit as st

APP_TITLE = "YVORA Wine Pairing"

BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "yvora_logo.png"


# ===============================
# LOGO FIX (corrige seu problema)
# ===============================
def render_logo():
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
    else:
        st.write("")  # não quebra layout


# ===============================
# HELPERS
# ===============================
def normalize_id(x):
    if not x:
        return ""
    s = str(x)
    m = re.search(r"\d+", s)
    return m.group(0) if m else ""


def split_ids(x):
    if not x:
        return []
    return [normalize_id(i) for i in re.split(r"[|,;/]", str(x)) if normalize_id(i)]


# ===============================
# LOAD DATA
# ===============================
def load_csv(url):
    r = requests.get(url)
    return pd.read_csv(io.StringIO(r.text), dtype=str).fillna("")


# ===============================
# CORE FIX (AQUI ESTAVA O ERRO)
# ===============================
def get_pairings_for_dish(pairings, dish_id):

    # 1. FILTRA APENAS LINHAS INDIVIDUAIS
    df = pairings[pairings["ids_pratos"].apply(lambda x: dish_id in split_ids(x))]

    # 2. REMOVE QUALQUER COISA QUE NÃO SEJA EXATAMENTE 1 PRATO
    df = df[df["ids_pratos"].apply(lambda x: len(split_ids(x)) == 1)]

    return df


# ===============================
# APP
# ===============================
def main():

    st.set_page_config(layout="wide")

    with st.sidebar:
        render_logo()

    st.title("Wine Pairing")

    menu_url = st.secrets["MENU_SHEET_URL"]
    wines_url = st.secrets["WINES_SHEET_URL"]
    pairings_url = st.secrets["PAIRINGS_SHEET_URL"]

    menu = load_csv(menu_url)
    wines = load_csv(wines_url)
    pairings = load_csv(pairings_url)

    pratos = menu["nome_prato"].tolist()

    selected = st.selectbox("Escolha o prato", pratos)

    if selected:

        row = menu[menu["nome_prato"] == selected].iloc[0]
        dish_id = normalize_id(row["id_prato"])

        st.write(f"ID selecionado: {dish_id}")

        df = get_pairings_for_dish(pairings, dish_id)

        if df.empty:
            st.error("Nenhum pairing encontrado")
            return

        for _, r in df.iterrows():

            vinho_id = str(r["id_vinho"]).strip()

            vinho = wines[wines["id_vinho"] == vinho_id]

            if vinho.empty:
                continue

            vinho_nome = vinho.iloc[0]["nome_vinho"]

            st.subheader(vinho_nome)
            st.write(r.get("motivo_score", ""))


if __name__ == "__main__":
    main()
