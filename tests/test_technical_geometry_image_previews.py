import ast
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
EXPECTED_VIEWS = {
    "Top view": ("uploaded_top_view", "creo_top_view"),
    "Bottom view": ("uploaded_bottom_view", "creo_bottom_view"),
    "Left view": ("uploaded_left_view", "creo_left_view"),
    "Right view": ("uploaded_right_view", "creo_right_view"),
}


def _app_tree():
    return ast.parse(APP_PATH.read_text(encoding="utf-8"))


def _string_argument(call):
    if call.args and isinstance(call.args[0], ast.Constant):
        return call.args[0].value
    return None


def test_geometry_uploaders_keep_existing_types_and_keys():
    uploaders = {
        _string_argument(node): node
        for node in ast.walk(_app_tree())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "file_uploader"
    }

    assert set(EXPECTED_VIEWS).issubset(uploaders)
    for view, (_, key) in EXPECTED_VIEWS.items():
        uploader = uploaders[view]
        keywords = {keyword.arg: keyword.value for keyword in uploader.keywords}
        assert ast.literal_eval(keywords["type"]) == ["png", "jpg", "jpeg"]
        assert ast.literal_eval(keywords["key"]) == key


def test_each_geometry_upload_has_a_conditional_full_width_preview():
    tree = _app_tree()
    for view, (uploaded_name, _) in EXPECTED_VIEWS.items():
        uploader_assignment = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == uploaded_name
                for target in node.targets
            )
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "file_uploader"
            and _string_argument(node.value) == view
        )
        parent_if = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == uploaded_name
            and any(
                isinstance(comparator, ast.Constant)
                and comparator.value is None
                for comparator in node.test.comparators
            )
            and isinstance(node.test.ops[0], ast.IsNot)
        )
        image_call = next(
            node
            for node in parent_if.body
            if isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "image"
        ).value

        assert uploader_assignment is not None
        assert isinstance(image_call.args[0], ast.Name)
        assert image_call.args[0].id == uploaded_name
        width = next(
            keyword.value
            for keyword in image_call.keywords
            if keyword.arg == "width"
        )
        assert ast.literal_eval(width) == "stretch"
