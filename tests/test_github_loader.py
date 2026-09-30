from pathlib import Path

from services.github_loader import GitHubExcelLoader


def test_cache_path_is_stable(tmp_path: Path):
    loader = GitHubExcelLoader("owner", "repo", cache_directory=tmp_path)
    first = loader._cache_path("materials/Materials.xlsx")
    second = loader._cache_path("materials/Materials.xlsx")
    assert first == second
    assert first.suffix == ".xlsx"


def test_path_normalisation_rejects_parent_navigation():
    try:
        GitHubExcelLoader._normalise_path("../secret.xlsx")
        assert False, "Expected ValueError"
    except ValueError:
        assert True
