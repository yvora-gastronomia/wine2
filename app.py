import io
import re
import json
import time
from pathlib import Path

import pandas as pd
import streamlit as st

# ======================================================
# CONFIG
# ======================================================
st.set_page_config(
    page_title="YVORA | Wine Pairing",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ======================================================
# ESTILO
# ======================================================
st.markdown(
    """
<style>
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
}
.stApp {
    background-color: #EFE7DD;
}
.block-container {
    max-width: 1180px;
    padding-top: 1.2rem;
    padding-bottom: 2rem;
}
.yv-card {
    background: #F7F3ED;
    border-radius: 22px;
    padding: 22px 26px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.04);
    border: 1px solid rgba(14,42,71,0.06);
}
.yv-title {
    color: #0E2A47;
    font-size: 2.9rem;
    line-height: 1.0;
    font-weight: 800;
    margin-bottom: 0.7rem;
}
.yv-subtitle {
    color: #5F6B7A;
    font-size: 1.05rem;
    margin-bottom: 0;
}
.yv-section-title {
    color: #0E2A47;
    font-size: 1.15rem;
    font-weight: 800;
    margin: 0.6rem 0 0.9rem 0;
}
.yv-wine-card {
    background: #FFFFFF;
    border-radius: 18px;
    padding: 18px 18px 14px 18px;
    border: 1px solid rgba(14,42,71,0.08);
    box-shadow: 0 2px 8px rgba(0,0,0,0.03);
    margin-bottom: 14px;
}
.yv-wine-title {
    color: #0E2A47;
    font-size: 1.1rem;
    font-weight: 800;
    margin-bottom: 0.3rem;
}
.yv-meta {
    color: #6A7380;
    font-size: 0.95rem;
    margin-bottom: 0.65rem;
}
.yv-badge {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 999px;
    background: #EFE7DD;
    color: #0E2A47;
    font-size: 0.82rem;
    font-weight: 700;
    margin-right: 8px;
    margin-bottom: 8px;
}
.yv-label {
    color: #0E2A47;
    font-weight: 700;
}
.yv-small {
    color: #6A7380;
    font-size: 0.92rem;
}
.yv-divider {
    margin: 10px 0 14px 0;
    border-top: 1px solid rgba(14,42,71,0.08);
}
div[data-testid="stMultiSelect"] label,
div[data-testid="stSelectbox"] label {
    font-weight: 700 !important;
    color: #0E2A47 !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# ======================================================
# HELPERS
# ======================================================
def clean_text(x) -> str:
    if pd.isna(x):
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()

def norm_id(x) -> str:
    s = clean_text(x)
    if not s:
        return ""
    if s.endswith(".0"):
        s = s[:-2]
    return s

def normalize_label(s: str) -> str:
    s = clean_text(s).lower()
    repl = {
        "á": "a", "à": "a", "â": "a", "ã": "a",
        "é": "e", "ê": "e",
        "í": "i",
        "ó": "o", "ô": "o", "õ": "o",
        "ú": "u",
        "ç": "c",
    }
    for a, b in repl.items():
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

@st.cache_data(show_spinner=False)
def load_csv(uploaded_file) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()
    return pd.read_csv(uploaded_file)

def ensure_required_columns(df: pd.DataFrame, cols: list[str], df_name: str):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        st.error(f"O arquivo {df_name} não contém as colunas obrigatórias: {missing}")
        st.stop()

def prepare_menu_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [clean_text(c) for c in df.columns]

    ensure_required_columns(df, ["Id", "Prato", "Ativo"], "menu")

    df["Id"] = df["Id"].map(norm_id)
    df["Prato"] = df["Prato"].map(clean_text)
    df["Ativo"] = df["Ativo"].map(norm_id)

    df = df[df["Ativo"] == "1"].copy()
    df = df[df["Id"] != ""].copy()

    if "Descrição_curta_Menu" not in df.columns:
        df["Descrição_curta_Menu"] = ""
    if "Descrição" not in df.columns:
        df["Descrição"] = ""

    df["descricao_exibicao"] = df["Descrição_curta_Menu"].map(clean_text)
    df.loc[df["descricao_exibicao"] == "", "descricao_exibicao"] = df["Descrição"].map(clean_text)

    df["menu_label"] = df["Prato"] + " | ID " + df["Id"]
    return df

def prepare_pairings_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [clean_text(c) for c in df.columns]

    required = [
        "ids_pratos", "nomes_pratos", "id_vinho", "nome_vinho", "preco",
        "frase_mesa", "por_que_carne", "por_que_queijo", "por_que_combo",
        "perfil_custo_beneficio", "por_que_vale", "a_melhor_para",
        "rotulo_valor", "origem", "ativo"
    ]
    ensure_required_columns(df, required, "pairings")

    df["ids_pratos"] = df["ids_pratos"].map(norm_id)
    df["nomes_pratos"] = df["nomes_pratos"].map(clean_text)
    df["id_vinho"] = df["id_vinho"].map(clean_text)
    df["nome_vinho"] = df["nome_vinho"].map(clean_text)
    df["preco"] = df["preco"].map(clean_text)
    df["origem"] = df["origem"].map(clean_text)
    df["rotulo_valor"] = df["rotulo_valor"].map(clean_text)

    text_cols = [
        "frase_mesa", "por_que_carne", "por_que_queijo", "por_que_combo",
        "perfil_custo_beneficio", "por_que_vale", "a_melhor_para"
    ]
    for c in text_cols:
        df[c] = df[c].map(clean_text)

    if "ativo" in df.columns:
        df["ativo"] = df["ativo"].astype(str).str.strip()
        df = df[df["ativo"].isin(["1", "True", "true"])].copy()

    df = df[df["ids_pratos"] != ""].copy()
    return df

def enrich_pairings_with_menu(pairings_df: pd.DataFrame, menu_df: pd.DataFrame) -> pd.DataFrame:
    menu_lookup = menu_df[["Id", "Prato", "descricao_exibicao"]].copy()
    menu_lookup = menu_lookup.rename(columns={
        "Id": "ids_pratos",
        "Prato": "menu_prato",
        "descricao_exibicao": "menu_descricao",
    })

    out = pairings_df.merge(menu_lookup, on="ids_pratos", how="left")

    out["nome_exibicao_prato"] = out["menu_prato"]
    out.loc[out["nome_exibicao_prato"].isna() | (out["nome_exibicao_prato"] == ""), "nome_exibicao_prato"] = out["nomes_pratos"]

    out["descricao_exibicao_prato"] = out["menu_descricao"].fillna("")
    return out

def find_pairings_for_ids(pairings_df: pd.DataFrame, selected_ids: list[str]) -> pd.DataFrame:
    if not selected_ids:
        return pairings_df.iloc[0:0].copy()
    selected_ids = [norm_id(x) for x in selected_ids if norm_id(x)]
    return pairings_df[pairings_df["ids_pratos"].isin(selected_ids)].copy()

def sort_pairings(df: pd.DataFrame) -> pd.DataFrame:
    def price_num(x):
        try:
            return float(str(x).replace(",", "."))
        except Exception:
            return 999999

    tmp = df.copy()
    tmp["_price_num"] = tmp["preco"].map(price_num)
    tmp = tmp.sort_values(
        by=["ids_pratos", "_price_num", "nome_vinho"],
        ascending=[True, True, True]
    )
    return tmp.drop(columns=["_price_num"])

def render_wine_card(row: pd.Series):
    st.markdown('<div class="yv-wine-card">', unsafe_allow_html=True)

    title = clean_text(row["nome_vinho"])
    meta_parts = []
    if clean_text(row["origem"]):
        meta_parts.append(clean_text(row["origem"]))
    if clean_text(row["preco"]):
        meta_parts.append(f"R$ {clean_text(row['preco'])}")
    meta = " • ".join(meta_parts)

    st.markdown(f'<div class="yv-wine-title">{title}</div>', unsafe_allow_html=True)
    if meta:
        st.markdown(f'<div class="yv-meta">{meta}</div>', unsafe_allow_html=True)

    badges = []
    if clean_text(row["rotulo_valor"]):
        badges.append(clean_text(row["rotulo_valor"]))

    if badges:
        st.markdown(
            "".join([f'<span class="yv-badge">{b}</span>' for b in badges]),
            unsafe_allow_html=True
        )

    if clean_text(row["frase_mesa"]):
        st.markdown(f"**Na mesa**  \n{clean_text(row['frase_mesa'])}")

    if clean_text(row["por_que_carne"]):
        st.markdown(f"**Por que com a carne**  \n{clean_text(row['por_que_carne'])}")

    if clean_text(row["por_que_queijo"]):
        st.markdown(f"**Por que com o queijo**  \n{clean_text(row['por_que_queijo'])}")

    if clean_text(row["por_que_combo"]):
        st.markdown(f"**Por que o combo funciona**  \n{clean_text(row['por_que_combo'])}")

    if clean_text(row["perfil_custo_beneficio"]):
        st.markdown(f"**Perfil custo-benefício**  \n{clean_text(row['perfil_custo_beneficio'])}")

    if clean_text(row["por_que_vale"]):
        st.markdown(f"**Por que vale**  \n{clean_text(row['por_que_vale'])}")

    if clean_text(row["a_melhor_para"]):
        st.markdown(f"**A melhor para**  \n{clean_text(row['a_melhor_para'])}")

    st.markdown("</div>", unsafe_allow_html=True)

def render_dish_block(dish_id: str, menu_df: pd.DataFrame, pairings_df: pd.DataFrame):
    menu_row = menu_df[menu_df["Id"] == dish_id]
    if menu_row.empty:
        st.error(f"ID {dish_id} não existe no menu ativo.")
        return

    menu_row = menu_row.iloc[0]
    prato = clean_text(menu_row["Prato"])
    desc = clean_text(menu_row.get("descricao_exibicao", ""))

    st.markdown(f"## {prato}")
    if desc:
        st.markdown(f"<div class='yv-small'>{desc}</div>", unsafe_allow_html=True)

    dish_pairings = pairings_df[pairings_df["ids_pratos"] == dish_id].copy()
    dish_pairings = sort_pairings(dish_pairings)

    if dish_pairings.empty:
        st.error(f"{prato}: não existe linha correspondente no pairings para o ID {dish_id}.")
        return

    st.markdown("<div class='yv-divider'></div>", unsafe_allow_html=True)

    for _, row in dish_pairings.iterrows():
        render_wine_card(row)

# ======================================================
# SIDEBAR
# ======================================================
with st.sidebar:
    st.markdown("### YVORA | Meat & Cheese Lab")
    st.markdown("Wine Pairing por ID")
    st.markdown("---")
    st.markdown("Carregue os arquivos usados pelo app.")

    menu_file = st.file_uploader(
        "Menu CSV",
        type=["csv"],
        key="menu_csv"
    )
    pairings_file = st.file_uploader(
        "Pairings CSV",
        type=["csv"],
        key="pairings_csv"
    )

    st.markdown("---")
    show_debug = st.checkbox("Mostrar diagnóstico técnico", value=False)

# ======================================================
# HEADER
# ======================================================
st.markdown(
    """
<div class="yv-card">
    <div class="yv-title">Wine Pairing</div>
    <div class="yv-subtitle">Escolha até 2 pratos para ver a recomendação de vinho por ID, com pareamento confiável entre menu e pairings.</div>
</div>
""",
    unsafe_allow_html=True,
)

st.write("")

# ======================================================
# LOAD DATA
# ======================================================
if menu_file is None or pairings_file is None:
    st.info("Envie os arquivos CSV de menu e pairings para continuar.")
    st.stop()

menu_df = prepare_menu_df(load_csv(menu_file))
pairings_df = prepare_pairings_df(load_csv(pairings_file))
pairings_df = enrich_pairings_with_menu(pairings_df, menu_df)

# ======================================================
# DIAGNÓSTICO DE INTEGRAÇÃO
# ======================================================
menu_ids = set(menu_df["Id"].tolist())
pairing_ids = set(pairings_df["ids_pratos"].tolist())

ids_sem_pairing = sorted(menu_ids - pairing_ids)
pairings_sem_menu = sorted(pairing_ids - menu_ids)

# ======================================================
# SELEÇÃO
# ======================================================
st.markdown('<div class="yv-section-title">Escolha seus pratos</div>', unsafe_allow_html=True)

options_df = menu_df[["Id", "Prato", "menu_label"]].drop_duplicates().copy()
options_df = options_df.sort_values(by=["Prato", "Id"])

selected_labels = st.multiselect(
    "Selecione até 2 pratos",
    options=options_df["menu_label"].tolist(),
    max_selections=2,
    label_visibility="collapsed",
)

selected_ids = options_df.loc[
    options_df["menu_label"].isin(selected_labels), "Id"
].tolist()

# ======================================================
# DEBUG
# ======================================================
if show_debug:
    with st.expander("Diagnóstico técnico", expanded=True):
        st.write("Menu ativo carregado:", len(menu_df))
        st.write("Pairings carregados:", len(pairings_df))
        st.write("IDs ativos no menu:", len(menu_ids))
        st.write("IDs encontrados no pairings:", len(pairing_ids))
        st.write("IDs do menu sem pairings:", ids_sem_pairing)
        st.write("IDs do pairings sem menu:", pairings_sem_menu)

        if selected_ids:
            st.write("IDs selecionados:", selected_ids)
            preview = pairings_df[pairings_df["ids_pratos"].isin(selected_ids)][
                ["ids_pratos", "nome_exibicao_prato", "id_vinho", "nome_vinho", "preco"]
            ]
            st.dataframe(preview, use_container_width=True)

# ======================================================
# RESULTADOS
# ======================================================
if not selected_ids:
    st.info("Selecione 1 ou 2 pratos para visualizar as harmonizações.")
    st.stop()

pairings_selected = find_pairings_for_ids(pairings_df, selected_ids)

if pairings_selected.empty:
    st.error("Nenhuma linha correspondente encontrada no pairings para os IDs selecionados.")
    st.stop()

for dish_id in selected_ids:
    render_dish_block(dish_id, menu_df, pairings_selected)
    st.write("")
