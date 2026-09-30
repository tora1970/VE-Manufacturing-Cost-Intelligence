# =====================================================
# TECHNOLOGY TAB
# =====================================================

with tab_technology:

    st.header("Technology Cost Models")

    if (
        masterdata.technologies is not None
        and not masterdata.technologies.empty
    ):

        tech_column = None

        for candidate in [
            "Technology_Name",
            "Technology",
            "Name"
        \]:
            if candidate in masterdata.technologies.columns:
                tech_column = candidate
                break

        if tech_column:

            technologies = sorted(
                masterdata.technologies[tech_column]
                .dropna()
                .unique()
            )

            selected_technology = st.selectbox(
                "Select Technology",
                technologies
            )

            st.success(
                f"Selected Technology: {selected_technology}"
            )

        else:

            st.error(
                "No valid technology column found."
            )

    else:

        st.warning(
            "Technology masterdata not loaded."
        )
