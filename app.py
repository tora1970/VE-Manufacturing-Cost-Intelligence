import streamlit as st

from services.masterdata_repository import masterdata
from services.machine_rate_resolution import (
    resolve_machine_rate,
    technology_name_mapping,
)
from services.machine_cost_calculation import calculate_machine_cost
from services.tooling_capex_status import classify_tooling_capex_status
from services.tooling_cost_calculation import calculate_analytical_tooling_cost
from services.tooling_business_case_calculation import (
    calculate_modelled_tooling_business_case,
)


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

    technical_col, input_col, resolved_col = st.columns(
        [1.05, 1.05, 1.30],
        gap="large",
    )

    with technical_col:

        st.subheader("Technical Geometry")

        view_col1, view_col2 = st.columns(2)

        with view_col1:
            st.file_uploader(
                "Top view",
                type=["png", "jpg", "jpeg"],
                key="creo_top_view",
            )

        with view_col2:
            st.file_uploader(
                "Bottom view",
                type=["png", "jpg", "jpeg"],
                key="creo_bottom_view",
            )

        view_col1, view_col2 = st.columns(2)

        with view_col1:
            st.file_uploader(
                "Left view",
                type=["png", "jpg", "jpeg"],
                key="creo_left_view",
            )

        with view_col2:
            st.file_uploader(
                "Right view",
                type=["png", "jpg", "jpeg"],
                key="creo_right_view",
            )

        st.subheader("Technology Cost Model")

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

    with input_col:

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
                "Current Price [EUR/part]",
                min_value=0.0,
                value=0.00,
                step=0.10
            )

        cycle_time_sec = st.number_input(
            "Cycle Time [sec]",
            min_value=1,
            value=45,
            step=1
        )

        st.markdown("#### Tooling Investment")
        tooling_capex_eur = st.number_input(
            "Tooling CAPEX [EUR]",
            min_value=0.0,
            value=0.0,
            step=1000.0,
            key="tooling_capex_eur_input",
        )
        tooling_amortization_volume_pcs = st.number_input(
            "Tooling Amortization Volume [pcs]",
            min_value=0,
            value=0,
            step=1000,
            key="tooling_amortization_volume_pcs_input",
        )
        tooling_payment_treatment = "upfront_capex"
        tooling_resolution_status = classify_tooling_capex_status(
            tooling_capex_eur,
            tooling_amortization_volume_pcs,
        )

        if tooling_resolution_status == "ready_for_analysis":
            analytical_tooling_cost_per_part_eur, analytical_tooling_cost_status = (
                calculate_analytical_tooling_cost(
                    tooling_capex_eur,
                    tooling_amortization_volume_pcs,
                )
            )
        else:
            analytical_tooling_cost_per_part_eur = None
            analytical_tooling_cost_status = "unavailable"

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

    # =====================================================
    # PART CONTEXT
    # =====================================================

    material_name = "N/A"
    material_group = "N/A"
    density = "N/A"
    material_cost = "N/A"

    labour_rate = "N/A"
    overhead_factor = "N/A"
    currency = "N/A"

    # -----------------------------------------
    # Material Context
    # -----------------------------------------

    if (
        hasattr(masterdata, "materials")
        and selected_material != "No Materials Loaded"
    ):

        try:

            material_row = masterdata.materials[
                masterdata.materials["Material_ID"].astype(str)
                == str(selected_material)
            ]

            if not material_row.empty:

                material_row = material_row.iloc[0]

                material_name = material_row.get(
                    "Material_Name",
                    "N/A"
                )

                material_group = material_row.get(
                    "Material_Group",
                    "N/A"
                )

                density = material_row.get(
                    "Density",
                    "N/A"
                )

                material_cost = material_row.get(
                    "Default_Price_EUR_kg",
                    "N/A"
                )

        except Exception:
            pass

    # -----------------------------------------
    # Region Context
    # -----------------------------------------

    if (
        hasattr(masterdata, "regions")
        and selected_region != "No Regions Loaded"
    ):

        try:

            region_row = masterdata.regions[
                masterdata.regions["Region Name"].astype(str)
                == str(selected_region)
            ]

            if not region_row.empty:

                region_row = region_row.iloc[0]

                labour_rate = region_row.get(
                    "Labour Rate EUR hr",
                    "N/A"
                )

                overhead_factor = region_row.get(
                    "Overhead factor",
                    "N/A"
                )

                currency = region_row.get(
                    "Currency",
                    "N/A"
                )

        except Exception:
            pass

    machine_rate_eur_hr, machine_rate_resolution_status = resolve_machine_rate(
        technology,
        technology_name_mapping,
        getattr(masterdata, "technology_cost_library", None),
    )

    # -----------------------------------------
    # Display Context
    # -----------------------------------------

    with resolved_col:

        st.subheader("Resolved Cost Inputs")

        ctx_col1, ctx_col2 = st.columns(2)

        with ctx_col1:

            st.markdown("#### Material Context")

            st.write(f"Material Name: {material_name}")
            st.write(f"Material Group: {material_group}")

            if density not in [None, "N/A"]:
                st.write(
                    f"Density: {float(density):,.0f} kg/m³"
                )
            else:
                st.write("Density: N/A")

            if material_cost not in [None, "N/A"]:
                st.write(
                    f"Default Material Cost: €{float(material_cost):,.2f}/kg"
                )
            else:
                st.write(
                    "Default Material Cost: N/A")

        with ctx_col2:

            st.markdown("#### Region Context")

            st.write(f"Region: {selected_region}")

            if labour_rate not in [None, "N/A"]:
                st.write(
                    f"Labour Rate: {float(labour_rate):,.2f} {currency}/hr"
                )
            else:
                st.write("Labour Rate: N/A")

            if overhead_factor not in [None, "N/A"]:
                st.write(
                    f"Overhead Factor: {float(overhead_factor):,.4f}"
                )
            else:
                st.write("Overhead Factor: N/A")

            st.write(f"Currency: {currency}")

            st.write("Tooling Payment: Upfront CAPEX")
            if tooling_capex_eur > 0:
                st.write(f"Tooling CAPEX: €{tooling_capex_eur:,.2f}")
            else:
                st.write("Tooling CAPEX: Not provided")

            if tooling_amortization_volume_pcs > 0:
                st.write(
                    f"Amortization Volume: {tooling_amortization_volume_pcs:,} pcs"
                )
            else:
                st.write("Amortization Volume: Not provided")

            if tooling_resolution_status == "ready_for_analysis":
                if analytical_tooling_cost_status == "calculated":
                    st.write(
                        "Analytical Tooling Cost per Part: "
                        f"€{analytical_tooling_cost_per_part_eur:,.2f}/part"
                    )
                else:
                    st.write("Analytical Tooling Cost per Part: Unavailable")

            if (
                machine_rate_resolution_status == "resolved"
                and machine_rate_eur_hr is not None
            ):
                st.write(f"Machine Rate: €{machine_rate_eur_hr:,.2f}/hr")
            else:
                st.write("Machine Rate: Unavailable")

        if tooling_resolution_status == "incomplete":
            st.warning(
                "Both CAPEX and amortization volume are required for future analytical tooling allocation."
            )

        if machine_rate_resolution_status == "unavailable":
            st.warning(
                f"No verified standard machine rate exists for {technology}."
            )

    # -----------------------------------------
    # Session State
    # -----------------------------------------

    st.session_state["part_context"] = {
        "material_name": material_name,
        "material_group": material_group,
        "density": density,
        "material_cost": material_cost,
        "region_name": selected_region,
        "labour_rate": labour_rate,
        "overhead_factor": overhead_factor,
        "currency": currency,
        "machine_rate_eur_hr": machine_rate_eur_hr,
        "machine_rate_resolution_status": machine_rate_resolution_status,
        "tooling_capex_eur": tooling_capex_eur,
        "tooling_amortization_volume_pcs": tooling_amortization_volume_pcs,
        "tooling_payment_treatment": tooling_payment_treatment,
        "tooling_resolution_status": tooling_resolution_status,
        "analytical_tooling_cost_per_part_eur": analytical_tooling_cost_per_part_eur,
        "analytical_tooling_cost_status": analytical_tooling_cost_status,
    }

    # =====================================================
    # COST BREAKDOWN
    # =====================================================

    st.markdown("---")
    st.subheader("Cost Breakdown")

    cost_breakdown = {
        "material_cost": 0.0,
        "machine_cost": None,
        "labour_cost": 0.0,
        "tooling_cost": 0.0,
        "surface_treatment_cost": 0.0,
        "packaging_cost": 0.0,
        "logistics_cost": 0.0,
    }
    # -----------------------------------------
    # Material Cost Calculation
    # -----------------------------------------

    try:

        if material_cost not in [None, "N/A", ""]:

            calculated_material_cost = (
                float(part_weight)
                * float(material_cost)
            )

        else:

            calculated_material_cost = 0.0

    except Exception:

        calculated_material_cost = 0.0

    cost_breakdown["material_cost"] = calculated_material_cost

        # -----------------------------------------
    # Labour Cost Calculation
    # -----------------------------------------

    try:

        if labour_rate not in [None, "N/A", ""]:

            calculated_labour_cost = (
                float(cycle_time_sec)
                / 3600
            ) * float(labour_rate)

        else:

            calculated_labour_cost = 0.0

    except Exception:

        calculated_labour_cost = 0.0

    cost_breakdown["labour_cost"] = calculated_labour_cost

    calculated_machine_cost, machine_cost_status = calculate_machine_cost(
        cycle_time_sec,
        machine_rate_eur_hr,
    )

    if machine_cost_status == "calculated":
        cost_breakdown["machine_cost"] = calculated_machine_cost
        should_cost_status = "complete"
        total_should_cost = sum(cost_breakdown.values())
    else:
        cost_breakdown["machine_cost"] = None
        should_cost_status = "incomplete"
        total_should_cost = None

    cost_breakdown["total_should_cost"] = total_should_cost
    analytical_fully_loaded_cost_per_part_eur = None
    if (
        should_cost_status == "complete"
        and analytical_tooling_cost_status == "calculated"
    ):
        analytical_fully_loaded_cost_per_part_eur = (
            total_should_cost + analytical_tooling_cost_per_part_eur
        )

    st.session_state["part_context"].update(
        {
            "machine_cost": calculated_machine_cost,
            "machine_cost_status": machine_cost_status,
            "should_cost_status": should_cost_status,
            "analytical_fully_loaded_cost_per_part_eur": (
                analytical_fully_loaded_cost_per_part_eur
            ),
        }
    )

    st.session_state["cost_breakdown"] = cost_breakdown

    breakdown_col1, breakdown_col2 = st.columns(2)

    with breakdown_col1:

        st.markdown("#### Manufacturing Costs")

        st.write(
            f"Material Cost: €{cost_breakdown['material_cost']:,.2f}"
        )

        if machine_cost_status == "calculated":
            st.write(
                f"Machine Cost: €{cost_breakdown['machine_cost']:,.2f}"
            )
        else:
            st.write("Machine Cost: Unavailable")

        st.write(
            f"Labour Cost: €{cost_breakdown['labour_cost']:,.2f}"
        )

        st.write("Tooling CAPEX: Shown separately")
        if tooling_capex_eur > 0:
            st.write(f"Upfront Tooling CAPEX: €{tooling_capex_eur:,.2f}")

    with breakdown_col2:

        st.markdown("#### Additional Costs")

        st.write(
            f"Surface Treatment Cost: €{cost_breakdown['surface_treatment_cost']:,.2f}"
        )

        st.write(
            f"Packaging Cost: €{cost_breakdown['packaging_cost']:,.2f}"
        )

        st.write(
            f"Logistics Cost: €{cost_breakdown['logistics_cost']:,.2f}"
        )

    if should_cost_status == "complete":
        st.metric(
            "Total Should Cost",
            f"€{total_should_cost:,.2f}"
        )
        try:
            current_price_value = float(current_price)
            savings_eur = current_price_value - total_should_cost

            if current_price_value > 0:
                savings_pct = (
                    savings_eur /
                    current_price_value
                ) * 100
            else:
                savings_pct = 0.0

        except Exception:
            savings_eur = 0.0
            savings_pct = 0.0
    else:
        st.metric("Total Should Cost", "Incomplete")
        st.warning(
            "Total Should Cost is incomplete because Machine Cost is unavailable."
        )
        savings_eur = None
        savings_pct = None

    currency_status = (
        "verified_eur"
        if isinstance(currency, str) and currency.strip().upper() == "EUR"
        else "unavailable"
    )
    modelled_business_case = calculate_modelled_tooling_business_case(
        savings_eur,
        annual_volume,
        tooling_capex_eur,
        currency_status,
    )
    st.session_state["part_context"].update(
        {
            "recurring_savings_per_part_eur": savings_eur,
            "recurring_savings_per_part_status": (
                "calculated" if savings_eur is not None else "unavailable"
            ),
            "annual_modelled_volume_pcs": annual_volume,
            "annual_modelled_recurring_savings_eur": (
                modelled_business_case.annual_modelled_recurring_savings_eur
            ),
            "annual_modelled_recurring_savings_status": (
                modelled_business_case.annual_modelled_recurring_savings_status
            ),
            "simple_payback_volume_pcs": (
                modelled_business_case.simple_payback_volume_pcs
            ),
            "simple_payback_volume_status": (
                modelled_business_case.simple_payback_volume_status
            ),
            "simple_payback_years": modelled_business_case.simple_payback_years,
            "simple_payback_years_status": (
                modelled_business_case.simple_payback_years_status
            ),
            "business_case_currency_status": currency_status,
        }
    )

    st.metric(
        "Analytical Fully Loaded Cost per Part",
        (
            f"€{analytical_fully_loaded_cost_per_part_eur:,.2f}"
            if analytical_fully_loaded_cost_per_part_eur is not None
            else "Unavailable"
        ),
    )

    st.markdown("---")

    st.subheader(
        "Cost Intelligence Summary"
    )

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Savings [EUR]",
            f"€{savings_eur:,.2f}" if savings_eur is not None else "Unavailable"
        )

    with col2:
        st.metric(
            "Savings [%]",
            f"{savings_pct:,.1f}%" if savings_pct is not None else "Unavailable"
        )

    st.markdown("---")
    st.subheader("Modelled Business Case")
    st.metric(
        "Recurring Savings per Part (Modelled)",
        f"€{savings_eur:,.2f}" if savings_eur is not None else "Unavailable",
    )
    st.metric(
        "Annual Modelled Recurring Savings",
        (
            f"€{modelled_business_case.annual_modelled_recurring_savings_eur:,.2f}"
            if modelled_business_case.annual_modelled_recurring_savings_eur
            is not None
            else "Unavailable"
        ),
    )
    st.metric("Upfront Tooling CAPEX", f"€{tooling_capex_eur:,.2f}")
    st.metric(
        "Simple Payback Volume (Modelled)",
        (
            f"{modelled_business_case.simple_payback_volume_pcs:,.2f} pcs"
            if modelled_business_case.simple_payback_volume_pcs is not None
            else modelled_business_case.simple_payback_volume_status.replace(
                "_", " "
            ).title()
        ),
    )
    st.metric(
        "Simple Payback Years (Modelled)",
        (
            f"{modelled_business_case.simple_payback_years:,.2f}"
            if modelled_business_case.simple_payback_years is not None
            else modelled_business_case.simple_payback_years_status.replace(
                "_", " "
            ).title()
        ),
    )
    st.caption(
        "Modelled outputs use the entered annual run-rate and do not represent "
        "realized fiscal-year savings."
    )
    st.caption(
        "Simple payback is an undiscounted screening metric and is not ROI, IRR "
        "or NPV."
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