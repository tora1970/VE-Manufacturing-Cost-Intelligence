import streamlit as st

st.set_page_config(
    page_title="VE Manufacturing Cost Intelligence",
    page_icon="📊",
    layout="wide"
)

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

    st.info(
        "Technology-specific cost models will be launched from here."
    )

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

    st.write(f"Selected technology: {technology}")

# =====================================================
# MASTERDATA
# =====================================================

with tab_masterdata:

    st.header("Masterdata")

    st.info(
        "Masterdata integration will be added in the next step."
    )

# =====================================================
# SYSTEM
# =====================================================

with tab_system:

    st.header("System")

    st.success("Application running successfully")

    st.write("Repository: VE-Manufacturing-Cost-Intelligence")

    st.write("Status: OK")