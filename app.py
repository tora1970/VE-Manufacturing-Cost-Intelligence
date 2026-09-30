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
# INITIALIZE MASTERDATA
# =====================================================

if "masterdata_loaded" not in st.session_state:

    try:
        masterdata.load_all()
        st.session_state.masterdata_loaded = True

    except Exception as e:
        st.error(f"❌ Failed to load masterdata: {e}")
        st.stop()


# =====================================================
# SIDEBAR
# =====================================================

with st.sidebar:

    st.title("VEMCI")
    st.caption("VE Manufacturing Cost Intelligence")

    st.markdown("---")

    st.subheader("System")

    if st.button(
        "🔄 Reload Masterdata",
        use_container_width=True
    ):
        try:
            masterdata.load_all()
            st.success("Masterdata reloaded successfully")

        except Exception as e:
            st.error(f"Reload failed: {e}")

    st.markdown("---")

    st.subheader("Masterdata Status")

    st.metric(
        "Materials",
        len(masterdata.materials)
        if masterdata.materials is not None
        else 0
    )

    st.metric(
        "Processes",
        len(masterdata.processes)
        if masterdata.processes is not None
        else 0
    )

    st.metric(
        "Technologies",
        len(masterdata.technologies)
        if masterdata.technologies is not None
        else 0
    )

    st.metric(
        "Regions",
        len(masterdata.regions)
        if masterdata.regions is not None
        else 0
    )


# =====================================================
# HEADER
# =====================================================

st.title("VE Manufacturing Cost Intelligence")

st.caption(
    "Digital Cost Intelligence Platform"
)

st.markdown("---")


# =====================================================
# MAIN TABS
# =====================================================

tab_technology, tab_masterdata, tab_system = st.tabs(
    [
        "Technologies",
        "Masterdata",
        "System"
    ]
)


# =====================================================
# TECHNOLOGIES TAB
# =====================================================

with tab_technology:

    st.header("Technology Cost Models")

    if (
        masterdata.technologies is not None
        and not masterdata.technologies.empty
    ):

        tech_column = None

        for col in [
            "Technology_Name",
            "Technology",
            "Name"
        \]:
            if col in masterdata.technologies.columns:
                tech_column = col
                break

        if tech_column:

            technologies = sorted(
                masterdata.technologies[
                    tech_column
                ]
                .dropna()
                .unique()
            )

            selected_technology = st.selectbox(
                "Select Technology",
                technologies
            )

            st.info(
                f"Selected Technology: {selected_technology}"
            )

            # Future technology models
            #
            # HPDC
            # Machining
            # Injection Molding
            # LPDC
            # Gravity Die Casting
            # Sheet Metal

        else:

            st.error(
                "Technology column not found in Technologies.xlsx"
            )

    else:

        st.warning(
            "Technologies masterdata not loaded."
        )


# =====================================================
# MASTERDATA TAB
# =====================================================

with tab_masterdata:

    st.header("Masterdata")

    md_tabs = st.tabs(
        [
            "Materials",
            "Processes",
            "Technologies",
            "Regions"
        ]
    )

    with md_tabs[0\]:

        if masterdata.materials is not None:
            st.dataframe(
                masterdata.materials,
                use_container_width=True
            )
        else:
            st.warning("Materials not loaded")

    with md_tabs[1\]:

        if masterdata.processes is not None:
            st.dataframe(
                masterdata.processes,
                use_container_width=True
            )
        else:
            st.warning("Processes not loaded")

    with md_tabs[2\]:

        if masterdata.technologies is not None:
            st.dataframe(
                masterdata.technologies,
                use_container_width=True
            )
        else:
            st.warning("Technologies not loaded")

    with md_tabs[3\]:

        if masterdata.regions is not None:
            st.dataframe(
                masterdata.regions,
                use_container_width=True
            )
        else:
            st.warning("Regions not loaded")


# =====================================================
# SYSTEM TAB
# =====================================================

with tab_system:

    st.header("System Information")

    st.write("Masterdata loaded successfully.")

    st.write(
        f"Materials: "
        f"{len(masterdata.materials) if masterdata.materials is not None else 0}"
    )

    st.write(
        f"Processes: "
        f"{len(masterdata.processes) if masterdata.processes is not None else 0}"
    )

    st.write(
        f"Technologies: "
        f"{len(masterdata.technologies) if masterdata.technologies is not None else 0}"
    )

    st.write(
        f"Regions: "
        f"{len(masterdata.regions) if masterdata.regions is not None else 0}"
    )

    st.markdown("---")

    st.code(
        "Masterdata
