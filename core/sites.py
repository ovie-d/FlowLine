"""Group incidents that share a physical site (station, facility) into site ids.

Many CER incidents at compressor or meter stations report the station's
coordinates, so 427 rows share exact coordinates with another row. Area-history
features count *sites*, not rows, so one busy facility is not many locations.

Leader clustering: points are visited in a fixed order; each joins the first
existing site whose leader lies within `radius_km`, else starts a new site.
Unlike single-linkage, sites cannot chain along a pipeline.
"""

from __future__ import annotations

import numpy as np

from core.geo import haversine_km

SITE_RADIUS_KM = 1.0


def assign_sites(
    lat: np.ndarray, lon: np.ndarray, radius_km: float = SITE_RADIUS_KM
) -> np.ndarray:
    """Return an integer site id per point (0-based, in visiting order)."""
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    order = np.lexsort((lon, lat))
    leader_lat: list[float] = []
    leader_lon: list[float] = []
    site = np.empty(len(lat), dtype=int)
    for i in order:
        if leader_lat:
            d = haversine_km(lat[i], lon[i], np.array(leader_lat), np.array(leader_lon))
            j = int(np.argmin(d))
            if d[j] <= radius_km:
                site[i] = j
                continue
        site[i] = len(leader_lat)
        leader_lat.append(float(lat[i]))
        leader_lon.append(float(lon[i]))
    return site
