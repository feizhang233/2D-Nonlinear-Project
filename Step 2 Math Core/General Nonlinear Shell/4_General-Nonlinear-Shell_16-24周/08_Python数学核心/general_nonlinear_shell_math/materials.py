"""Immutable one-dimensional bilinear plasticity trial/commit primitive."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MaterialState1D:
    plastic_strain: float = 0.0
    accumulated_plastic_strain: float = 0.0
    stress: float = 0.0


@dataclass(frozen=True)
class MaterialResponse1D:
    trial_stress: float
    yield_function_trial: float
    plastic_multiplier: float
    stress: float
    algorithmic_tangent: float
    trial_state: MaterialState1D
    yielded: bool


@dataclass(frozen=True)
class BilinearIsotropic1D:
    elastic_modulus: float
    hardening_modulus: float
    yield_stress: float

    def __post_init__(self) -> None:
        if not np.isfinite(self.elastic_modulus) or self.elastic_modulus <= 0.0:
            raise ValueError("elastic_modulus must be finite and positive")
        if not np.isfinite(self.hardening_modulus) or self.hardening_modulus < 0.0:
            raise ValueError("hardening_modulus must be finite and nonnegative")
        if not np.isfinite(self.yield_stress) or self.yield_stress <= 0.0:
            raise ValueError("yield_stress must be finite and positive")

    def evaluate(
        self, total_strain: float, committed: MaterialState1D
    ) -> MaterialResponse1D:
        """Evaluate a trial state without mutating ``committed``."""

        strain = float(total_strain)
        if not np.isfinite(strain):
            raise ValueError("total_strain must be finite")
        trial_stress = self.elastic_modulus * (strain - committed.plastic_strain)
        current_yield = (
            self.yield_stress
            + self.hardening_modulus * committed.accumulated_plastic_strain
        )
        yield_function = abs(trial_stress) - current_yield
        if yield_function <= 0.0:
            trial_state = MaterialState1D(
                plastic_strain=committed.plastic_strain,
                accumulated_plastic_strain=committed.accumulated_plastic_strain,
                stress=trial_stress,
            )
            return MaterialResponse1D(
                trial_stress=trial_stress,
                yield_function_trial=yield_function,
                plastic_multiplier=0.0,
                stress=trial_stress,
                algorithmic_tangent=self.elastic_modulus,
                trial_state=trial_state,
                yielded=False,
            )

        sign = 1.0 if trial_stress >= 0.0 else -1.0
        plastic_multiplier = yield_function / (
            self.elastic_modulus + self.hardening_modulus
        )
        plastic_strain = committed.plastic_strain + plastic_multiplier * sign
        accumulated = committed.accumulated_plastic_strain + plastic_multiplier
        stress = trial_stress - self.elastic_modulus * plastic_multiplier * sign
        tangent = (
            self.elastic_modulus
            * self.hardening_modulus
            / (self.elastic_modulus + self.hardening_modulus)
        )
        trial_state = MaterialState1D(
            plastic_strain=plastic_strain,
            accumulated_plastic_strain=accumulated,
            stress=stress,
        )
        return MaterialResponse1D(
            trial_stress=trial_stress,
            yield_function_trial=yield_function,
            plastic_multiplier=plastic_multiplier,
            stress=stress,
            algorithmic_tangent=tangent,
            trial_state=trial_state,
            yielded=True,
        )

    @staticmethod
    def commit(response: MaterialResponse1D) -> MaterialState1D:
        return response.trial_state

    @staticmethod
    def rollback(committed: MaterialState1D) -> MaterialState1D:
        return committed
