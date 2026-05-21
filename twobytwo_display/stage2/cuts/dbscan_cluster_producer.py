from __future__ import annotations

from typing import Any, MutableMapping

from ...clustering import dbscan_clusters
from ...selection import muon_region_labels
from ..pipeline import CutStep, ParamSpec, StepResult


class DBSCANClusterProducer(CutStep):
    name = "dbscan_cluster_producer"
    param_specs = [
        ParamSpec("eps_cm", 1.5, "DBSCAN neighborhood radius in cm", label="DBSCAN eps [cm]", kind="float", step=0.1),
        ParamSpec("min_samples", 10, "DBSCAN min_samples", label="DBSCAN min_samples", kind="int", step=1),
        ParamSpec("cluster_min_hits", 20, "Minimum hits to keep a cluster", label="Keep nhits ≥", kind="int", step=1),
        ParamSpec("cluster_max_extent_cm", 8.0, "Maximum extent to keep a cluster", label="Keep max extent ≤ [cm]", kind="float", step=0.5),
    ]

    def run(self, context: MutableMapping[str, Any]) -> StepResult:
        hits = context.get("hits")
        muon_track = context.get("muon_track")
        if hits is None:
            return StepResult({"clusters": []})

        labels = muon_region_labels(hits, muon_track, r_core=5.0, r_near=25.0)
        mask_far = labels == 2
        clusters = dbscan_clusters(
            hits,
            eps_cm=float(self.params.get("eps_cm", 1.5)),
            min_samples=int(self.params.get("min_samples", 10)),
            mask=mask_far,
        )
        clusters = [
            c
            for c in clusters
            if c.n_hits >= int(self.params.get("cluster_min_hits", 20))
            and c.extent_max_cm <= float(self.params.get("cluster_max_extent_cm", 8.0))
        ]
        return StepResult({"clusters": clusters})
