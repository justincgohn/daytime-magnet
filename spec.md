# Daytime Magnet — Specification

## Concept

Enter a county → see weekday population swing (in-commuters vs out-commuters). "Job magnet or bedroom community?" using Census LEHD LODES commuter data.

## Data Source

Census LEHD LODES v8 Origin-Destination Employment Statistics
- URL: https://lehd.ces.census.gov/data/
- Geography: Census block → aggregated to county (first 5 digits of geocode)
- Year: 2023 (48 states), 2021 (AK, MI)
- Job type: JT01 (primary jobs)
- Files: od_main (intra-state) + od_aux (cross-state commuting)

## Metrics

| Metric | Definition |
|--------|-----------|
| internal | Workers who live AND work in same county |
| employed_here | Total jobs in county = internal + in_commuters |
| live_here | Total workers residing in county = internal + out_commuters |
| in_commuters | Workers coming from other counties = employed_here - internal |
| out_commuters | Residents going to other counties = live_here - internal |
| net_swing_pct | (in_commuters - out_commuters) / live_here * 100 |

## Classification

| Category | Threshold |
|----------|-----------|
| Job Magnet | net_swing_pct > +5% |
| Self-Contained | -5% to +5% |
| Bedroom Community | net_swing_pct < -5% |

## Visualization

- Amber/orange theme (#f59e0b primary)
- Hero stat: large swing percentage + classification badge
- Percentile bar (position relative to all US counties)
- 3 stat cards: Work Here / Live Here / Live & Work Here
- Horizontal stacked bar: out-commuters (indigo, negative) | internal (gray) | in-commuters (amber, positive)
- Flow tables: Top 5 origins + Top 5 destinations, county names clickable
- Insight callout: dynamic text based on swing magnitude

## Technical

- Static site: HTML/CSS/JS + Chart.js
- Data: Pre-processed JSON (~1.5MB commuter_data.json + ~175KB county_list.json)
- Processing: DuckDB for aggregation (handles 100M+ block-level rows)
- Hosting: GitHub Pages from /docs

## v2 Path

Change geocode[:5] (county) to geocode[:11] (tract) for tract-level drill-down. Output per-county tract JSON files loaded on demand.
