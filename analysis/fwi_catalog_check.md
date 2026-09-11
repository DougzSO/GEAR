# FWI -- CDS catalogue check for CMIP6 relative humidity and wind speed

Query: `POST projections-cmip6/constraints` on the Copernicus CDS (metadata only -- no data retrieved, nothing queued). Purpose: confirm whether the two extra inputs a self-computed Canadian FWI System needs (beyond the already-downloaded tasmax/pr) are on the catalogue for the **already-configured** GCMs and scenarios. No decision on the FWI formula here.

- Models (`config.CMIP6_SOURCE_ID_CDS`): gfdl_esm4, miroc6
- Scenarios (`config.CMIP6_SCENARIOS`): ssp126 (ssp1_2_6), ssp585 (ssp5_8_5), ssp370 (ssp3_7_0)
- Window: 2041-2070
- Countries (Brazil, Portugal, India): the `projections-cmip6` catalogue is global; the `area` subset is a retrieval parameter, not a catalogue constraint, so availability is identical for all three.

## 0. Are the variables on the daily catalogue at all?

| CDS variable | meaning | listed for temporal_resolution=daily |
| --- | --- | --- |
| `near_surface_relative_humidity` | hurs -- daily near-surface relative humidity (FWI noon RH input) | **NO** |
| `near_surface_wind_speed` | sfcWind -- daily near-surface wind speed (FWI noon wind input) | yes |

## 1. Per variable x model -- all three active scenarios + 2041-2070

| CDS variable | model | ssp126 + ssp370 + ssp585 all present, 2041-2070 covered |
| --- | --- | --- |
| `near_surface_relative_humidity` | - | n/a -- not on daily catalogue |
| `near_surface_wind_speed` | gfdl_esm4 | yes |
| `near_surface_wind_speed` | miroc6 | yes |

## 2. Per variable x model x scenario detail

| variable | model | scenario | catalogue status | year span offered | covers 2041-2070 | years missing in window |
| --- | --- | --- | --- | --- | --- | --- |
| near_surface_wind_speed | gfdl_esm4 | ssp126 (ssp1_2_6) | available | 2015-2100 | yes | none |
| near_surface_wind_speed | gfdl_esm4 | ssp585 (ssp5_8_5) | available | 2015-2100 | yes | none |
| near_surface_wind_speed | gfdl_esm4 | ssp370 (ssp3_7_0) | available | 2015-2100 | yes | none |
| near_surface_wind_speed | miroc6 | ssp126 (ssp1_2_6) | available | 2015-2100 | yes | none |
| near_surface_wind_speed | miroc6 | ssp585 (ssp5_8_5) | available | 2015-2100 | yes | none |
| near_surface_wind_speed | miroc6 | ssp370 (ssp3_7_0) | available | 2015-2100 | yes | none |

## 3. Realisation member / grid

Not queried here -- the `projections-cmip6` `constraints` endpoint does not expose `r?i?p?f?` or grid label; per the SPEI precedent (`analysis/spei_catalog_check.md`), this can only be confirmed on the first real download and checked for r1i1p1f1 parity with the already-downloaded tasmax/pr series.
