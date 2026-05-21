from __future__ import annotations

import numpy as np


def get_active_mask(context, n_hits: int):
    mask = context.get("active_mask")
    if mask is None:
        return np.ones(int(n_hits), dtype=bool)
    arr = np.asarray(mask, dtype=bool)
    if arr.shape[0] != int(n_hits):
        raise ValueError(f"active_mask length {arr.shape[0]} does not match n_hits={n_hits}")
    return arr
