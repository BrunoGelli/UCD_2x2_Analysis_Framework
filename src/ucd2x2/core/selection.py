from __future__ import annotations

import numpy as np


def _point_to_segment_distance(P, A, B):
    AB = B - A
    AP = P - A
    denom = float(np.dot(AB, AB))
    if denom <= 0:
        return np.linalg.norm(P - A, axis=1)
    t = (AP @ AB) / denom
    t = np.clip(t, 0.0, 1.0)
    proj = A + t[:, None] * AB[None, :]
    return np.linalg.norm(P - proj, axis=1)


def muon_region_labels(hits, muon_track, r_core=5.0, r_near=25.0):
    if muon_track is None or len(hits) == 0:
        return np.full(len(hits), 2, dtype=np.int8)
    A = np.array([muon_track["x_start"], muon_track["y_start"], muon_track["z_start"]], dtype=float)
    B = np.array([muon_track["x_end"], muon_track["y_end"], muon_track["z_end"]], dtype=float)
    P = np.vstack([hits["x"], hits["y"], hits["z"]]).T.astype(float)
    d = _point_to_segment_distance(P, A, B)
    lab = np.full(len(hits), 2, dtype=np.int8)
    lab[d <= r_near] = 1
    lab[d <= r_core] = 0
    return lab
