def main():
    set_page_style()
    sidebar_brand()
    dm = dm_login_block()
    st.markdown("<div class='yvora-shell'>", unsafe_allow_html=True)
    header_area()

    try:
        menu_df, wines_df, pair_df = load_all_data()
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
