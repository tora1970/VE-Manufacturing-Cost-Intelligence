from __future__ import annotations

import math
from dataclasses import asdict

import pandas as pd
import streamlit as st

from models.hpdc import HPDCInput, HPDCModel, calculate_cavity_layout
from services.cost_engine import CostEngine
from services.machine_rate_resolution import resolve_hpdc_machine
from services.masterdata_service import MasterDataError, MasterDataService, find_column
from services.result_store import ResultStore


def _lookup_numeric(
    frame: pd.DataFrame,
    name: str,
    name_aliases: list[str],
    value_aliases: list[str],
) -> float:
    name_col = find_column(frame, name_aliases)
    value_col = find_column(frame, value_aliases)
    match = frame[frame[name_col].astype(str).str.strip().str.casefold() == name.strip().casefold()]
    if match.empty:
        raise MasterDataError(f"'{name}' was not found in masterdata column '{name_col}'.")
    value = pd.to_numeric(match.iloc[0][value_col], errors="coerce")
    if pd.isna(value):
        raise MasterDataError(f"Value for '{name}' in column '{value_col}' is not numeric.")
    return float(value)


def _material_price_from_record(record: pd.Series, material: str) -> float:
    frame = record.to_frame().T
    price = _lookup_numeric(
        frame,
        material,
        ["Material", "Material Name", "Alloy", "Alloy Name", "Name"],
        [
            "Material Price EUR/kg",
            "Default Price EUR/kg",
            "Default Price EUR kg",
            "Price EUR/kg",
            "Price EUR kg",
            "EUR/kg",
            "Material Price",
            "Price per kg",
        ],
    )
    if not math.isfinite(price) or price <= 0:
        raise MasterDataError(
            f"Material price for '{material}' must be finite and greater than zero."
        )
    return price


def _material_price(service: MasterDataService, material: str) -> float:
    return _material_price_from_record(service.material_record(material), material)


def _labour_rate(service: MasterDataService, region: str) -> float:
    frame = service.regions()
    return _lookup_numeric(
        frame,
        region,
        ["Region", "Region Name", "Country", "Name"],
        [
            "Labour Rate EUR/h",
            "Labour Rate EUR hr",
            "Labor Rate EUR/h",
            "EUR/h",
            "Labour Rate",
            "Labor Rate",
        ],
    )


def render_hpdc_agent(service: MasterDataService, settings: dict) -> None:
    defaults = settings["hpdc_defaults"]
    currency = settings["application"].get("currency", "EUR")
    github = settings["github"]
    masterdata_paths = settings["masterdata"]
    st.header("HPDC should-cost")
    st.caption(
        f"Masterdata source: {github['owner']}/{github['repository']}@{github['branch']} | "
        f"materials -> {masterdata_paths['materials']} | "
        f"machine -> {masterdata_paths['machine']}"
    )
    st.caption(
        "Predicted cycle time currently uses the configured HPDC baseline; "
        "this project does not yet include a cycle-time prediction equation."
    )

    try:
        materials = service.material_options()
        regions = service.region_options()
        machine_data = service.hpdc_machines()
    except Exception as exc:
        st.error(f"Masterdata could not be loaded: {exc}")
        st.info("Check repository owner, repository name, branch, file paths and Excel column names in config/settings.yaml.")
        return

    if not materials or not regions:
        st.error("At least one HPDC material and region is required in masterdata.")
        return
    if machine_data.empty:
        st.error("HPDC machine masterdata contains no machine rows.")
        return

    with st.form("hpdc_input_form"):
        left, middle, right = st.columns(3)
        with left:
            annual_volume = st.number_input(
                "Annual Volume [good parts/year]",
                min_value=1,
                value=int(defaults["annual_volume"]),
                step=100,
            )
            number_of_cavities = st.number_input(
                "Number of Cavities [parts/shot]",
                min_value=1,
                value=int(defaults["cavities"]),
                step=1,
            )
            net_part_weight = st.number_input(
                "Net Part Weight [kg/part]",
                min_value=0.0,
                value=float(defaults["part_weight_kg"]),
                step=0.01,
                format="%.4f",
            )
            process_scrap_rate = st.number_input(
                "Process Scrap [%]",
                min_value=0.0,
                max_value=99.0,
                value=float(defaults["scrap_rate"]) * 100,
                step=0.5,
            )
            material = st.selectbox("Material / alloy", materials)
            material_record = None
            material_price = None
            material_error = None
            try:
                material_record = service.material_record(material)
                material_price = _material_price_from_record(material_record, material)
            except MasterDataError as exc:
                material_error = str(exc)
            if material_price is None:
                st.error(f"Material masterdata error: {material_error}")
            else:
                st.text_input(
                    "Material Price [EUR/kg]",
                    value=f"{material_price:.2f}",
                    disabled=True,
                )
                st.caption("Material source: Masterdata/Materials.xlsx")
        with middle:
            part_length = st.number_input(
                "Part Length [mm]", min_value=0.0, value=0.0, step=1.0
            )
            part_width = st.number_input(
                "Part Width [mm]", min_value=0.0, value=0.0, step=1.0
            )
            part_height = st.number_input(
                "Part Height [mm]", min_value=0.0, value=0.0, step=1.0
            )
            metal_yield = st.number_input(
                "Metal Yield [%]",
                min_value=1.0,
                max_value=100.0,
                value=float(defaults["casting_yield"]) * 100,
                step=1.0,
            )
            override_cycle_time = st.checkbox("Override cycle time")
            cycle_time_override = (
                st.number_input(
                    "Cycle Time Override [s]",
                    min_value=0.1,
                    value=float(defaults["cycle_time_s"]),
                    step=1.0,
                )
                if override_cycle_time
                else None
            )
        with right:
            region_default = settings["application"].get("default_region")
            region_index = regions.index(region_default) if region_default in regions else 0
            region = st.selectbox("Region", regions, index=region_index)
            oee = st.number_input(
                "OEE [%]",
                min_value=1.0,
                max_value=100.0,
                value=float(defaults["oee"]) * 100,
                step=1.0,
            )
            operators = st.number_input(
                "Direct Operators [FTE per machine]",
                min_value=0.0,
                value=float(defaults["operators"]),
                step=0.1,
            )
            tooling_cost = st.number_input(
                f"Tooling Investment [{currency}]",
                min_value=0.0,
                value=float(defaults["tooling_cost_eur"]),
                step=1000.0,
            )
            tool_life = st.number_input(
                "Tool Life [shots]",
                min_value=1,
                value=int(defaults["tool_life_shots"]),
                step=1000,
            )
            overhead_rate = st.number_input(
                "Overhead on Direct Cost [%]",
                min_value=0.0,
                max_value=99.0,
                value=float(defaults["overhead_rate"]) * 100,
                step=1.0,
            )
        layout_factor = float(defaults["layout_factor"])
        st.caption(
            f"Estimated cavity layout uses a configurable layout factor of {layout_factor:g}; "
            "it is not a validated die design."
        )
        st.caption(
            "Materials.xlsx has no process-compatibility field; all materials in the "
            "masterdata list are shown."
        )
        submitted = st.form_submit_button(
            "Calculate should-cost",
            type="primary",
            disabled=material_price is None,
        )

    if not submitted:
        return
    if material_record is None or material_price is None:
        st.error("A valid selected material record and price are required.")
        return

    try:
        cavities = int(number_of_cavities)
        layout_length, layout_width, _ = calculate_cavity_layout(
            cavities,
            float(part_length),
            float(part_width),
            layout_factor,
        )
        net_weight_per_shot = float(net_part_weight) * cavities
        total_shot_weight = net_weight_per_shot / (float(metal_yield) / 100)
        cycle_time_predicted = float(defaults["cycle_time_s"])
        machine = resolve_hpdc_machine(
            machine_data,
            layout_length,
            layout_width,
            total_shot_weight,
        )
        data = HPDCInput(
            annual_volume=int(annual_volume),
            part_weight_kg=float(net_part_weight),
            material_price_eur_kg=material_price,
            casting_yield=float(metal_yield) / 100,
            cycle_time_s=cycle_time_predicted,
            cavities=cavities,
            machine_rate_eur_h=machine.machine_hour_rate_eur_hr,
            oee=float(oee) / 100,
            labour_rate_eur_h=_labour_rate(service, region),
            operators=float(operators),
            scrap_rate=float(process_scrap_rate) / 100,
            tooling_cost_eur=float(tooling_cost),
            tool_life_shots=int(tool_life),
            overhead_rate=float(overhead_rate) / 100,
            currency=currency,
            material=material,
            region=region,
            machine=machine.size,
            number_of_cavities=cavities,
            process_scrap_rate=float(process_scrap_rate) / 100,
            net_part_weight_kg=float(net_part_weight),
            part_length_mm=float(part_length),
            part_width_mm=float(part_width),
            part_height_mm=float(part_height),
            metal_yield=float(metal_yield) / 100,
            cycle_time_predicted_s=cycle_time_predicted,
            cycle_time_override_s=(
                float(cycle_time_override) if cycle_time_override is not None else None
            ),
            layout_factor=layout_factor,
            machine_rate_source="Machine.xlsx masterdata",
            selected_machine_process=machine.process,
            selected_machine_size=machine.size,
            machine_selection_method=machine.selection_method,
            machine_selection_reason=machine.selection_reason,
            selected_machine_max_part_size=machine.max_part_size,
            selected_machine_max_part_weight_kg=machine.max_part_weight_kg,
        )
        result = CostEngine().calculate(HPDCModel(), data)
    except Exception as exc:
        st.error(f"Calculation failed: {exc}")
        return

    if result.cycle_time_warning:
        st.warning(result.cycle_time_warning)

    one, two, three = st.columns(3)
    one.metric("Total Should-cost", f"{result.total_cost:,.2f} {currency}/pc")
    two.metric("Annual Cost", f"{result.annual_cost:,.0f} {currency}")
    two.caption(f"Based on {data.annual_volume:,} good parts/year")
    three.metric("Machine Cost per Good Part", f"{result.machine_cost_per_good_part:,.4f} {currency}")

    st.subheader("Resolved Production Inputs")
    st.dataframe(
        pd.DataFrame(
            [
                ("Predicted Cycle Time [s]", result.cycle_time_predicted_s),
                ("Cycle Time Override [s]", result.cycle_time_override_s),
                ("Effective Cycle Time [s]", result.cycle_time_effective_s),
                ("Cycle Time Source", result.cycle_time_source),
                ("Selected Machine Size", result.selected_machine_size),
                ("Machine Rate [EUR/h]", result.machine_rate_eur_hr),
                ("Required Cavity Layout [mm]", f"{result.required_layout_length_mm:g} x {result.required_layout_width_mm:g}"),
                ("Total Shot Weight [kg]", result.total_shot_weight_kg),
                ("Shots per Hour", result.shots_per_hour),
                ("Gross Parts per Hour", result.gross_parts_per_hour),
                ("Good Parts per Hour", result.good_parts_per_hour),
                ("Required Machine Hours per Year", result.machine_hours_year),
                ("Machine Cost per Good Part", result.machine_cost_per_good_part),
            ],
            columns=["Resolved Field", "Value"],
        ),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(f"Machine selection: {result.machine_selection_reason}")

    chart = pd.DataFrame(
        {
            "Cost element": ["Material", "Machine", "Labour", "Tooling", "Scrap", "Overhead"],
            f"{currency}/pc": [
                result.material_cost,
                result.machine_cost,
                result.labour_cost,
                result.tooling_cost,
                result.scrap_cost,
                result.overhead_cost,
            ],
        }
    ).set_index("Cost element")
    st.subheader("Cost Breakdown")
    st.bar_chart(chart)
    st.dataframe(chart, use_container_width=True)

    payload = {"inputs": asdict(data), "result": result.to_dict()}
    left, right = st.columns(2)
    with left:
        st.download_button(
            "Download Calculation as JSON",
            data=pd.Series(payload).to_json(indent=2),
            file_name="vemci_hpdc_result.json",
            mime="application/json",
        )
    with right:
        if st.button("Save Result Locally"):
            path = ResultStore().save("HPDC", asdict(data), result.to_dict())
            st.success(f"Saved as {path}")
