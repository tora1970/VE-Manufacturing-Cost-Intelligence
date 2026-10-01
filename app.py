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
        "CNC Machining",
        "Injection Molding",
        "Sand Casting",
        "HP Multi Jet Fusion"
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

    st.markdown("---")
    st.subheader("Manufacturing Input")

    col1, col2, col3 = st.columns(3)

    with col1:
        part_weight = st.number_input(
            "Part Weight [kg]",
            min_value=0.0,
            value=0.10,
            step=0.01
        )

    with col2:
        annual_volume = st.number_input(
            "Annual Volume [pcs/year]",
            min_value=1,
            value=10000,
            step=100
        )

    with col3:
        current_price = st.number_input(
            "Current Price [EUR]",
            min_value=0.0,
            value=0.00,
            step=0.10
        )

    col1, col2 = st.columns(2)

    with col1:

        materials = []

        if hasattr(masterdata, "materials"):

            try:
                materials = (
                    masterdata.materials.iloc[:, 0]
                    .dropna()
                    .astype(str)
                    .tolist()
                )
            except:
                pass

        selected_material = st.selectbox(
            "Material",
            materials if materials else ["No Materials Loaded"]
        )

    with col2:

        regions = []

        if hasattr(masterdata, "regions"):

            try:

                if "Region Name" in masterdata.regions.columns:

                    regions = (
                        masterdata.regions["Region Name"]
                        .dropna()
                        .astype(str)
                        .tolist()
                    )

            except Exception:
                pass

        selected_region = st.selectbox(
            "Manufacturing Region",
            regions if regions else ["No Regions Loaded"]
        )

    surface_treatment = st.selectbox(
        "Surface Treatment",
        [
            "None",
            "Anodize",
            "Powder Coat",
            "Paint",
            "Other"
        ]
    )

    st.markdown("### Selected Input Values")

    st.write(f"Weight: {part_weight:.3f} kg")
    st.write(f"Volume: {annual_volume:,} pcs/year")
    st.write(f"Current Price: €{current_price:.2f}")
    st.write(f"Material: {selected_material}")
    st.write(f"Region: {selected_region}")
    st.write(f"Surface Treatment: {surface_treatment}")

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