"""Roundoff-aware work/energy comparison without mixing force and moment units."""

import numpy as np


def energy_check(energy, work, displacement, stiffness, work_magnitude):
    """Return adjusted relative error, absolute error [J], roundoff budget [J].

    Prescribed rigid motion can make work a cancellation of much larger terms.
    Bound matrix-vector/dot-product roundoff using their absolute magnitudes;
    retain the unadjusted absolute error so this allowance stays inspectable.
    """
    magnitude = float(np.abs(displacement) @ np.abs(stiffness) @ np.abs(displacement))
    budget = 64 * np.finfo(float).eps * (magnitude + abs(work_magnitude))
    error = abs(2 * energy - work)
    ratio = max(0.0, error - budget) / max(1e-12, abs(2 * energy), abs(work))
    return float(ratio), float(error), float(budget)
