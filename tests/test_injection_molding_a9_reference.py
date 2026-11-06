import pytest

from models.injection_molding import InjectionMoldingInput, InjectionMoldingModel


@pytest.fixture
def a9_injection_molding_input():
    # 1.0 kg finished weight / 1.03 kg used gives material_utilization = 1/1.03.
    # A9's process equation does not apply OEE, so 1.0 is a normalization;
    # the separate A9 "Utilization = 0.5" is not interpreted as OEE.
    # Process scrap and overhead are excluded because VEMCI's generic rates
    # do not have equivalent semantic scope to A9's separate cost elements.
    return InjectionMoldingInput(
        annual_volume=11504,
        part_weight_kg=1.0,
        material_price_eur_kg=2.5,
        material_utilization=1.0 / 1.03,
        cycle_time_s=94,
        cavities=1,
        machine_rate_eur_h=28.881166666666665,
        oee=1.0,
        labour_rate_eur_h=12.669741252,
        operators=0.5,
        scrap_rate=0.0,
        tooling_cost_eur=0.0,
        tool_life_shots=1,
        overhead_rate=0.0,
        currency="EUR",
        material="ASA",
        region="Hungary",
    )


def test_a9_reference_input_validates(a9_injection_molding_input):
    a9_injection_molding_input.validate()


def test_a9_material_cost_reproduces_reference_quantity(
    a9_injection_molding_input,
):
    result = InjectionMoldingModel().calculate(a9_injection_molding_input)

    assert result.material_cost == pytest.approx(2.575, abs=1e-4)


def test_a9_machine_cost_matches_normalized_reference(
    a9_injection_molding_input,
):
    result = InjectionMoldingModel().calculate(a9_injection_molding_input)

    assert result.machine_cost == pytest.approx(0.7541, abs=1e-4)


def test_a9_labour_cost_matches_normalized_reference(
    a9_injection_molding_input,
):
    result = InjectionMoldingModel().calculate(a9_injection_molding_input)

    assert result.labour_cost == pytest.approx(0.1654, abs=1e-4)


def test_a9_machine_and_labour_match_plastic_molding_process_cost(
    a9_injection_molding_input,
):
    result = InjectionMoldingModel().calculate(a9_injection_molding_input)

    assert result.machine_cost + result.labour_cost == pytest.approx(
        0.9195, abs=1e-4
    )


def test_a9_tooling_cost_is_neutral(a9_injection_molding_input):
    result = InjectionMoldingModel().calculate(a9_injection_molding_input)

    assert result.tooling_cost == 0


def test_a9_scrap_cost_is_neutral(a9_injection_molding_input):
    result = InjectionMoldingModel().calculate(a9_injection_molding_input)

    assert result.scrap_cost == 0


def test_a9_overhead_cost_is_neutral(a9_injection_molding_input):
    result = InjectionMoldingModel().calculate(a9_injection_molding_input)

    assert result.overhead_cost == 0


def test_a9_currency_remains_eur(a9_injection_molding_input):
    result = InjectionMoldingModel().calculate(a9_injection_molding_input)

    assert result.currency == "EUR"


def test_a9_annual_cost_uses_normalized_total_cost(
    a9_injection_molding_input,
):
    result = InjectionMoldingModel().calculate(a9_injection_molding_input)

    assert result.total_cost == pytest.approx(3.4945, abs=1e-4)
    assert result.annual_cost == round(
        result.total_cost * a9_injection_molding_input.annual_volume, 2
    )
