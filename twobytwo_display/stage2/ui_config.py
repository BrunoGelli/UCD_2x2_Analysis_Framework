from __future__ import annotations

from typing import Any, Dict, Mapping, MutableMapping


DBSCAN_STEP_NAME = "dbscan_cluster_producer"


def build_stage2_config_from_dbscan_values(values: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "pipeline": [
            {
                "name": DBSCAN_STEP_NAME,
                "enabled": bool(values.get("show_clusters", False)),
                "params": {
                    "eps_cm": float(values.get("eps_cm", 1.5)),
                    "min_samples": int(values.get("min_samples", 10)),
                    "cluster_min_hits": int(values.get("cluster_min_hits", 20)),
                    "cluster_max_extent_cm": float(values.get("cluster_max_extent_cm", 8.0)),
                },
            }
        ]
    }


def apply_stage2_config_to_dbscan_values(config: Mapping[str, Any], values: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    steps = config.get("pipeline", [])
    if not isinstance(steps, list):
        return values
    for step in steps:
        if not isinstance(step, Mapping):
            continue
        if step.get("name") != DBSCAN_STEP_NAME:
            continue
        values["show_clusters"] = bool(step.get("enabled", True))
        params = step.get("params", {})
        if isinstance(params, Mapping):
            if "eps_cm" in params:
                values["eps_cm"] = float(params["eps_cm"])
            if "min_samples" in params:
                values["min_samples"] = int(params["min_samples"])
            if "cluster_min_hits" in params:
                values["cluster_min_hits"] = int(params["cluster_min_hits"])
            if "cluster_max_extent_cm" in params:
                values["cluster_max_extent_cm"] = float(params["cluster_max_extent_cm"])
    return values
