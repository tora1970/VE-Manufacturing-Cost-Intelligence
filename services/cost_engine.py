from __future__ import annotations

from typing import Protocol, TypeVar


InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class CostModel(Protocol[InputT, OutputT]):
    technology: str
    def calculate(self, data: InputT) -> OutputT: ...


class CostEngine:
    def calculate(self, model: CostModel[InputT, OutputT], data: InputT) -> OutputT:
        if not hasattr(model, "calculate"):
            raise TypeError("The supplied model does not implement calculate().")
        return model.calculate(data)
