# Extreme Wind (CMIP6 sfcWind) -- CDS catalogue re-check

Query: `POST projections-cmip6/constraints` on the Copernicus CDS (metadata only -- no data retrieved, nothing queued). Purpose: re-verify the `near_surface_wind_speed` finding already recorded in `analysis/fwi_catalog_check.md` specifically at daily resolution and against the exact grid/download pattern this pipeline uses for tasmax/pr, plus check whether a daily-MAXIMUM sfcWind variant exists (this pipeline's own convention for tasmax). No decision on Extreme Wind's data source here.

- Models (`config.CMIP6_SOURCE_ID_CDS`): gfdl_esm4, miroc6
- Scenarios (`config.CMIP6_SCENARIOS`): ssp126 (ssp1_2_6), ssp585 (ssp5_8_5), ssp370 (ssp3_7_0)
- Window: 2041-2070
- Countries (Brazil, Portugal, India): the `projections-cmip6` catalogue is global; the `area` subset is a retrieval parameter, not a catalogue constraint, so availability is identical for all three.

## 0. Are the variables on the daily catalogue at all?

| CDS variable | meaning | listed for temporal_resolution=daily |
| --- | --- | --- |
| `near_surface_wind_speed` | sfcWind -- daily MEAN near-surface wind speed (already checked in the Phase 2.2 FWI investigation, re-verified here) | yes |
| `daily_maximum_near_surface_wind_speed` | sfcWindmax -- daily MAXIMUM near-surface wind speed (this pipeline's established convention for tasmax: use the daily-max variant when it exists, not the daily-mean one) | **NO** |
| `instantaneous_10m_wind_gust` | gust -- the ERA5 quantity already downloaded by era5_wind_downloader.py, checked here only to confirm it does NOT appear on the CMIP6 projections catalogue under this or any name | **NO** |

## 1. Per variable x model -- all three active scenarios + 2041-2070

| CDS variable | model | ssp126 + ssp370 + ssp585 all present, 2041-2070 covered |
| --- | --- | --- |
| `near_surface_wind_speed` | gfdl_esm4 | yes |
| `near_surface_wind_speed` | miroc6 | yes |
| `daily_maximum_near_surface_wind_speed` | - | n/a -- not on daily catalogue |
| `instantaneous_10m_wind_gust` | - | n/a -- not on daily catalogue |

## 2. Per variable x model x scenario detail

| variable | model | scenario | catalogue status | year span offered | covers 2041-2070 | years missing in window |
| --- | --- | --- | --- | --- | --- | --- |
| near_surface_wind_speed | gfdl_esm4 | ssp126 (ssp1_2_6) | available | 2015-2100 | yes | none |
| near_surface_wind_speed | gfdl_esm4 | ssp585 (ssp5_8_5) | available | 2015-2100 | yes | none |
| near_surface_wind_speed | gfdl_esm4 | ssp370 (ssp3_7_0) | available | 2015-2100 | yes | none |
| near_surface_wind_speed | miroc6 | ssp126 (ssp1_2_6) | available | 2015-2100 | yes | none |
| near_surface_wind_speed | miroc6 | ssp585 (ssp5_8_5) | available | 2015-2100 | yes | none |
| near_surface_wind_speed | miroc6 | ssp370 (ssp3_7_0) | available | 2015-2100 | yes | none |
| daily_maximum_near_surface_wind_speed | gfdl_esm4 | ssp126 (ssp1_2_6) | n/a -- variable not on daily catalogue | - | - | - |
| daily_maximum_near_surface_wind_speed | gfdl_esm4 | ssp585 (ssp5_8_5) | n/a -- variable not on daily catalogue | - | - | - |
| daily_maximum_near_surface_wind_speed | gfdl_esm4 | ssp370 (ssp3_7_0) | n/a -- variable not on daily catalogue | - | - | - |
| daily_maximum_near_surface_wind_speed | miroc6 | ssp126 (ssp1_2_6) | n/a -- variable not on daily catalogue | - | - | - |
| daily_maximum_near_surface_wind_speed | miroc6 | ssp585 (ssp5_8_5) | n/a -- variable not on daily catalogue | - | - | - |
| daily_maximum_near_surface_wind_speed | miroc6 | ssp370 (ssp3_7_0) | n/a -- variable not on daily catalogue | - | - | - |
| instantaneous_10m_wind_gust | gfdl_esm4 | ssp126 (ssp1_2_6) | n/a -- variable not on daily catalogue | - | - | - |
| instantaneous_10m_wind_gust | gfdl_esm4 | ssp585 (ssp5_8_5) | n/a -- variable not on daily catalogue | - | - | - |
| instantaneous_10m_wind_gust | gfdl_esm4 | ssp370 (ssp3_7_0) | n/a -- variable not on daily catalogue | - | - | - |
| instantaneous_10m_wind_gust | miroc6 | ssp126 (ssp1_2_6) | n/a -- variable not on daily catalogue | - | - | - |
| instantaneous_10m_wind_gust | miroc6 | ssp585 (ssp5_8_5) | n/a -- variable not on daily catalogue | - | - | - |
| instantaneous_10m_wind_gust | miroc6 | ssp370 (ssp3_7_0) | n/a -- variable not on daily catalogue | - | - | - |

## 3. Realisation member / grid

The `projections-cmip6` `constraints` endpoint does not expose the realization member (`r?i?p?f?`) or grid label -- fixed server-side, only visible in the NetCDF filename after a retrieval, same limitation already on record for tasmin/pr (`analysis/spei_catalog_check.md`). Whether `sfcWind`/`sfcWindmax` ship the same `r1i1p1f1` member as the already-downloaded tasmax series (gfdl_esm4 r1i1p1f1/gr1, miroc6 r1i1p1f1/gn) is NOT confirmed by this catalogue query and would need a real first download to check -- same open item already flagged for pr/tasmin/spei.
