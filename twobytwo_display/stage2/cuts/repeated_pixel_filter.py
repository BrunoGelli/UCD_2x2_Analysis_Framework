from __future__ import annotations

from typing import Any, MutableMapping

import numpy as np

from ..masking import get_active_mask
from ..pipeline import CutStep, ParamSpec, StepResult


class RepeatedPixelFilter(CutStep):
    name = "repeated_pixel_filter"
    param_specs = [
        ParamSpec("max_hits_per_pixel", 10, "Deactivate pixels above this occupancy", label="Max hits per pixel", kind="int", step=1),
        ParamSpec("pixel_fields", "y,z", "Comma-separated fields defining a pixel", label="Pixel fields", kind="str"),
        ParamSpec("round_decimals", 3, "Decimals for rounding float fields", label="Round decimals", kind="int", step=1),
    ]

    def run(self, context: MutableMapping[str, Any]) -> StepResult:
        hits = context.get("hits")
        if hits is None or len(hits) == 0:
            return StepResult({
                "active_mask": np.zeros(0, dtype=bool),
                "repeated_pixel_mask": np.zeros(0, dtype=bool),
                "n_repeated_pixel_hits": 0,
                "n_repeated_pixels": 0,
            })

        n_hits = len(hits)
        active_mask = get_active_mask(context, n_hits).copy()
        repeated_mask = np.zeros(n_hits, dtype=bool)

        field_names = [s.strip() for s in str(self.params.get("pixel_fields", "y,z")).split(",") if s.strip()]
        if not field_names:
            raise ValueError("repeated_pixel_filter requires at least one field in pixel_fields")

        names = hits.dtype.names or ()
        for f in field_names:
            if f not in names:
                raise ValueError(f"repeated_pixel_filter missing pixel field '{f}'")

        round_decimals = int(self.params.get("round_decimals", 3))
        parts = []
        for f in field_names:
            col = hits[f]
            if np.issubdtype(col.dtype, np.floating):
                col = np.round(col.astype(float), decimals=round_decimals)
            parts.append(col)

        keys = list(zip(*parts))
        active_idx = np.where(active_mask)[0]
        if len(active_idx) == 0:
            return StepResult({
                "active_mask": active_mask,
                "repeated_pixel_mask": repeated_mask,
                "n_repeated_pixel_hits": 0,
                "n_repeated_pixels": 0,
            })

        limit = int(self.params.get("max_hits_per_pixel", 10))
        counts = {}
        for i in active_idx:
            k = keys[int(i)]
            counts[k] = counts.get(k, 0) + 1

        repeated_keys = {k for k, c in counts.items() if c > limit}
        if repeated_keys:
            for i in active_idx:
                if keys[int(i)] in repeated_keys:
                    repeated_mask[int(i)] = True
            active_mask[repeated_mask] = False

        return StepResult({
            "active_mask": active_mask,
            "repeated_pixel_mask": repeated_mask,
            "n_repeated_pixel_hits": int(np.sum(repeated_mask)),
            "n_repeated_pixels": int(len(repeated_keys)),
        })
