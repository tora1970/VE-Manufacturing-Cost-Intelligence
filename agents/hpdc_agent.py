from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from models.hpdc import HPDCInput, HPDCModel
from services.cost_engine import CostEngine
from services.masterdata_service import MasterDataError, MasterDataService, find_column
from services.result_store import ResultStore


def _lookup_numeric(frame: pd.DataFrame, name: str, name_aliases: list[str], value_aliases: list[str]) -> float:
    name_col = find_column(frame, name_aliases)
    value_col = find_column(frame, value_aliases)
    match = frame[frame[name_col].astype(str).str.strip().str.casefold() == name.strip().casefold()]
    if match.empty:
        raise MasterDataError(f"'{name}' was not found in masterdata column '{name_col}'.")
    value = pd.to_numeric(match.iloc[0][value_col], errors="coerce")
    if pd.isna(value):
        raise MasterDataError(f"Value for '{name}' in column '{value_col}' is not numeric.")
    return float(value)


def _material_price(service: MasterDataService, material: str) -> float:
    frame = service.hpdc_alloys()
    return _lookup_numeric(
        frame,
        material,
        ["Material", "Material Name", "Alloy", "Alloy Name", "Name"],
        ["Material Price EUR/kg", "Price EUR/kg", "EUR/kg", "Material Price", "Price per kg"],
    )


def _machine_rate(service: MasterDataService, machine: str) -> float:
    frame = service.hpdc_machines()
    return _lookup_numeric(
        frame,
        machine,
        ["Machine", "Machine Name", "Machine ID", "Name"],
        ["Machine Rate EUR/h", "Rate EUR/h", "EUR/h", "Hourly Rate", "Machine Rate"],
    )


def _labour_rate(service: MasterDataService, region: str) -> float:
    frame = service.regions()
    return _lookup_numeric(
        frame,
        region,
        ["Region", "Region Name", "Country", "Name"],
        ["Labour Rate EUR/h", "Labor Rate EUR/h", "EUR/h", "Labour Rate", "Labor Rate"],
    )


def render_hpdc_agent(service: MasterDataService, settings: dict) -> None:
    defaults = settings["hpdc_defaults"]
    currency = settings["application"].get("currency", "EUR")
    st.header("HPDC should-cost")
    st.caption("Masterdata is loaded from the configured GitHub repository and cached locally.")

    try:
        materials = service.material_options()
        regions = service.region_options()
        machines = service.machine_options()
    except Exception as exc:
        st.error(f"Masterdata could not be loaded: {exc}")
        st.info("Check repository owner, repository name, branch, file paths and Excel column names in config/settings.yaml.")
        return

    if not materials or not regions or not machines:
        st.error("At least one HPDC material, region and machine is required in masterdata.")
        return

    with st.form("hpdc_input_form"):
        left, middle, right = st.columns(3)
        with left:
            annual_volume = st.number_input("Annual volume [pcs]", min_value=1, value=int(defaults["annual_volume"]), step=100)
            part_weight = st.number_input("Net part weight [kg]", min_value=0.0001, value=float(defaults["part_weight_kg"]), step=0.01, format="%.4f")
            material = st.selectbox("Material / alloy", materials)
            region_default = settings["application"].get("default_region")
            region_index = regions.index(region_default) if region_default in regions else 0
            region = st.selectbox("Region", regions, index=region_index)
        with middle:
            machine = st.selectbox("Machine", machines)
            cycle_time = st.number_input("Cycle time [s]", min_value=0.1, value=float(defaults["cycle_time_s"]), step=1.0)
            cavities = st.number_input("Cavities", min_value=1, value=int(defaults["cavities"]), step=1)
            casting_yield = st.number_input("Casting yield [%]", min_value=1.0, max_value=100.0, value=float(defaults["casting_yield"]) * 100, step=1.0)
        with right:
            oee = st.number_input("OEE [%]", min_value=1.0, max_value=100.0, value=float(defaults["oee"]) * 100, step=1.0)
            scrap_rate = st.number_input("Scrap rate [%]", min_value=0.0, max_value=99.0, value=float(defaults["scrap_rate"]) * 100, step=0.5)
            tooling_cost = st.number_input(f"Tooling investment [{currency}]", min_value=0.0, value=float(defaults["tooling_cost_eur"]), step=1000.0)
            tool_life = st.number_input("Tool life [shots]", min_value=1, value=int(defaults["tool_life_shots"]), step=1000)
        with st.expander("Advanced labour and overhead inputs"):
            operators = st.number_input("Direct operators [FTE per machine]", min_value=0.0, value=float(defaults["operators"]), step=0.1)
            overhead_rate = st.number_input("Overhead on direct cost [%]", min_value=0.0, max_value=99.0, value=float(defaults["overhead_rate"]) * 100, step=1.0)
        submitted = st.form_submit_button("Calculate should-cost", type="primary")

    if not submitted:
        return

    try:
        data = HPDCInput(
            annual_volume=int(annual_volume),
            part_weight_kg=float(part_weight),
            material_price_eur_kg=_material_price(service, material),
            casting_yield=float(casting_yield) / 100,
            cycle_time_s=float(cycle_time),
            cavities=int(cavities),
            machine_rate_eur_h=_machine_rate(service, machine),
            oee=float(oee) / 100,
            labour_rate_eur_h=_labour_rate(service, region),
            operators=float(operators),
            scrap_rate=float(scrap_rate) / 100,
            tooling_cost_eur=float(tooling_cost),
            tool_life_shots=int(tool_life),
            overhead_rate=float(overhead_rate) / 100,
            currency=currency,
            material=material,
            region=region,
            machine=machine,
        )
        result = CostEngine().calculate(HPDCModel(), data)
    except Exception as exc:
        st.error(f"Calculation failed: {exc}")
        return

    one, two, three = st.columns(3)
    one.metric("Total should-cost", f"{result.total_cost:,.2f} {currency}/pc")
    two.metric("Annual cost", f"{result.annual_cost:,.0f} {currency}")
    two.caption(f"Based on {data.annual_volume:,} pcs/year")
    three.metric("Material share", f"{result.material_cost / result.total_cost:.1%}")

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
    st.subheader("Cost breakdown")
    st.bar_chart(chart)
    st.dataframe(chart, use_container_width=True)

    payload = {"inputs": asdict(data), "result": result.to_dict()}
    left, right = st.columns(2)
    with left:
        st.download_button(
            "Download calculation as JSON",
            data=pd.Series(payload).to_json(indent=2),
            file_name="vemci_hpdc_result.json",
            mime="application/json",
        )
    with right:
        if st.button("Save result locally"):
            path = ResultStore().save("HPDC", asdict(data), result.to_dict())
            st.success(f"Saved as {path}")
