# California Open Water Data Atlas

A multi-page atlas of California's Open and Transparent Water Data Act (AB 1755, 2016; Water Code §12400 et seq.): the law, the April 2018 Strategic Plan, and the state of implementation since.

**Live site:** https://ggearheart.github.io/CA_Open_Water_Data_Atlas/

## Structure

- `index.html` — atlas landing page
- `plates/` — one page per plate (I The Law, II The Plan, III Timeline, IV Scorecard, V Ecosystem, VI Today, VII Dashboard)
- `data/strategic_actions.csv` — the plan's 49 strategic actions; the scorecard's source of truth
- `data/water_datasets.csv` — every dataset in the Water group on data.ca.gov and data.cnra.ca.gov, with publisher, topic, page views and its federated twin on the other portal (Plate VII)
- `scripts/build_water_dashboard_data.py` — rebuilds that CSV from the two CKAN APIs (stdlib Python, ~4 min)
- `assets/` — shared CSS and JS (no build step, no dependencies)
- `sources/` — source documents (Strategic Plan PDF + extracted text)

## Refresh the dashboard data

```bash
python3 scripts/build_water_dashboard_data.py
```

## Run locally

Pages load CSV with `fetch`, so serve over HTTP:

```bash
python3 -m http.server 8057
```

Not an official State publication. Status judgments are drafts and open to correction.
