# Daytime Magnet

*"Job magnet or bedroom community?" — Weekday population swing using Census commuter data.*

---

## Status: LIVE

**Live URL:** https://justincgohn.github.io/daytime-magnet/
**GitHub repo:** https://github.com/justincgohn/daytime-magnet
**Added to:** https://justingohn.com/builds.html
**Deployed:** February 2026

---

## Quick Reference

| Doc | Purpose |
|-----|---------|
| `spec.md` | Full requirements, design decisions |
| `data/scripts/process_lodes.py` | Download + aggregate LODES OD data to county-level JSON |

---

## What This Tool Does

Enter a county → see weekday population swing (3,143 counties).

- Hero stat: "+X% weekday population swing" with national percentile
- Diverging bar: in-commuters vs out-commuters vs internal workers
- Top 5 origin counties (where workers come from)
- Top 5 destination counties (where residents go to work)
- Insight callout: "Job Magnet" / "Bedroom Community" / "Self-Contained"

---

## Data Source

**Census LEHD LODES v8 (Origin-Destination Employment Statistics)**

| Detail | Value |
|--------|-------|
| URL | https://lehd.ces.census.gov/data/ |
| Geography | Census block → aggregated to county |
| Year | 2023 (48 states), 2021 (AK, MI) |
| Job type | JT01 (primary jobs) |
| Processing | DuckDB for block-to-county aggregation |

---

## Project Structure

```
Daytime Magnet/
├── CLAUDE.md
├── spec.md
├── data/
│   ├── raw/               ← LODES downloads (.csv.gz) — gitignored
│   ├── processed/         ← commuter_data.json, county_list.json
│   └── scripts/
│       └── process_lodes.py
└── docs/                  ← Frontend (GitHub Pages)
    ├── index.html
    ├── styles.css
    ├── app.js
    └── data/
        ├── commuter_data.json (2.6 MB)
        └── county_list.json (0.2 MB)
```

---

## Data Pipeline

```bash
cd data/scripts && python3 process_lodes.py
```

Downloads ~700MB of LODES files, aggregates with DuckDB, outputs JSON.

---

## v2 Path

Change `geocode[:5]` (county) to `geocode[:11]` (tract) for tract-level drill-down.

---

*Created: February 22, 2026*
*Deployed: February 22, 2026*
