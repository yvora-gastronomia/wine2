import io
import re
import unicodedata
from pathlib import Path
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


def get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def norm_text(x) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass
    return str(x).strip()


def clean_text(x) -> str:
    return re.sub(r"\s+", " ", norm_text(x)).strip()


def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def normalize_name(x) -> str:
    s = clean_text(x).lower()
    s = strip_accents(s)
    s = s.replace("–", "-").replace("—", "-")
    s = s.replace("&", " e ")
    s = s.replace("/", " ")
    s = s.replace("\\", " ")
    s = s.replace("(", " ")
    s = s.replace(")", " ")
    s = s.replace("[", " ")
    s = s.replace("]", " ")
    s = s.replace("{", " ")
    s = s.replace("}", " ")
    s = s.replace("-", " ")
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


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
    parts = re.split(r"[|,;/+]+", raw)
    vals = [normalize_id(p) for p in parts]
    return [v for v in vals if v]


def score_to_stars(score_raw: str) -> str:
    try:
        score = int(float(norm_text(score_raw)))
    except Exception:
        score = 0

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


def build_prato_label(nome_prato: str) -> str:
    return clean_text(nome_prato)


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
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/csv,application/csv,text/plain,*/*",
    }
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


def standardize_menu(df: pd.DataFrame) -> pd.DataFrame:
    raw = df.copy()
    raw.columns = [str(c).strip() for c in raw.columns]

    c_id = next((c for c in raw.columns if str(c).strip().lower() in ["id", "id_prato", "prato_id"]), None)
    c_name = next((c for c in raw.columns if str(c).strip().lower() in ["prato", "nome_prato", "nome", "title"]), None)
    c_desc = next((c for c in raw.columns if str(c).strip().lower() in ["descrição", "descricao", "descricao_prato", "desc"]), None)
    c_active = next((c for c in raw.columns if str(c).strip().lower() in ["ativo", "active", "status"]), None)

    if not c_name:
        raise ValueError(f"MENU sem coluna de nome identificável. Colunas: {list(raw.columns)}")

    out = pd.DataFrame()
    out["id_prato"] = raw[c_id] if c_id else ""
    out["nome_prato"] = raw[c_name]
    out["descricao_prato"] = raw[c_desc] if c_desc else ""
    out["ativo"] = raw[c_active] if c_active else "1"

    out["id_prato"] = out["id_prato"].apply(normalize_id)
    out["nome_prato"] = out["nome_prato"].apply(clean_text)
    out["descricao_prato"] = out["descricao_prato"].apply(clean_text)
    out["ativo_num"] = out["ativo"].apply(
        lambda x: 1 if norm_text(x).lower() in ["", "1", "1.0", "true", "sim"] else 0
    )

    missing = out["id_prato"].eq("")
    out.loc[missing, "id_prato"] = out.loc[missing, "nome_prato"]

    out = out[(out["nome_prato"] != "") & (out["ativo_num"] == 1)].copy()
    out["nome_key"] = out["nome_prato"].apply(normalize_name)
    out["prato_label"] = out["nome_prato"].apply(build_prato_label)

    return out.drop_duplicates(subset=["id_prato", "nome_prato"])


def standardize_wines(df: pd.DataFrame) -> pd.DataFrame:
    raw = df.copy()
    raw.columns = [str(c).strip() for c in raw.columns]

    c_id = next((c for c in raw.columns if str(c).strip().lower() in ["wine_id", "id_vinho", "id", "vinho_id"]), None)
    c_name = next((c for c in raw.columns if str(c).strip().lower() in ["nome", "nome_vinho", "wine_name", "vinho"]), None)
    c_price = next((c for c in raw.columns if str(c).strip().lower() in ["preco", "preço", "price", "valor"]), None)
    c_stock = next((c for c in raw.columns if str(c).strip().lower() in ["estoque", "stock", "qtd", "quantidade"]), None)
    c_active = next((c for c in raw.columns if str(c).strip().lower() in ["ativo", "active", "status"]), None)
    c_type = next((c for c in raw.columns if str(c).strip().lower() in ["tipo_vinho_padrao", "tipo", "wine_type", "type", "categoria"]), None)
    c_profile = next((c for c in raw.columns if str(c).strip().lower() in ["perfil_aromatico_curto", "perfil_vinho", "perfil"]), None)
    c_region = next((c for c in raw.columns if str(c).strip().lower() in ["region", "regiao"]), None)

    if not c_id or not c_name:
        raise ValueError(f"WINES sem colunas mínimas. Colunas: {list(raw.columns)}")

    out = pd.DataFrame()
    out["id_vinho"] = raw[c_id]
    out["nome_vinho"] = raw[c_name]
    out["preco"] = raw[c_price] if c_price else ""
    out["estoque"] = raw[c_stock] if c_stock else "0"
    out["ativo"] = raw[c_active] if c_active else "1"
    out["tipo_vinho"] = raw[c_type] if c_type else ""
    out["perfil_vinho"] = raw[c_profile] if c_profile else ""
    out["region"] = raw[c_region] if c_region else ""
    out["country"] = ""

    out["id_vinho"] = out["id_vinho"].apply(clean_text)
    out["nome_vinho"] = out["nome_vinho"].apply(clean_text)
    out["preco"] = out["preco"].apply(clean_text)
    out["estoque_num"] = pd.to_numeric(out["estoque"], errors="coerce").fillna(0)
    out["ativo_num"] = out["ativo"].apply(
        lambda x: 1 if norm_text(x).lower() in ["", "1", "1.0", "true", "sim"] else 0
    )
    out["tipo_vinho"] = out["tipo_vinho"].apply(clean_text)
    out["perfil_vinho"] = out["perfil_vinho"].apply(clean_text)
    out["country"] = out["country"].apply(clean_text)
    out["region"] = out["region"].apply(clean_text)

    return out[out["nome_vinho"] != ""].drop_duplicates(subset=["id_vinho", "nome_vinho"])


def standardize_pairings(df: pd.DataFrame) -> pd.DataFrame:
    raw = df.copy()
    raw.columns = [str(c).strip().lower() for c in raw.columns]

    defaults = {
        "chave_pratos": "",
        "ids_pratos": "",
        "nomes_pratos": "",
        "id_vinho": "",
        "nome_vinho": "",
        "preco": "",
        "score_harmonizacao": "",
        "estrategia_harmonizacao": "",
        "papel_do_vinho": "",
        "motivo_score": "",
        "origem": "",
        "ativo": "1",
    }
    for c, d in defaults.items():
        if c not in raw.columns:
            raw[c] = d

    out = raw.copy()
    out["ids_pratos"] = out["ids_pratos"].apply(clean_text)
    out["nomes_pratos"] = out["nomes_pratos"].apply(clean_text)
    out["id_vinho"] = out["id_vinho"].apply(clean_text)
    out["nome_vinho"] = out["nome_vinho"].apply(clean_text)
    out["score_ord"] = pd.to_numeric(out["score_harmonizacao"], errors="coerce").fillna(0)
    out["ativo_num"] = out["ativo"].apply(
        lambda x: 1 if norm_text(x).lower() in ["", "1", "1.0", "true", "sim"] else 0
    )

    out["ids_list"] = out["ids_pratos"].apply(split_ids)
    out["dish_count"] = out["ids_list"].apply(len)

    out = out[(out["id_vinho"] != "") & (out["ativo_num"] == 1)].copy()
    return out


def filter_available(pairings_subset: pd.DataFrame, wines: pd.DataFrame) -> pd.DataFrame:
    if pairings_subset.empty:
        return pairings_subset.copy()

    available_ids = set(
        wines[
            (wines["ativo_num"] == 1) &
            (wines["estoque_num"] > 0)
        ]["id_vinho"].astype(str).tolist()
    )

    return pairings_subset[pairings_subset["id_vinho"].isin(available_ids)].copy()


def get_single_pairings(pairings: pd.DataFrame, prato_id: str) -> pd.DataFrame:
    pid = normalize_id(prato_id)
    if not pid:
        return pairings.iloc[0:0].copy()

    rows = pairings[
        (pairings["dish_count"] == 1) &
        (pairings["ids_list"].apply(lambda xs: pid in xs))
    ].copy()

    return rows


def get_combo_pairings(pairings: pd.DataFrame, prato_ids: list[str]) -> pd.DataFrame:
    wanted_ids = sorted(set(normalize_id(x) for x in prato_ids if normalize_id(x)))
    if len(wanted_ids) != 2:
        return pairings.iloc[0:0].copy()

    rows = pairings[
        (pairings["dish_count"] == 2) &
        (pairings["ids_list"].apply(lambda xs: sorted(set(xs)) == wanted_ids))
    ].copy()

    return rows


def enrich_pairings_with_wines(pairings_subset: pd.DataFrame, wines: pd.DataFrame) -> pd.DataFrame:
    if pairings_subset.empty:
        return pairings_subset.copy()

    merged = pairings_subset.merge(
        wines[["id_vinho", "nome_vinho", "tipo_vinho", "perfil_vinho", "country", "region", "preco"]],
        on="id_vinho",
        how="left",
        suffixes=("", "_wine"),
    )

    if "nome_vinho_wine" in merged.columns:
        merged["nome_vinho"] = merged["nome_vinho_wine"].where(
            merged["nome_vinho_wine"].astype(str).str.strip() != "",
            merged["nome_vinho"],
        )
    if "tipo_vinho_wine" in merged.columns:
        merged["tipo_vinho"] = merged["tipo_vinho_wine"].where(
            merged["tipo_vinho_wine"].astype(str).str.strip() != "",
            merged["tipo_vinho"],
        )
    if "perfil_vinho_wine" in merged.columns:
        merged["perfil_vinho"] = merged["perfil_vinho_wine"].where(
            merged["perfil_vinho_wine"].astype(str).str.strip() != "",
            merged["perfil_vinho"],
        )
    if "preco_wine" in merged.columns:
        merged["preco"] = merged["preco_wine"].where(
            merged["preco_wine"].astype(str).str.strip() != "",
            merged["preco"],
        )

    return merged


def render_logo(width: int | None = None, use_container_width: bool = False):
    logo_url = get_secret("LOGO_URL", "")
    try:
        if LOGO_LOCAL_PATH.exists():
            st.image(str(LOGO_LOCAL_PATH), width=width, use_container_width=use_container_width)
            return
    except Exception:
        pass

    if logo_url:
        try:
            r = requests.get(logo_url, timeout=20)
            r.raise_for_status()
            st.image(r.content, width=width, use_container_width=use_container_width)
            return
        except Exception:
            pass

    st.markdown("<div style='height:140px'></div>", unsafe_allow_html=True)


def render_sidebar():
    with st.sidebar:
        render_logo(use_container_width=True)
        st.caption("YVORA | Meat & Cheese Lab")


def render_header():
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


def render_pairing_block(title: str, df: pd.DataFrame, wines_meta: dict) -> None:
    st.markdown(f"<div class='yvora-section-head'>{title}</div>", unsafe_allow_html=True)

    df = df.copy().sort_values(["score_ord", "nome_vinho"], ascending=[False, True]).head(2)

    for i, (_, row) in enumerate(df.iterrows(), start=1):
        row = row.to_dict()
        meta = wines_meta.get(row.get("id_vinho", ""), {})

        st.markdown("<div class='yvora-card'>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='yvora-card-title'>{clean_text(row.get('nome_vinho', ''))}</div>",
            unsafe_allow_html=True,
        )

        origem = " • ".join([x for x in [meta.get("country", ""), meta.get("region", "")] if clean_text(x)])
        st.markdown(f"<div class='yvora-card-sub'>{origem}</div>" if origem else "<div class='yvora-card-sub'></div>", unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                f"""
                <div class="yvora-signal-box">
                  <div class="yvora-signal-label">✨ {i}ª opção</div>
                  <div class="yvora-signal-value">{score_to_stars(row.get('score_harmonizacao', ''))}</div>
                  <div class="yvora-signal-sub">Score Match</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f"""
                <div class="yvora-signal-box">
                  <div class="yvora-signal-label">Estratégia</div>
                  <div class="yvora-signal-value">{clean_text(row.get('estrategia_harmonizacao', '')) or '-'}</div>
                  <div class="yvora-signal-sub">Como o vinho entra</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.write("")

        st.markdown(
            f"""
            <div class="yvora-signal-box">
              <div class="yvora-signal-label">Papel do vinho</div>
              <div class="yvora-signal-value">{clean_text(row.get('papel_do_vinho', '')) or '-'}</div>
              <div class="yvora-signal-sub">O que ele faz</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if clean_text(row.get("motivo_score", "")):
            st.markdown(
                f"<div class='yvora-context'><b>Motivo técnico:</b> {clean_text(row.get('motivo_score', ''))}</div>",
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)


def render_client(menu: pd.DataFrame, wines: pd.DataFrame, pairings: pd.DataFrame) -> None:
    st.markdown("<div class='yvora-section-head'>Escolha seus pratos</div>", unsafe_allow_html=True)

    menu_options = menu[["prato_label", "id_prato", "nome_prato"]].drop_duplicates(subset=["prato_label"]).copy()
    label_to_row = {
        row["prato_label"]: {"id_prato": row["id_prato"], "nome_prato": row["nome_prato"]}
        for _, row in menu_options.iterrows()
    }

    selected_labels = st.multiselect(
        "Escolha seus pratos",
        options=menu_options["prato_label"].tolist(),
        max_selections=2,
        placeholder="Digite para buscar no menu",
        key="selected_pratos_labels",
        label_visibility="collapsed",
    )

    if not selected_labels:
        return

    selected_ids = []
    selected_titles = []

    for label in selected_labels:
        row = label_to_row.get(label)
        if row:
            selected_ids.append(row["id_prato"])
            selected_titles.append(row["nome_prato"])

    wines_meta = {
        str(row["id_vinho"]): {
            "tipo_vinho": clean_text(row.get("tipo_vinho", "")),
            "perfil_vinho": clean_text(row.get("perfil_vinho", "")),
            "country": clean_text(row.get("country", "")),
            "region": clean_text(row.get("region", "")),
        }
        for _, row in wines.iterrows()
    }

    if len(selected_ids) == 2:
        combo_rows = get_combo_pairings(pairings, selected_ids)
        combo_rows = filter_available(combo_rows, wines)
        combo_rows = enrich_pairings_with_wines(combo_rows, wines)

        if combo_rows.empty:
            st.markdown(
                "<div class='yvora-warn'><b>Sem recomendação para a combinação agora.</b><br>Não existe linha correspondente no pairings.</div>",
                unsafe_allow_html=True,
            )
        else:
            render_pairing_block("Sugestão para a combinação", combo_rows, wines_meta)

        st.write("")

    for pid, pname in zip(selected_ids, selected_titles):
        single_rows = get_single_pairings(pairings, pid)
        single_rows = filter_available(single_rows, wines)
        single_rows = enrich_pairings_with_wines(single_rows, wines)

        if single_rows.empty:
            st.markdown(
                f"<div class='yvora-warn'><b>{pname}:</b> não existe linha individual correspondente no pairings.</div>",
                unsafe_allow_html=True,
            )
        else:
            render_pairing_block(f"Melhor por prato • {pname}", single_rows, wines_meta)


def main() -> None:
    set_page_style()
    render_sidebar()
    render_header()

    try:
        menu_url = get_secret("MENU_SHEET_URL", "")
        wines_url = get_secret("WINES_SHEET_URL", "")
        pairings_url = get_secret("PAIRINGS_SHEET_URL", "")

        if not menu_url:
            raise ValueError("MENU_SHEET_URL não configurado.")
        if not wines_url:
            raise ValueError("WINES_SHEET_URL não configurado.")
        if not pairings_url:
            raise ValueError("PAIRINGS_SHEET_URL não configurado.")

        menu_raw = load_csv_from_url(menu_url, "MENU")
        wines_raw = load_csv_from_url(wines_url, "WINES")
        pairings_raw = load_csv_from_url(pairings_url, "PAIRINGS")

        menu = standardize_menu(menu_raw)
        wines = standardize_wines(wines_raw)
        pairings = standardize_pairings(pairings_raw)

    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        st.stop()

    render_client(menu, wines, pairings)

    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
