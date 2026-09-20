"""Frozen P0 contract constants. Do not change without a new ADR."""

from __future__ import annotations

from pathlib import Path
from typing import Final, Literal

SCHEMA_VERSION: Final = "1.0.0"
CORE_VERSION: Final = "1.0.0"
CONTRACT_STAGE: Final = "P10"

GUIDE_DIR: Final = Path(__file__).resolve().parents[2] / "2D-Shell-Project_Math-Core-Guide"
P0_DIR: Final = GUIDE_DIR / "00_P0_范围与合同"
P0_SCHEMA_PATH: Final = P0_DIR / "schema" / "shell-core-contract.schema.json"
PACKAGED_SCHEMA_PATH: Final = (
    Path(__file__).resolve().parent / "data" / "shell-core-contract.schema.json"
)
P0_EXAMPLE_DIR: Final = P0_DIR / "examples"


def resolve_contract_schema_path() -> Path:
    """Prefer the packaged schema so an installed wheel does not need the repo."""

    if PACKAGED_SCHEMA_PATH.is_file():
        return PACKAGED_SCHEMA_PATH
    if P0_SCHEMA_PATH.is_file():
        return P0_SCHEMA_PATH
    raise FileNotFoundError(
        "Frozen P0 schema is not packaged and the repository copy was not found"
    )


CONTRACT_SCHEMA_PATH: Final = PACKAGED_SCHEMA_PATH

ID_PATTERN: Final = r"^[A-Za-z][A-Za-z0-9_.:-]{0,63}$"

GLOBAL_DOF_ORDER: Final = ("UX", "UY", "UZ", "RX", "RY", "RZ")
LOCAL_DOF_ORDER: Final = ("u'", "v'", "w'", "theta_x'", "theta_y'")
DOF_PER_NODE_GLOBAL: Final = 6
DOF_PER_NODE_LOCAL: Final = 5
NODES_PER_Q4: Final = 4

DofName = Literal["UX", "UY", "UZ", "RX", "RY", "RZ"]
DOF_OFFSET: Final[dict[str, int]] = {
    "UX": 0,
    "UY": 1,
    "UZ": 2,
    "RX": 3,
    "RY": 4,
    "RZ": 5,
}

Q4_NATURAL_NODES: Final = (
    (-1.0, -1.0),
    (1.0, -1.0),
    (1.0, 1.0),
    (-1.0, 1.0),
)
Q4_LOCAL_EDGES: Final = ((0, 1), (1, 2), (2, 3), (3, 0))
GAUSS_2X2_ABSCISSA: Final = 3.0**-0.5
GAUSS_2X2_POINTS: Final = (
    (-GAUSS_2X2_ABSCISSA, -GAUSS_2X2_ABSCISSA),
    (GAUSS_2X2_ABSCISSA, -GAUSS_2X2_ABSCISSA),
    (GAUSS_2X2_ABSCISSA, GAUSS_2X2_ABSCISSA),
    (-GAUSS_2X2_ABSCISSA, GAUSS_2X2_ABSCISSA),
)
GAUSS_POINT_IDS: Final = ("G1", "G2", "G3", "G4")

SI_UNITS: Final[dict[str, str]] = {
    "system": "SI",
    "length": "m",
    "angle": "rad",
    "force": "N",
    "moment": "N*m",
    "bending_resultant": "N",
    "stress": "Pa",
    "line_load": "N/m",
    "surface_load": "N/m^2",
    "body_force": "N/m^3",
    "energy": "J",
}

# ADR-006 strict_flat_q4_v1
WARP_WARNING: Final = 1e-10
WARP_ERROR: Final = 1e-8
EDGE_RATIO_ERROR: Final = 1e-10
JHAT_WARNING: Final = 1e-10
JHAT_ERROR: Final = 1e-12
RJ_WARNING: Final = 0.10
COLLINEAR_AREA_RATIO: Final = 1e-10

PRODUCTION_SHEAR: Final = "qlll_assumed_strain"
PRODUCTION_DRILLING: Final = "continuum_consistent"
VERIFICATION_SHEAR: Final = "raw_q4_full"
VERIFICATION_DRILLING: Final = "none"
