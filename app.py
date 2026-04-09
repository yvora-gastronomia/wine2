import io
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import pandas as pd
import requests
import streamlit as st


APP_TITLE = "YVORA Wine Pairing"

BRAND_BG = "#EFE7DD"
BRAND_BLUE = "#0E2A47"
BRAND_MUTED = "#6B7785"
BRAND_CARD = "#F5EFE7"
BRAND_WARN = "#F3D6CF"
BRAND_SOFT = "#F8F4EE"
BRAND_WHITE = "#FFFFFF"

BASE_DIR = Path(__file__).resolve().parent
POSSIBLE_LOGOS = [
    BASE_DIR / "yvora_logo.png",
    BASE_DIR / "assets" / "yvora_logo.png",
]
LOGO_LOCAL_PATH = next((p for p in POSSIBLE_LOGOS if p.exists()), POSSIBLE_LOGOS[0])


# =========================================================
# BASICS
# =========================================================
def _get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def norm_text(x) -> str:
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass
    s = str(x)
    s = s.replace("–", "-").replace("•", "-")
    s = unicodedata.normalize("NFC", s)
    return s.strip()


def clean_display_text(s: str) -> str:
    s = norm_text(s)
    if not s:
        return ""
    s = s.replace("_", " ")
    return re.sub(r"\s+", " ", s).strip()


def normalize_for_key(s: str) -> str:
    s = clean_display_text(s).lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = s.replace("'", "").replace('"', "")
    s = s.replace("&", " e ")
    s = s.replace("+", " ")
    s = s.replace("|", " ")
    s = s.replace("/", " ").replace("\\", " ")
    s = s.replace("(", " ").replace(")", " ")
    s = s.replace("[", " ").replace("]", " ")
    s = s.replace("{", " ").replace("}", " ")
    s = s.replace("-", " ")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_id_token(x) -> str:
    s = norm_text(x)
    if not s:
        return ""

    s = s.replace(",", ".")
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


def to_int(x, default: int = 0) -> int:
    s = norm_text(x)
    if not s:
        return default
    try:
        return int(float(s.replace(",", ".")))
    except Exception:
        return default


def to_float(x) -> Optional[float]:
    s = norm_text(x).replace("R$", "").replace(".", "").replace(",", ".").strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def safe_numeric_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str)
        .str.replace(",", ".", regex=False)
        .str.extract(r"(-?\d+(?:\.\d+)?)", expand=False),
        errors="coerce",
    )


# =========================================================
# STYLE
# =========================================================
def set_page_style() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="🍷",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    css = f"""
    <style>
    .stApp {{
        background: linear-gradient(180deg, {BRAND_BG} 0%, #FBF8F3 100%);
    }}

    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, rgba(14,42,71,0.98) 0%, rgba(14,42,71,0.94) 100%);
        border-right: 1px solid rgba(255,255,255,0.08);
    }}

    [data-testid="stSidebar"] * {{
        color: {BRAND_WHITE};
    }}

    .block-container {{
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }}

    .yvora-shell {{
        max-width: 1240px;
        margin: 0 auto;
    }}

    .yvora-hero {{
        background: linear-gradient(135deg, rgba(255,255,255,0.95) 0%, rgba(245,239,231,0.95) 100%);
        border: 1px solid rgba(14,42,71,0.08);
        box-shadow: 0 14px 36px rgba(14,42,71,0.08);
        border-radius: 26px;
        padding: 22px;
        margin-bottom: 18px;
    }}

    .yvora-title {{
        color: {BRAND_BLUE};
        font-size: 2.15rem;
        font-weight: 800;
        margin: 0;
    }}

    .yvora-subtitle {{
        color: {BRAND_MUTED};
        font-size: 1rem;
        line-height: 1.45rem;
        margin-top: 8px;
        max-width: 700px;
    }}

    .yvora-card {{
        background: linear-gradient(180deg, {BRAND_CARD} 0%, {BRAND_SOFT} 100%);
        border-radius: 22px;
        padding: 18px 18px 14px 18px;
        border: 1px solid rgba(14,42,71,0.08);
        margin-bottom: 18px;
        box-shadow: 0 10px 28px rgba(14,42,71,0.05);
    }}

    .yvora-card-title {{
        font-size: 1.28rem;
        font-weight: 800;
        color: {BRAND_BLUE};
        margin-bottom: 4px;
    }}

    .yvora-card-sub, .yvora-mini {{
        color: {BRAND_MUTED};
    }}

    .yvora-card-sub {{
        font-size: 0.93rem;
        margin-bottom: 10px;
    }}

    .yvora-section-head {{
        color: {BRAND_BLUE};
        font-size: 1.02rem;
        font-weight: 800;
        margin: 6px 0 8px 0;
    }}

    .yvora-warn {{
        background: {BRAND_WARN};
        border-radius: 14px;
        padding: 14px 16px;
        border: 1px solid rgba(14,42,71,0.08);
        color: {BRAND_BLUE};
        white-space: pre-wrap;
    }}

    .yvora-chip {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 11px;
        border-radius: 999px;
        border: 1px solid rgba(14,42,71,0.12);
        color: {BRAND_BLUE};
        font-size: 0.82rem;
        font-weight: 600;
        margin-right: 7px;
        margin-top: 6px;
        background: rgba(255,255,255,0.8);
        white-space: nowrap;
    }}

    .yvora-quote {{
        background: rgba(255,255,255,0.86);
        border: 1px solid rgba(14,42,71,0.08);
        border-radius: 16px;
        padding: 14px 15px;
        margin: 14px 0 12px 0;
        color: {BRAND_BLUE};
        font-weight: 700;
        font-size: 1rem;
        line-height: 1.45rem;
    }}

    .yvora-context {{
        background: rgba(255,255,255,0.78);
        border: 1px solid rgba(14,42,71,0.08);
        border-radius: 18px;
        padding: 15px;
        margin: 12px 0;
        color: {BRAND_BLUE};
        font-size: 0.95rem;
        line-height: 1.5rem;
    }}

    .yvora-signal-box {{
        background: rgba(255,255,255,0.78);
        border: 1px solid rgba(14,42,71,0.08);
        border-radius: 16px;
        padding: 12px;
        min-height: 72px;
        height: 100%;
    }}

    .yvora-signal-label {{
        color: {BRAND_MUTED};
        font-size: 0.76rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 4px;
    }}

    .yvora-signal-value {{
        color: {BRAND_BLUE};
        font-size: 1.1rem;
        font-weight: 800;
        line-height: 1.2rem;
    }}

    .yvora-signal-sub {{
        color: {BRAND_MUTED};
        font-size: 0.82rem;
        margin-top: 4px;
        line-height: 1.1rem;
    }}

    .yvora-summary {{
        display: grid;
        grid-template-columns: 1fr;
        gap: 10px;
        margin-top: 12px;
    }}

    .yvora-line {{
        display: flex;
        gap: 10px;
        align-items: flex-start;
        background: rgba(255,255,255,0.8);
        border: 1px solid rgba(14,42,71,0.08);
        padding: 12px 13px;
        border-radius: 16px;
        color: {BRAND_BLUE};
        font-size: 0.95rem;
        line-height: 1.38rem;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# =========================================================
# GOOGLE SHEETS CSV LOADER
# =========================================================
def _decode_csv_bytes(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("cp1252", errors="replace")


def _extract_sheet_id_and_gid(url: str) -> Tuple[str, str]:
    u = norm_text(url).replace("\n", "").strip()
    if not u:
        return "", "0"

    parsed = urlparse(u)
    gid = "0"

    if parsed.fragment:
        frag_qs = parse_qs(parsed.fragment)
        gid = (frag_qs.get("gid", [gid]) or [gid])[0] or gid

    qs = parse_qs(parsed.query)
    if "gid" in qs:
        gid = (qs.get("gid", [gid]) or [gid])[0] or gid

    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", u)
    if m:
        return m.group(1), gid

    return "", gid


def _candidate_sheet_csv_urls(url: str) -> List[str]:
    u = norm_text(url).replace("\n", "").strip()
    if not u:
        raise ValueError("URL vazia.")

    if "docs.google.com/spreadsheets" not in u:
        raise ValueError(f"URL inválida para Google Sheets: {u}")

    sheet_id, gid = _extract_sheet_id_and_gid(u)
    if not sheet_id:
        raise ValueError("Não foi possível identificar o ID da planilha.")

    gid = gid or "0"
    return [
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}",
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}",
    ]


def load_csv_from_url(url: str, source_name: str) -> pd.DataFrame:
    candidate_urls = _candidate_sheet_csv_urls(url)
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/csv,application/csv,text/plain,*/*",
    }

    last_error = None
    for idx, export_url in enumerate(candidate_urls, start=1):
        try:
            r = requests.get(export_url, headers=headers, timeout=30)
            r.raise_for_status()
            csv_text = _decode_csv_bytes(r.content)

            if not csv_text.strip():
                last_error = ValueError(f"[{source_name}] retorno vazio.")
                continue

            content_type = r.headers.get("Content-Type", "").lower()
            stripped = csv_text.lstrip().lower()
            if "text/html" in content_type or stripped.startswith("<!doctype html") or stripped.startswith("<html"):
                last_error = ValueError(f"[{source_name}] Google retornou HTML em vez de CSV.")
                continue

            return pd.read_csv(io.StringIO(csv_text), dtype=str, keep_default_na=False)

        except Exception as e:
            last_error = ValueError(f"[{source_name}] tentativa {idx} falhou: {e}")
            continue

    raise last_error if last_error else ValueError(f"[{source_name}] falha ao carregar planilha.")


# =========================================================
# PARSERS
# =========================================================
def split_ids_tokens(s: str) -> List[str]:
    raw = norm_text(s)
    if not raw:
        return []
    parts = re.split(r"[|,;/]+", raw)
    vals = [normalize_id_token(p) for p in parts]
    return [v for v in vals if v]


def split_name_tokens(s: str) -> List[str]:
    raw = clean_display_text(s)
    if not raw:
        return []
    if "|" in raw:
        parts = raw.split("|")
    elif re.search(r"\s\+\s", raw):
        parts = re.split(r"\s\+\s", raw)
    elif ";" in raw:
        parts = raw.split(";")
    else:
        parts = [raw]
    return [clean_display_text(p) for p in parts if clean_display_text(p)]


def make_ids_key(values: List[str]) -> str:
    vals = [normalize_id_token(v) for v in values if normalize_id_token(v)]
    vals = sorted(set(vals))
    return "|".join(vals)


def make_names_key(values: List[str]) -> str:
    vals = [normalize_for_key(v) for v in values if normalize_for_key(v)]
    vals = sorted(set(vals))
    return "|".join(vals)


def standardize_menu(menu_df: pd.DataFrame) -> pd.DataFrame:
    df = menu_df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    def pick(opts: List[str]) -> str:
        for c in opts:
            if c in df.columns:
                return c
        return ""

    c_id = pick(["id_prato", "id", "prato_id"])
    c_nome = pick(["nome_prato", "prato", "nome", "title"])
    c_desc = pick(["descricao_prato", "descricao", "descrição", "desc"])
    c_ativo = pick(["ativo", "active", "status"])

    out = pd.DataFrame()
    out["id_prato"] = df[c_id] if c_id else ""
    out["nome_prato"] = df[c_nome] if c_nome else ""
    out["descricao_prato"] = df[c_desc] if c_desc else ""
    out["ativo"] = df[c_ativo] if c_ativo else "1"

    out["id_prato"] = out["id_prato"].apply(normalize_id_token)
    out["nome_prato"] = out["nome_prato"].apply(clean_display_text)
    out["descricao_prato"] = out["descricao_prato"].apply(clean_display_text)

    raw_ativo = out["ativo"].astype(str).str.strip().str.lower()
    valid_ativo = raw_ativo.isin(["1", "1.0", "true", "sim", "0", "0.0", "false", "nao", "não"])
    if valid_ativo.any():
        out["ativo_num"] = raw_ativo.isin(["1", "1.0", "true", "sim"]).astype(int)
    else:
        out["ativo_num"] = 1

    missing = out["id_prato"].eq("")
    out.loc[missing, "id_prato"] = out.loc[missing, "nome_prato"]

    out = out[(out["nome_prato"] != "") & (out["ativo_num"] == 1)].copy()
    out["nome_prato_key"] = out["nome_prato"].apply(normalize_for_key)
    return out.drop_duplicates(subset=["id_prato", "nome_prato"])


def _normalize_wine_type(raw: str) -> str:
    t = norm_text(raw).lower()
    if not t:
        return ""
    if "espum" in t or "spark" in t or "champ" in t:
        return "Espumante"
    if "rose" in t or "rosé" in t:
        return "Rosé"
    if "branco" in t or "white" in t:
        return "Branco"
    if "tinto" in t or "red" in t:
        return "Tinto"
    return clean_display_text(raw.title())


def standardize_wines(wines_df: pd.DataFrame) -> pd.DataFrame:
    df = wines_df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    def pick(opts: List[str]) -> str:
        for c in opts:
            if c in df.columns:
                return c
        return ""

    c_id = pick(["wine_id", "id_vinho", "id", "vinho_id"])
    c_nome = pick(["wine_name", "nome_vinho", "vinho", "nome"])
    c_price = pick(["price", "preco", "preço", "valor"])
    c_stock = pick(["estoque", "stock", "qtd", "quantidade"])
    c_active = pick(["active", "ativo", "status"])
    c_type = pick(["tipo", "cor", "estilo", "wine_type", "type", "categoria", "tipo_vinho_padrao"])
    c_profile = pick(["perfil_vinho", "style", "perfil"])
    c_country = pick(["country", "pais"])
    c_region = pick(["region", "regiao"])

    out = pd.DataFrame()
    out["id_vinho"] = df[c_id] if c_id else ""
    out["nome_vinho"] = df[c_nome] if c_nome else ""
    out["preco_num"] = df[c_price].apply(to_float) if c_price else None
    out["estoque"] = df[c_stock].apply(lambda x: to_int(x, 0)) if c_stock else 0
    out["ativo"] = df[c_active] if c_active else "1"
    out["tipo_vinho"] = df[c_type] if c_type else ""
    out["perfil_vinho"] = df[c_profile] if c_profile else ""
    out["region"] = df[c_region] if c_region else ""
    out["country"] = df[c_country] if c_country else ""

    out["id_vinho"] = out["id_vinho"].apply(norm_text)
    out["nome_vinho"] = out["nome_vinho"].apply(clean_display_text)
    out["tipo_vinho"] = out["tipo_vinho"].apply(_normalize_wine_type)
    out["perfil_vinho"] = out["perfil_vinho"].apply(clean_display_text)
    out["region"] = out["region"].apply(clean_display_text)
    out["country"] = out["country"].apply(clean_display_text)

    raw_ativo = out["ativo"].astype(str).str.strip().str.lower()
    valid_ativo = raw_ativo.isin(["1", "1.0", "true", "sim", "0", "0.0", "false", "nao", "não"])
    if valid_ativo.any():
        out["ativo_num"] = raw_ativo.isin(["1", "1.0", "true", "sim"]).astype(int)
    else:
        out["ativo_num"] = 1

    missing = out["id_vinho"].eq("")
    out.loc[missing, "id_vinho"] = out.loc[missing, "nome_vinho"]

    return out[out["nome_vinho"] != ""].drop_duplicates(subset=["id_vinho", "nome_vinho"])


def standardize_pairings(pair_df: pd.DataFrame) -> pd.DataFrame:
    p = pair_df.copy()
    p.columns = [str(c).strip().lower() for c in p.columns]

    defaults = {
        "tipo_pairing": "",
        "ids_pratos": "",
        "nomes_pratos": "",
        "id_vinho": "",
        "nome_vinho": "",
        "ativo": "",
        "score_harmonizacao": "",
        "ordem_recomendacao": "",
        "tipo_vinho": "",
        "perfil_vinho": "",
        "rotulo_valor": "",
        "estrategia_harmonizacao": "",
        "papel_do_vinho": "",
        "motivo_score": "",
        "frase_mesa": "",
        "por_que_carne": "",
        "por_que_queijo": "",
        "por_que_combo": "",
        "por_que_vale": "",
    }
    for c, default in defaults.items():
        if c not in p.columns:
            p[c] = default

    raw_ativo = p["ativo"].astype(str).str.strip().str.lower()
    valid_ativo = raw_ativo.isin(["1", "1.0", "true", "sim", "0", "0.0", "false", "nao", "não"])
    if valid_ativo.any():
        p["ativo_num"] = raw_ativo.isin(["1", "1.0", "true", "sim"]).astype(int)
        if (p["ativo_num"] == 1).any():
            p = p[p["ativo_num"] == 1].copy()
    else:
        p["ativo_num"] = 1

    p["ids_list"] = p["ids_pratos"].apply(split_ids_tokens)
    p["ids_key"] = p["ids_list"].apply(make_ids_key)

    p["names_list"] = p["nomes_pratos"].apply(split_name_tokens)
    p["names_key"] = p["names_list"].apply(make_names_key)

    p["dish_count"] = p["ids_list"].apply(len)
    p.loc[p["dish_count"] == 0, "dish_count"] = p["names_list"].apply(len)

    p["score_ord"] = safe_numeric_series(p["score_harmonizacao"]).fillna(0)
    p["ordem_ord"] = safe_numeric_series(p["ordem_recomendacao"]).fillna(999)

    for c in p.columns:
        if p[c].dtype == object:
            p[c] = p[c].apply(clean_display_text)

    return p


# =========================================================
# MATCH
# =========================================================
def get_pairings_for_single(pairings: pd.DataFrame, prato_id: str, prato_nome: str) -> pd.DataFrame:
    target_id_key = make_ids_key([prato_id])
    target_name_key = make_names_key([prato_nome])

    by_id = pairings[
        (pairings["dish_count"] == 1) &
        (pairings["ids_key"] == target_id_key)
    ].copy()
    if not by_id.empty:
        return by_id

    by_name = pairings[
        (pairings["dish_count"] == 1) &
        (pairings["names_key"] == target_name_key)
    ].copy()
    return by_name


def get_pairings_for_combo(pairings: pd.DataFrame, prato_ids: List[str], prato_nomes: List[str]) -> pd.DataFrame:
    target_ids_key = make_ids_key(prato_ids)
    target_names_key = make_names_key(prato_nomes)
    target_count = len([x for x in prato_ids if normalize_id_token(x)]) or len(prato_nomes)

    by_id = pairings[
        (pairings["dish_count"] == target_count) &
        (pairings["ids_key"] == target_ids_key)
    ].copy()
    if not by_id.empty:
        return by_id

    by_name = pairings[
        (pairings["dish_count"] == target_count) &
        (pairings["names_key"] == target_names_key)
    ].copy()
    return by_name


def filter_to_available_wines(pairings_subset: pd.DataFrame, wines: pd.DataFrame) -> pd.DataFrame:
    if pairings_subset.empty:
        return pairings_subset.copy()

    available_ids = set(
        wines[
            (wines["ativo_num"] == 1) &
            (wines["estoque"] > 0)
        ]["id_vinho"].astype(str).tolist()
    )

    if not available_ids and len(wines) > 0:
        return pairings_subset.copy()

    return pairings_subset[pairings_subset["id_vinho"].isin(available_ids)].copy()


# =========================================================
# RENDER
# =========================================================
def score_to_stars(score_raw: str) -> int:
    score = to_int(score_raw, 0)
    if score >= 90:
        return 5
    if score >= 80:
        return 4
    if score >= 70:
        return 3
    if score >= 60:
        return 2
    return 1


def render_star_string(n: int) -> str:
    n = max(1, min(5, n))
    return "★" * n + "☆" * (5 - n)


def _signal_box(label: str, value: str, sub: str) -> None:
    st.markdown(
        f"""
        <div class="yvora-signal-box">
          <div class="yvora-signal-label">{label}</div>
          <div class="yvora-signal-value">{value}</div>
          <div class="yvora-signal-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_signal_grid_and_tags(row: Dict, option_label: str, wines_meta_map: Dict[str, Dict[str, str]]) -> None:
    stars_n = score_to_stars(row.get("score_harmonizacao", ""))
    stars = render_star_string(stars_n)
    strategy = clean_display_text(row.get("estrategia_harmonizacao", ""))
    role = clean_display_text(row.get("papel_do_vinho", ""))
    id_vinho = clean_display_text(row.get("id_vinho", ""))
    meta = wines_meta_map.get(id_vinho, {})
    wine_type = clean_display_text(row.get("tipo_vinho", "")) or clean_display_text(meta.get("tipo_vinho", ""))
    wine_profile = clean_display_text(row.get("perfil_vinho", "")) or clean_display_text(meta.get("perfil_vinho", ""))

    c1, c2 = st.columns(2)
    with c1:
        _signal_box(f"✨ {option_label}", stars, "Score Match")
    with c2:
        _signal_box("Estratégia", strategy or "-", "Como o vinho entra")

    c3, _ = st.columns([1, 1])
    with c3:
        _signal_box("Papel do vinho", role or "-", "O que ele faz")

    chips = []
    rotulo = clean_display_text(row.get("rotulo_valor", ""))
    if rotulo:
        chips.append(f"<span class='yvora-chip'>🏷️ {rotulo}</span>")
    if wine_profile:
        chips.append(f"<span class='yvora-chip'>🍇 {wine_profile}</span>")
    if strategy:
        chips.append(f"<span class='yvora-chip'>✨ {strategy}</span>")
    if wine_type:
        chips.append(f"<span class='yvora-chip'>🍷 {wine_type}</span>")

    if chips:
        st.markdown("".join(chips), unsafe_allow_html=True)


def render_exact_text_block(row: Dict) -> None:
    frase_mesa = clean_display_text(row.get("frase_mesa", ""))
    por_que_carne = clean_display_text(row.get("por_que_carne", ""))
    por_que_queijo = clean_display_text(row.get("por_que_queijo", ""))
    por_que_combo = clean_display_text(row.get("por_que_combo", ""))
    por_que_vale = clean_display_text(row.get("por_que_vale", ""))
    motivo_score = clean_display_text(row.get("motivo_score", ""))

    if frase_mesa:
        st.markdown(f"<div class='yvora-quote'>💬 {frase_mesa}</div>", unsafe_allow_html=True)
    if motivo_score:
        st.markdown(f"<div class='yvora-context'><b>Motivo técnico:</b> {motivo_score}</div>", unsafe_allow_html=True)
    if por_que_carne or por_que_queijo or por_que_combo:
        st.markdown(
            f"""
            <div class="yvora-summary">
              <div class="yvora-line">🥩 <span>{por_que_carne or "-"}</span></div>
              <div class="yvora-line">🧀 <span>{por_que_queijo or "-"}</span></div>
              <div class="yvora-line">🧠 <span>{por_que_combo or "-"}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander("Ver leitura completa"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Carne**")
            st.write(por_que_carne or "-")
            st.markdown("**Queijo**")
            st.write(por_que_queijo or "-")
        with c2:
            st.markdown("**Conjunto**")
            st.write(por_que_combo or "-")
            st.markdown("**Valor da escolha**")
            st.write(por_que_vale or "-")


def render_recos_block(title: str, p_subset: pd.DataFrame, wines_meta_map: Dict[str, Dict[str, str]]) -> None:
    st.markdown("<div class='yvora-card'>", unsafe_allow_html=True)
    st.markdown(f"<div class='yvora-card-title'>{title}</div>", unsafe_allow_html=True)
    st.markdown("<div class='yvora-card-sub'>Sugestões vindas diretamente da linha correspondente na base.</div>", unsafe_allow_html=True)

    p_subset = p_subset.copy()
    has_explicit_order = (p_subset["ordem_ord"] < 999).any()

    if has_explicit_order:
        p_subset = p_subset.sort_values(
            ["ordem_ord", "score_ord", "nome_vinho"],
            ascending=[True, False, True],
            kind="mergesort",
        )
    else:
        p_subset = p_subset.sort_values(
            ["score_ord", "nome_vinho"],
            ascending=[False, True],
            kind="mergesort",
        )

    p_subset = p_subset.head(2)

    for idx, (_, row_series) in enumerate(p_subset.iterrows()):
        row = row_series.to_dict()
        nome_vinho = clean_display_text(row.get("nome_vinho", ""))
        id_vinho = clean_display_text(row.get("id_vinho", ""))
        meta = wines_meta_map.get(id_vinho, {})
        origem_wine = " • ".join(
            [x for x in [clean_display_text(meta.get("country", "")), clean_display_text(meta.get("region", ""))] if x]
        )

        st.markdown(f"### {nome_vinho}")
        if origem_wine:
            st.markdown(f"<div class='yvora-mini'>{origem_wine}</div>", unsafe_allow_html=True)

        render_signal_grid_and_tags(row, "1ª opção" if idx == 0 else "2ª opção", wines_meta_map)
        render_exact_text_block(row)
        st.divider()

    st.markdown("</div>", unsafe_allow_html=True)


def header_area() -> None:
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


# =========================================================
# UI LOGIC
# =========================================================
def render_client(menu: pd.DataFrame, wines: pd.DataFrame, pairings: pd.DataFrame) -> None:
    st.markdown("<div class='yvora-section-head'>Escolha seus pratos</div>", unsafe_allow_html=True)

    selected_names = st.multiselect(
        "Selecione 1 ou 2 pratos",
        options=menu["nome_prato"].tolist(),
        max_selections=2,
        placeholder="Digite para buscar no menu",
        key="selected_pratos",
    )

    if len(selected_names) == 0:
        st.info("Selecione ao menos 1 prato para ver as sugestões.")
        return

    selected = menu[menu["nome_prato"].isin(selected_names)].copy()

    if selected.empty:
        st.markdown(
            "<div class='yvora-warn'><b>Nenhum prato válido foi encontrado no MENU.</b></div>",
            unsafe_allow_html=True,
        )
        return

    selected_ids = selected["id_prato"].tolist()
    selected_titles = selected["nome_prato"].tolist()

    wines_meta_map = {
        norm_text(row["id_vinho"]): {
            "tipo_vinho": clean_display_text(row.get("tipo_vinho", "")),
            "perfil_vinho": clean_display_text(row.get("perfil_vinho", "")),
            "country": clean_display_text(row.get("country", "")),
            "region": clean_display_text(row.get("region", "")),
        }
        for _, row in wines.iterrows()
    }

    if len(selected_ids) == 2:
        pair_rows = get_pairings_for_combo(pairings, selected_ids, selected_titles)
        pair_rows_available = filter_to_available_wines(pair_rows, wines)
        combo_title = " | ".join(selected_titles)

        if pair_rows.empty:
            st.markdown(
                "<div class='yvora-warn'><b>Sem recomendação para a combinação agora.</b><br>Não existe linha exata para esta dupla.</div>",
                unsafe_allow_html=True,
            )
        elif pair_rows_available.empty:
            st.markdown(
                "<div class='yvora-warn'><b>A combinação existe na base, mas os vinhos recomendados não estão disponíveis agora.</b></div>",
                unsafe_allow_html=True,
            )
        else:
            render_recos_block(combo_title, pair_rows_available, wines_meta_map)

        st.write("")

    st.markdown("<div class='yvora-section-head'>Melhor por prato</div>", unsafe_allow_html=True)

    for pid, prato_nome in zip(selected_ids, selected_titles):
        pair_rows = get_pairings_for_single(pairings, pid, prato_nome)
        pair_rows_available = filter_to_available_wines(pair_rows, wines)

        if pair_rows.empty:
            st.markdown(
                f"<div class='yvora-warn'><b>{prato_nome}:</b> não existe linha individual exata no arquivo de pairings.</div>",
                unsafe_allow_html=True,
            )
            continue

        if pair_rows_available.empty:
            st.markdown(
                f"<div class='yvora-warn'><b>{prato_nome}:</b> há recomendação na base, mas os vinhos sugeridos não estão disponíveis agora.</div>",
                unsafe_allow_html=True,
            )
            continue

        render_recos_block(prato_nome, pair_rows_available, wines_meta_map)


def render_dm(menu: pd.DataFrame, wines: pd.DataFrame, pairings: pd.DataFrame) -> None:
    st.markdown("<div class='yvora-section-head'>Diagnóstico DM</div>", unsafe_allow_html=True)

    st.write(f"Linhas MENU: **{len(menu)}**")
    st.write(f"Linhas WINES: **{len(wines)}**")
    st.write(f"Linhas PAIRINGS ativas: **{len(pairings)}**")

    pratos_menu = sorted(set(menu["nome_prato"].dropna().astype(str).map(clean_display_text).tolist()))
    st.write(f"Pratos do MENU: **{len(pratos_menu)}**")
    st.write(pratos_menu[:50])

    selected_from_ui = st.session_state.get("selected_pratos", [])
    if selected_from_ui:
        st.markdown("### Verificação do prato selecionado")
        selected = menu[menu["nome_prato"].isin(selected_from_ui)].copy()
        for _, row in selected.iterrows():
            prato_id = row["id_prato"]
            prato_nome = row["nome_prato"]
            target_ids_key = make_ids_key([prato_id])
            target_names_key = make_names_key([prato_nome])

            by_id = pairings[
                (pairings["dish_count"] == 1) &
                (pairings["ids_key"] == target_ids_key)
            ].copy()

            by_name = pairings[
                (pairings["dish_count"] == 1) &
                (pairings["names_key"] == target_names_key)
            ].copy()

            st.write(
                {
                    "prato_nome": prato_nome,
                    "id_prato": prato_id,
                    "target_ids_key": target_ids_key,
                    "target_names_key": target_names_key,
                    "matches_por_id": len(by_id),
                    "matches_por_nome": len(by_name),
                }
            )

            if not by_id.empty:
                st.dataframe(
                    by_id[["tipo_pairing", "ids_pratos", "ids_key", "nomes_pratos", "names_key", "id_vinho", "nome_vinho"]],
                    use_container_width=True,
                )
            elif not by_name.empty:
                st.dataframe(
                    by_name[["tipo_pairing", "ids_pratos", "ids_key", "nomes_pratos", "names_key", "id_vinho", "nome_vinho"]],
                    use_container_width=True,
                )

    debug_cols = [
        "tipo_pairing",
        "ids_pratos",
        "ids_key",
        "nomes_pratos",
        "names_key",
        "dish_count",
        "id_vinho",
        "nome_vinho",
        "ordem_recomendacao",
        "score_harmonizacao",
        "ativo_num",
    ]
    for c in debug_cols:
        if c not in pairings.columns:
            pairings[c] = ""

    st.dataframe(
        pairings[debug_cols].sort_values(["nomes_pratos", "nome_vinho"], ascending=[True, True]),
        use_container_width=True,
    )


def dm_login_block() -> bool:
    admin_password = _get_secret("ADMIN_PASSWORD", "")
    if "dm" not in st.session_state:
        st.session_state.dm = False

    with st.sidebar:
        st.markdown("### Acesso DM")
        if st.session_state.dm:
            st.success("Modo DM ativo")
            if st.button("Sair do DM", use_container_width=True):
                st.session_state.dm = False
                st.rerun()
        else:
            pwd = st.text_input("Senha", type="password", placeholder="Digite a senha do DM")
            if st.button("Entrar", use_container_width=True):
                if pwd and admin_password and pwd == admin_password:
                    st.session_state.dm = True
                    st.rerun()
                else:
                    st.error("Senha inválida.")
    return bool(st.session_state.dm)


# =========================================================
# MAIN
# =========================================================
def main() -> None:
    set_page_style()
    sidebar_brand()
    dm = dm_login_block()

    st.markdown("<div class='yvora-shell'>", unsafe_allow_html=True)
    header_area()

    try:
        menu_url = _get_secret("MENU_SHEET_URL", "")
        wines_url = _get_secret("WINES_SHEET_URL", "")
        pairings_url = _get_secret("PAIRINGS_SHEET_URL", "")

        if not menu_url:
            raise ValueError("MENU_SHEET_URL não configurado.")
        if not wines_url:
            raise ValueError("WINES_SHEET_URL não configurado.")
        if not pairings_url:
            raise ValueError("PAIRINGS_SHEET_URL não configurado.")

        menu_df = load_csv_from_url(menu_url, "MENU")
        wines_df = load_csv_from_url(wines_url, "WINES")
        pair_df = load_csv_from_url(pairings_url, "PAIRINGS")

        menu = standardize_menu(menu_df)
        wines = standardize_wines(wines_df)
        pairings = standardize_pairings(pair_df)

    except Exception as e:
        st.markdown(
            f"<div class='yvora-warn'><b>Erro ao carregar dados:</b><br>{e}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    if dm:
        render_dm(menu, wines, pairings)
    else:
        render_client(menu, wines, pairings)

    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()