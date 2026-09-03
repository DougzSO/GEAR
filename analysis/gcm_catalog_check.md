# V3 + V4 — CDS catalogue check for a second GCM

Query: `POST projections-cmip6/constraints` on the Copernicus CDS (metadata endpoint — no data retrieved, nothing queued). For each candidate model the endpoint reports which `experiment` values and which `year` values remain valid once `temporal_resolution = daily` and `variable = daily_maximum_near_surface_air_temperature` are fixed.

Reference model in use (`config.CMIP6_SOURCE_ID_CDS`): **gfdl_esm4: r1i1p1f1 (grid gr1, from tasmax_day_GFDL-ESM4_ssp126_r1i1p1f1_gr1_20410101-20701231.nc)**.

## 1. Per model — all three scenarios + 2041-2070 together

| model (priority order) | daily tasmax exists | ssp126 + ssp370 + ssp585 all present, 2041-2070 covered | variant / run |
| --- | --- | --- | --- |
| ipsl_cm6a_lr | yes | no | not exposed by CDS catalogue API |
| miroc6 | yes | yes | not exposed by CDS catalogue API |
| mpi_esm1_2_lr | yes | yes | not exposed by CDS catalogue API |
| cnrm_cm6_1 | yes | yes | not exposed by CDS catalogue API |

## 2. Per model × scenario detail

| model | scenario | catalogue status | year span offered | covers 2041-2070 |
| --- | --- | --- | --- | --- |
| ipsl_cm6a_lr | ssp126 (ssp1_2_6) | unavailable | — | — |
| ipsl_cm6a_lr | ssp370 (ssp3_7_0) | available | 2015–2100 | yes |
| ipsl_cm6a_lr | ssp585 (ssp5_8_5) | unavailable | — | — |
| miroc6 | ssp126 (ssp1_2_6) | available | 2015–2100 | yes |
| miroc6 | ssp370 (ssp3_7_0) | available | 2015–2100 | yes |
| miroc6 | ssp585 (ssp5_8_5) | available | 2015–2100 | yes |
| mpi_esm1_2_lr | ssp126 (ssp1_2_6) | available | 2015–2100 | yes |
| mpi_esm1_2_lr | ssp370 (ssp3_7_0) | available | 2015–2100 | yes |
| mpi_esm1_2_lr | ssp585 (ssp5_8_5) | available | 2015–2100 | yes |
| cnrm_cm6_1 | ssp126 (ssp1_2_6) | available | 2015–2100 | yes |
| cnrm_cm6_1 | ssp370 (ssp3_7_0) | available | 2015–2100 | yes |
| cnrm_cm6_1 | ssp585 (ssp5_8_5) | available | 2015–2100 | yes |

**Variant / run.** The CDS `projections-cmip6` catalogue and its `constraints` endpoint do not expose the realization member (`r?i?p?f?`) — it is fixed server-side and only visible in the NetCDF filename after a retrieval. `gfdl_esm4` returned `r1i1p1f1` / grid `gr1` (see reference line above). The member for each candidate above cannot be confirmed from the catalogue alone; it will be readable from the first real download and should be checked for `r1i1p1f1` parity at that point (CNRM-family models are the known exception — they commonly ship `r1i1p1f2`).

## 3. Final V3 check — SSP3-7.0 for the reference GCM (`gfdl_esm4`)

ARCHITECTURE.md Section 9 (V3) adds SSP3-7.0 to the active scenario set only if the CDS catalogue offers it **for both** GCMs. MIROC6 is covered in the tables above; this is the check for `gfdl_esm4`.

| model | scenario | catalogue status | year span offered | covers 2041-2070 | years missing in 2041-2070 |
| --- | --- | --- | --- | --- | --- |
| gfdl_esm4 | ssp370 (ssp3_7_0) | available | 2015–2100 | yes | none |

**Result:** SSP3-7.0 is available for the reference GCM over the full 2041-2070 window — the V3 both-GCMs criterion is met.
