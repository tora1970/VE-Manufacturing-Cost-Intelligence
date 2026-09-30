from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from services.github_loader import GitHubExcelLoader


class MasterDataError(RuntimeError):
    pass


def _clean_columns(frame: pd.DataFrame) -> pd.DataFrame:
    cleaned = frame.copy()
    cleaned.columns = [str(column).strip() for column in cleaned.columns]
    return cleaned.dropna(how="all").reset_index(drop=True)


def find_column(frame: pd.DataFrame, aliases: Iterable[str], required: bool = True) -> str | None:
    lookup = {str(column).strip().lower().replace("_", " "): str(column) for column in frame.columns}
    for alias in aliases:
        key = alias.strip().lower().replace("_", " ")
        if key in lookup:
            return lookup[key]
    if required:
        raise MasterDataError(
            f"None of the expected columns {list(aliases)} were found. Available columns: {list(frame.columns)}"
        )
    return None


@dataclass
class MasterDataService:
    loader: GitHubExcelLoader
    paths: dict[str, str]

    def _load(self, key: str, force_refresh: bool = False) -> pd.DataFrame:
        path = self.paths.get(key)
        if not path:
            raise MasterDataError(f"No masterdata path configured for '{key}'.")
        data = self.loader.load_excel(path, force_refresh=force_refresh)
        if not isinstance(data, pd.DataFrame):
            raise MasterDataError(f"Expected one worksheet for '{key}', got multiple worksheets.")
        return _clean_columns(data)

    def materials(self, force_refresh: bool = False) -> pd.DataFrame:
        return self._load("materials", force_refresh)

    def regions(self, force_refresh: bool = False) -> pd.DataFrame:
        return self._load("regions", force_refresh)

    def technologies(self, force_refresh: bool = False) -> pd.DataFrame:
        return self._load("technologies", force_refresh)

    def technology_rules(self, force_refresh: bool = False) -> pd.DataFrame:
        return self._load("technology_rules", force_refresh)

    def technology_cost_library(self, force_refresh: bool = False) -> pd.DataFrame:
        return self._load("technology_cost_library", force_refresh)

    def hpdc_machines(self, force_refresh: bool = False) -> pd.DataFrame:
        return self._load("hpdc_machines", force_refresh)

    def hpdc_alloys(self, force_refresh: bool = False) -> pd.DataFrame:
        key = "hpdc_alloys" if self.paths.get("hpdc_alloys") else "materials"
        return self._load(key, force_refresh)

    def hpdc_parameters(self, force_refresh: bool = False) -> pd.DataFrame:
        return self._load("hpdc_parameters", force_refresh)

    def material_options(self) -> list[str]:
        frame = self.hpdc_alloys()
        column = find_column(frame, ["Material", "Material Name", "Alloy", "Alloy Name", "Name"])
        return sorted(frame[column].dropna().astype(str).str.strip().unique().tolist())

    def region_options(self) -> list[str]:
        frame = self.regions()
        column = find_column(frame, ["Region", "Region Name", "Country", "Name"])
        return sorted(frame[column].dropna().astype(str).str.strip().unique().tolist())

    def machine_options(self) -> list[str]:
        frame = self.hpdc_machines()
        column = find_column(frame, ["Machine", "Machine Name", "Machine ID", "Name"])
        return sorted(frame[column].dropna().astype(str).str.strip().unique().tolist())
