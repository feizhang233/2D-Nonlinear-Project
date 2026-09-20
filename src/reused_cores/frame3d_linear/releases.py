"""A02: simultaneous stiffness/load condensation and internal-angle recovery."""

from dataclasses import dataclass

import numpy as np

from .models import array


@dataclass(frozen=True, slots=True)
class CondensedElement:
    stiffness: np.ndarray
    load: np.ndarray
    retained: np.ndarray
    released: np.ndarray
    recovery_matrix: np.ndarray
    recovery_load: np.ndarray

    def recover(self, local_displacements):
        d = array("local_displacements", local_displacements, (12,)).copy()
        if self.released.size:
            d[self.released] = self.recovery_load - self.recovery_matrix @ d[self.retained]
        return d


def condense_releases(stiffness, load, releases=()):
    k = array("stiffness", stiffness, (12, 12))
    f = array("load", load, (12,))
    raw = tuple(releases)
    if len(set(raw)) != len(raw) or any(
        isinstance(i, (bool, np.bool_))
        or not isinstance(i, (int, np.integer))
        or i not in (3, 4, 5, 9, 10, 11)
        for i in raw
    ):
        raise ValueError("releases must be unique local rotational indices")
    r = np.array(sorted(raw), dtype=int)
    p = np.array([i for i in range(12) if i not in raw], dtype=int)
    if not r.size:
        return CondensedElement(k.copy(), f.copy(), p, r, np.empty((0, 12)), np.empty(0))
    krr = k[np.ix_(r, r)]
    scale = np.sqrt(np.diag(krr))
    if np.any(scale <= 0) or np.linalg.eigvalsh(krr / np.outer(scale, scale))[0] <= 1e-12:
        raise ValueError("singular release block K_rr; release set contains an internal mechanism")
    a = np.linalg.solve(krr, k[np.ix_(r, p)])
    b = np.linalg.solve(krr, f[r])
    kc, fc = np.zeros((12, 12)), np.zeros(12)
    block = k[np.ix_(p, p)] - k[np.ix_(p, r)] @ a
    kc[np.ix_(p, p)] = (block + block.T) / 2
    fc[p] = f[p] - k[np.ix_(p, r)] @ b
    return CondensedElement(kc, fc, p, r, a, b)
