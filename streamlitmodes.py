from __future__ import annotations
from typing import TYPE_CHECKING, Sequence, Any
if TYPE_CHECKING:
    pass

from enum import Flag, auto

class StreamlitMode(Flag):
    NameInputStandard = auto()
    NameInputNewCompany = auto()
    VehicleTypeStandard = auto()
    VehicleTypeNew = auto()
    VehicleCompaniesStandard = auto()
    VehicleCompaniesExpanded = auto()
    VehicleCompaniesNew = auto()
