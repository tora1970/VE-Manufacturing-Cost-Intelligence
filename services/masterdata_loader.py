from pathlib import Path
import pandas as pd


class MasterDataLoader:

    def __init__(self, masterdata_path="masterdata"):

        self.masterdata_path = Path(masterdata_path)

        self.materials = None
        self.processes = None
        self.technologies = None
        self.regions = None
        self.routings = None
        self.routing_operations = None
        self.technology_rules = None
        self.technology_cost_library = None

    def load_all(self):

        self.materials = pd.read_excel(
            self.masterdata_path / "Materials.xlsx"
        )

        self.processes = pd.read_excel(
            self.masterdata_path / "Processes.xlsx"
        )

        self.technologies = pd.read_excel(
            self.masterdata_path / "Technologies.xlsx"
        )

        self.regions = pd.read_excel(
            self.masterdata_path / "Regions.xlsx"
        )

        self.routings = pd.read_excel(
            self.masterdata_path / "Routings.xlsx"
        )

        self.routing_operations = pd.read_excel(
            self.masterdata_path / "Routing_Operations.xlsx"
        )

        self.technology_rules = pd.read_excel(
            self.masterdata_path / "Technology_Rules.xlsx"
        )

        self.technology_cost_library = pd.read_excel(
            self.masterdata_path / "Technology_Cost_Library.xlsx"
        )

        return True
