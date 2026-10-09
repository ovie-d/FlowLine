# Data guide

Two kinds of data live here:

- **Bundled seed (committed):** a 2015-through-August-2026 Alberta subset of the CER
  Pipeline Incident Data, used by the **Risk Ranking** tab (the original v1 product).
- **Shipped derived data (committed):** `data/processed/incident_weather.csv` (station
  weather around each incident, derived from ECCC Historical Climate Data) and
  `data/processed/pipelines_ca.geojson` (CER pipeline systems). These make every install
  match the reference build without the hour-long weather download.
- **Downloaded on first run (not committed):** the full national CER incident file and
  data dictionary (`data/raw/`) and the Alberta OpenStreetMap extract (`data/osm/`). The
  raw ECCC station files (`data/weather/`) are only needed to regenerate the weather CSV
  (`python -m scripts.fetch_weather`). The **Hazard Forecast** and its database are built
  by `start.sh` (`python -m scripts.load_postgres`).

---

## Bundled seed

| File | What it is |
|---|---|
| `cer_pipeline_incidents_alberta_2015.csv` | 313 Alberta incidents, 2015 through August 2026, 128 corridors |

Columns: `date`, `company` (short name), `corridor` (nearest town), `substance`, `release_m3`, `incident_type`, `cause`, `latitude`, `longitude`, `consequence`.

- **`company`:** shortened for readability (`NOVA Gas` covers NOVA Gas Transmission Ltd. and NGTL; `Keystone` is TransCanada Keystone; `Spectra` is Westcoast/Spectra). Full names are in the source file.
- **`corridor`:** nearest populated centre with the province suffix stripped (`Grand Prairie` fixed to `Grande Prairie`). Good enough to score hotspots; not a surveyed address.
- **`consequence`:** a **lab label**, not a regulator risk model.
  - `high` - sour gas or crude substance, or release of 100 m³ or more, or explosion / fatality
  - `medium` - other releases (sweet gas, NGLs, smaller spills)
  - `low` - fires or limit breaches with no substance released
- **Dropped rows:** 141 Alberta records with no usable occurrence date were excluded (mostly serious-injury filings with no timestamp). `release_m3` is empty where nothing was released.

---

## Primary source

**Canada Energy Regulator - Pipeline Incident Data (2008 to current, updated quarterly)**

- **CSV:** https://www.cer-rec.gc.ca/open/incident/pipeline-incidents-comprehensive-data.csv
- **Dictionary:** https://www.cer-rec.gc.ca/open/incident/pipeline-incidents-data-dictionary.csv
- **Portal:** https://open.canada.ca/data/en/dataset/7dffedc4-23fa-440c-a36d-adf5a6cc09f1
- **Licence:** [Open Government Licence - Canada](https://open.canada.ca/en/open-government-licence-canada)

Do not commit the full national file if you re-download it; this seed is Alberta, 2015 through August 2026.

---

## Loading example

```python
import pandas as pd

df = pd.read_csv("data/cer_pipeline_incidents_alberta_2015.csv", parse_dates=["date"])
print(df["consequence"].value_counts())
print(df["date"].dt.year.value_counts().sort_index())
```

---

## Citation

Canada Energy Regulator. Pipeline Incident Data. https://www.cer-rec.gc.ca/open/incident/pipeline-incidents-comprehensive-data.csv (Alberta slice, 2015 through August 2026, pulled September 2026).
