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

BASE_DIR = Path(__file__).resolve().parent
POSSIBLE_LOGOS = [BASE_DIR / "yvora_logo.png", BASE_DIR / "assets" / "yvora_logo.png"]
LOGO_LOCAL_PATH = next((p for p in POSSIBLE_LOGOS if p.exists()), POSSIBLE_LOGOS[0])


def set_page_style() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="🍷",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(
        f"""
        <style>
        .stApp {{ background: linear-gradient(180deg, {BRAND_BG} 0%, #FBF8F3 100%); }}
        [data-testid="stSidebar"] {{ display: none; }}
        [data-testid="collapsedControl"] {{ display: none; }}
        .block-container {{ padding-top: 1.2rem; padding-bottom: 2rem; }}
        .yvora-shell {{ max-width: 1240px; margin: 0 auto; }}
        .yvora-hero {{ background: linear-gradient(135deg, rgba(255,255,255,0.95) 0%, rgba(245,239,231,0.95) 100%); border: 1px solid rgba(14,42,71,0.08); box-shadow: 0 14px 36px rgba(14,42,71,0.08); border-radius: 26px; padding: 22px; margin-bottom: 18px; }}
        .yvora-title {{ color: {BRAND_BLUE}; font-size: 2.15rem; font-weight: 800; margin: 0; }}
        .yvora-subtitle {{ color: {BRAND_MUTED}; font-size: 1rem; line-height: 1.45rem; margin-top: 8px; max-width: 700px; }}
        .yvora-card {{ background: linear-gradient(180deg, {BRAND_CARD} 0%, {BRAND_SOFT} 100%); border-radius: 22px; padding: 18px; border: 1px solid rgba(14,42,71,0.08); margin-bottom: 18px; box-shadow: 0 10px 28px rgba(14,42,71,0.05); }}
        .yvora-card-title {{ font-size: 1.28rem; font-weight: 800; color: {BRAND_BLUE}; margin-bottom: 4px; }}
        .yvora-card-sub, .yvora-mini {{ color: {BRAND_MUTED}; }}
        .yvora-card-sub {{ font-size: 0.93rem; margin-bottom: 10px; }}
        .yvora-section-head {{ color: {BRAND_BLUE}; font-size: 1.02rem; font-weight: 800; margin: 6px 0 8px 0; }}
        .yvora-warn {{ background: {BRAND_WARN}; border-radius: 14px; padding: 14px 16px; border: 1px solid rgba(14,42,71,0.08); color: {BRAND_BLUE}; white-space: pre-wrap; }}
        .yvora-chip {{ display: inline-flex; align-items: center; gap: 6px; padding: 6px 11px; border-radius: 999px; border: 1px solid rgba(14,42,71,0.12); color: {BRAND_BLUE}; font-size: 0.82rem; font-weight: 600; margin-right: 7px; margin-top: 6px; background: rgba(255,255,255,0.8); white-space: nowrap; }}
        .yvora-context {{ background: rgba(255,255,255,0.78); border: 1px solid rgba(14,42,71,0.08); border-radius: 18px; padding: 15px; margin: 12px 0; color: {BRAND_BLUE}; font-size: 0.95rem; line-height: 1.5rem; }}
        .yvora-signal-box {{ background: rgba(255,255,255,0.78); border: 1px solid rgba(14,42,71,0.08); border-radius: 16px; padding: 12px; min-height: 72px; height: 100%; }}
        .yvora-signal-label {{ color: {BRAND_MUTED}; font-size: 0.76rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 4px; }}
        .yvora-signal-value {{ color: {BRAND_BLUE}; font-size: 1.1rem; font-weight: 800; line-height: 1.2rem; }}
        .yvora-signal-sub {{ color: {BRAND_MUTED}; font-size: 0.82rem; margin-top: 4px; line-height: 1.1rem; }}
        .yvora-summary {{ display: grid; grid-template-columns: 1fr; gap: 10px; margin-top: 12px; }}
        .yvora-line {{ display: flex; gap: 10px; align-items: flex-start; background: rgba(255,255,255,0.8); border: 1px solid rgba(14,42,71,0.08); padding: 12px 13px; border-radius: 16px; color: {BRAND_BLUE}; font-size: 0.95rem; line-height: 1.38rem; }}
        .sensorial-card {{ background: rgba(255,255,255,0.86); border: 1px solid rgba(14,42,71,0.08); border-radius: 16px; padding: 14px 15px; margin: 14px 0 12px 0; color: {BRAND_BLUE}; }}
        .sensorial-block {{ margin-bottom: 13px; }}
        .sensorial-block:last-child {{ margin-bottom: 0; }}
        .sensorial-title {{ font-weight: 800; color: {BRAND_BLUE}; font-size: 1rem; margin-bottom: 3px; }}
        .sensorial-text {{ color: {BRAND_BLUE}; font-size: 0.98rem; line-height: 1.42rem; font-weight: 600; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


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
    s = strip_accents(clean_text(x).lower())
    for old, new in [("&", " e "), ("/", " "), ("\\", " "), ("-", " ")]:
        s = s.replace(old, new)
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


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
    return [v for v in [normalize_id(p) for p in re.split(r"[|,;/]+", norm_text(x))] if v]


def split_names(x) -> list[str]:
    raw = clean_text(x)
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
    return [normalize_name(p) for p in parts if normalize_name(p)]


def make_ids_key(values: list[str]) -> str:
    return "|".join(sorted(set(normalize_id(v) for v in values if normalize_id(v))))


def make_names_key(values: list[str]) -> str:
    return "|".join(sorted(set(normalize_name(v) for v in values if normalize_name(v))))


def tokenize_name(x: str) -> set[str]:
    return set(t for t in normalize_name(x).split() if len(t) >= 3)


def names_match_flexible(target_name: str, row_name: str, threshold: float = 0.75) -> bool:
    a, b = normalize_name(target_name), normalize_name(row_name)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    sa, sb = tokenize_name(a), tokenize_name(b)
    if not sa or not sb:
        return False
    return len(sa & sb) / max(1, min(len(sa), len(sb))) >= threshold


def to_int(x, default: int = 0) -> int:
    try:
        return int(float(norm_text(x).replace(",", ".")))
    except Exception:
        return default


def score_to_stars(score_raw: str) -> str:
    score = to_int(score_raw, 0)
    n = 5 if score >= 90 else 4 if score >= 80 else 3 if score >= 70 else 2 if score >= 60 else 1
    return "★" * n + "☆" * (5 - n)


def format_frase_mesa(frase: str) -> str:
    texto = clean_text(frase)
    if not texto:
        return ""
    texto = texto.replace("👁 Visual:", "<div class='sensorial-block'><div class='sensorial-title'>👁 Visual</div><div class='sensorial-text'>")
    texto = texto.replace("👃 Intuição aromática:", "</div></div><div class='sensorial-block'><div class='sensorial-title'>👃 Intuição aromática</div><div class='sensorial-text'>")
    texto = texto.replace("🍽 Experiência:", "</div></div><div class='sensorial-block'><div class='sensorial-title'>🍽 Experiência</div><div class='sensorial-text'>")
    return f"<div class='sensorial-card'>{texto}</div></div></div>"


def extract_sheet_id_and_gid(url: str) -> tuple[str, str]:
    parsed = urlparse(norm_text(url))
    gid = "0"
    if parsed.fragment:
        gid = (parse_qs(parsed.fragment).get("gid", [gid]) or [gid])[0] or gid
    gid = (parse_qs(parsed.query).get("gid", [gid]) or [gid])[0] or gid
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", norm_text(url))
    return (m.group(1), gid) if m else ("", gid)


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


def pick_col(df: pd.DataFrame, options: list[str]) -> str:
    cols = [str(c).strip().lower() for c in df.columns]
    return next((opt for opt in options if opt in cols), "")


def standardize_menu(df: pd.DataFrame) -> pd.DataFrame:
    raw = df.copy()
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    c_id = pick_col(raw, ["id_prato", "id", "prato_id"])
    c_name = pick_col(raw, ["nome_prato", "prato", "nome", "title"])
    c_desc = pick_col(raw, ["descricao_prato", "descricao", "descrição", "desc"])
    c_active = pick_col(raw, ["ativo", "active", "status"])
    out = pd.DataFrame()
    out["id_prato"] = raw[c_id] if c_id else ""
    out["nome_prato"] = raw[c_name] if c_name else ""
    out["descricao_prato"] = raw[c_desc] if c_desc else ""
    out["ativo"] = raw[c_active] if c_active else "1"
    out["id_prato"] = out["id_prato"].apply(normalize_id)
    out["nome_prato"] = out["nome_prato"].apply(clean_text)
    out["descricao_prato"] = out["descricao_prato"].apply(clean_text)
    out["ativo_num"] = out["ativo"].apply(lambda x: 1 if norm_text(x).lower() in ["", "1", "1.0", "true", "sim"] else 0)
    out.loc[out["id_prato"].eq(""), "id_prato"] = out.loc[out["id_prato"].eq(""), "nome_prato"]
    out = out[(out["nome_prato"] != "") & (out["ativo_num"] == 1)].copy()
    out["nome_key"] = out["nome_prato"].apply(normalize_name)
    return out.drop_duplicates(subset=["id_prato", "nome_prato"])


def standardize_wines(df: pd.DataFrame) -> pd.DataFrame:
    raw = df.copy()
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    c_id = pick_col(raw, ["wine_id", "id_vinho", "id", "vinho_id"])
    c_name = pick_col(raw, ["wine_name", "nome_vinho", "vinho", "nome"])
    c_price = pick_col(raw, ["price", "preco", "preço", "valor"])
    c_stock = pick_col(raw, ["estoque", "stock", "qtd", "quantidade"])
    c_active = pick_col(raw, ["active", "ativo", "status"])
    c_type = pick_col(raw, ["tipo", "cor", "estilo", "wine_type", "type", "categoria"])
    c_profile = pick_col(raw, ["perfil_vinho", "style", "perfil"])
    c_country = pick_col(raw, ["country", "pais"])
    c_region = pick_col(raw, ["region", "regiao"])
    out = pd.DataFrame()
    out["id_vinho"] = raw[c_id] if c_id else ""
    out["nome_vinho"] = raw[c_name] if c_name else ""
    out["preco"] = raw[c_price] if c_price else ""
    out["estoque"] = raw[c_stock] if c_stock else "0"
    out["ativo"] = raw[c_active] if c_active else "1"
    out["tipo_vinho"] = raw[c_type] if c_type else ""
    out["perfil_vinho"] = raw[c_profile] if c_profile else ""
    out["country"] = raw[c_country] if c_country else ""
    out["region"] = raw[c_region] if c_region else ""
    for col in ["id_vinho", "nome_vinho", "preco", "tipo_vinho", "perfil_vinho", "country", "region"]:
        out[col] = out[col].apply(clean_text)
    out["estoque_num"] = out["estoque"].apply(to_int)
    out["ativo_num"] = out["ativo"].apply(lambda x: 1 if norm_text(x).lower() in ["", "1", "1.0", "true", "sim"] else 0)
    out.loc[out["id_vinho"].eq(""), "id_vinho"] = out.loc[out["id_vinho"].eq(""), "nome_vinho"]
    return out[out["nome_vinho"] != ""].drop_duplicates(subset=["id_vinho", "nome_vinho"])


def standardize_pairings(df: pd.DataFrame) -> pd.DataFrame:
    raw = df.copy()
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    for c in ["tipo_pairing", "ids_pratos", "nomes_pratos", "id_vinho", "nome_vinho", "ativo", "score_harmonizacao", "ordem_recomendacao", "tipo_vinho", "perfil_vinho", "rotulo_valor", "estrategia_harmonizacao", "papel_do_vinho", "motivo_score", "frase_mesa", "por_que_carne", "por_que_queijo", "por_que_combo", "por_que_vale"]:
        if c not in raw.columns:
            raw[c] = ""
    out = raw.copy()
    out["ativo_num"] = out["ativo"].apply(lambda x: 1 if norm_text(x).lower() in ["", "1", "1.0", "true", "sim"] else 0)
    out = out[out["ativo_num"] == 1].copy()
    out["ids_list"] = out["ids_pratos"].apply(split_ids)
    out["ids_key"] = out["ids_list"].apply(make_ids_key)
    out["names_list"] = out["nomes_pratos"].apply(split_names)
    out["names_key"] = out["names_list"].apply(make_names_key)
    out["dish_count"] = out["ids_list"].apply(len)
    out.loc[out["dish_count"] == 0, "dish_count"] = out["names_list"].apply(len)
    out["score_ord"] = pd.to_numeric(out["score_harmonizacao"], errors="coerce").fillna(0)
    out["ordem_ord"] = pd.to_numeric(out["ordem_recomendacao"], errors="coerce").fillna(999)
    for c in out.columns:
        if out[c].dtype == object:
            out[c] = out[c].apply(clean_text)
    return out


def filter_available(pairings_subset: pd.DataFrame, wines: pd.DataFrame) -> pd.DataFrame:
    if pairings_subset.empty:
        return pairings_subset.copy()
    available_ids = set(wines[(wines["ativo_num"] == 1) & (wines["estoque_num"] > 0)]["id_vinho"].astype(str).tolist())
    if not available_ids:
        return pairings_subset.copy()
    return pairings_subset[pairings_subset["id_vinho"].isin(available_ids)].copy()


def get_single_pairings(pairings: pd.DataFrame, prato_id: str, prato_nome: str) -> pd.DataFrame:
    id_key = make_ids_key([prato_id])
    name_key = make_names_key([prato_nome])
    by_id = pairings[(pairings["dish_count"] == 1) & (pairings["ids_key"] == id_key)].copy()
    if not by_id.empty:
        return by_id
    by_name = pairings[(pairings["dish_count"] == 1) & (pairings["names_key"] == name_key)].copy()
    if not by_name.empty:
        return by_name
    candidates = pairings[pairings["dish_count"] == 1].copy()
    if candidates.empty:
        return candidates
    return candidates[candidates["nomes_pratos"].apply(lambda x: names_match_flexible(prato_nome, x))].copy()


def combo_names_match_flexible(target_names: list[str], row_names_raw: str) -> bool:
    row_parts = split_names(row_names_raw)
    target_norm = [normalize_name(x) for x in target_names if normalize_name(x)]
    used = set()
    for target in target_norm:
        found = False
        for i, row_part in enumerate(row_parts):
            if i not in used and names_match_flexible(target, row_part):
                used.add(i)
                found = True
                break
        if not found:
            return False
    return bool(target_norm) and len(used) == len(target_norm)


def get_combo_pairings(pairings: pd.DataFrame, prato_ids: list[str], prato_nomes: list[str]) -> pd.DataFrame:
    id_key = make_ids_key(prato_ids)
    name_key = make_names_key(prato_nomes)
    target_count = len([x for x in prato_ids if normalize_id(x)]) or len(prato_nomes)
    by_id = pairings[(pairings["dish_count"] == target_count) & (pairings["ids_key"] == id_key)].copy()
    if not by_id.empty:
        return by_id
    by_name = pairings[(pairings["dish_count"] == target_count) & (pairings["names_key"] == name_key)].copy()
    if not by_name.empty:
        return by_name
    candidates = pairings[pairings["dish_count"] == target_count].copy()
    if candidates.empty:
        return candidates
    return candidates[candidates["nomes_pratos"].apply(lambda x: combo_names_match_flexible(prato_nomes, x))].copy()


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
    st.caption("Logo não encontrada.")


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
    df = df.copy()
    if (df["ordem_ord"] < 999).any():
        df = df.sort_values(["ordem_ord", "score_ord", "nome_vinho"], ascending=[True, False, True])
    else:
        df = df.sort_values(["score_ord", "nome_vinho"], ascending=[False, True])
    for i, (_, row) in enumerate(df.head(2).iterrows(), start=1):
        row = row.to_dict()
        meta = wines_meta.get(row.get("id_vinho", ""), {})
        origem = " • ".join([x for x in [meta.get("country", ""), meta.get("region", "")] if clean_text(x)])
        st.markdown("<div class='yvora-card'>", unsafe_allow_html=True)
        st.markdown(f"<div class='yvora-card-title'>{clean_text(row.get('nome_vinho', ''))}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='yvora-card-sub'>{origem}</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"<div class='yvora-signal-box'><div class='yvora-signal-label'>✨ {i}ª opção</div><div class='yvora-signal-value'>{score_to_stars(row.get('score_harmonizacao', ''))}</div><div class='yvora-signal-sub'>Score Match</div></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='yvora-signal-box'><div class='yvora-signal-label'>Estratégia</div><div class='yvora-signal-value'>{clean_text(row.get('estrategia_harmonizacao', '')) or '-'}</div><div class='yvora-signal-sub'>Como o vinho entra</div></div>", unsafe_allow_html=True)
        st.write("")
        st.markdown(f"<div class='yvora-signal-box'><div class='yvora-signal-label'>Papel do vinho</div><div class='yvora-signal-value'>{clean_text(row.get('papel_do_vinho', '')) or '-'}</div><div class='yvora-signal-sub'>O que ele faz</div></div>", unsafe_allow_html=True)
        chips = []
        for icon, key in [("🏷️", "rotulo_valor"), ("🍇", "perfil_vinho"), ("✨", "estrategia_harmonizacao")]:
            if clean_text(row.get(key, "")):
                chips.append(f"<span class='yvora-chip'>{icon} {clean_text(row.get(key, ''))}</span>")
        tipo_meta = clean_text(meta.get("tipo_vinho", "")) or clean_text(row.get("tipo_vinho", ""))
        if tipo_meta:
            chips.append(f"<span class='yvora-chip'>🍷 {tipo_meta}</span>")
        if chips:
            st.markdown("".join(chips), unsafe_allow_html=True)
        if clean_text(row.get("frase_mesa", "")):
            st.markdown(format_frase_mesa(row.get("frase_mesa", "")), unsafe_allow_html=True)
        if clean_text(row.get("motivo_score", "")):
            st.markdown(f"<div class='yvora-context'><b>Motivo técnico:</b> {clean_text(row.get('motivo_score', ''))}</div>", unsafe_allow_html=True)
        if clean_text(row.get("por_que_carne", "")) or clean_text(row.get("por_que_queijo", "")) or clean_text(row.get("por_que_combo", "")):
            st.markdown(f"<div class='yvora-summary'><div class='yvora-line'>🥩 <span>{clean_text(row.get('por_que_carne', '')) or '-'}</span></div><div class='yvora-line'>🧀 <span>{clean_text(row.get('por_que_queijo', '')) or '-'}</span></div><div class='yvora-line'>🧠 <span>{clean_text(row.get('por_que_combo', '')) or '-'}</span></div></div>", unsafe_allow_html=True)
        if clean_text(row.get("por_que_vale", "")):
            with st.expander("Ver leitura completa"):
                st.markdown("**Valor da escolha**")
                st.write(clean_text(row.get("por_que_vale", "")))
        st.markdown("</div>", unsafe_allow_html=True)


def render_client(menu: pd.DataFrame, wines: pd.DataFrame, pairings: pd.DataFrame) -> None:
    st.markdown("<div class='yvora-section-head'>Escolha seus pratos</div>", unsafe_allow_html=True)
    selected_names = st.multiselect(
        "Escolha seus pratos",
        options=menu["nome_prato"].tolist(),
        max_selections=2,
        placeholder="Digite para buscar no menu",
        key="selected_pratos",
        label_visibility="collapsed",
    )
    if not selected_names:
        return
    selected = menu[menu["nome_prato"].isin(selected_names)].copy()
    selected_ids = selected["id_prato"].tolist()
    selected_titles = selected["nome_prato"].tolist()
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
        combo_rows = filter_available(get_combo_pairings(pairings, selected_ids, selected_titles), wines)
        if combo_rows.empty:
            st.markdown("<div class='yvora-warn'><b>Sem recomendação para a combinação agora.</b><br>Não existe linha correspondente no pairings.</div>", unsafe_allow_html=True)
        else:
            render_pairing_block("Sugestão para a combinação", combo_rows, wines_meta)
        st.write("")
    for pid, pname in zip(selected_ids, selected_titles):
        single_rows = filter_available(get_single_pairings(pairings, pid, pname), wines)
        if single_rows.empty:
            st.markdown(f"<div class='yvora-warn'><b>{pname}:</b> não existe linha individual correspondente no pairings.</div>", unsafe_allow_html=True)
        else:
            render_pairing_block(f"Melhor por prato • {pname}", single_rows, wines_meta)


def main() -> None:
    set_page_style()
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
        menu = standardize_menu(load_csv_from_url(menu_url, "MENU"))
        wines = standardize_wines(load_csv_from_url(wines_url, "WINES"))
        pairings = standardize_pairings(load_csv_from_url(pairings_url, "PAIRINGS"))
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        st.stop()
    render_client(menu, wines, pairings)
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
