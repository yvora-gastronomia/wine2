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


def _find_logo_path() -> Path:
    for p in POSSIBLE_LOGOS:
        try:
            if p.exists():
                return p
        except Exception:
            continue
    return POSSIBLE_LOGOS[0]


LOGO_LOCAL_PATH = _find_logo_path()


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
    s = s.replace("+", " + ")
    s = s.replace("|", " | ")
    s = s.replace("/", " ").replace("\\", " ")
    s = s.replace("(", " ").replace(")", " ")
    s = s.replace("[", " ").replace("]", " ")
    s = s.replace("{", " ").replace("}", " ")
    s = s.replace("-", " ")
    s = re.sub(r"[^a-z0-9\s|+]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


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

    if "googleusercontent.com" in u:
        raise ValueError("Use o link original da planilha do Google Sheets, não um link temporário googleusercontent.")

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


@st.cache_data(ttl=3600, show_spinner=False)
def get_asset_bytes(local_path: Path, fallback_url: str = "") -> Optional[bytes]:
    try:
        if local_path.exists():
            return local_path.read_bytes()
    except Exception:
        pass

    fb = norm_text(fallback_url)
    if fb:
        try:
            r = requests.get(fb, timeout=30)
            r.raise_for_status()
            return r.content
        except Exception:
            return None
    return None


@st.cache_data(ttl=60, show_spinner=False)
def load_csv_from_url(url: str, source_name: str = "SHEET") -> pd.DataFrame:
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
                last_error = ValueError(f"[{source_name}] tentativa {idx}: retorno vazio.\nURL: {export_url}")
                continue

            content_type = r.headers.get("Content-Type", "").lower()
            stripped = csv_text.lstrip().lower()

            if "text/html" in content_type or stripped.startswith("<!doctype html") or stripped.startswith("<html"):
                last_error = ValueError(
                    f"[{source_name}] tentativa {idx}: o Google retornou HTML em vez de CSV.\nURL: {export_url}"
                )
                continue

            return pd.read_csv(io.StringIO(csv_text), dtype=str, keep_default_na=False)

        except Exception as e:
            last_error = ValueError(f"[{source_name}] tentativa {idx} falhou.\nURL: {export_url}\nErro: {e}")
            continue

    raise last_error if last_error else ValueError(f"[{source_name}] Falha ao carregar planilha.")


def render_logo(width: Optional[int] = None, use_container_width: bool = False):
    logo_url = _get_secret("LOGO_URL", "")
    b = get_asset_bytes(LOGO_LOCAL_PATH, logo_url)
    if b:
        st.image(b, width=width, use_container_width=use_container_width)
    else:
        st.caption("Logo não encontrada. Inclua em assets/ ou configure LOGO_URL em secrets.")


def sidebar_brand():
    with st.sidebar:
        render_logo(use_container_width=True)
        st.caption("YVORA | Meat & Cheese Lab")


def set_page_style():
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

    h1, h2, h3, h4 {{
        color: {BRAND_BLUE};
        letter-spacing: -0.02em;
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
        letter-spacing: -0.03em;
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

    .yvora-card-sub, .yvora-mini, .yvora-muted {{
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


def split_combo_names(s: str) -> List[str]:
    raw = clean_display_text(s)
    if not raw:
        return []
    parts = re.split(r"\s+\+\s+|\|", raw)
    return [clean_display_text(p) for p in parts if clean_display_text(p)]


def pairings_from_csv(pair_df: pd.DataFrame) -> pd.DataFrame:
    p = pair_df.copy()
    p.columns = [str(c).strip().lower() for c in p.columns]

    needed_defaults = {
        "tipo_pairing": "",
        "nomes_pratos": "",
        "id_vinho": "",
        "nome_vinho": "",
        "tipo_vinho": "",
        "perfil_vinho": "",
        "preco": "",
        "rotulo_valor": "",
        "score_harmonizacao": "",
        "estrategia_harmonizacao": "",
        "papel_do_vinho": "",
        "motivo_score": "",
        "frase_mesa": "",
        "por_que_carne": "",
        "por_que_queijo": "",
        "por_que_combo": "",
        "por_que_vale": "",
        "ordem_recomendacao": "",
        "ativo": "",
    }

    for c, default in needed_defaults.items():
        if c not in p.columns:
            p[c] = default

    for c in p.columns:
        if p[c].dtype == object:
            p[c] = p[c].apply(clean_display_text)

    if "ativo" in p.columns:
        p["ativo_num"] = p["ativo"].apply(lambda x: 1 if norm_text(x).lower() in ["1", "1.0", "true", "sim"] else 0)
    else:
        p["ativo_num"] = 1

    p = p[p["ativo_num"] == 1].copy()

    p["tipo_pairing"] = p["tipo_pairing"].str.lower().str.strip()
    p["nomes_pratos_key"] = p["nomes_pratos"].apply(normalize_for_key)
    p["combo_names_list"] = p["nomes_pratos"].apply(split_combo_names)
    p["combo_names_key"] = p["combo_names_list"].apply(lambda xs: "|".join(sorted([normalize_for_key(x) for x in xs if normalize_for_key(x)])))

    p["score_ord"] = safe_numeric_series(p["score_harmonizacao"]).fillna(0)
    p["ordem_ord"] = safe_numeric_series(p["ordem_recomendacao"]).fillna(999)

    return p


def wines_from_csv(wines_df: pd.DataFrame) -> pd.DataFrame:
    df = wines_df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    def pick(opts: List[str]) -> str:
        for c in opts:
            if c in df.columns:
                return c
        return ""

    c_id = pick(["wine_id", "id_vinho", "id", "vinho_id"])
    c_nome = pick(["wine_name", "nome_vinho", "vinho", "nome"])
    c_type = pick(["tipo", "cor", "estilo", "wine_type", "type", "categoria", "tipo_vinho_padrao"])
    c_profile = pick(["perfil_vinho", "style", "perfil"])
    c_country = pick(["country", "pais"])
    c_region = pick(["region", "regiao"])

    out = pd.DataFrame()
    out["id_vinho"] = df[c_id] if c_id else ""
    out["nome_vinho"] = df[c_nome] if c_nome else ""
    out["tipo_vinho"] = df[c_type] if c_type else ""
    out["perfil_vinho"] = df[c_profile] if c_profile else ""
    out["country"] = df[c_country] if c_country else ""
    out["region"] = df[c_region] if c_region else ""

    for c in out.columns:
        out[c] = out[c].apply(clean_display_text)

    out = out[out["nome_vinho"] != ""].copy()
    return out.drop_duplicates(subset=["id_vinho", "nome_vinho"])


def sort_pairings_subset(p_subset: pd.DataFrame) -> pd.DataFrame:
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

    return p_subset.head(2)


def render_signal_grid(row: Dict, option_label: str):
    stars_n = score_to_stars(row.get("score_harmonizacao", ""))
    stars = render_star_string(stars_n)
    strategy = clean_display_text(row.get("estrategia_harmonizacao", ""))
    role = clean_display_text(row.get("papel_do_vinho", ""))

    c1, c2 = st.columns(2)
    with c1:
        _signal_box(f"✨ {option_label}", stars, "Score Match")
    with c2:
        _signal_box("Estratégia", strategy or "-", "Como o vinho entra")

    c3, _ = st.columns([1, 1])
    with c3:
        _signal_box("Papel do vinho", role or "-", "O que ele faz")


def render_exact_text_block(row: Dict):
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
        colA, colB = st.columns(2)
        with colA:
            st.markdown("**Carne**")
            st.write(por_que_carne or "-")
            st.markdown("**Queijo**")
            st.write(por_que_queijo or "-")
        with colB:
            st.markdown("**Conjunto**")
            st.write(por_que_combo or "-")
            st.markdown("**Valor da escolha**")
            st.write(por_que_vale or "-")


def render_recos_block(
    title: str,
    p_subset: pd.DataFrame,
    wines_meta_map: Dict[str, Dict[str, str]],
):
    st.markdown("<div class='yvora-card'>", unsafe_allow_html=True)
    st.markdown(f"<div class='yvora-card-title'>{title}</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='yvora-card-sub'>Sugestões vindas diretamente da linha correspondente na base.</div>",
        unsafe_allow_html=True,
    )

    p_subset = sort_pairings_subset(p_subset)

    for idx, (_, row_series) in enumerate(p_subset.iterrows()):
        row = row_series.to_dict()

        nome_vinho = clean_display_text(row.get("nome_vinho", ""))
        id_vinho = clean_display_text(row.get("id_vinho", ""))
        option_label = "1ª opção" if idx == 0 else "2ª opção"

        meta = wines_meta_map.get(id_vinho, {})
        wine_type = clean_display_text(row.get("tipo_vinho", "")) or clean_display_text(meta.get("tipo_vinho", ""))
        wine_profile = clean_display_text(row.get("perfil_vinho", "")) or clean_display_text(meta.get("perfil_vinho", ""))
        origem_wine = " • ".join(
            [x for x in [clean_display_text(meta.get("country", "")), clean_display_text(meta.get("region", ""))] if x]
        )

        st.markdown(f"### {nome_vinho}")
        if origem_wine:
            st.markdown(f"<div class='yvora-mini'>{origem_wine}</div>", unsafe_allow_html=True)

        render_signal_grid(row, option_label)

        chips = []
        rotulo = clean_display_text(row.get("rotulo_valor", ""))
        estrategia = clean_display_text(row.get("estrategia_harmonizacao", ""))

        if rotulo:
            chips.append(f"<span class='yvora-chip'>🏷️ {rotulo}</span>")
        if wine_profile:
            chips.append(f"<span class='yvora-chip'>🍇 {wine_profile}</span>")
        if estrategia:
            chips.append(f"<span class='yvora-chip'>✨ {estrategia}</span>")
        if wine_type:
            chips.append(f"<span class='yvora-chip'>🍷 {wine_type}</span>")

        if chips:
            st.markdown("".join(chips), unsafe_allow_html=True)

        render_exact_text_block(row)
        st.divider()

    st.markdown("</div>", unsafe_allow_html=True)


def header_area():
    col1, col2 = st.columns([1, 4], vertical_alignment="center")
    with col1:
        render_logo(width=130)
    with col2:
        st.markdown(
            """
            <div class="yvora-hero">
              <div class="yvora-title">Wine Pairing</div>
              <div class="yvora-subtitle">Escolha até 2 pratos para ver a recomendação de vinho.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_client(pairings: pd.DataFrame, wines: pd.DataFrame):
    st.markdown("<div class='yvora-section-head'>Escolha seus pratos</div>", unsafe_allow_html=True)

    single_dishes = (
        pairings[pairings["tipo_pairing"] == "prato"]["nomes_pratos"]
        .dropna()
        .astype(str)
        .tolist()
    )
    single_dishes = sorted(set([clean_display_text(x) for x in single_dishes if clean_display_text(x)]))

    selected_names = st.multiselect(
        "Selecione 1 ou 2 pratos",
        options=single_dishes,
        max_selections=2,
        placeholder="Digite para buscar no menu",
        key="selected_pratos",
    )

    if len(selected_names) == 0:
        st.info("Selecione ao menos 1 prato para ver as sugestões.")
        return

    wines_meta_map = {}
    if not wines.empty:
        wines_meta_map = {
            clean_display_text(row["id_vinho"]): {
                "tipo_vinho": clean_display_text(row.get("tipo_vinho", "")),
                "perfil_vinho": clean_display_text(row.get("perfil_vinho", "")),
                "country": clean_display_text(row.get("country", "")),
                "region": clean_display_text(row.get("region", "")),
            }
            for _, row in wines.iterrows()
        }

    if len(selected_names) == 1:
        dish = clean_display_text(selected_names[0])
        dish_key = normalize_for_key(dish)

        p_one = pairings[
            (pairings["tipo_pairing"] == "prato") &
            (pairings["nomes_pratos_key"] == dish_key)
        ].copy()

        if p_one.empty:
            st.markdown(
                f"<div class='yvora-warn'><b>{dish}:</b> não existe linha exata no arquivo de pairings.</div>",
                unsafe_allow_html=True,
            )
            return

        render_recos_block(dish, p_one, wines_meta_map)
        return

    if len(selected_names) == 2:
        selected_clean = [clean_display_text(x) for x in selected_names]
        combo_key = "|".join(sorted([normalize_for_key(x) for x in selected_clean]))

        p_combo = pairings[
            (pairings["tipo_pairing"] == "combo") &
            (pairings["combo_names_key"] == combo_key)
        ].copy()

        if p_combo.empty:
            st.markdown(
                "<div class='yvora-warn'><b>Sem recomendação para a combinação agora.</b><br>Não existe linha exata para esta dupla no arquivo de pairings.</div>",
                unsafe_allow_html=True,
            )
        else:
            render_recos_block(" | ".join(selected_clean), p_combo, wines_meta_map)

        st.write("")
        st.markdown("<div class='yvora-section-head'>Melhor por prato</div>", unsafe_allow_html=True)

        for dish in selected_clean:
            dish_key = normalize_for_key(dish)
            p_one = pairings[
                (pairings["tipo_pairing"] == "prato") &
                (pairings["nomes_pratos_key"] == dish_key)
            ].copy()

            if p_one.empty:
                st.markdown(
                    f"<div class='yvora-warn'><b>{dish}:</b> não existe linha exata no arquivo de pairings.</div>",
                    unsafe_allow_html=True,
                )
            else:
                render_recos_block(dish, p_one, wines_meta_map)


def render_dm(pairings: pd.DataFrame):
    st.markdown("<div class='yvora-section-head'>Diagnóstico DM</div>", unsafe_allow_html=True)
    st.write(f"Linhas ativas no pairings: **{len(pairings)}**")

    debug_cols = [
        "tipo_pairing",
        "nomes_pratos",
        "nomes_pratos_key",
        "combo_names_key",
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
        pairings[debug_cols].sort_values(["tipo_pairing", "nomes_pratos", "nome_vinho"], ascending=[True, True, True]),
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


def main():
    set_page_style()
    sidebar_brand()
    dm = dm_login_block()
    st.markdown("<div class='yvora-shell'>", unsafe_allow_html=True)
    header_area()

    try:
        pairings_url = _get_secret("PAIRINGS_SHEET_URL", "")
        wines_url = _get_secret("WINES_SHEET_URL", "")

        if not pairings_url:
            raise ValueError("PAIRINGS_SHEET_URL não configurado.")

        pair_df_raw = load_csv_from_url(pairings_url, "PAIRINGS")
        pairings = pairings_from_csv(pair_df_raw)

        wines = pd.DataFrame()
        if wines_url:
            wines_df_raw = load_csv_from_url(wines_url, "WINES")
            wines = wines_from_csv(wines_df_raw)

    except Exception as e:
        st.markdown(
            f"<div class='yvora-warn'><b>Erro ao carregar dados:</b><br>{e}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    if dm:
        render_dm(pairings)
    else:
        render_client(pairings, wines)

    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
