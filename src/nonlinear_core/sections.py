"""Validation of the optional Studio section library and its materialized properties."""

from __future__ import annotations

from math import isclose, isfinite, pi
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from nonlinear_core.model import ModelInput

Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]


class SectionDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Annotated[str, Field(min_length=1, max_length=80)]
    name: Annotated[str, Field(min_length=1, max_length=80)]
    shape: Literal["custom", "rectangle", "circle", "i_section", "tube", "thickness"]
    dimensions: dict[str, Positive]

    def properties(self) -> dict[str, float]:
        d = self.dimensions
        keys = {
            "custom": {"area", "second_moment"},
            "rectangle": {"width", "height"},
            "circle": {"diameter"},
            "tube": {"outer_diameter", "wall_thickness"},
            "i_section": {"width", "height", "web_thickness", "flange_thickness"},
            "thickness": {"thickness"},
        }
        if set(d) != keys[self.shape]:
            raise ValueError(f"Section {self.id}: unexpected or missing dimensions")
        if self.shape in {"custom", "thickness"}:
            return d
        if self.shape == "rectangle":
            return {
                "area": d["width"] * d["height"],
                "second_moment": d["width"] * d["height"] ** 3 / 12,
            }
        if self.shape == "circle":
            return {
                "area": pi * d["diameter"] ** 2 / 4,
                "second_moment": pi * d["diameter"] ** 4 / 64,
            }
        if self.shape == "tube":
            outer, wall = d["outer_diameter"], d["wall_thickness"]
            if 2 * wall >= outer:
                raise ValueError("Tube wall must be less than half the outer diameter")
            inner = outer - 2 * wall
            return {
                "area": pi * (outer**2 - inner**2) / 4,
                "second_moment": pi * (outer**4 - inner**4) / 64,
            }
        width, height = d["width"], d["height"]
        web, flange = d["web_thickness"], d["flange_thickness"]
        if 2 * flange >= height or web >= width:
            raise ValueError("I-section flanges and web must fit inside the section")
        inner_height = height - 2 * flange
        return {
            "area": 2 * width * flange + inner_height * web,
            "second_moment": (width * height**3 - (width - web) * inner_height**3) / 12,
        }


class SectionLibrary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definitions: Annotated[list[SectionDefinition], Field(max_length=1000)]
    default_id: str | None

    @model_validator(mode="after")
    def check_ids(self):
        ids = [section.id for section in self.definitions]
        if len(set(ids)) != len(ids):
            raise ValueError("Section IDs must be unique")
        if self.default_id is not None and self.default_id not in ids:
            raise ValueError("Default section must refer to an existing section")
        return self


def validate_sections(model: ModelInput) -> None:
    raw = model.extensions.get("section_library")
    if raw is None:
        return  # Legacy element properties remain authoritative without a library.
    library = SectionLibrary.model_validate(raw)
    properties = {}
    for section in library.definitions:
        if not section.name.strip():
            raise ValueError("Section name cannot be blank")
        if (section.shape == "thickness") == (model.model_family.value == "frame"):
            raise ValueError("Section shape is incompatible with this model family")
        try:
            properties[section.id] = section.properties()
            if any(not isfinite(value) or value <= 0 for value in properties[section.id].values()):
                raise ValueError("Section properties must be positive and finite")
        except OverflowError as error:
            raise ValueError("Section dimensions exceed the numeric range") from error
    for element in model.elements:
        section_id = element.extensions.get("section_id")
        if section_id is None:
            continue
        if not isinstance(section_id, str) or section_id not in properties:
            raise ValueError(f"Element {element.id} references an unknown section")
        for key, expected in properties[section_id].items():
            actual = element.properties.get(key)
            if not isinstance(actual, (int, float)) or not isclose(
                actual, expected, rel_tol=1e-10, abs_tol=1e-15
            ):
                raise ValueError(f"Element {element.id} {key} differs from its section")
