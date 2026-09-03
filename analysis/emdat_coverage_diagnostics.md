# V2 — EM-DAT coverage and administrative geocoding

Source files: `data/raw/validation/emdat_{country}.csv`, written by `src/downloaders/emdat_downloader.py` at Stage 1. Descriptive only.

**Inclusion criteria actually applied by the downloader.** `filter_and_split_by_country` filters the EM-DAT Archive on two conditions only: `ISO` equals the country code, and `Disaster Type` is one of `Drought`, `Extreme temperature`, `Flood`, `Storm`. It applies **no** &ge;10-deaths / &ge;100-affected / declared-emergency threshold of its own — that quadruple criterion is EM-DAT's own database-entry rule, already satisfied by every row in the Archive. The “eligible events” count below is therefore the full type-filtered row count. The severity-signal breakdown that follows is reported separately, and is lower than the row count mainly because pre-1990 events often carry no recorded deaths or affected figure.

## 1. Eligible events (type-filtered row count)

| country | eligible events | year span | Drought | Extreme temp. | Flood | Storm |
| --- | --- | --- | --- | --- | --- | --- |
| Brazil | 239 | 1948–2024 | 22 | 7 | 185 | 25 |
| Portugal | 38 | 1941–2024 | 4 | 9 | 13 | 12 |
| India | 622 | 1900–2024 | 16 | 64 | 327 | 215 |

## 2. Severity signal present in the columns we hold

| country | events | deaths ≥ 10 | affected ≥ 100 | Declaration = Yes | OFDA/BHA = Yes | ≥ 1 signal |
| --- | --- | --- | --- | --- | --- | --- |
| Brazil | 239 | 126 | 205 | 67 | 31 | 227 (95.0%) |
| Portugal | 38 | 16 | 16 | 0 | 6 | 24 (63.2%) |
| India | 622 | 540 | 371 | 7 | 42 | 613 (98.6%) |

`Appeal = Yes` is 0 in all three countries, so it is omitted from the table.

## 3. Usable location fields (country level and below)

| country | events | free-text `Location` | `GADM Admin Units` | point `Latitude`/`Longitude` |
| --- | --- | --- | --- | --- |
| Brazil | 239 | 225 (94.1%) | 124 (51.9%) | 29 (12.1%) |
| Portugal | 38 | 32 (84.2%) | 20 (52.6%) | 2 (5.3%) |
| India | 622 | 584 (93.9%) | 313 (50.3%) | 65 (10.5%) |

`Location` is free text (“Bahia state”, “Northeastern states”, comma-separated municipality lists, vague directional descriptors); “parseable” here means only non-empty. `GADM Admin Units` carries structured GID codes; `Latitude`/`Longitude` is a single event centroid.

## 4. Structured `Admin Units` by administrative tier

EM-DAT's `Admin Units` field is a JSON list of `{adm1_code, adm1_name}` (state / UF / region) and/or `{adm2_code, adm2_name}` (municipality / district) records. An event can name both tiers. Counts below are events carrying at least one record at that tier.

| country | events | `Admin Units` non-null | has adm1 (state) | has adm2 (district) | unparseable |
| --- | --- | --- | --- | --- | --- |
| Brazil | 239 | 128 (53.6%) | 71 (29.7%) | 71 (29.7%) | 0 |
| Portugal | 38 | 20 (52.6%) | 14 (36.8%) | 7 (18.4%) | 0 |
| India | 622 | 314 (50.5%) | 191 (30.7%) | 165 (26.5%) | 0 |

`GADM Admin Units` (structured GID, previous table) tracks `Admin Units` almost one-for-one — the small gaps are events whose EM-DAT admin name did not migrate to a GADM GID.
