import io
import re
from urllib.parse import parse_qs, urlparse

import pandas as pd
import requests
import streamlit as st


APP_TITLE = "YVORA Wine Pairing"


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


def normalize_name(x) -> str:
    s = clean_text(x).lower()
    s = s.replace("–", "-").replace("—", "-")
    s = s.replace("&", " e ")
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
    parts = re.split(r"[|,;/]+", raw)
    vals = [normalize_id(p) for p in parts]
    return [v for v in vals if v]


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
    vals = [normalize_name(p) for p in parts]
    return [v for v in vals if v]


def make_ids_key(values: list[str]) -> str:
    vals = sorted(set(normalize_id(v) for v in values if normalize_id(v)))
    return "|".join(vals)


def make_names_key(values: list[str]) -> str:
    vals = sorted(set(normalize_name(v) for v in values if normalize_name(v)))
    return "|".join(vals)


def to_int(x, default: int = 0) -> int:
    s = norm_text(x)
    if not s:
        return default
    try:
        return int(float(s.replace(",", ".")))
    except Exception:
        return default


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


def pick_col(df: pd.DataFrame, options: list[str]) -> str:
    cols = [str(c).strip().lower() for c in df.columns]
    for opt in options:
        if opt in cols:
            return opt
    return ""


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
    out["ativo_num"] = out["ativo"].apply(lambda x: 1 if norm_text(x).lower() in ["1", "1.0", "true", "sim"] else 0)

    missing = out["id_prato"].eq("")
    out.loc[missing, "id_prato"] = out.loc[missing, "nome_prato"]

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
    c_type = pick_col(raw, ["tipo", "cor", "estilo", "wine_type", "type", "categoria", "tipo_vinho_padrao"])
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

    out["id_vinho"] = out["id_vinho"].apply(clean_text)
    out["nome_vinho"] = out["nome_vinho"].apply(clean_text)
    out["preco"] = out["preco"].apply(clean_text)
    out["estoque_num"] = out["estoque"].apply(to_int)
    out["ativo_num"] = out["ativo"].apply(lambda x: 1 if norm_text(x).lower() in ["1", "1.0", "true", "sim"] else 0)
    out["tipo_vinho"] = out["tipo_vinho"].apply(clean_text)
    out["perfil_vinho"] = out["perfil_vinho"].apply(clean_text)
    out["country"] = out["country"].apply(clean_text)
    out["region"] = out["region"].apply(clean_text)

    missing = out["id_vinho"].eq("")
    out.loc[missing, "id_vinho"] = out.loc[missing, "nome_vinho"]

    return out[out["nome_vinho"] != ""].drop_duplicates(subset=["id_vinho", "nome_vinho"])


def standardize_pairings(df: pd.DataFrame) -> pd.DataFrame:
    raw = df.copy()
    raw.columns = [str(c).strip().lower() for c in raw.columns]

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
    for c, d in defaults.items():
        if c not in raw.columns:
            raw[c] = d

    out = raw.copy()
    out["ativo_num"] = out["ativo"].apply(lambda x: 1 if norm_text(x).lower() in ["", "1", "1.0", "true", "sim"] else 0)
    out = out[out["ativo_num"] == 1].copy()

    out["ids_list"] = out["ids_pratos"].apply(split_ids_tokens)
    out["ids_key"] = out["ids_list"].apply(make_ids_key)

    out["names_list"] = out["nomes_pratos"].apply(split_name_tokens)
    out["names_key"] = out["names_list"].apply(make_names_key)

    out["dish_count"] = out["ids_list"].apply(len)
    out.loc[out["dish_count"] == 0, "dish_count"] = out["names_list"].apply(len)

    out["score_ord"] = safe_numeric_series(out["score_harmonizacao"]).fillna(0)
    out["ordem_ord"] = safe_numeric_series(out["ordem_recomendacao"]).fillna(999)

    for c in out.columns:
        if out[c].dtype == object:
            out[c] = out[c].apply(clean_text)

    return out


def get_single_pairings(pairings: pd.DataFrame, prato_id: str, prato_nome: str) -> pd.DataFrame:
    id_key = make_ids_key([prato_id])
    name_key = make_names_key([prato_nome])

    by_id = pairings[(pairings["dish_count"] == 1) & (pairings["ids_key"] == id_key)].copy()
    if not by_id.empty:
        return by_id

    by_name = pairings[(pairings["dish_count"] == 1) & (pairings["names_key"] == name_key)].copy()
    return by_name


def get_combo_pairings(pairings: pd.DataFrame, prato_ids: list[str], prato_nomes: list[str]) -> pd.DataFrame:
    id_key = make_ids_key(prato_ids)
    name_key = make_names_key(prato_nomes)
    target_count = len([x for x in prato_ids if normalize_id(x)]) or len(prato_nomes)

    by_id = pairings[(pairings["dish_count"] == target_count) & (pairings["ids_key"] == id_key)].copy()
    if not by_id.empty:
        return by_id

    by_name = pairings[(pairings["dish_count"] == target_count) & (pairings["names_key"] == name_key)].copy()
    return by_name


def filter_available(pairings_subset: pd.DataFrame, wines: pd.DataFrame) -> pd.DataFrame:
    if pairings_subset.empty:
        return pairings_subset.copy()

    available_ids = set(
        wines[(wines["ativo_num"] == 1) & (wines["estoque_num"] > 0)]["id_vinho"].astype(str).tolist()
    )

    if not available_ids:
        return pairings_subset.copy()

    return pairings_subset[pairings_subset["id_vinho"].isin(available_ids)].copy()


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


def render_logo() -> None:
    logo_url = get_secret("LOGO_URL", "")
    try:
        if LOGO_LOCAL_PATH.exists():
            st.sidebar.image(str(LOGO_LOCAL_PATH), use_container_width=True)
            return
    except Exception:
        pass

    if logo_url:
        try:
            r = requests.get(logo_url, timeout=20)
            r.raise_for_status()
            st.sidebar.image(r.content, use_container_width=True)
            return
        except Exception:
            pass


def render_sidebar(dm_on: bool) -> None:
    render_logo()
    st.sidebar.caption("YVORA | Meat & Cheese Lab")
    st.sidebar.markdown("### Acesso DM")

    if dm_on:
        st.sidebar.success("Modo DM ativo")
        if st.sidebar.button("Sair do DM", use_container_width=True):
            st.session_state.dm = False
            st.rerun()
    else:
        pwd = st.sidebar.text_input("Senha", type="password", placeholder="Digite a senha do DM")
        if st.sidebar.button("Entrar", use_container_width=True):
            admin_password = get_secret("ADMIN_PASSWORD", "")
            if pwd and admin_password and pwd == admin_password:
                st.session_state.dm = True
                st.rerun()
            else:
                st.sidebar.error("Senha inválida.")


def render_header() -> None:
    st.title("Wine Pairing")
    st.caption("Escolha até 2 pratos para ver a recomendação de vinho.")


def render_pairing_cards(title: str, df: pd.DataFrame, wines_meta: Dict[str, Dict[str, str]]) -> None:
    st.subheader(title)

    df = df.copy()
    has_order = (df["ordem_ord"] < 999).any()

    if has_order:
        df = df.sort_values(["ordem_ord", "score_ord", "nome_vinho"], ascending=[True, False, True])
    else:
        df = df.sort_values(["score_ord", "nome_vinho"], ascending=[False, True])

    df = df.head(2)

    for i, (_, row) in enumerate(df.iterrows(), start=1):
        row = row.to_dict()
        meta = wines_meta.get(row.get("id_vinho", ""), {})
        with st.container(border=True):
            st.markdown(f"**{i}ª opção • {clean_text(row.get('nome_vinho', ''))}**")
            origem = " • ".join([x for x in [meta.get("country", ""), meta.get("region", "")] if clean_text(x)])
            if origem:
                st.caption(origem)

            c1, c2, c3 = st.columns(3)
            c1.metric("Score", score_to_stars(row.get("score_harmonizacao", "")))
            c2.write("**Estratégia**")
            c2.write(clean_text(row.get("estrategia_harmonizacao", "")) or "-")
            c3.write("**Papel do vinho**")
            c3.write(clean_text(row.get("papel_do_vinho", "")) or "-")

            if clean_text(row.get("frase_mesa", "")):
                st.info(clean_text(row.get("frase_mesa", "")))

            if clean_text(row.get("motivo_score", "")):
                st.write("**Motivo técnico**")
                st.write(clean_text(row.get("motivo_score", "")))

            c4, c5, c6 = st.columns(3)
            c4.write("**Carne**")
            c4.write(clean_text(row.get("por_que_carne", "")) or "-")
            c5.write("**Queijo**")
            c5.write(clean_text(row.get("por_que_queijo", "")) or "-")
            c6.write("**Conjunto**")
            c6.write(clean_text(row.get("por_que_combo", "")) or "-")

            if clean_text(row.get("por_que_vale", "")):
                st.write("**Valor da escolha**")
                st.write(clean_text(row.get("por_que_vale", "")))


def render_client(menu: pd.DataFrame, wines: pd.DataFrame, pairings: pd.DataFrame) -> None:
    selected_names = st.multiselect(
        "Escolha seus pratos",
        options=menu["nome_prato"].tolist(),
        max_selections=2,
        placeholder="Digite para buscar no menu",
        key="selected_pratos",
    )

    if not selected_names:
        st.info("Selecione ao menos 1 prato.")
        return

    selected = menu[menu["nome_prato"].isin(selected_names)].copy()
    if selected.empty:
        st.warning("Nenhum prato válido encontrado no MENU.")
        return

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
        combo_rows = get_combo_pairings(pairings, selected_ids, selected_titles)
        combo_rows = filter_available(combo_rows, wines)

        if combo_rows.empty:
            st.warning("Não existe recomendação exata para esta dupla.")
        else:
            render_pairing_cards("Sugestão para a combinação", combo_rows, wines_meta)

        st.write("")

    for pid, pname in zip(selected_ids, selected_titles):
        single_rows = get_single_pairings(pairings, pid, pname)
        single_rows = filter_available(single_rows, wines)

        if single_rows.empty:
            st.warning(f"{pname}: não existe linha individual correspondente no pairings.")
        else:
            render_pairing_cards(f"Melhor por prato • {pname}", single_rows, wines_meta)


def render_dm(menu: pd.DataFrame, wines: pd.DataFrame, pairings: pd.DataFrame) -> None:
    st.subheader("Diagnóstico DM")

    st.write(f"MENU: {len(menu)} linhas")
    st.write(f"WINES: {len(wines)} linhas")
    st.write(f"PAIRINGS: {len(pairings)} linhas")

    if st.session_state.get("selected_pratos"):
        selected = menu[menu["nome_prato"].isin(st.session_state["selected_pratos"])].copy()
        for _, row in selected.iterrows():
            prato_id = row["id_prato"]
            prato_nome = row["nome_prato"]
            target_ids_key = make_ids_key([prato_id])
            target_names_key = make_names_key([prato_nome])

            by_id = pairings[(pairings["dish_count"] == 1) & (pairings["ids_key"] == target_ids_key)].copy()
            by_name = pairings[(pairings["dish_count"] == 1) & (pairings["names_key"] == target_names_key)].copy()

            st.write({
                "prato_nome": prato_nome,
                "id_prato": prato_id,
                "target_ids_key": target_ids_key,
                "target_names_key": target_names_key,
                "matches_por_id": len(by_id),
                "matches_por_nome": len(by_name),
            })

            if not by_id.empty:
                st.dataframe(by_id[["ids_pratos", "ids_key", "nomes_pratos", "names_key", "id_vinho", "nome_vinho"]], use_container_width=True)
            elif not by_name.empty:
                st.dataframe(by_name[["ids_pratos", "ids_key", "nomes_pratos", "names_key", "id_vinho", "nome_vinho"]], use_container_width=True)

    debug_cols = ["ids_pratos", "ids_key", "nomes_pratos", "names_key", "dish_count", "id_vinho", "nome_vinho"]
    for c in debug_cols:
        if c not in pairings.columns:
            pairings[c] = ""
    st.dataframe(pairings[debug_cols], use_container_width=True)


def main() -> None:
    set_page_style()

    if "dm" not in st.session_state:
        st.session_state.dm = False

    render_sidebar(bool(st.session_state.dm))
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

        menu_df = load_csv_from_url(menu_url, "MENU")
        wines_df = load_csv_from_url(wines_url, "WINES")
        pairings_df = load_csv_from_url(pairings_url, "PAIRINGS")

        menu = standardize_menu(menu_df)
        wines = standardize_wines(wines_df)
        pairings = standardize_pairings(pairings_df)

    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        st.stop()

    if st.session_state.dm:
        render_dm(menu, wines, pairings)
    else:
        render_client(menu, wines, pairings)


if __name__ == "__main__":
    main()