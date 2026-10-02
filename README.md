# California Open Water Data Atlas

A multi-page atlas of California's Open and Transparent Water Data Act (AB 1755, 2016; Water Code §12400 et seq.): the law, the April 2018 Strategic Plan, and the state of implementation since.

**Live site:** https://ggearheart.github.io/CA_Open_Water_Data_Atlas/

## Structure

- `index.html` — atlas landing page
- `plates/` — one page per plate (I The Law, II The Plan, III Timeline, IV Scorecard, V Ecosystem, VI Today)
- `data/strategic_actions.csv` — the plan's 49 strategic actions; the scorecard's source of truth
- `assets/` — shared CSS and JS (no build step, no dependencies)
- `sources/` — source documents (Strategic Plan PDF + extracted text)

## Run locally

Pages load CSV with `fetch`, so serve over HTTP:

```bash
python3 -m http.server 8057
```

Not an official State publication. Status judgments are drafts and open to correction.
