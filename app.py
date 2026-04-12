import io
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
import requests
import streamlit as st

APP_TITLE = "YVORA Wine Pairing"
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "yvora_logo.png"

BRAND_BG = "#EFE7DD"
BRAND_BLUE = "#0E2A47"
BRAND_MUTED = "#6B7785"
BRAND_CARD = "#F5EFE7"
BRAND_SOFT = "#F8F4EE"
BRAND_WHITE = "#FFFFFF"
BRAND_WARN = "#F3D6CF"


def set_page_style() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🍷", layout="wide", initial_sidebar_state="expanded")
    st.markdown(
        f"""
        <style>
        .stApp {{ background: linear-gradient(180deg, {BRAND_BG} 0%, #FBF8F3 100%); }}
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, rgba(14,42,71,0.98) 0%, rgba(14,42,71,0.94) 100%);
            border-right: 1px solid rgba(255,255,255,0.08);
        }}
        [data-testid="stSidebar"] * {{ color: {BRAND_WHITE}; }}
        .block-container {{ padding-top: 1.2rem; padding-bottom: 2rem; }}
        .yvora-shell {{ max-width: 1240px; margin: 0 auto; }}
        .yvora-hero {{
            background: linear-gradient(135deg, rgba(255,255,255,0.95) 0%, rgba(245,239,231,0.95) 100%);
            border: 1px solid rgba(14,42,71,0.08);
            box-shadow: 0 14px 36px rgba(14,42,71,0.08);
            border-radius: 26px;
            padding: 22px;
            margin-bottom: 18px;
        }}
        .yvora-title {{ color: {BRAND_BLUE}; font-size: 2.15rem; font-weight: 800; margin: 0; }}
        .yvora-subtitle {{ color: {BRAND_MUTED}; font-size: 1rem; line-height: 1.45rem; margin-top: 8px; max-width: 700px; }}
        .yvora-card {{
            background: linear-gradient(180deg, {BRAND_CARD} 0%, {BRAND_SOFT} 100%);
            border-radius: 22px;
            padding: 18px 18px 14px 18px;
            border: 1px solid rgba(14,42,71,0.08);
            margin-bottom: 18px;
            box-shadow: 0 10px 28px rgba(14,42,71,0.05);
        }}
        .yvora-card-title {{ font-size: 1.28rem; font-weight: 800; color: {BRAND_BLUE}; margin-bottom: 4px; }}
        .yvora-card-sub {{ color: {BRAND_MUTED}; font-size: 0.93rem; margin-bottom: 10px; }}
        .yvora-section-head {{ color: {BRAND_BLUE}; font-size: 1.02rem; font-weight: 800; margin: 6px 0 8px 0; }}
        .yvora-warn {{ background: {BRAND_WARN}; border-radius: 14px; padding: 14px 16px; border: 1px solid rgba(14,42,71,0.08); color: {BRAND_BLUE}; white-space: pre-wrap; }}
        .yvora-signal-box {{ background: rgba(255,255,255,0.78); border: 1px solid rgba(14,42,71,0.08); border-radius: 16px; padding: 12px; min-height: 72px; height: 100%; }}
        .yvora-signal-label {{ color: {BRAND_MUTED}; font-size: 0.76rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 4px; }}
        .yvora-signal-value {{ color: {BRAND_BLUE}; font-size: 1.1rem; font-weight: 800; line-height: 1.2rem; }}
        .yvora-signal-sub {{ color: {BRAND_MUTED}; font-size: 0.82rem; margin-top: 4px; line-height: 1.1rem; }}
        .yvora-context {{ background: rgba(255,255,255,0.78); border: 1px solid rgba(14,42,71,0.08); border-radius: 18px; padding: 15px; margin: 12px 0; color: {BRAND_BLUE}; font-size: 0.95rem; line-height: 1.5rem; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_logo(width: int | None = None, use_container_width: bool = False):
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=width, use_container_width=use_container_width)
    else:
        st.markdown("<div style='height:140px'></div>", unsafe_allow_html=True)


def norm_text(x) -> str:
    return "" if x is None else str(x).strip()


def clean_text(x) -> str:
    return re.sub(r"\s+", " ", norm_text(x)).strip()


def normalize_id(x) -> str:
    s = norm_text(x).replace(",", ".")
    if not s:
        return ""
    m = re.search(r"[A-Za-z0-9]+(?:\.[0-9]+)?", s)
    if not m:
        return ""
    token = m.group(0)
    try:
        f = float(token)
        if f.is_integer():
            return str(int(f))
    except Exception:
        pass
    return token.strip()


def split_ids(x) -> list[str]:
    raw = norm_text(x)
    if not raw:
        return []
    parts = re.split(r"[|,;/]+", raw)
    vals = [normalize_id(p) for p in parts]
    return [v for v in vals if v]


def to_int(x, default: int = 0) -> int:
    s = norm_text(x)
    if not s:
        return default
    try:
        return int(float(s.replace(",", ".")))
    except Exception:
        return default


def score_to_stars(score_raw: str) -> str:
    score = to_int(score_raw, 0)
    if score >= 90:
        n = 5
    elif score >= 80:
        n = 4
    elif score >= 70:
        n = 3
    elif score >= 60:
        n = 2
    else:
        n = 1
    return "★" * n + "☆" * (5 - n)


def extract_sheet_id_and_gid(url: str) -> tuple[str, str]:
    u = norm_text(url)
    parsed = urlparse(u)
    gid = "0"
    if parsed.fragment:
        frag_qs = parse_qs(parsed.fragment)
        gid = (frag_qs.get("gid", [gid]) or [gid])[0] or gid
    qs = parse_qs(parsed.query)
    if "gid" in qs:
        gid = (qs.get("gid", [gid]) or [gid])[0] or gid
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", u)
    if not m:
        return "", gid
    return m.group(1), gid


def candidate_csv_urls(url: str) -> list[str]:
    sheet_id, gid = extract_sheet_id_and_gid(url)
    if not sheet_id:
        raise ValueError("Não foi possível identificar o ID da planilha.")
    return [
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}",
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}",
    ]


def load_csv_from_url(url: str, source_name: str) -> pd.DataFrame:
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/csv,application/csv,text/plain,*/*"}
    last_error = None
    for export_url in candidate_csv_urls(url):
        try:
            r = requests.get(export_url, headers=headers, timeout=30)
            r.raise_for_status()
            text = r.content.decode("utf-8-sig", errors="replace")
            if not text.strip():
                last_error = ValueError(f"{source_name}: retorno vazio.")
                continue
            if text.lstrip().lower().startswith("<html"):
                last_error = ValueError(f"{source_name}: Google retornou HTML em vez de CSV.")
                continue
            return pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
        except Exception as e:
            last_error = e
    raise ValueError(f"Falha ao carregar {source_name}: {last_error}")


def resolve_menu_columns(df: pd.DataFrame) -> tuple[str | None, str | None]:
    cols = {str(c).strip().lower(): c for c in df.columns}
    id_col = cols.get("id_prato") or cols.get("id") or cols.get("prato_id")
    name_col = cols.get("nome_prato") or cols.get("prato") or cols.get("nome") or cols.get("title")
    if not name_col:
        for c in df.columns:
            lc = str(c).lower()
            if "nome" in lc or "prato" in lc:
                name_col = c
                break
    return id_col, name_col


def standardize_menu(df: pd.DataFrame) -> pd.DataFrame:
    id_col, name_col = resolve_menu_columns(df)
    if not name_col:
        raise ValueError(f"A planilha MENU não possui coluna de nome de prato. Colunas recebidas: {list(df.columns)}")
    out = pd.DataFrame()
    out["id_prato"] = df[id_col] if id_col else ""
    out["nome_prato"] = df[name_col]
    out["id_prato"] = out["id_prato"].apply(normalize_id)
    out["nome_prato"] = out["nome_prato"].apply(clean_text)
    missing = out["id_prato"].eq("")
    out.loc[missing, "id_prato"] = out.loc[missing, "nome_prato"]
    out = out[out["nome_prato"] != ""].drop_duplicates(subset=["id_prato", "nome_prato"]).copy()
    out = out.sort_values(["nome_prato", "id_prato"], ascending=[True, True])
    return out


def resolve_wine_columns(df: pd.DataFrame) -> tuple[str | None, str | None]:
    cols = {str(c).strip().lower(): c for c in df.columns}
    id_col = cols.get("id_vinho") or cols.get("wine_id") or cols.get("id") or cols.get("vinho_id")
    name_col = cols.get("nome_vinho") or cols.get("wine_name") or cols.get("vinho") or cols.get("nome")
    return id_col, name_col


def standardize_wines(df: pd.DataFrame) -> pd.DataFrame:
    id_col, name_col = resolve_wine_columns(df)
    if not id_col or not name_col:
        raise ValueError(f"A planilha WINES não possui colunas mínimas esperadas. Colunas recebidas: {list(df.columns)}")
    out = pd.DataFrame()
    out["id_vinho"] = df[id_col].apply(clean_text)
    out["nome_vinho"] = df[name_col].apply(clean_text)
    out = out[(out["id_vinho"] != "") & (out["nome_vinho"] != "")].drop_duplicates(subset=["id_vinho"]).copy()
    return out


def resolve_pairing_columns(df: pd.DataFrame) -> tuple[str | None, str | None, str | None, str | None]:
    cols = {str(c).strip().lower(): c for c in df.columns}
    ids_pratos = cols.get("ids_pratos") or cols.get("id_prato")
    nome_vinho = cols.get("nome_vinho") or cols.get("wine_name")
    id_vinho = cols.get("id_vinho") or cols.get("wine_id")
    motivo = cols.get("motivo_score") or cols.get("por_que_vale") or cols.get("frase_mesa")
    return ids_pratos, id_vinho, nome_vinho, motivo


def standardize_pairings(df: pd.DataFrame) -> pd.DataFrame:
    ids_pratos_col, id_vinho_col, nome_vinho_col, motivo_col = resolve_pairing_columns(df)
    if not ids_pratos_col:
        raise ValueError(f"A planilha PAIRINGS não possui coluna ids_pratos. Colunas recebidas: {list(df.columns)}")
    out = pd.DataFrame()
    out["ids_pratos"] = df[ids_pratos_col].apply(clean_text)
    out["id_vinho"] = df[id_vinho_col].apply(clean_text) if id_vinho_col else ""
    out["nome_vinho"] = df[nome_vinho_col].apply(clean_text) if nome_vinho_col else ""
    out["motivo_score"] = df[motivo_col].apply(clean_text) if motivo_col else ""
    out = out[out["ids_pratos"] != ""].copy()
    return out


def get_pairings_for_dish(pairings: pd.DataFrame, dish_id: str) -> pd.DataFrame:
    df = pairings[pairings["ids_pratos"].apply(lambda x: dish_id in split_ids(x))].copy()
    df = df[df["ids_pratos"].apply(lambda x: len(split_ids(x)) == 1)].copy()
    return df


def render_pairing_cards(df: pd.DataFrame):
    for _, r in df.iterrows():
        st.markdown("<div class='yvora-card'>", unsafe_allow_html=True)
        st.markdown(f"<div class='yvora-card-title'>{clean_text(r.get('nome_vinho', ''))}</div>", unsafe_allow_html=True)
        st.markdown("<div class='yvora-card-sub'></div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                f"""
                <div class="yvora-signal-box">
                  <div class="yvora-signal-label">✨ opção</div>
                  <div class="yvora-signal-value">{score_to_stars('90')}</div>
                  <div class="yvora-signal-sub">Score Match</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                """
                <div class="yvora-signal-box">
                  <div class="yvora-signal-label">Estratégia</div>
                  <div class="yvora-signal-value">harmonização</div>
                  <div class="yvora-signal-sub">Como o vinho entra</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        if clean_text(r.get("motivo_score", "")):
            st.markdown(
                f"<div class='yvora-context'><b>Motivo técnico:</b> {clean_text(r.get('motivo_score', ''))}</div>",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)


def main():
    set_page_style()

    with st.sidebar:
        render_logo(use_container_width=True)
        st.caption("YVORA | Meat & Cheese Lab")

    st.markdown("<div class='yvora-shell'>", unsafe_allow_html=True)

    c1, c2 = st.columns([1, 4], vertical_alignment="center")
    with c1:
        render_logo(width=130)
    with c2:
        st.markdown(
            """
            <div class="yvora-hero">
              <div class="yvora-title">Wine Pairing</div>
              <div class="yvora-subtitle">Escolha até 2 pratos para ver a recomendação de vinho.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    try:
        menu_url = st.secrets["MENU_SHEET_URL"]
        wines_url = st.secrets["WINES_SHEET_URL"]
        pairings_url = st.secrets["PAIRINGS_SHEET_URL"]

        menu = standardize_menu(load_csv_from_url(menu_url, "MENU"))
        wines = standardize_wines(load_csv_from_url(wines_url, "WINES"))
        pairings = standardize_pairings(load_csv_from_url(pairings_url, "PAIRINGS"))
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        st.stop()

    st.markdown("<div class='yvora-section-head'>Escolha seus pratos</div>", unsafe_allow_html=True)

    pratos = menu["nome_prato"].tolist()
    selected = st.selectbox("Escolha o prato", pratos, label_visibility="collapsed")

    if selected:
        row = menu[menu["nome_prato"] == selected].iloc[0]
        dish_id = normalize_id(row["id_prato"])

        st.markdown(
            f"<div class='yvora-section-head'>Melhor por prato • {clean_text(selected)}</div>",
            unsafe_allow_html=True,
        )

        df = get_pairings_for_dish(pairings, dish_id)

        if df.empty:
            st.markdown(
                f"<div class='yvora-warn'><b>{clean_text(selected)}:</b> não existe linha individual correspondente no pairings.</div>",
                unsafe_allow_html=True,
            )
        else:
            df = df.merge(wines, on="id_vinho", how="left", suffixes=("", "_wine"))
            if "nome_vinho_wine" in df.columns:
                df["nome_vinho"] = df["nome_vinho_wine"].where(
                    df["nome_vinho_wine"].astype(str).str.strip() != "",
                    df["nome_vinho"],
                )
            df = df[df["nome_vinho"].astype(str).str.strip() != ""].copy()
            render_pairing_cards(df)

    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
