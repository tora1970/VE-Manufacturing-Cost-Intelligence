import streamlit as st

from services.masterdata_repository import masterdata


# =====================================================
# PAGE CONFIG
# =====================================================

st.set_page_config(
    page_title="VE Manufacturing Cost Intelligence",
    page_icon="📊",
    layout="wide"
)


# =====================================================
# MASTERDATA LOAD
# =====================================================

masterdata_loaded = False
masterdata_error = None

try:

    masterdata.load_all()

    masterdata_loaded = True

except Exception as e:

    masterdata_error = str(e)


# =====================================================
# HEADER
# =====================================================

st.title("VE Manufacturing Cost Intelligence")
st.caption("Digital Cost Intelligence Platform")


# =====================================================
# MAIN NAVIGATION
# =====================================================

tab_technology, tab_masterdata, tab_system = st.tabs(
    [
        "Technologies",
        "Masterdata",
        "System"
    ]
)


# =====================================================
# TECHNOLOGIES
# =====================================================

with tab_technology:

    st.header("Technology Cost Models")

    technology = st.selectbox(
        "Select Technology",
        [
            "HPDC",
            "Machining",
            "Injection Molding",
            "LPDC",
            "Gravity Die Casting",
            "Sheet Metal"
        ]
    )

    st.info(
        f"Selected technology: {technology}"
    )

    if masterdata_loaded:

        st.success(
            "Masterdata available"
        )

    else:

        st.error(
            "Masterdata unavailable"
        )


# =====================================================
# MASTERDATA
# =====================================================

with tab_masterdata:

    st.header("Masterdata")

    if not masterdata_loaded:

        st.error(
            f"Masterdata load failed: {masterdata_error}"
        )

    else:

        st.success(
            "Masterdata loaded successfully"
        )

        st.subheader(
            "Data Overview"
        )

        if hasattr(masterdata, "materials"):
            st.write(
                f"Materials: {len(masterdata.materials)}"
            )

        if hasattr(masterdata, "processes"):
            st.write(
                f"Processes: {len(masterdata.processes)}"
            )

        if hasattr(masterdata, "technologies"):
            st.write(
                f"Technologies: {len(masterdata.technologies)}"
            )

        if hasattr(masterdata, "regions"):
            st.write(
                f"Regions: {len(masterdata.regions)}"
            )

        st.markdown("---")

        materials_tab, processes_tab, technologies_tab, regions_tab = st.tabs(
            [
                "Materials",
                "Processes",
                "Technologies",
                "Regions"
            ]
        )

        with materials_tab:

            if hasattr(masterdata, "materials"):

                st.dataframe(
                    masterdata.materials,
                    use_container_width=True
                )

        with processes_tab:

            if hasattr(masterdata, "processes"):

                st.dataframe(
                    masterdata.processes,
                    use_container_width=True
                )

        with technologies_tab:

            if hasattr(masterdata, "technologies"):

                st.dataframe(
                    masterdata.technologies,
                    use_container_width=True
                )

        with regions_tab:

            if hasattr(masterdata, "regions"):

                st.dataframe(
                    masterdata.regions,
                    use_container_width=True
                )


# =====================================================
# SYSTEM
# =====================================================

with tab_system:

    st.header("System")

    if masterdata_loaded:

        st.success(
            "Masterdata loaded successfully"
        )

    else:

        st.error(
            f"Masterdata load failed: {masterdata_error}"
        )

    st.markdown("---")

    if st.button("Reload Masterdata"):

        try:

            masterdata.load_all()

            st.success(
                "Masterdata reloaded successfully"
            )

            st.rerun()

        except Exception as e:

            st.error(
                f"Reload failed: {e}"
            )