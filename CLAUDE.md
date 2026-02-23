# Daytime Magnet

*"Job magnet or bedroom community?" — Weekday population swing using Census commuter data.*

---

## Quick Reference

| Doc | Purpose |
|-----|---------|
| `spec.md` | Full requirements, design decisions, user flow, edge cases |
| `data/scripts/process_lodes.py` | Download + aggregate LODES OD data to county-level JSON |

---

## Status

**Phase 1 (Spec):** In progress
**Phase 2 (Data pipeline):** Not started
**Phase 3 (Frontend):** Not started
**Phase 4 (Deploy):** Not started

**Target URL:** https://justincgohn.github.io/daytime-magnet/
**Repo:** https://github.com/justincgohn/daytime-magnet (not yet created)
**Add to:** https://justingohn.com/builds.html

---

## What This Tool Does

Enter a county → see weekday population swing.

**v1 (county level):**
- One big stat: "+X% weekday population swing" with national percentile
- Diverging bar or Venn: in-commuters vs out-commuters vs internal workers
- Top 5 origin counties (where workers come from)
- Top 5 destination counties (where residents go to work)
- Insight callout: "Job Magnet" / "Bedroom Community" / "Self-Contained" classification

**v2 (tract-level drill-down) — FUTURE:**
- Click into a county → see which tracts are the real job magnets
- Tract-level heatmap or ranked list within county
- Requires separate tract-level JSON, loaded on demand
- Design v1 data pipeline and JSON schema to support this upgrade path

---

## Data Source

**Census LEHD LODES v8.4 (Origin-Destination Employment Statistics)**

| Detail | Value |
|--------|-------|
| URL | https://lehd.ces.census.gov/data/ |
| Geography | Census block (aggregate to county via crosswalk) |
| Time range | 2002-2023 (most recent release: Dec 2025) |
| Format | Compressed CSV (.csv.gz), state-based files |
| Cost | Free |
| Gaps | Alaska + Michigan missing from 2023; fall back to 2022 |

**OD file columns used:**
- `w_geocode` — workplace census block (first 5 digits = county FIPS)
- `h_geocode` — home/residence census block (first 5 digits = county FIPS)
- `S000` — total jobs
- `SE01/SE02/SE03` — jobs by earnings bracket (v2 potential)
- `SI01/SI02/SI03` — jobs by industry sector (v2 potential)

**File types needed:**
- `od_main` — both home and work in same state
- `od_aux` — work in-state, home in different state (critical for cross-border commuting)

---

## Data Pipeline

**Processing approach:** One-time Python batch job → static JSON for frontend.

1. Download all 50 state OD files (main + aux) for 2023 (2022 for AK/MI)
2. Extract county FIPS from h_geocode and w_geocode (first 5 digits)
3. Group by (home_county, work_county), sum S000
4. For each county compute: employed_here, live_here, in_commuters, out_commuters, internal, net_swing_pct
5. Capture top 5 origin counties and top 5 destination counties
6. Export to JSON

**v2 pipeline extension:** Same process but aggregate to tract (first 11 digits) instead of county (first 5). Store as separate per-county JSON files loaded on demand.

---

## Project Structure

```
Daytime Magnet/
├── CLAUDE.md              ← This file
├── spec.md                ← Full specification (create via iterative questioning)
├── data/
│   ├── raw/               ← LODES downloads (.csv.gz) — gitignored
│   ├── processed/
│   │   ├── commuter_data.json
│   │   └── county_list.json
│   └── scripts/
│       └── process_lodes.py
└── docs/                  ← Frontend (GitHub Pages serves from /docs)
    ├── index.html
    ├── styles.css
    ├── app.js
    └── data/
        ├── commuter_data.json
        └── county_list.json
```

---

## Deployment Checklist

- [ ] Create GitHub repo: `justincgohn/daytime-magnet`
- [ ] Enable GitHub Pages from `/docs` branch
- [ ] Verify live at https://justincgohn.github.io/daytime-magnet/
- [ ] Add to https://justingohn.com/builds.html

---

## Key Decisions Still Needed (spec.md)

- Exact visualization: diverging bar vs Venn vs something else?
- Classification thresholds: what net swing % = "Job Magnet" vs "Bedroom Community"?
- Time series: show swing % change over 2002-2023, or just latest year?
- County-to-county flow detail: top 5 or top 10?
- How to handle counties with very few workers (suppress or caveat?)

---

## Patterns (from prior tools)

- **Architecture:** Vanilla HTML/CSS/JS, Chart.js, pre-processed JSON, GitHub Pages
- **County search:** Autocomplete from county_list.json (~3,100 entries)
- **FIPS handling:** Use plain 5-digit FIPS (no underscores). Learned from Peak Business Calculator bug.
- **Design:** Minimal, clean, responsive. Match existing tools' visual language.
- **Attribution:** "Data source: U.S. Census Bureau LEHD" in footer

---

*Created: February 22, 2026*
