from models.hpdc import HPDCInput, HPDCModel


def test_hpdc_calculation_is_positive():
    data = HPDCInput(
        annual_volume=25000,
        part_weight_kg=0.85,
        material_price_eur_kg=2.5,
        casting_yield=0.65,
        cycle_time_s=35,
        cavities=1,
        machine_rate_eur_h=85,
        oee=0.75,
        labour_rate_eur_h=18,
        operators=0.5,
        scrap_rate=0.03,
        tooling_cost_eur=120000,
        tool_life_shots=150000,
        overhead_rate=0.12,
    )
    result = HPDCModel().calculate(data)
    assert result.total_cost > 0
    assert result.annual_cost == round(result.total_cost * data.annual_volume, 2)
    assert result.total_cost >= result.material_cost


def test_invalid_oee_rejected():
    data = HPDCInput(1, 1, 1, 0.5, 1, 1, 1, 0, 1, 1, 0, 0, 1, 0)
    try:
        HPDCModel().calculate(data)
        assert False, "Expected ValueError"
    except ValueError:
        assert True
