import ast
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _app_tree():
    return ast.parse(APP_PATH.read_text(encoding="utf-8"))


def _call_label(call):
    if not call.args or not isinstance(call.args[0], ast.Constant):
        return None
    return call.args[0].value


def test_surface_treatment_options_match_contract_vocabulary():
    selectbox = next(
        node
        for node in ast.walk(_app_tree())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "selectbox"
        and _call_label(node) == "Surface Treatment"
    )

    assert ast.literal_eval(selectbox.args[1]) == [
        "None",
        "Anodizing",
        "Powder Coating",
        "Wet Painting",
        "PVD",
        "Other",
    ]


def test_surface_treatment_inputs_are_visible_and_disabled_for_none():
    calls = [
        node
        for node in ast.walk(_app_tree())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "number_input"
        and _call_label(node)
        in {"Surface Area [m²]", "Surface Treatment Add-on [EUR/part]"}
    ]

    assert {_call_label(call) for call in calls} == {
        "Surface Area [m²]",
        "Surface Treatment Add-on [EUR/part]",
    }
    assert len(calls) == 2
    assert all(
        any(
            keyword.arg == "disabled"
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id == "no_surface_treatment"
            for keyword in call.keywords
        )
        for call in calls
    )
    assert all(
        any(
            keyword.arg == "min_value"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value == 0.0
            for keyword in call.keywords
        )
        for call in calls
    )


def test_none_treatment_resets_local_surface_inputs_to_zero():
    none_branch = next(
        node
        for node in ast.walk(_app_tree())
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "no_surface_treatment"
        and any(
            isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "surface_area_m2"
                for target in statement.targets
            )
            for statement in node.body
        )
    )
    zero_assignments = {
        target.id: ast.literal_eval(statement.value)
        for statement in none_branch.body
        if isinstance(statement, ast.Assign)
        and isinstance(statement.value, ast.Constant)
        for target in statement.targets
        if isinstance(target, ast.Name)
    }

    assert zero_assignments["surface_area_m2"] == 0.0
    assert zero_assignments["surface_treatment_addon_eur_per_part"] == 0.0
