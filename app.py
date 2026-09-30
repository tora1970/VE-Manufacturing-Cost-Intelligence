import streamlit as st

from services.masterdata_repository import masterdata


# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------

st.set_page_config(
    page_title="VE Manufacturing Cost Intelligence",
    page_icon="📊",
    layout="wide"
)


# --------------------------------------------------
# INITIAL MASTERDATA LOAD
# --------------------------------------------------

if "masterdata_loaded" not in st.session_state:

    try:

        masterdata.load_all()

        st.session_state.masterdata_loaded = True

    except Exception as e:

        st.error(
            f"❌ Failed to load masterdata: {e}"
        )

        st.stop()


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

with st.sidebar:

    st.image(
        "https://img.icons8.com/color/96/database.png",
        width=50
    )

    st.title("VEMCI")

    st.markdown("---")

    st.subheader("System")

    if st.button(
        "🔄 Reload Masterdata",
        use_container_width=True
    ):

        try:

            masterdata.load_all()

            st.success(
                "Masterdata reloaded successfully"
            )

        except Exception as e:

            st.error(
                f"Reload failed: {e}"
            )

    st.markdown("---")

    st.subheader("Masterdata Status")

    try:

        st.metric(
            "Materials",
            len(masterdata.materials)
        )

        st.metric(
            "Processes",
            len(masterdata.processes)
        )

        st.metric(
            "Technologies",
            len(masterdata.technologies)
        )

        st.metric(
            "Regions",
            len(masterdata.regions)
        )

    except:
        st.warning(
            "Masterdata not loaded"
        )


# --------------------------------------------------
# HEADER
# --------------------------------------------------

st.title("VE Manufacturing Cost Intelligence")

st.caption(
    "Digital Cost Intelligence Platform"
)

st.markdown("---")


# --------------------------------------------------
# MAIN TABS
# --------------------------------------------------

tab1, tab2, tab3 = st.tabs(
    [
        "Technologies",
        "Masterdata",
        "System"
    ]
)


# --------------------------------------------------
# TECHNOLOGIES
# --------------------------------------------------

with tab1:

    st.header("Technology Cost Models")

    technologies = sorted(
        masterdata.technologies[
            "Technology_Name"
        ].unique()
    )

    selected_technology = st.selectbox(
        "Select Technology",
        technologies
    )

    st.info(
        f"Selected Technology: {selected_technology}"
    )

    # TODO
    # HPDC
    # Machining
    # Injection Molding
    # LPDC
    # Sheet Metal


# --------------------------------------------------
# MASTERDATA
# --------------------------------------------------

with tab2:

    st.header("Masterdata")

    md_tabs = st.tabs([
        "Materials",
        "Processes",
        "Technologies",
        "Regions"
    ])

    with md_tabs[0\]:
        st.dataframe(
            masterdata.materials,
            use_container_width=True
        )

    with md_tabs[1\]:
        st.dataframe(
            masterdata.processes,
            use_container_width=True
        )

    with md_tabs[2\]:
        st.dataframe(
            masterdata.technologies,
            use_container_width=True
        )

    with md_tabs[3\]:
        st.dataframe(
            masterdata.regions,
            use_container_width=True
        )


# --------------------------------------------------
# SYSTEM
# --------------------------------------------------

with tab3:

    st.header("System Information")

    st.write(
        "Masterdata loaded successfully."
    )

    st.write(
        f"Materials: {len(masterdata.materials)}"
    )

    st.write(
        f"Processes: {len(masterdata.processes)}"
    )

    st.write(
        f"Technologies: {len(masterdata.technologies)}"
    )

    st.write(
        f"Regions: {len(masterdata.regions)}"
    )
