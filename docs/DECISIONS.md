# GEAR Framework — DECISIONS.md

Log of every methodological and data-source decision made during this project, in English, concise and objective. Every entry can be revised, replaced, or removed if better data, methods, or sources emerge. Format per entry:

## [YYYY-MM-DD] Short title
- Decision:
- Reason:
- Status: active | superseded by <link to entry> | removed

## [2026-09-03] Target CRS: EPSG:4326
- Decision: All spatial layers are produced and stacked in EPSG:4326 (`config.CRS_TARGET`).
- Reason: Ported from the prior GEAR pipeline. The hazard layers, boundaries and asset coordinates are all natively lon/lat; a single geographic CRS avoids reprojection error accumulation across the stack. Area-based operations that need an equal-area CRS are handled locally where they occur, not by changing the pipeline CRS.
- Status: active

## [2026-09-03] Target grid resolution: 0.008333 deg (~1 km nominal)
- Decision: The common raster grid is 0.008333 deg (`config.RESOLUTION_TARGET_DEG`), ~1 km at the equator.
- Reason: Ported from the prior pipeline. It is the resolution of the finest hazard input (Aqueduct basin rasterisation) and a practical common denominator. For the heat layer this figure is nominal only — see the CMIP6 resampling entry.
- Status: active

## [2026-09-03] Study countries and emission-scenario list
- Decision: Countries = Brazil, Portugal, India (`config.COUNTRIES`). Emission scenarios = SSP1-2.6 and SSP5-8.5 as contrasting bounds. Time horizon = 2041-2070, represented by 2050 (`config.YEAR_TARGET`).
- Reason: Ported from ARCHITECTURE.md Sections 2-3. SSP3-7.0 (available in the Aqueduct download as `bau`) is deliberately excluded from the active set pending verification item V3.
- Status: active

## [2026-09-03] National boundaries: GADM 4.1 level 0
- Decision: National outlines are the GADM 4.1 administrative level-0 GeoPackage, one file per country, from `https://geodata.ucdavis.edu/gadm/gadm4.1/gpkg` (`config.GADM_BASE_URL`), layer `ADM_ADM_0`, saved as `data/raw/boundaries/gadm/gadm41_{ISO3}.gpkg`.
- Reason: Ported. The boundary is used to clip ~1 km rasters and to bound climate API queries; a coarse outline (e.g. Natural Earth 1:110m) would leak or clip whole grid cells. GADM is versioned and citable.
- Status: active

## [2026-09-03] Mainland-only scope for Portugal
- Decision: For countries in `config.MAINLAND_ONLY_COUNTRIES` (Portugal only), the boundary geometry is reduced to its largest polygon by area, and asset records outside the resulting mainland bounding box are physically removed and archived to `gem_excluded_azores_madeira.csv`.
- Reason: Ported from ARCHITECTURE.md Section 2. The studied fleet and hydroclimatic regime of interest are continental; the Azores/Madeira archipelagos would also inflate every country-level bounding box used for climate queries. Removed records are preserved with a reason, never silently dropped. The largest-polygon heuristic must be checked visually at least once.
- Status: active

## [2026-09-03] Global coastline: Natural Earth 10m
- Decision: Coastline layer is Natural Earth 10m physical/coastline (`ne_10m_coastline`), downloaded once from naciscdn.org and shared across countries.
- Reason: Ported. A dedicated global coastline avoids measuring distance to a land border instead of to the sea. SLR is outside the active hazard scope (ARCHITECTURE.md Section 3), so no processor currently consumes this layer; it is acquired and retained as a reference boundary layer.
- Status: active

## [2026-09-03] Global rivers: Natural Earth 10m
- Decision: Rivers layer is Natural Earth 10m physical/rivers_lake_centerlines, downloaded once and shared across countries.
- Reason: Ported. Same status as the coastline layer — retained as a reference boundary layer, no active downstream consumer while SLR is out of scope.
- Status: active

## [2026-09-03] Extreme heat: Copernicus CDS projections-cmip6, daily tasmax
- Decision: The extreme-heat input is daily `daily_maximum_near_surface_air_temperature` from the Copernicus CDS dataset `projections-cmip6`, one request per country/model/scenario covering 2041-2070, saved under `data/raw/climate/cds_tasmax/{country}/{model}/{scenario}/`. Credential: `CDS_API_URL` / `CDS_API_KEY`.
- Reason: Ported. The indicator needs a real daily series; monthly climatologies cannot support a threshold-day count.
- Status: active

## [2026-09-03] Extreme heat indicator: mean days/year with tasmax > 40 C
- Decision: The heat indicator is the mean number of days per year with tasmax above 40 C (`config.EXTREME_HEAT_THRESHOLD_C`) over the 30-year window: total exceedance days divided by 30.
- Reason: Ported from ARCHITECTURE.md Section 3.
- Status: active

## [2026-09-03] Extreme heat CMIP6 GCM: GFDL-ESM4, with a mandatory second model slot
- Decision: `config.CMIP6_SOURCE_ID_CDS` is a list. It currently holds only `gfdl_esm4` (CDS `model` label). The downloader and every report iterate over the list and write model-tagged outputs (`extreme_heat_days_{country}_{model}_{scenario}_{native,1km}.tif`).
- Reason: ARCHITECTURE.md Section 4 makes a second CMIP6 GCM a mandatory sensitivity check. The list structure and model-tagged paths are in place now so that adding the second model is a config-only change. Choice of the second model and its country coverage is verification item V4.
- Update (2026-09-03): V4 closed — the list now holds `["gfdl_esm4", "miroc6"]` and all three countries are covered. See "Second CMIP6 GCM: MIROC6 (V4 closed); SSP3-7.0 added as intermediate scenario (V3 closed)" below.
- Status: active

## [2026-09-03] Extreme heat scenario labels for the CDS API
- Decision: Scenarios `ssp126` / `ssp585` map to CDS `experiment` values `ssp1_2_6` / `ssp5_8_5` (`config.CMIP6_SCENARIO_TO_CDS_EXPERIMENT`).
- Reason: Ported; required by the CDS request schema.
- Status: active

## [2026-09-03] Extreme heat spatial resampling: nearest neighbour to ~1 km nominal
- Decision: The native GCM per-cell day count (~1 deg, ~100 km) is resampled to `RESOLUTION_TARGET_DEG` by nearest neighbour and clipped to the country bounding box. Both the native raster and the 1 km raster are written.
- Reason: Ported. There is no bias correction here, so a higher-order interpolator would fake spatial precision the data does not have. The "1 km" of this layer is nominal, for stacking with the other hazards; this is stated in the manuscript methods.
- Update (2026-09-03): "the country bounding box" is now `cds_tasmax_downloader._climate_bounds` — the per-coordinate union of the GADM bounds and `config.COUNTRY_BBOX_FALLBACK[country]` — used for BOTH the CDS request area and the post-resample clip box. See the dedicated "Climate download bbox: union of GADM bounds and a per-country floor box" entry below.
- Update (2026-09-03, grid alignment): `_resample_to_1km` no longer clips a resolution-only reprojection to the bbox. It reprojects directly onto a fixed per-country destination grid (`_target_grid` = `_climate_bounds` + `RESOLUTION_TARGET_DEG`), identical transform/shape/CRS for every GCM, so the per-country multi-model Min-Max pool downstream sees one grid. This was required once a second GCM (MIROC6, ~1.4 deg) joined GFDL-ESM4 (~1.25 deg) — see the "Second CMIP6 GCM: MIROC6" entry's 2026-09-03 update.
- Status: active

## [2026-09-03] Climate download bbox: union of GADM bounds and a per-country floor box
- Decision: The extreme-heat downloader requests, and clips to, `cds_tasmax_downloader._climate_bounds(country)` = the per-coordinate union of the GADM level-0 bounds and `config.COUNTRY_BBOX_FALLBACK[country]` (same box for the CDS `area` and the `_resample_to_1km` clip, so they never disagree). `COUNTRY_BBOX_FALLBACK` — previously unused — now holds that floor box: India `(67.5, 6.5, 97.5, 37.5)`, Portugal `(-9.75, 36.75, -6.0, 43.0)` (mainland only), Brazil `(-73.99, -33.75, -28.84, 5.27)` ≈ its GADM bounds (union is a no-op). `get_country_bounds` itself is unchanged, so the Portugal mainland-only asset filter still uses raw GADM bounds.
- Reason: Two effects pulled the heat raster below the study footprint. (1) GADM 4.1 level-0 India stops at ~33.26 N / ~68.19 E — it omits most of Indian-administered Jammu & Kashmir and Ladakh (Chenab/Jhelum hydro) and the far west of Kutch (thermal). (2) The GFDL-ESM4 native grid (~1 deg lat, ~1.25 deg lon) snaps the requested area inward by up to one cell, which had erased the northern border of mainland Portugal. Both are bbox-coverage gaps, not data-availability gaps — CDS/CMIP6 covers this territory.
- Measured impact (India + Portugal re-downloaded, gfdl_esm4, both scenarios, 2026-09-03):
  - India 1 km raster extent: `(68.75, 6.99, 97.17, 33.0)` -> `(67.5, 6.49, 97.51, 37.5)`; shape `(3121, 3411)` -> `(3721, 3601)`; `.nc` 16.1 MB -> 19.9 MB per scenario.
  - Portugal 1 km raster extent: `(-9.51, 36.99, -6.24, 42.0)` -> `(-9.75, 36.99, -6.24, 43.0)`; shape `(601, 392)` -> `(721, 421)`; `.nc` 0.53 MB -> 0.57 MB per scenario.
  - Plant-level heat match (operating GEM plants, per scenario): India no-match 20 -> 0; Portugal no-match 5 -> 0. The 14 India plants (11 J&K/Ladakh hydro + Akrimota, Sanghipuram, Vayor near Kutch) and the 5 Portugal Ventominho units now sample a finite heat cell in both ssp126 and ssp585.
  - Side effect on water: the water raster rides on the heat grid, so the wider extent also recovered water matches — India water no-match 25 -> 18, Portugal 6 -> 1. The residual water-only no-matches (India 18: high-Himalaya endorheic points incl. Chutak/Kishanganga, plus Arunachal and small southern islands; Portugal 1: Windfloat Atlantic offshore) are Aqueduct basin-geometry gaps, not a raster bbox issue — same class as the Brazil coastal-basin no-matches, out of scope here.
  - Brazil untouched: bbox, rasters and its 21 water-only no-matches unchanged.
- Companion: `heat_stress_processor` and `water_stress_processor` outputs for India and Portugal were regenerated on the new grid (Brazil's stay on the old grid; the heat processor's grid guard is per-country, so they do not conflict). Verified in `analysis/plant_level_hazard_values.csv` / `analysis/normalization_diagnostics.md`.
- Status: active

## [2026-09-03] Water stress: WRI Aqueduct 4.0 future_annual via Google Earth Engine
- Decision: Water-stress input is the Earth Engine FeatureCollection `WRI/Aqueduct_Water_Risk/V4/future_annual` (`config.AQUEDUCT_FC_ID`), one EE call + one HTTP download per country, saved as `data/raw/climate/aqueduct/{country}/aqueduct_2050.csv`. Credential: `GEE_PROJECT_ID` (optional — the step is reported as SKIPPED, never silently passed, when absent).
- Reason: Ported. The collection is wide (one column per scenario per basin), so a single download covers every scenario; there is no scenario filter to apply to the query.
- Status: active

## [2026-09-03] Aqueduct basin selection uses a simplified country polygon
- Decision: Before the Earth Engine `filterBounds` query, the GADM level-0 polygon is simplified with a 0.05 deg (~5 km) tolerance (`aqueduct_downloader.GEOMETRY_SIMPLIFY_TOLERANCE_DEG`).
- Reason: Simplification is mandatory, not an optimisation: the raw polygons are 17.4 MB (Brazil) and 19.8 MB (India) as GeoJSON and the query fails outright at Earth Engine's 10 MB inline payload limit. Any tolerance from 0.0005 to 0.05 deg brings both under the limit.
- Measured impact (2026-09-03, `filterBounds` basin count, `simplify(0.05)` vs `simplify(0.0005)` ≈ near-native):
  - India: 403 basins in both — no difference at any tested tolerance.
  - Brazil: 1118 basins at 0.05 vs 1115 at 0.0005. The 0.05 boundary is slightly "fatter" at the border: it pulls in 5 basins the near-native boundary excludes (4 inland, 1 coastal — pfaf_id 616707) and drops 2 that it includes (both absent from the stage-1 download, so not further characterised). Net +3 border basins. It never drops interior basins.
  - This is a small, mostly-inland, directional border effect — not zero. The single coastal basin gained is a boundary artefact, not a scope decision; downstream analysis clips to basin geometry by intersection regardless.
- Status: active

## [2026-09-03] Water stress scenarios and horizon
- Decision: Aqueduct scenarios used are `bau`, `opt`, `pes` (`config.AQUEDUCT_SCENARIOS`), horizon suffix `50` (year 2050), raw column `{scenario}50_ws_x_r` (water stress, consumption-to-availability ratio). SSP-RCP identities (WRI data dictionary / Kuzma et al. 2023): `opt` = SSP1-2.6, `bau` = SSP3-7.0, `pes` = SSP5-8.5.
- Reason: Ported. `opt`/`pes` are the same SSP-RCP scenarios as the heat layer under different labels; `bau` has no heat counterpart.
- Status: active

## [2026-09-03] Water-heat scenario pairing
- Decision: Cross-hazard pairing by SSP-RCP identity: `ssp126` <-> Aqueduct `opt`, `ssp585` <-> Aqueduct `pes` (`config.AQUEDUCT_SCENARIO_FOR_CMIP6`). `bau` (SSP3-7.0) is left unpaired.
- Reason: Ported. Inclusion of SSP3-7.0 as an intermediate scenario depends on heat-data availability and is verification item V3.
- Status: active

## [2026-09-03] Disaster events: EM-DAT Archive on the UCLouvain Dataverse
- Decision: Disaster events come from the EM-DAT Archive, UCLouvain Dataverse, persistent id `doi:10.14428/DVN/I0LTPH` (`config.EMDAT_ARCHIVE_PERSISTENT_ID`), API base `https://dataverse.uclouvain.be/api`. The `.xlsx` file id is discovered at run time (filename keyword `emdat_archive`), never hardcoded. Snapshot taken 2026-04-30 by the EM-DAT team; coverage 1900-2024. Events filtered by ISO code to the three countries and to disaster types Drought, Extreme temperature, Flood, Storm. Output: `data/raw/validation/emdat_{country}.csv`.
- Reason: Ported. The Archive is open (no registration), one row per event with a `Location` field, and is the option EM-DAT's own documentation recommends for reproducible research. Acquisition only — no geocoding, no cross-validation in this layer.
- Status: active

## [2026-09-03] Asset base: GEM Global Integrated Power Tracker, manual snapshot
- Decision: The asset base is a manual export of the Global Energy Monitor Global Integrated Power Tracker, file `gem_global_integrated_power_tracker_{20260809}.xlsx` (export dated 2026-08-09), placed by hand in `data/raw/assets/`. Only `Status == "operating"` records enter the main pipeline; `construction` / `announced` / `pre-construction` are preserved separately; all other statuses are counted and dropped. GEM's native per-technology capacity thresholds are kept unmodified.
- Reason: Ported from ARCHITECTURE.md Section 2 and INVENTORY.md. GEM has no stable anonymous API, so the snapshot must be versioned and dated in the manuscript. The operating-only filter caps the most recent commissioning year at the export date — a declared limitation, not a bug.
- Status: active

## [2026-09-03] Plant aggregation rule
- Decision: Generating units are aggregated to plants on the key country + normalised name + coordinate rounded to `DUPLICATE_COORD_TOLERANCE_DEG = 0.0009` deg (~100 m). `capacity_mw` is summed (all-missing stays NaN, not 0); `commissioning_year` is the minimum across units (oldest unit); a divergent `fuel_type` across units yields `None` + `mixed_fuel_type = True`.
- Reason: Ported. Coordinates in open registries carry rounding noise between units of the same plant, so an explicit tolerance is used rather than exact equality. Minimum commissioning year is conservative for a downstream age factor.
- Status: active

## [2026-09-03] Fuel bucketing: four buckets, coal merged into thermal
- Decision: Plants receive `fuel_type_bucket` in {hydro, wind, solar, thermal}. GEM `Type` values map: hydropower -> hydro; wind -> wind; utility-scale solar -> solar; coal, oil/gas, nuclear, bioenergy, geothermal -> thermal. Seven mixed-fuel plants use per-name overrides (all resolve to thermal). The column was named `fuel_type_ahp_bucket` in the prior repository.
- Reason: ARCHITECTURE.md Section 6 confirms coal and other thermal technologies are merged into a single `thermal` bucket (same physical mechanism: cooling-water dependence and temperature sensitivity of that water). The rename drops the coupling to the discarded AHP method (INVENTORY.md). The prior repository's five-bucket split (separate `coal` / `thermal_other`) is not carried over. The age-curve tension inside the merged bucket is verification item V1.
- Status: active

## [2026-09-03] Dependencies restricted to the acquisition/processing layer
- Decision: `requirements.txt` is restricted to numpy, pandas, xarray, rioxarray, rasterio, geopandas, shapely, pyproj, earthengine-api, cdsapi, netcdf4, h5netcdf, requests, openpyxl, tqdm, python-dotenv, plus pytest. A dedicated `.venv` is created in the project root (venv paths are not portable, so the prior environment is not copied).
- Reason: These are the libraries this layer actually imports (INVENTORY.md). Libraries used only by the not-yet-rebuilt index/weighting/visualisation layer (scipy, scikit-learn, seaborn, cartopy, contextily, osmnx, earthaccess, ...) are added when that layer is written.
- Status: active

## [2026-09-03] ANEEL / DGOVPT endpoint constants retained as inert
- Decision: `config.ANEEL_CKAN_BASE_URL` and `config.DGOVPT_API_BASE_URL` are kept in `config.py` even though their downloaders (`aneel_downloader`, `dgeg_downloader`) are not part of this rebuild. `POWER_BASE_URL`, already marked "Removido" in INVENTORY.md's config table, was dropped.
- Reason: INVENTORY.md's `config.py` table lists these two constants; they are retained so the values exist if the decision to reintroduce complementary national asset registries (ANEEL for Brazil, DGEG for Portugal) is revisited. They are not read by any code in the current pipeline.
- Status: active (inert — no active consumer)

## [2026-09-03] Water stress normalisation: per-country Min-Max, scenarios pooled
- Decision: `water_stress_processor` produces a normalised layer with `risk_norm = clip((v - min) / (max - min), 0, 1)`, where `min`/`max` are computed PER COUNTRY over the three Aqueduct scenarios (bau, opt, pes) pooled together, never across countries (`compute_country_minmax`). It also writes the raw physical layer (consumption-to-availability ratio) on the same grid.
- Reason: Ported from the prior repository. The normalised layer answers "ranking within this country"; "1.0" is this country's most water-stressed basin in any scenario and is not comparable in absolute level between countries. The NAES (not built yet) must use the raw layer, never the normalised one.
- Status: active
- Update (2026-09-03): the raw consumption-to-availability layer is the CCRS input (ARCHITECTURE.md Section 5.1) -- "NAES" above is the superseded name for that consumer. The per-country normalised layer is retained as a standalone within-country product, not on the CCRS path. See "CCRS replaces SCI/NAES as the unified risk architecture".

## [2026-09-03] Water stress WRI sentinel (9999) handling
- Decision: Basins with `RAW_SENTINEL_VALUE = 9999.0` in the raw column are excluded from the Min-Max max calculation, then substituted with the real per-country max in BOTH the normalised and the raw output. They are NOT removed from the dataset.
- Reason: Ported. 9999 is WRI's code for a non-finite consumption-to-availability ratio and always coincides with WRI category 4 / score 5.0 — a real "Extremely High" stress signal, not missing data. A literal 9999 in the pool would crush every real value (which top out near 30 for India) toward zero. Removing the basins would understate water stress exactly where INVENTORY.md flags the raw layer as least neutral (India). Measured on the real data (2026-09-03): 34 sentinel basin-scenario entries for India across bau/opt/pes; 0 for Brazil and Portugal.
- Status: active

## [2026-09-03] Water stress output grid = the extreme-heat grid
- Decision: The water-stress rasters are written on the exact grid (transform/shape/CRS) of an already processed `extreme_heat_days_{country}_{model}_{scenario}_1km.tif` (`_load_reference_grid`, using the first configured model / ssp126). The heat layer must be processed first.
- Reason: Ported. Reusing the grid rather than rebuilding it from bounds+resolution avoids floating-point misalignment between the two hazard layers, which would break pixel-wise map algebra downstream. The 1 km grid depends only on country bounds and target resolution, so it is identical across models and scenarios.
- Status: active

## [2026-09-03] Heat stress normalisation: per-country Min-Max, scenarios AND models pooled jointly
- Decision: `heat_stress_processor` normalises each `extreme_heat_days_*_1km.tif` with `clip((v - min) / (max - min), 0, 1)`, where `min`/`max` are computed PER COUNTRY over every configured CMIP6 model and all three scenarios (ssp126, ssp585, ssp370) pooled jointly into a single domain. Never pooled across countries. Outputs stay model-tagged (`heat_stress_{country}_{model}_{scenario}_1km.tif`) but share the one country domain. The processor iterates over every model in `cds_tasmax_downloader.configured_models()`.
- Reason: This is the design originally specified for the layer — per-country Min-Max over all scenarios, ported from the prior single-GCM repository and generalised to "all models" rather than one. An intermediate revision made the domain per-model (rationale: keep a second GCM as a clean sensitivity check whose normalised output is not shifted by another model's extremes); that per-model design is reverted here.
- Guard: `_assert_consistent_grid` raises `GridMismatchError` (never a silent pass) if the model rasters to be pooled disagree on shape, resolution/transform or CRS. No-op with one model; present so that adding the second GCM under V4 fails loudly instead of silently misaligning the normalised stack.
- Open question (tied to V4): joint pooling is the current default. Whether to keep it or switch to per-model normalisation once real second-GCM data exists is not resolved here — it depends on how different the second GCM's extremes turn out to be, and is part of verification item V4.
- Status: active
- Update (2026-09-03): the raw `extreme_heat_days` layer is the CCRS heat input (ARCHITECTURE.md Section 5.1); the per-country normalised layer is a standalone within-country product, not on the CCRS path. The V4-tied joint-vs-per-model open question is unaffected. See "CCRS replaces SCI/NAES as the unified risk architecture".

## [2026-09-03] Heat stress raw layer is a passthrough of the downloader output
- Decision: `heat_stress_processor.raw_raster_path()` returns `cds_tasmax_downloader.resampled_raster_path()` — the raw heat layer is the `extreme_heat_days_*_1km.tif` the downloader already wrote, not a new file. The processor references it, never copies or recomputes it.
- Reason: Ported. Unlike water, the raw physical value for heat (days/year with tasmax > 40 C) already exists on disk on the exact grid the processor normalises. Unit: `days_per_year_with_tasmax_gt_40C`.
- Status: active

## [2026-09-03] Hazard combination — linear sum retained, interaction term rejected
- Scope: index architecture / open question (ARCHITECTURE.md Section 6), not a resolved decision. The index layer is not built yet; this records a direction and a rejected alternative, not an implemented result.
- Decision: `Risk_i` keeps the linear form `w_water · WaterStress_i + w_heat · HeatStress_i`. No non-linear interaction term between water and heat is introduced.
- Reason: `analysis/normalization_diagnostics.md` task 4 found plant-level Spearman correlations between the two hazards (3-scenario pooled pairing: ssp126/opt + ssp585/pes + ssp370/bau) of about -0.45 (Brazil), +0.08 (Portugal), +0.41 (India) — India moderately compounding (the same plants tend to face both), Brazil moderately offsetting, Portugal largely independent. These reflect geographic co-location of arid/hot regions, not a documented physical mechanism by which water stress amplifies heat sensitivity (or vice versa) for a given power plant. Fitting an interaction term to this sample-specific correlation would be a category error — mistaking spatial correlation for causal compounding — and would either break cross-country comparability (if the term were country-specific) or ignore the observed country differences (if fixed).
- Status: active — the linear, no-interaction decision is carried into "CCRS replaces SCI/NAES as the unified risk architecture"; still open to revision only if literature-based (not sample-derived) evidence of physical compound risk for energy infrastructure is found.
- Companion note: per-hazard decomposition (water-only and heat-only contribution) remains an auxiliary diagnostic output alongside the combined score, not a replacement for it.
- Update (2026-09-03): superseded framing, not decision. `Risk_i` is now `Hazard_i,s` (ARCHITECTURE.md Section 5.1) with **four** hazard terms (ws, sv, iv, heat) and per-bucket weights; "combined SCI" above is the superseded SCI-era name. The linear weighted sum with no water×heat interaction term is unchanged. The Spearman citation in the Reason line is the plant-level water/heat correlation and stands.

## [2026-09-03] Age factor for thermal bucket: fuel-specific curves (V1 closed)

- Decision: `age_factor` is no longer a single curve for the `thermal`
  bucket. It is differentiated by `fuel_type` (not `fuel_type_bucket`):
  - Coal: 0.25%/year heat-consumption deterioration between overhauls,
    with faster loss (~2%) in the first two years, then stabilising.
    Source: IEA / Coal Industry Advisory Board, *Power Generation from
    Coal: Measuring and Reporting Efficiency Performance and CO2
    Emissions*, Paris, 2010, Section 2 ("Deterioration"). The source
    measures heat-rate (efficiency) deterioration, not generating
    capacity, and states this deterioration is largely restored at major
    overhauls — the linear `age_factor` does not model that recovery,
    so it overstates cumulative loss for well-maintained plants. Declared
    limitation.
  - Gas/oil-gas: unchanged, efficiency gain with age (US data
    2001-2018), opposite sign to coal, already on record in
    ARCHITECTURE.md Section 7.1.
  - Nuclear: fixed at 1.0 (neutral). Nuclear capacity change with age is
    governed by regulatory licensing and decommissioning, not gradual
    physical degradation; no defensible physical curve exists at this
    tier of evidence. Declared scope limit.
  - Bioenergy: uses the coal curve as a proxy (0.25%/year), on the
    grounds of shared combustion-plant ageing mechanisms (boiler wear,
    tube corrosion, heat-loss increase). Declared simplification; fuel
    heterogeneity within bioenergy (residues, dedicated energy crops,
    bagasse) is not separately modelled.
  - Mixed-fuel plants (`mixed_fuel_type = True`, 6 plants): `age_factor`
    is the simple average of the component fuels' curves, capacity-
    weighted average is used instead if per-fuel capacity is available
    in the source data.
- Reason: `gem_validated_plants_{country}.csv` shows thermal-bucket
  fuel composition is close to a mirror image across the three
  countries — coal is 86.4% of Indian thermal capacity vs. 5.5% Brazil
  and 0% Portugal; gas/oil is 87.4% Portugal vs. 52.7% Brazil vs. 9.5%
  India. This satisfies the ARCHITECTURE.md Section 9 (V1) criterion for
  heterogeneity large enough to invert cross-country rankings under a
  single averaged curve. The `thermal` fusion is kept for the water/heat
  hazard weights (Section 6.1) — the cooling-water dependence mechanism
  is shared across fuels — but not for `age_factor`, which tracks a
  different, fuel-specific physical process.
- Two earlier candidate sources for the coal curve were checked and
  rejected: the Global Coal Plant Tracker's 10%/15%/20% age penalties
  (at 9/19/29 years) are a CO2-accounting convention GEM applies to
  estimate lifetime emissions, not a measured capacity or efficiency
  curve; Aich, Nandi & Bhattacharya (2019) measures weathering of an
  open-air raw coal stockpile over 330 days, not power-plant ageing.
  Neither supports a physical age_factor and both are excluded from
  the manuscript.
- Status: superseded by [2026-09-03] Age factor curves revised with additional literature (V1 revision) — numeric curves for coal/wind/solar/bioenergy revised; nuclear/gas/mixed-fuel rule unchanged.

## [2026-09-03] Age factor curves revised with additional literature (V1 revision)

- Decision: age_factor curves updated for coal, wind, solar and
  bioenergy with newly verified literature; nuclear confirmed at
  neutral baseline (1.0); gas curve unchanged.
- Coal: 0.25%/year heat-consumption deterioration (unchanged rate,
  IEA 2010), now cross-validated by a second independent source --
  Sagaf (2020), two 660 MW units, 0.19-0.44%/year boiler efficiency
  deterioration (mean ~0.32%/year), consistent order of magnitude.
- Wind: 0.15 percentage points of capacity factor decline per year
  (Olauson, Edström & Rydén, 2017, Wind Energy, Swedish turbine
  fleet -- verified). Converted to age_factor via
  age_factor = 1 - (0.0015 x age / CF_initial). Fallback of 0.4%/year
  relative if per-turbine capacity factor data is unavailable,
  documented as a placeholder.
- Solar: 0.7%/year at plant level (module physics 0.5%/year plus
  soiling/downtime/inverter losses), compound decay
  age_factor = (1-0.007)^age. Sources: Deline et al. (NREL, 2020,
  2024), Boretti & Castellotto (2024).
- Nuclear: confirmed at 1.0 (neutral) -- no change from original V1,
  reinforced by Blake (1992) and Simola (1999): US capacity factors
  improved with fleet age, aging is component-level and
  non-predictable at fleet scale.
- Bioenergy: changed to 1.0 (neutral). Original V1 used the coal curve
  as a proxy (0.25%/year) on shared combustion-plant ageing grounds;
  that proxy is dropped for want of fleet-level longitudinal evidence
  (Ghenai & Hachicha, 2017, is a fuel-mix effect study, not an aging
  study), aligning bioenergy with nuclear at the neutral baseline.
- Mixed-fuel plants: unchanged, simple average of component curves
  (capacity-weighted if per-fuel capacity data available).
- Status: active (supersedes 0861754's numeric curves for coal/wind/
  solar/bioenergy; nuclear/gas/mixed-fuel rule unchanged)

## [2026-09-03] Second CMIP6 GCM: MIROC6 (V4 closed); SSP3-7.0 added as intermediate scenario (V3 closed)

- Decision: MIROC6 is added as the second CMIP6 GCM, alongside
  gfdl_esm4, for the extreme-heat layer. SSP3-7.0 is added as a third
  scenario, alongside SSP1-2.6 and SSP5-8.5, for both GCMs -- pairing
  with the existing Aqueduct `bau` label on the water side
  (`config.AQUEDUCT_SCENARIO_FOR_CMIP6` gains an ssp370 <-> bau entry).
- Reason (V4): Of four candidates checked against the CDS
  projections-cmip6 catalogue (ipsl_cm6a_lr, miroc6, mpi_esm1_2_lr,
  cnrm_cm6_1), IPSL-CM6A-LR was excluded outright -- ssp126 and ssp585
  are absent from its catalogue entry, so it cannot serve as a second
  anchor-scenario GCM regardless of structural divergence. Among the
  three with full ssp126/ssp370/ssp585 coverage, MIROC6 was chosen for
  the greatest structural divergence from GFDL-ESM4 (distinct
  convection scheme and model lineage). CNRM-CM6-1 was passed over
  because CNRM-family models typically ship as r1i1p1f2 rather than
  r1i1p1f1, which would break variant parity with the already-downloaded
  gfdl_esm4 (r1i1p1f1/gr1); MPI-ESM1-2-LR is the fallback if the first
  MIROC6 download surfaces a variant or grid problem. The CDS catalogue
  endpoint does not expose the variant label pre-download -- MIROC6's
  r?i?p?f? must be confirmed on first download and checked for
  r1i1p1f1 parity.
- Reason (V3): SSP3-7.0 (Aqueduct `bau`) is confirmed available on the
  CDS catalogue for gfdl_esm4 and for miroc6, both covering 2041-2070.
  Including it changes the heat Min-Max pool from 2 to 3 scenarios per
  the existing per-country joint-pooling design (see the heat
  normalisation entry above) -- this changes the normalisation
  denominator for every heat pixel already processed and requires
  reprocessing, not just an additive run.
- Update (2026-09-03): executed. `config.CMIP6_SOURCE_ID_CDS` is now
  `["gfdl_esm4", "miroc6"]` and `CMIP6_SCENARIOS` gains `ssp370`; all
  3 countries x 2 models x 3 scenarios were downloaded and reprocessed
  (heat and water).
  - MIROC6 realisation member confirmed **`r1i1p1f1`** (grid label `gn`)
    for all three scenarios -- parity with gfdl_esm4 (`r1i1p1f1` / `gr1`)
    holds, so this decision is unchanged.
  - **Grid-alignment bug found and fixed.** `_resample_to_1km` derived the
    1 km output grid from each model's own native extent, so GFDL-ESM4
    (~1.25x1 deg) and MIROC6 (~1.4x1.4 deg) landed on offset,
    differently-shaped 1 km rasters (Portugal 721x421 vs 751x338) and
    `heat_stress_processor._assert_consistent_grid` correctly refused to
    pool them. Fix: `_resample_to_1km` now reprojects every model onto one
    common per-country grid derived only from `_climate_bounds(country)` +
    `RESOLUTION_TARGET_DEG` (`_target_grid`). All 6 rasters per country now
    share one grid and the guard passes. Water rasters were reprocessed
    because the fix also shifts the gfdl_esm4/ssp126 reference grid
    (Portugal 721x421 -> 751x451; Brazil 4650x5389 -> 4683x5419; India
    unchanged at 3721x3601).
  - **Declared limitation -- MIROC6 resolution at Portugal scale.**
    MIROC6's native ~1.4x1.4 deg grid gives only 2 longitude cells over
    mainland Portugal (western native cell edge at -9.14 E). 34 of 450
    Portuguese plants -- the Lisboa / Torres Vedras / Lourinha coastal
    wind-and-solar strip plus Sines Refinery -- fall west of that edge and
    are NaN for MIROC6 (nearest-neighbour reprojection does not
    extrapolate past the source extent); they are scored by GFDL-ESM4
    only. Brazil has 12 such coastal MIROC6 no-matches, India 0. The high
    MIROC6 magnitudes for Portugal (`extreme_heat_days` up to ~67-79
    days/yr, plant-level p50 ~9-11, vs GFDL-ESM4's ~2.5-6 max and ~0.2-0.5
    p50) are **genuine MIROC6 output, not a resampling artefact** -- the
    grid fix changed raster shape/transform but not one native value.
    MIROC6 is a warm, high-sensitivity model and its coarse cells spread
    hot interior/border values; this cross-model spread is what the
    mandatory second-GCM sensitivity check is meant to expose. GCM remains
    MIROC6 -- V4 is not reopened.
- Status: active

## [2026-09-03] NAES/SCI computable-capacity denominator (V6 closed)

- Decision: The known asymmetry in the computable capacity base
  (coordinates + commissioning_year available) is declared as a
  manuscript footnote. No alternative-denominator sensitivity check is
  run.
- Reason: Per-country computable fraction of declared capacity: Brazil
  98.22%, Portugal 99.59%, India 95.83% (source:
  gem_validated_plants_{country}.csv, Stage 1/2 output). Every plant in
  all three countries has a usable coordinate; the only limiting field
  is commissioning_year. Max-min spread is 3.76 percentage points,
  under the 5-point threshold set in ARCHITECTURE.md Section 9 (V6),
  so the criterion for a footnote-only treatment is met.
- Status: active
- Update (2026-09-03): "NAES/SCI denominator" is now the per-country capacity roll-up base of the CCRS "% capacity by risk band" report (ARCHITECTURE.md Section 5.5). The 3.76-point asymmetry finding and the footnote-only treatment are unchanged; only the NAES/SCI name is superseded. See "CCRS replaces SCI/NAES as the unified risk architecture".

## [2026-09-03] Event factor: country-level EM-DAT frequency (V2 closed)

- Decision: `event_factor` moves off the fixed 1.0 placeholder to a
  per-country event-frequency factor built from EM-DAT, replacing the
  country-only granularity ceiling -- no state/district-level factor is
  built.
- Reason: Type-filtered EM-DAT event counts are 239 (Brazil), 38
  (Portugal), 622 (India), each event carrying a severity signal
  (deaths >= 10, affected >= 100, official declaration, or OFDA/BHA
  recognition) in 95.0% / 63.2% / 98.6% of cases respectively --
  country-level counts are 100% usable by construction, since every
  EM-DAT row carries an ISO country code independent of the Location
  text field. Structured administrative-tier data (adm1/state or
  adm2/district) is present in only 50-54% of events per country, and
  splits close to evenly and low between adm1 (~30-37%) and adm2
  (~18-30%) -- too sparse and too similar across countries to support a
  defensible sub-national factor; building one would drop roughly
  two-thirds of events from the factor's evidence base. This applies
  the country-only branch of the ARCHITECTURE.md Section 9 (V2)
  criterion.
- Open implementation question, not yet resolved: whether the country
  frequency factor is a raw event count, a count normalised by fleet
  capacity or plant-count exposure, or a rate per unit time over the
  EM-DAT archive's 1900-2024 span. This is deferred to the event_factor
  implementation itself, once all of V1-V6 are closed.
- Status: active
- Update (2026-09-03): under the CCRS this becomes `EventMultiplier_c`
  (ARCHITECTURE.md Section 7.2) -- a multiplier on the CCRS score, not a
  sub-factor of `Resilience_i` (which is dissolved). Functional form set:
  `EventMultiplier_c = 1 + 0.5 * (rate_c / rate_max)`, `rate_c =
  N_events(c) / 124`, resolving the open raw-count-vs-rate sub-question
  above in favour of the rate. Values: Brazil 1.192, Portugal 1.031, India
  1.500. Country-level granularity unchanged -- V2 is not reopened. See
  "CCRS replaces SCI/NAES as the unified risk architecture".

## [2026-09-03] CCRS replaces SCI/NAES as the unified risk architecture

- Decision: The two non-interchangeable index outputs -- the within-country
  Spatial Criticality Index (SCI) and the cross-country National Aggregate
  Exposure Score (NAES) -- are replaced by a single Climate Change Risk
  Score (CCRS): one continuous value per plant per scenario on one
  cross-country scale. `CCRS_i,s = Hazard_i,s * age_factor_i *
  EventMultiplier_c`, with `Hazard_i,s = w_water[bucket] * water_sub +
  w_heat[bucket] * Tlog(heat)` and `water_sub = 0.4164 * Tlog(ws) + 0.2505 *
  Tlin(sv) + 0.3331 * Tlin(iv)`. Four hazard terms (ws, sv, iv from
  Aqueduct; heat from CMIP6); `wd` excluded as rank-redundant with `ws`
  (Spearman 0.98-0.998). All transforms use global (all-country,
  all-scenario) Min-Max -- no per-country normalisation in the aggregate.
  Per-bucket water/heat weights closed: hydro (1.0, 0.0), thermal
  (0.75, 0.25), wind (0.0, 1.0), solar (0.0, 1.0); the within-water
  ws/sv/iv weights come from the WRI Aqueduct 4.0 category-step widths.
  Classification is two independent bands: WaterRiskBand (ws+sv+iv,
  absolute WRI Aqueduct 4.0 cuts 0.208 / 0.415 / 0.667 / 1.0) and
  HeatRiskBand (heat alone, sample-relative pooled p25/p75/p95, declared
  limitation -- no published absolute threshold for annual 40 C day
  frequency). `age_factor` is a >= 1 multiplier (curves per fuel_type, V1
  + V1 revision). `EventMultiplier_c = 1 + 0.5 * (rate_c / rate_max)`,
  country-level per V2 (Brazil 1.192, Portugal 1.031, India 1.500).
  GFDL-ESM4 is the primary GCM for every cited figure; MIROC6 is a
  sensitivity panel, never a 50/50 blend. Capacity enters only at the
  per-country roll-up (computable base, V6). `fuel_factor` is not included;
  its fate stays with V5 (open). Closed design of record:
  `analysis/climate_risk_score_spec.md`; summary in ARCHITECTURE.md
  Section 5.
- Reason: SCI normalised both `Risk_i` and `Resilience_i` per country, and
  the `event_factor` inside `Resilience_i` was country-uniform, so it
  appeared identically in the numerator and the per-country ceiling and
  cancelled exactly (modulo the rarely-binding 0.1 floor) -- it contributed
  nothing to the within-country SCI ranking. NAES used no resilience term at
  all. A country-level disaster-frequency signal therefore did no work
  anywhere in the original outputs. NAES also gave a cross-country number
  with no per-plant visibility, so ranking and cross-country comparison
  lived in two disconnected metrics. A single absolute score with global
  Min-Max gives both at once -- the same CCRS value means the same exposure
  in any country, plants rank on one list, and the EM-DAT signal (as
  `EventMultiplier`, on a non-per-country-normalised score) actually moves a
  country's plants. The two-term `Risk_i` also could not carry the Aqueduct
  variability indicators (sv, iv), which the plant-level diagnostics showed
  were distinct from the stress level; the CCRS has four terms.
- Status: active. Supersedes the SCI/NAES index architecture (ARCHITECTURE.md
  Section 5, rewritten in this commit) and the 3-factor `Resilience_i`
  product (Section 7, dissolved). Related entries are carried forward with
  update notes, none deleted: "Water stress normalisation ...", "Heat stress
  normalisation ...", "Hazard combination -- linear sum retained ...",
  "NAES/SCI computable-capacity denominator (V6 closed)", "Event factor:
  country-level EM-DAT frequency (V2 closed)". The linear no-interaction
  hazard combination and the country-level event factor are unchanged in
  substance. `fuel_factor` is removed (V5 closed -- see below); the frozen
  global Min-Max transform constants remain open.

## [2026-09-03] fuel_factor removed from resilience formula (V5 closed)

- Decision: fuel_factor is removed entirely, not just from the
  dissolved 3-factor Resilience product -- no bucket gets a
  fuel_factor as a CCRS multiplier, closed or conditional.
- Reason: investigated across all four buckets (thermal cooling-
  system type, hydro storage/regularisation, wind component thermal
  robustness, solar technology thermal-cycling robustness). Every
  candidate mechanism is real but fails the "defensible, codifiable,
  independent of the water/heat hazard weights already captured"
  test: thermal cooling type determines HOW a plant responds to
  WaterStress_i, not a separable quantity, and coverage data
  (PLATTS/GlobalData) is not publicly available for the 3 countries;
  hydro storage requires basin-specific hydrological simulation not
  available at this scope; wind/solar component-level differences
  lack public normalised failure/degradation datasets. See
  analysis/ (V5 research document, if versioned) for full per-bucket
  evidence and citations.
- Status: active

## [2026-09-04] CCRS global Min-Max bounds: heat per-GCM, water GCM-independent

- Decision: The global Min-Max bounds that the CCRS per-term transforms use
  (`Tlog`/`Tlin`, ARCHITECTURE.md Section 5.1) are computed as follows, and
  frozen as `ccrs_calculator.FROZEN_BOUNDS`:
  - `heat` (`extreme_heat_days`): one `(min, max)` pair **per GCM** --
    `gfdl_esm4` and `miroc6` each get their own pair, pooled over the 3
    countries x 3 scenarios, and are **never pooled or averaged with each
    other**.
  - `ws` / `sv` / `iv` (Aqueduct water stress and seasonal / interannual
    variability): one `(min, max)` pair per term, computed **once**, pooled
    over the 3 countries x 3 scenarios. This is GCM-independent by
    construction -- the water rasters (`water_stress_raw_*`,
    `seasonal_variability_raw_*`, `interannual_variability_raw_*`) carry no
    GCM axis, and sampling them against the plant set produces identical
    values whichever GCM's run is used to assemble the pool.
  - Pool membership: plant x scenario rows with a known `fuel_type_bucket`
    (currently all validated plants) whose term value is finite (the plant
    intersects an Aqueduct basin for `ws`/`sv`/`iv`, or a heat raster cell
    for `heat`).
- Reason: ARCHITECTURE.md Section 5.4 forbids blending GFDL-ESM4 and MIROC6 --
  they are a primary figure plus a sensitivity panel, not an ensemble. That
  rule is applied here to the **bounds computation**, not only to the final
  Hazard value: a heat bound pooled across both GCMs would let MIROC6's
  ~10-100x larger day-counts set the denominator for GFDL-ESM4's transformed
  heat term (and vice versa), which is exactly the cross-model contamination
  Section 5.4 rejects. The water terms have no such axis, so a single frozen
  pair per term is the correct "global, documented, not per-run" constant
  (spec item G).
- This was **not** spelled out in `analysis/climate_risk_score_spec.md`
  item G, which only says the `(min, max)` constants must be "computed once
  from a dated data snapshot and frozen ... not a per-run quantity" without
  addressing the GCM axis. This entry is the retroactive formalisation of the
  choice made when `ccrs_calculator.py` was implemented.
- References: `src/index/ccrs_calculator.py` (introduced in commit 244de40),
  frozen-bounds data snapshot `BOUNDS_DATA_SNAPSHOT = 2026-09-04`, regression
  lock in
  `tests/test_ccrs_calculator.py::test_frozen_bounds_match_recomputed_from_data`.
  Engineering detail in `docs/memory/05-decisoes-tecnicas.md` item 12.
- Status: active
- **Reopened (2026-09-14), appended, original entry above left verbatim --
  not edited.** New reason, not present when this entry was written or
  when it was last touched (the 2026-09-14 wind addition, "GEAR v3 wind
  Risk_i,h integration"): `docs/rework/GEAR_v3_methodology_nature_format.md`
  Section 8.1 names "FROZEN_BOUNDS percentile choices" as a Sobol
  candidate parameter group (quoted exactly, `GEAR_v3_methodology_
  nature_format.md:722-723`: "Applied only to genuinely continuous
  parameters: FROZEN_BOUNDS percentile choices, age_factor decay rates,
  and any other parameter that varies smoothly."). Read against what this
  entry actually decided and what `risk_calculator.FROZEN_BOUNDS` actually
  is today, that phrase does not match the implementation: this entry
  froze **raw pooled sample min/max**, no percentile trimming anywhere in
  its computation (`compute_global_bounds`/`_recommend_one`-style direct
  `sample.min()`/`sample.max()`, confirmed by direct code read), and
  `analysis/climate_risk_score_spec.md` item G -- the spec item this entry
  itself cites as its source -- also never named a percentile, only "computed
  once from a dated data snapshot and frozen." The methodology text's own
  wording, taken literally, describes something this pipeline does not do
  for `FROZEN_BOUNDS` and never has. This is not a new finding invalidating
  the original decision (min/max is what was built, deliberately, for a
  documented reason above) -- it is a discovered mismatch between what a
  *later* methodology document's prose says and what the *earlier*, still
  -active implementation actually is, surfaced while mapping Phase 6's
  Sobol parameter inventory (this file, "Phase 6 (Sensitivity/uncertainty)
  input mapping", open item 5).
  - **Percentile value, if the source names one**: it does not. The exact
    Section 8.1 quote above never specifies a percentile (no "p1/p99" or
    equivalent anywhere in that sentence or its surrounding paragraph).
    The only percentile value connected to *bounds* (as opposed to
    `risk_bands.py`'s separately-named RiskBand classification cuts) found
    anywhere in this repository's methodology/spec documents is
    `analysis/climate_risk_score_spec.md`'s item I ("Outlier handling for
    `Tlin` (sv/iv)"): "Whether a p99 clip precedes the linear Min-Max" --
    explicitly logged there as **"Open"**, phrased as "a p99 clip... **may
    be needed** -- flag for review," never adopted, and scoped only to
    `sv`/`iv`'s linear (`Tlin`) transform, not to `FROZEN_BOUNDS` as a
    whole or to any `Tlog` term. `p99` is therefore a **candidate
    mentioned once in a different, older, still-open item about a
    different subset of terms** -- not a value the current methodology
    document assigns to "FROZEN_BOUNDS percentile choices." Registered as
    a new open item below rather than assumed.
  - **Consumers of `risk_calculator.FROZEN_BOUNDS` today, by grep (the
    real blast radius of any future percentile-based recompute)**:
    - `src/index/risk_calculator.py:698` (`compute_risk_by_hazard`):
      `bounds = bounds or FROZEN_BOUNDS` -- the production default,
      feeding every real `Risk_{i,h}` value via `transform_term`
      (`:717-718`). The one consumer that actually changes computed
      output if `FROZEN_BOUNDS` changes.
    - `src/index/risk_calculator.py:593-604`
      (`assert_frozen_bounds_current`): recomputes live bounds and raises
      `BoundsRegressionError` on drift from the frozen snapshot -- a
      guard, not a data consumer, but it would need its own recomputation
      logic changed in lockstep with any percentile-based redefinition.
    - `tests/test_risk_calculator.py:202-246`
      (`test_frozen_bounds_structure_unchanged_from_retired_module`,
      `test_frozen_bounds_match_recomputed_from_data`): reads
      `rc.FROZEN_BOUNDS` directly for structural and regression checks.
    - `tests/test_normalization.py:218`: asserts
      `set(rc.FROZEN_BOUNDS) == set(rc.HAZARD_TERMS)` (1:1 key coverage,
      not a value check).
    - `tests/test_hazard_scope.py:86-110` (comments only): documents the
      `HAZARD_TERMS`/`FROZEN_BOUNDS` pairing convention that
      `PENDING_RISK_I_H_HAZARDS` enforces; no direct value read.
  - **Confirmed NOT a consumer, direct or indirect, by grep and by direct
    code read (the point this reopening was specifically asked to
    check)**:
    - `src/index/normalization.py`: every `FROZEN_BOUNDS` mention
      (`:2,11,14,23,84`) is module-docstring prose explicitly stating this
      module does **not** touch `risk_calculator.FROZEN_BOUNDS` -- no
      executable line reads it. `normalization.py` computes its own,
      independent empirical min/max per candidate term
      (`_recommend_one`), never `risk_calculator.FROZEN_BOUNDS`.
    - `src/index/risk_bands.py`: same pattern -- `:20,109` are docstring
      prose stating RiskBand classification "does **not** ... touch ...
      `risk_calculator.FROZEN_BOUNDS`/`transform_term`"; confirmed by
      grep that neither name appears anywhere outside that prose in the
      module.
    - `src/index/psae.py`: consumes `risk_bands.RiskBandTable.frame` only
      (commit `6b70a36`) -- does not import `risk_calculator` at all.
      Since `risk_bands.py` itself never touches `FROZEN_BOUNDS`, `psae.py`
      has **zero** exposure to it, direct or indirect through
      `risk_bands.py` -- confirmed by tracing the actual import graph, not
      assumed from `risk_bands.py`'s own "does not touch" claim alone.
    - `src/index/monte_carlo.py:36,76,88,319,363,716-722` and
      `tests/test_monte_carlo.py:136-155`: read `ccrs_calculator.
      FROZEN_BOUNDS` -- the **retired** module's own constant, a
      different object entirely, not `risk_calculator.FROZEN_BOUNDS`.
      Both files are already confirmed non-importable/non-collectable
      (`ImportError: cannot import name 'ccrs_calculator'`, this file's
      Phase 3.3/Phase 4 entries above) -- dead code today, zero live
      exposure regardless of what `risk_calculator.FROZEN_BOUNDS` is.
    - `src/processors/spei_processor.py:20`, `src/visualization/
      diagrams.py:165`: prose/label-string mentions only, no data read.
  - **New open item (registered here, not resolved)**: whether
    `risk_calculator.FROZEN_BOUNDS` should incorporate a percentile-based
    trim at all (matching Section 8.1's literal wording), and if so, which
    percentile, for which term(s) (all `FROZEN_BOUNDS` entries uniformly,
    or only the `Tlog`/`Tlin` subset `climate_risk_score_spec.md` item I's
    `p99` candidate was originally scoped to), is **not decided by this
    entry**. No value is assumed. This sits alongside, and is narrower
    than, this file's "Phase 6 (Sensitivity/uncertainty) input mapping"
    entry's open item 5, which flagged the same textual ambiguity without
    yet tracing the consumer graph or the `spec.md` item I precedent this
    reopening adds.
  - Action taken here: mapping, citation, and reopening only, per
    instruction -- no recompute of `FROZEN_BOUNDS`, no percentile logic,
    and no code change of any kind was made by this entry.
  - **Closed (2026-09-14), same day, appended -- not editing the mapping
    above.** The published article's Supplementary Table S3 (pasted by the
    author into this session) is now cited as the primary source, settling
    the open item registered directly above without inventing a
    percentile:
    > "Each hazard is normalized against a frozen (non-sample-dependent)
    > bound, with transform selected by a per-hazard skewness check...
    > Full bounds, transform, and provenance per hazard: Supplementary
    > Table S3."
    >
    > Table S3 footnote: "All bounds in this table are derived empirically
    > from the pooled sample (minimum/maximum), not from an externally
    > cited physical constant -- the empirical designation applies to
    > bound derivation only, and is independent of each hazard's
    > separately reported Tier 1/Tier 3 classification."
    Every row Table S3 reports (`ws`, `sv`, `iv`, Extreme Heat x2 GCMs,
    Extreme Precipitation x2 GCMs, Drought/SPEI x2 GCMs) carries the tier
    label **"empirical (pooled sample min/max)"** in its own right-hand
    column -- not "percentile," for any hazard the table documents. This
    is the literal, published, peer-reviewed-track source for exactly what
    this entry's original decision (above, 2026-09-04) already built:
    `FROZEN_BOUNDS` is empirical pooled min/max, full stop, for every
    hazard the article currently documents. No percentile value is
    introduced here or anywhere in this closure -- there is no percentile
    to name, because bound derivation was never percentile-based in the
    first place, confirmed now by the published source itself rather than
    only by this repository's own code.
  - `docs/rework/GEAR_v3_methodology_nature_format.md:720-726` (Section
    8.1) is corrected in this same task: "FROZEN_BOUNDS percentile
    choices" is removed from the Sobol continuous-parameter list and
    replaced with a description matching Table S3 -- frozen normalization
    bounds are fixed empirical constants with no percentile parameter to
    perturb; the RiskBand Tier 3 percentile-cut thresholds (a real,
    separate, already-existing parameter family, `risk_bands.py`) remain
    in that list under their own name, not conflated with `FROZEN_BOUNDS`
    any longer. This is a text correction to the methodology document
    itself, per instruction, in place of inventing a percentile with no
    precedent.
  - **New item, registered separately here, not resolved by this
    entry -- manuscript pendency, not a code pendency**: Table S3 as
    pasted does not carry a row for Extreme Wind (its own footnote states
    why, as of when the article text was written: "Extreme Wind is not
    represented in this table: no country yet has a processed ERA5
    raster... so no bounds exist to report"). `wind` has since been wired
    into `risk_calculator.HAZARD_TERMS`/`FROZEN_BOUNDS` (this file, "GEAR
    v3 wind Risk_i,h integration: empirical transform result,
    PENDING_RISK_I_H_HAZARDS closed," 2026-09-14) and carries a real
    empirical `(9.123578071594238, 31.070894241333008)` bound
    (`risk_calculator.py:344-363`) under the `-ln(1-x)` transform (Phase
    3.3, commits `b305787`/`74915ea`). Table S3 is therefore stale
    relative to the code, missing exactly one row (`wind`, `pooled`,
    skew +0.6215, `-ln(1-x)`, empirical). This is **explicitly a
    manuscript-update pendency** (the published/submitted table needs a
    new row added), **not a code pendency** -- `risk_calculator.py` is
    already correct and complete for `wind`. Not actioned here; the
    author owns manuscript revision, not this session.
  - **Sobol dimension count `D` (this file's "Phase 6
    (Sensitivity/uncertainty) input mapping" entry, and
    `docs/rework/PHASE6_DESIGN.md` Section 1.3): revised from 7 to 6.**
    The prior count of 7 confirmed continuous dimensions was reached under
    `PHASE6_DESIGN.md`'s own working assumption (Section 1.2, "the most
    defensible reading... not a confirmed mapping") that Section 8.1's
    "FROZEN_BOUNDS percentile choices" might name a continuous parameter
    distinct from -- or additional to -- the RiskBand percentile-cut
    dimensions already grouped into that count. Table S3 and the Section
    8.1 text correction above close that ambiguity: there is no
    bounds-percentile parameter, so no such dimension exists to count.
    `D = 6`: coal decay rate, wind fallback rate, hydro retention rate,
    the neg-log tail-padding fraction, and the RiskBand percentile-cut
    rank grouped as (at minimum) one dimension for the P75/P90/P95 hazard
    family and one for the Wind/Solar P90/P95/P99 family -- unchanged from
    `PHASE6_DESIGN.md` Section 1.3's own grouped-minimum counting, only
    the now-removed bounds-percentile dimension is subtracted. Still
    subject to Phase 6 open items 1, 2, and 4 (solar retention range, coal
    overhaul ranges, percentile-cut grouping granularity) raising `D`
    further if the author resolves those toward finer granularity --
    `D = 6` is the floor with today's open items unresolved, not a final
    number.
  - References: article text and Table S3 (pasted by the author into this
    session, 2026-09-14); `docs/rework/
    GEAR_v3_methodology_nature_format.md:720-726` (corrected in this
    task); `src/index/risk_calculator.py:191-198,344-363`
    (`wind`'s `LOG_TERMS` membership and `FROZEN_BOUNDS` entry); this
    file, "Phase 6 (Sensitivity/uncertainty) input mapping" (open item 5,
    the ambiguity this closure resolves) and "GEAR v3 wind Risk_i,h
    integration" (wind's wiring date and skew figure).
  - Status of this reopening: **Closed (2026-09-14).** `FROZEN_BOUNDS` is
    confirmed, by the published article's own Table S3, to be empirical
    pooled min/max for every hazard, with no percentile parameter of any
    kind -- nothing invented, nothing assumed. Two items spawned by this
    closure remain open on their own, tracked separately, not by this
    reopening: the Table S3 manuscript-update pendency for `wind` (above),
    and Phase 6 open items 1/2/4 (`PHASE6_DESIGN.md`/this file's Phase 6
    mapping entry), which still bound on `D`.

## [2026-09-04] age_factor: >=1 multiplier via `2 - retention(age)` (spec item D closed)

- Decision: `age_factor_i` is the >=1 hazard multiplier of
  `CCRS_i,s = Hazard_i,s * age_factor_i * EventMultiplier_c`
  (`climate_risk_score_spec.md` Section 6, `ARCHITECTURE.md` Section 7.1).
  It is computed as:

      age_factor = 2 - clip(retention(age), 0, 1)

  where `retention(age) <= 1` is the technology's performance-retention curve
  and `age = REFERENCE_YEAR - commissioning_year`. This reconciles the two
  documents: spec Section 6 / ARCHITECTURE Section 7.1 state the convention
  `age_factor >= 1`, increasing with cumulative age-driven loss (their example:
  20% loss -> ~x1.2); the `<= 1` formulas previously logged in this file
  ("Age factor curves revised with additional literature (V1 revision)") were
  **retention curves, not final multipliers**. `2 - retention` maps a 20%
  retention loss (retention 0.8) to `age_factor` 1.2, matching the example.
  Every bucket goes through the same `2 - retention` conversion, so a neutral
  retention of 1.0 gives `age_factor` exactly 1.0. `clip(retention, 0, 1)`
  bounds `age_factor` to `[1, 2]` and is a defensive guard against
  implausible `commissioning_year` values; it does not bind on the current
  data (oldest plant age at 2050 is 150 yr; no linear curve reaches 0 before
  ~230-400 yr).

  Per-technology `retention(age)`:
  - **Coal**: `1 - 0.0025*age` (linear). 0.25%/yr heat-rate deterioration,
    IEA/CIAB 2010, cross-validated Sagaf 2020. **No overhaul term** --
    `years_since_overhaul` is dropped from scope; no such field exists in any
    GEM file, and the documented curve is a function of age that deliberately
    does not model overhaul recovery (declared limitation, V1 entry).
  - **Gas / oil-gas**: pinned neutral, `age_factor = 1.0` (retention 1.0).
    No literature-backed rate or functional form exists in any project
    document -- ARCHITECTURE Section 7.1 says only "efficiency gain with age,
    opposite sign to coal", with no number. **Marked provisional / open**:
    revisit if a defensible source is found. A gas plant that genuinely
    improves with age cannot be represented under the `age_factor >= 1`
    convention anyway; neutral is the honest placeholder.
  - **Nuclear**: `age_factor = 1.0` fixed (retention 1.0), unchanged
    (licensing/decommissioning-governed, not gradual decay; Blake 1992,
    Simola 1999).
  - **Bioenergy**: `age_factor = 1.0` fixed (retention 1.0), unchanged
    (coal proxy dropped in the V1 revision for want of fleet-level evidence).
  - **Wind**: `1 - 0.004*age` (linear). The `CF_initial`-based form from the
    V1 revision (`1 - 0.0015*age/CF_initial`) is **abandoned**: `CF_initial`
    (initial capacity factor) does not exist in any GEM file for any of the
    1986 wind plants across the three countries (Brazil 1126, Portugal 225,
    India 635 -- 100% would have taken the fallback). The 0.4%/yr relative
    fallback rate (Olauson, Edstrom & Ryden 2017, documented as the placeholder
    in the V1 revision) is applied to all wind plants.
  - **Solar**: `(1 - 0.007)^age` (compound), unchanged. 0.7%/yr plant-level
    (module physics + soiling/downtime/inverter); Deline et al. NREL
    2020/2024, Boretti & Castellotto 2024.
  - **Hydro**: `1 - 0.00435*age` (linear). Rate = 0.55%/yr (midpoint of the
    ARCHITECTURE Section 7.1 "~0.5-0.6 %/yr" range) x 0.79, the non-water-
    attributable share (Turner et al. 2024, *Nature Communications*: of the
    23% cumulative capacity-factor decline over 610 US plants 1980-2022, only
    21% is attributable to water availability). Scaling by 0.79 keeps the
    hydro age curve from double-counting the water-stress hazard already in
    `Hazard_i,s`.
  - **Mixed-fuel plants** (`mixed_fuel_type == True`, 6 plants, all thermal
    bucket): `age_factor` = **simple average** of the component fuels'
    `age_factor` (components from `fuel_types_found`, e.g. `bioenergy;coal`).
    Capacity-weighting is not possible -- no per-fuel capacity in the source
    data (confirmed).
  - **Missing `commissioning_year`** (~5.6% of plants: Brazil 97, Portugal 11,
    India 494): `age_factor = 1.0` (neutral). These rows are **kept** in the
    dataset, flagged, and counted per country in the output, never dropped.

- `age` definition: `REFERENCE_YEAR - commissioning_year` with
  `REFERENCE_YEAR = config.YEAR_TARGET = 2050` -- the single explicit
  study-horizon constant, already pinned to 2050 by hard asserts in
  `water_stress_processor.py` / `water_variability_processor.py` and used by
  `aqueduct_downloader.py`; the CCRS hazard layer represents the 2041-2070
  window by 2050 (this file, "Study countries and emission-scenario list").
  Plant age is therefore age at the study horizon, consistent with the hazard.

- Application: `age_factor` multiplies the Hazard term per `plant_uid`
  (`data/outputs/tables/ccrs_hazard.csv`), both GCM columns, all scenario
  rows (age does not depend on scenario or GCM). Multiplicative, never summed.

- Reason: closes spec Section 10 item D ("age_factor -> >= 1 multiplier
  mapping ... confirm sign convention"). `EventMultiplier` and the full
  `CCRS_i,s` assembly remain separate steps.

- References: `src/index/age_factor.py`, `tests/test_age_factor.py`,
  `docs/memory/05-decisoes-tecnicas.md` item 14. `load_plants` in
  `ccrs_calculator.py` extended to also return `fuel_type` /
  `mixed_fuel_type` / `fuel_types_found`.
- Status: superseded by "[2026-09-04] age_factor: >=1 multiplier via
  `2 - retention(age)`, with corrected coal/hydro/wind retention curves
  (final)" below. That entry confirms this one's mechanism
  (`2 - clip(retention, 0, 1)` in `[1, 2]`) as the definitive convention --
  an intervening entry briefly reverted it to a `<= 1` retention multiplier
  based on a mistaken premise about which document was authoritative; that
  reversal is itself superseded. This entry's per-fuel retention curves for
  gas/nuclear/bioenergy (neutral), solar, and the mixed-fuel / missing-year
  handling stand; coal and hydro's rates and wind's formula are refined in
  the final entry.

## [2026-09-04] age_factor: reverted to the <=1 capacity/efficiency-retention multiplier (the `2 - retention` conversion was unauthorised)

- Decision: `age_factor_i` is `clip(retention(age), 0, 1)` in `[0, 1]` -- a
  per-technology **capacity / efficiency retention** curve, applied as a
  *direct* multiplier on `Hazard_i,s` in
  `CCRS_i,s = Hazard_i,s * age_factor_i * EventMultiplier_c`. An older plant
  that has lost capacity/efficiency scales the hazard term **down**
  (retention 0.80 -> `age_factor` 0.80), never up.
  `age = REFERENCE_YEAR - commissioning_year`,
  `REFERENCE_YEAR = config.YEAR_TARGET = 2050`.

- What changed vs. the superseded entry:
  - **Sign convention reverted.** The `age_factor = 2 - clip(retention, 0, 1)`
    conversion into `[1, 2]` ("older plant -> higher hazard") was **not an
    approved decision** -- it was inferred by the assistant in a prior session
    from the `>= 1` prose in the spec / ARCHITECTURE. It is removed. The
    active convention is the retention form (`<= 1`), matching the numeric
    curves logged in "Age factor curves revised with additional literature
    (V1 revision)".
  - **Coal rate corrected to `1 - 0.0025 * years_since_overhaul`** (not
    `1 - 0.0025 * age`). The 0.25 pp/yr boiler heat-rate deterioration runs
    from the last major overhaul. Sources: IEA/CIAB 2010; Kim & Moon 2012
    (500 MW unit); Sagaf 2020, *Journal of Thermal Engineering* 6(6):247-256
    (660 MW unit, 0.19-0.44 %/yr, 0.25 pp/yr central). `_coal_retention`
    takes `years_since_overhaul` and an overhaul restarts the decay clock. No
    GEM file carries an overhaul / major-refurbishment date (only
    `commissioning_year`, `Retired year`, fuel `Unit conversion year`), so
    `years_since_overhaul` defaults to full `age` and the curve currently
    reduces to monotonic decay -- the conservative baseline. A genuine
    condition-based *partial* reset needs both overhaul dates and a
    recovery-fraction parameter; neither exists (declared limitation, carried
    from the V1 entry). `years_since_overhaul` is **in scope** as a parameter
    (the superseded entry had dropped it).
  - **Hydro rate corrected to `1 - 0.0055 * age`.** The 0.79 "non-water-
    attributable share" multiplier from the superseded entry is **removed** --
    it had no documented origin in any project source. The rate is now the
    plain 0.55 %/yr midpoint of ARCHITECTURE Section 7.1's "~0.5-0.6 %/yr"
    (Turner et al. 2024, *Nature Communications*).
  - **Wind reverted to the `CF_initial` form with a fallback**, not a
    universal fixed rate. `retention = 1 - 0.0015 * age / CF_initial` when the
    initial capacity factor is known; `retention = 1 - 0.004 * age`
    (0.3-0.5 %/yr relative, midpoint 0.4 %/yr) as the documented fallback
    otherwise. The observational parameter (Olauson, Edstrom & Ryden 2017,
    *Wind Energy* 20:2049-2053, Swedish fleet; Shin, Ko & Huh 2015,
    *IJMAIMME* 9:55-59; Byrne, Astolfi, Castellani & Hewitt 2020, *Energies*
    13:2086) is **pp of capacity factor per year**; converting it to a
    relative rate requires `CF_initial`. `CF_initial` is **absent from every
    GEM file** for all 1986 wind plants (Brazil 1126, Portugal 225, India
    635), so the fallback share is **100% in every country** -- above the 30%
    "stop and report" threshold. Flagged: the wind `age_factor` currently
    ships on the pre-approved 0.4 %/yr fallback for every wind plant, pending
    the author's confirmation or a per-plant capacity-factor source.
  - Unchanged from the superseded entry: solar `(1 - 0.007) ** age`
    (compound); gas/oil-gas, nuclear, bioenergy -> retention 1.0 (gas/oil-gas
    **provisional** -- no literature rate); mixed fuel = **simple average** of
    the component fuels' `age_factor`; missing `commissioning_year`
    (Brazil 97, Portugal 11, India 494; 602 total, 5.6%) -> `age_factor = 1.0`,
    rows kept, flagged (`age_factor_neutralized_missing_year`), counted per
    country.

- `clip(retention, 0, 1)` guards an implausible `commissioning_year` (negative
  age -> retention > 1; extreme age -> retention < 0). It does not bind on the
  current data: observed range 0.2520 (oldest Brazilian hydro) .. 1.0000.

- Application: `age_factor` multiplies the Hazard term per `plant_uid`
  (`data/outputs/tables/ccrs_hazard.csv`), both GCM columns, all scenario
  rows (age does not depend on scenario or GCM). Multiplicative, never summed.
  `apply_to_hazard` fails loud if any `plant_uid` in the CSV has no
  `age_factor` (stale CSV). Outputs: `ccrs_age_factors.csv`,
  `ccrs_hazard_aged.csv`, `age_factor_report.md`.

- OPEN -- document conflict, needs the author's revision: `analysis/
  climate_risk_score_spec.md` Section 6 and `docs/ARCHITECTURE.md` Section 7.1
  still state the `age_factor_i >= 1` convention (increasing with age, "a
  plant that has lost ~20 % to age -> ~x1.2") and Section 10 item D asks to
  "confirm sign convention". This module now implements the opposite (`<= 1`,
  retention). That prose was **not** updated here -- rewriting the
  methodology docs is the author's call, not the assistant's. Spec item D
  stays open until that text is reconciled.

- References: `src/index/age_factor.py`, `tests/test_age_factor.py`,
  `docs/memory/05-decisoes-tecnicas.md` item 14,
  `docs/memory/06-areas-de-risco.md` (wind fallback stop condition; India
  missing-`commissioning_year` concentration).
- Status: superseded by "[2026-09-04] age_factor: >=1 multiplier via
  `2 - retention(age)`, with corrected coal/hydro/wind retention curves
  (final)" below. This reversal should not have been made: it was executed on
  the assistant's own mistaken premise that the `<= 1` retention-form prose
  (the V1 revision entries) was the authoritative convention and that
  `spec`/`ARCHITECTURE`'s `>= 1` prose was the error to reconcile away. The
  author's explicit direction (option b) is the opposite: `spec` Section 6 /
  Section 10 item D and `ARCHITECTURE` Section 5 / Section 7.1 are correct and
  definitive; this entry's `<= 1` convention was the error. Its coal
  (assumed-overhaul) and wind (CF_initial dead-code / uniform 0.4%/yr)
  refinements are carried forward as the underlying retention curve in the
  final entry; its hydro rate (0.55%/yr, no 0.79 scaling) also carries
  forward unchanged. The OPEN document-conflict flag above is resolved, not
  carried forward -- item D is closed by the final entry.

## [2026-09-04] age_factor: >=1 multiplier via `2 - retention(age)`, with corrected coal/hydro/wind retention curves (final)

- Decision: `age_factor_i >= 1` is the **definitive** convention -- confirmed,
  not reopened again. `age_factor_i` is the hazard multiplier of
  `CCRS_i,s = Hazard_i,s * age_factor_i * EventMultiplier_c`
  (`climate_risk_score_spec.md` Section 6 / Section 10 item D,
  `ARCHITECTURE.md` Section 5 / Section 7.1, line 147), computed as:

      age_factor = 2 - clip(retention(age), 0, 1)

  where `retention(age) <= 1` is the technology's capacity/efficiency
  retention curve and `age = REFERENCE_YEAR - commissioning_year`,
  `REFERENCE_YEAR = config.YEAR_TARGET = 2050`. A 20% retention loss
  (retention 0.8) maps to `age_factor` 1.2, matching the spec Section 6
  example. `clip(retention, 0, 1)` bounds `age_factor` to `[1, 2]`, a
  defensive guard against an implausible `commissioning_year` that does not
  bind on the current data (observed range 1.0000 .. 1.7480).

- This closes spec item D **without an OPEN block**: the two intervening
  entries above are both superseded. The first (`2 - retention`, uncorrected
  coal/hydro/wind curves) had the right mechanism. The second (reverted to
  `<= 1`) had the wrong mechanism -- it was based on the assistant's mistaken
  premise about which document was authoritative, not an author decision; the
  author has now confirmed explicitly (option b) that `spec`/`ARCHITECTURE`'s
  `>= 1` convention is correct and the `<= 1` reversal was the error. This
  entry restores `2 - retention` as the final mechanism and carries forward
  the coal/wind refinements made while the module was (mistakenly) in the
  `<= 1` state, converted into `retention(age)` terms:

  - **Coal**: sawtooth, not a plain age curve. `COAL_DECAY_RATE = 0.0025`
    (0.25 pp/yr boiler heat-rate deterioration -- IEA/CIAB 2010, Kim & Moon
    2012 (500 MW unit), Sagaf 2020 *Journal of Thermal Engineering*
    6(6):247-256 (660 MW unit, 0.19-0.44 %/yr, 0.25 pp/yr central)) decays
    `retention` within a `COAL_OVERHAUL_CYCLE_YEARS = 5`-year cycle; at each
    completed cycle, `COAL_OVERHAUL_RECOVERY = 70%` of that cycle's
    accumulated loss is recovered (30% becomes permanent), then the cycle
    restarts. **The 5-year cycle length and the 70% recovery fraction are an
    assumed modelling premise, not values taken from Kim & Moon or Sagaf** --
    those sources give only the decay rate, not an overhaul schedule. No GEM
    file carries a per-plant overhaul date. Marked provisional/estimated;
    revisit if a real overhaul-history source appears. `age_factor` under
    this curve is now materially lower than a pure age curve (e.g. a 40-yr
    coal plant: `age_factor` ~1.03-1.07, vs ~1.10 under plain
    `1 - 0.0025*age` decay) because most of the accumulated loss is
    periodically recovered.
  - **Wind**: `1 - 0.004*age` (linear, 0.4%/yr relative), applied uniformly
    to every wind plant -- no conditional branch, no per-plant availability
    check. `CF_initial` (initial capacity factor) does not exist in any GEM
    file for any of the 1986 wind plants (Brazil 1126, Portugal 225, India
    635 -- confirmed against `gem_validated_plants_*.csv` and
    `gem_units_detail.csv`), so a `CF_initial`-conditioned branch would always
    take the fallback -- there is no operational fallback fraction to report,
    so the wind-fallback stop-and-report metric from the previous entry is
    removed as meaningless. The `1 - 0.0015*age/CF_initial` form
    (`_wind_retention_from_cf_initial`) is kept in the source as **dead
    code** -- defined, documented, never called from `age_factor` or any
    function on its call path (verified by
    `tests/test_age_factor.py::test_wind_cf_initial_formula_exists_but_is_dead_code`,
    which inspects the source of every function on the active path and the
    `age_factor` signature) -- to be wired in only if a real per-plant
    initial-capacity-factor source appears (Global Wind Atlas, manufacturer
    power curves).
  - **Hydro**: `1 - 0.0055*age` (linear, 0.55%/yr, the midpoint of
    ARCHITECTURE Section 7.1's "~0.5-0.6 %/yr"; Turner et al. 2024, *Nature
    Communications*). The 0.79 "non-water-attributable share" scaling from
    the first entry is **not** restored -- it had no documented origin in any
    project source.
  - **Solar**: `(1 - 0.007)^age` (compound), unchanged throughout all three
    entries. 0.7%/yr plant-level; Deline et al. NREL 2020/2024, Boretti &
    Castellotto 2024.
  - **Gas / oil-gas**: pinned neutral, `age_factor = 1.0` (retention 1.0).
    **Provisional / open** -- no literature-backed rate exists in any project
    document.
  - **Nuclear / Bioenergy**: `age_factor = 1.0` fixed (retention 1.0),
    unchanged. In pure retention terms both are already 1.0, so
    `2 - 1.0 = 1.0` -- the multiplier stays neutral under either convention;
    nothing to convert.
  - **Mixed-fuel plants** (6 plants, all thermal): `age_factor` = simple
    average of the component fuels' `age_factor` (from `fuel_types_found`).
    Capacity-weighting not possible -- no per-fuel capacity in the source
    data.
  - **Missing `commissioning_year`** (602 plants, 5.6%: Brazil 97, Portugal
    11, India 494): `age_factor = 1.0` (neutral). Rows kept, flagged
    (`age_factor_neutralized_missing_year`), counted per country, never
    dropped. India's 9.7% (vs Brazil 1.8%, Portugal 2.4%) concentrates in
    wind (258) and solar (172), zero hydro -- see
    `docs/memory/06-areas-de-risco.md`.

- Application unchanged: `age_factor` multiplies the Hazard term per
  `plant_uid` (`data/outputs/tables/ccrs_hazard.csv`), both GCM columns, all
  scenario rows. Multiplicative, never summed. `apply_to_hazard` fails loud
  on a stale hazard CSV (a `plant_uid` with no `age_factor`).

- Distribution observed on the current data (2050 horizon): global
  `age_factor` range **1.0000 .. 1.7480**. Hydro is highest (Brazil mean
  1.32, max 1.75 -- plants from ~1900); solar ~1.17-1.19; wind ~1.08-1.17;
  coal now much closer to neutral than the first entry's plain-decay form
  (~1.03-1.07, all countries) because of the assumed overhaul recovery.

- Reason: closes spec Section 10 item D. `EventMultiplier` and the full
  `CCRS_i,s` assembly remain separate steps.

- References: `src/index/age_factor.py`, `tests/test_age_factor.py`,
  `docs/memory/05-decisoes-tecnicas.md` item 14,
  `docs/memory/06-areas-de-risco.md`.
- Status: active (gas/oil-gas curve provisional; coal's 5-yr/70% overhaul
  schedule is an assumed, revisable parameter -- not gas/oil-gas-style open,
  but flagged as an estimate). Spec item D **closed**, no OPEN block.

---

## [2026-09-04] SPEI drought term added to Hazard (spec item F closed)

- Decision: the SPEI drought-frequency layer (`src/processors/spei_processor.py`,
  committed separately as Step 1) is wired into `Hazard_{i,s}`
  (`src/index/ccrs_calculator.py`) as a **new, independent third additive
  term**, not a complement folded into `water_sub`:

      Hazard_i,s = w_water[bucket]*water_sub + w_heat[bucket]*Tlog(heat)
                 + w_drought[bucket]*Tlog(spei_freq)

  `water_sub = 0.4164*Tlog(ws) + 0.2505*Tlin(sv) + 0.3331*Tlin(iv)` is
  **untouched** -- not renormalised, not given a fourth internal weight.
  `spei_freq` (mean months/yr with SPEI-12 <= -1.0) is transformed the same
  way as `heat` (`Tlog = MinMax(log1p(x))`, per-GCM bound) and added as its
  own weighted side.

- Reason for "new term" over "complement of water_sub": the
  `(0.4164, 0.2505, 0.3331)` within-water weights are a **closed, derived**
  quantity -- they come from the WRI Aqueduct 4.0 category step widths
  (`w_k proportional to 1/tau_k`, spec Section 8.1), not from a judgment
  call. Renormalising them to make room for a fourth water-side term would
  discard a derived value in favour of an arbitrary one, for no documented
  reason, and would silently change the meaning of `water_sub` used
  elsewhere (`risk_bands.py`'s `S_water`, WaterRiskBand). Adding SPEI as an
  independent bucket-weighted term instead: (a) preserves `water_sub`
  bit-for-bit (verified:
  `tests/test_ccrs_calculator.py::test_water_sub_weights_and_output_unchanged_by_spei_integration`),
  (b) treats drought as what it physically is -- a separate hazard pathway
  from water-stress-on-withdrawal, not a sub-component of it -- and (c)
  mirrors how `heat` was already added as an independent term rather than
  folded into anything else.

- Per-bucket weights -- **explicit judgment call, not a calibration or a
  literature value** (same transparency standard as `age_factor.py`'s
  assumed coal-overhaul cycle):

  | bucket  | w_water | w_heat | w_drought |
  |---|---|---|---|
  | hydro   | 0.55  | 0.00  | 0.45 |
  | thermal | 0.525 | 0.175 | 0.30 |
  | wind    | 0.00  | 0.95  | 0.05 |
  | solar   | 0.00  | 0.95  | 0.05 |

  Origin: a direct translation of Douglas's qualitative guidance --
  hydro and cooling-water-dependent thermal generation are materially more
  exposed to prolonged drought than to a single hot day (hence a large
  `w_drought`, and both existing water/heat weights rescaled proportionally
  to make room for it, preserving the original ratio between them); wind and
  solar have no physical water-dependence mechanism (unchanged from the
  pre-SPEI matrix, `w_water = 0`) but are deliberately **not** given an
  absolute-zero drought weight, since a drought-driven regional
  water/energy-system stress is not literally impossible for them either --
  hence the small, non-mechanistic `0.05`. This is **not** an AHP/pairwise
  calibration and **not** derived from any published water/heat/drought
  importance ratio -- no such ratio exists in the literature for any of
  these technologies. Revisit if a calibrated alternative becomes available.
  Flagged as a Monte Carlo sensitivity candidate (spec item J), not
  re-derived here.

- `FROZEN_BOUNDS` extension (spec item G) -- `spei` added as a new,
  per-GCM-keyed entry, same treatment as `heat` (SPEI depends on the GCM,
  unlike the Aqueduct water terms):

      "spei": {
          "gfdl_esm4": (1.4441261291503906, 4.022922515869141),
          "miroc6":    (1.2722063064575195, 4.160458564758301),
      }

  This is an **authorised extension**, not a perturbation or redefinition:
  the pre-existing `ws`/`sv`/`iv`/`heat` values were recomputed via
  `compute_global_bounds()` immediately before this change and confirmed
  byte-identical to the pre-SPEI snapshot. `BOUNDS_DATA_SNAPSHOT` stays
  `2026-09-04` (same day, real data on disk); the extension is recorded here
  rather than by moving the snapshot date, since no existing bound moved.

- **Comparability impact -- reported explicitly, not silently.** Adding a
  third additive Hazard term and rescaling every bucket's water/heat weights
  means `Hazard_{i,s}` and therefore `CCRS_{i,s}` for **every plant** changed
  relative to any T1-T6 number computed before this integration (the
  pre-SPEI 2-way `(w_water, w_heat)` matrix no longer applies to any output
  after this point). Formal before/after comparisons of Hazard/CCRS values,
  band shares, or capacity-share reports must not mix pre- and
  post-integration numbers. `analysis/ccrs_bucket_weighted_distribution.md`
  and other pre-integration diagnostics remain valid only as distribution-
  shape exploration under the old 2-way matrix, per their own disclaimers.

- Observed impact on this data (`compute_hazard_by_gcm()`, all three
  countries, GFDL-ESM4 / MIROC6, post-integration): Hazard range still
  `[0, ~0.99]` on both GCM columns (transform range is unchanged, `[0, 1]`
  per term). Per-bucket mean Hazard (GFDL-ESM4 / MIROC6): hydro 0.297/0.329,
  thermal 0.318/0.381, wind 0.195/0.603, solar 0.386/0.690 -- wind/solar
  remain the most GCM-sensitive buckets (heat-dominated, `w_heat = 0.95`),
  consistent with the pre-integration finding that MIROC6 runs hotter for
  heat-only buckets. 32,424 rows, zero `plant_uid` x scenario duplication
  (unchanged from T1).

- References: `src/index/ccrs_calculator.py`,
  `src/processors/spei_processor.py`,
  `tests/test_ccrs_calculator.py` (bucket-weight, water_sub-unchanged,
  frozen-bounds and end-to-end regression tests),
  `analysis/climate_risk_score_spec.md` Section 5 / Section 10 item F,
  `docs/ARCHITECTURE.md` Section 5.1/5.3.
- Status: active. Spec item F **closed**. Item J (Monte Carlo) still open --
  the thermal triple and the wind/solar drought allowance are candidates for
  perturbation, not yet implemented.

---

## GEAR v3 rework — Phase 0 blocking verifications (closed 2026-09-11)

The five entries below close Phase 0 of `docs/rework/GEAR_v3_work_plan.md`.
Scope note: these are findings for the v3 methodology reconstruction
(`docs/rework/GEAR_v3_methodology_nature_format.md`), not yet implemented in
`src/index/ccrs_calculator.py` or any active pipeline code -- CCRS above
remains the current computed output until Phase 1 lands. Tier of evidence
stated per entry per the standing rule.

## [2026-09-11] GEM cooling-technology field: confirmed absent (v3 Phase 0.1)
- Decision: Thermal plants are not split by cooling technology (once-through /
  recirculating / dry / hybrid) in GEAR v3. No such field exists in the
  ingested GEM data.
- Reason: Direct inspection of `gem_global_integrated_power_tracker_20260809.xlsx`
  (Global Integrated Power Tracker, August 2026 release, 52-column `Power
  facilities` sheet) found no column under any name containing "cooling".
  The closest field, `Technology`, records boiler/turbine cycle type
  (subcritical, combined cycle, etc.), not condenser cooling system --
  confirmed absent for Brazil, Portugal and India alike. Tier: data-
  availability finding, not a literature threshold; primary source is the
  raw GEM workbook itself.
- Status: active. Closes v3 methodology Section 3.2 ("pending") as resolved.

## [2026-09-11] GEM retrofit/repowering field: re-confirmed empty (v3 Phase 0.3)
- Decision: No overhaul/major-refurbishment date is available from GEM for
  GEAR v3, same as the pre-rework finding already on record (age_factor
  coal entry, 2026-09-04).
- Reason: Re-inspection of the same August 2026 GEM snapshot found no
  "retrofit"/"repower"/"refurbish" column. The adjacent "Conversion" field
  family (fuel-conversion events, not overhaul dates) is effectively 0
  non-null across Brazil, Portugal and India (two isolated non-material
  exceptions in Brazil's `Conversion to (fuel)`/`Conversion to (GEM unit
  ID)`). No rename, addition or removal relative to the prior inventory.
  Tier: data-availability finding, primary source is the raw GEM workbook.
- Status: active. Confirms unchanged status of the existing `age_factor`
  coal-curve limitation; no v3-specific action needed beyond noting the
  re-check.

## [2026-09-11] FWI/EFFIS wildfire danger classes: 6-class system adopted (v3 Phase 0.2)
- Decision: GEAR v3's Wildfire hazard uses the EFFIS 6-class FWI
  classification as Tier 1, not a 5-class simplification: Low (<11.2),
  Moderate (11.2-21.3), High (21.3-38.0), Very High (38.0-50.0), Extreme
  (50.0-70.0), Very Extreme (>70.0). Very Extreme is kept as a distinct
  class, not collapsed into Extreme.
- Reason: Verified against the primary source -- EFFIS (Copernicus
  Emergency Management Service) technical background, "Fire Danger
  Forecast" (`forest-fire.emergency.copernicus.eu/about-effis/technical-
  background/fire-danger-forecast`), built on Van Wagner & Pickett (1985).
  The "Very Extreme" tier was added by EFFIS in June 2021 specifically to
  discriminate danger within Mediterranean-summer areas otherwise flattened
  at "Extreme" -- collapsing it back would lose exactly the discrimination
  it was introduced to provide. Tier 1, cited primary source.
- Status: active. Closes v3 methodology Section 4's Wildfire Tier 1 entry.

## [2026-09-11] Extreme Precipitation downgraded Tier 1 -> Tier 3 (v3 Phase 0.2)
- Decision: GEAR v3's Extreme Precipitation hazard uses a Tier 3 sample-
  relative percentile cutoff (P50/P75/P90/P95 of CMIP6 `pr` extremes), the
  same approach already used for Extreme Heat, not a HAZUS-MH-derived
  absolute threshold.
- Reason: The drafted HAZUS-MH inundation-depth values (0.2/0.5/1.5 m) do
  not exist in the primary FEMA Hazus Flood Model Technical Manual. HAZUS-MH
  uses continuous depth-damage curves per building occupancy type (900+
  curves, depth in feet from finished floor, -4 to +24 ft), not categorical
  depth cutoffs -- confirmed against the Hazus 6.1 (July 2024) manual and
  Scawthorn et al. 2006 (*Natural Hazards Review* 7(2)). Independent of that
  mismatch, HAZUS-MH thresholds are structurally incompatible with this
  pipeline's input: Extreme Precipitation reuses CMIP6 precipitation-amount
  data (`pr`), and there is no hydrological conversion step from
  precipitation to inundation depth anywhere in the pipeline. No absolute
  physical threshold is available given current data; declared limitation,
  same as Extreme Heat's.
- Status: active. Closes v3 methodology Section 4's Extreme Precipitation
  entry; HAZUS-MH reference removed from that row.

## [2026-09-11] GEAR v3 Phase 1: Risk_i,h replaces the CCRS core (Equation 1)
- Decision: `src/index/ccrs_calculator.py` and `src/index/ccrs_report.py` are
  deleted, not deprecated in place. `src/index/risk_calculator.py` replaces
  them: `risk_i_h(hazard_i_h, exposure_mw, vulnerability) = hazard_i_h *
  exposure_mw * vulnerability` (Methods Section 1, Equation 1), computed and
  kept **per hazard** -- there is no combined "Hazard" value for a plant
  anywhere in this module, and nothing sums or blends `Risk_i,h` across
  hazards. `EventMultiplier` is removed from this core entirely (not
  imported, not called); `event_multiplier.py` itself is kept as a Phase 5
  contextual-validator candidate, unused for now. Exposure is exposed as two
  distinct forms: `exposure_capacity_mw` (raw MW, the only form `risk_i_h`
  accepts) and `exposure_log10_display` (visualization-only, returns a
  tagged `ExposureLog10Display` array type that `risk_i_h` raises
  `TypeError` on) -- the guard is enforced at the type level, not just by
  convention. Every hazard term's temporal-window assumption is an explicit
  named constant (`HAZARD_TEMPORAL_WINDOW`), not left to a processor's
  docstring. Tier: engineering/architecture decision implementing a closed
  methodology equation; no new empirical threshold introduced.
- Reason: the retired core computed one weighted-sum `Hazard_i,s` per plant
  (water/heat/drought bucket weights) and then `CCRS_i,s = Hazard_i,s *
  age_factor_i * EventMultiplier_c` -- exactly the aggregate-index and
  cross-hazard-summation pattern the v3 methodology treats as a
  methodological fallacy (Section 9). Equation 1 requires a Risk value per
  hazard, never combined; `age_factor` (Vulnerability) is unchanged and
  still applied, `EventMultiplier` has no place in this equation at all.
- **Flagged, not silently resolved**: the retired core also computed `sv`
  (seasonal variability) and `iv` (interannual variability) folded into a
  composite `water_sub` term alongside `ws`. The v3 methodology's Section 2
  hazard checklist names only "Water Stress" (`ws`) -- it does not list
  `sv`/`iv` as hazards, and gives no instruction to fold them into Water
  Stress. Rather than silently keeping the old composite or silently
  dropping the two indicators, `risk_calculator.py` computes `sv`/`iv` as
  their own independent, clearly labelled `Risk_i,h` terms (their existing
  per-term `FROZEN_BOUNDS` are reused unchanged), explicitly marked as not
  one of the v3 Section 2 hazards, pending Phase 3's applicable-hazard-set
  decision. This is an open question for the author, not decided here.
- Downstream breakage, expected and not silently patched: `src/index/
  risk_bands.py`, `src/index/monte_carlo.py`, `src/index/emdat_validation.py`,
  `src/main.py`, and the whole `src/visualization/` package still import the
  now-deleted `ccrs_calculator`/`ccrs_report` symbols (`BUCKET_WEIGHTS`,
  `compute_hazard`, `compute_hazard_by_gcm`, the `ccrs_{gcm}` columns) and
  fail at import or call time. These modules compute or display quantities
  (WaterRiskBand/HeatRiskBand from the retired combined Hazard, Monte Carlo
  perturbation of `BUCKET_WEIGHTS`, CCRS-labelled figures) that depend on
  methodology not yet decided for v3 (Phase 3's `RiskBand_i,h`, Phase 4's
  PSAE, Phase 6/7's sensitivity analysis and visualization). Patching them
  now would mean inventing that methodology ahead of its own phase; they are
  left broken and undocumented-as-working, not silently routed around.
  `age_factor.py` and `event_multiplier.py` are updated to import
  `risk_calculator` instead (a mechanical rename only, no logic change) so
  they remain independently usable.
- References: `src/index/risk_calculator.py`, `tests/test_risk_calculator.py`,
  `docs/rework/GEAR_v3_methodology_nature_format.md` Sections 1/3,
  `docs/rework/GEAR_v3_work_plan.md` Phase 1.
- Status: active. Phase 1.1, 1.2 and 1.4 closed. `sv`/`iv` inclusion is
  explicitly open, deferred to Phase 3.

## [2026-09-11] GEAR v3 Phase 2.1: Extreme Precipitation processor (Tier 3, percentile-cutoff)
- Decision: `src/processors/extreme_precipitation_processor.py` (new)
  computes the raw Extreme Precipitation raster: mean days/year, over the
  2041-2070 window, with daily CMIP6 `pr` exceeding that pixel's own P95
  threshold of wet-day (`pr >= 1 mm/day`, ETCCDI convention) amounts. No new
  download -- reuses the daily `pr` series `cds_precipitation_downloader`
  already acquires for the SPEI drought term (`spei_processor`'s
  `raw_dir`/`_open_series`/`_pick_var`, unchanged). Same unified grid
  infrastructure as every other hazard (native CMIP6 grid -> nearest-neighbour
  resample to the country's fixed 1 km grid via
  `cds_tasmax_downloader._resample_to_1km` -> per-country Min-Max, models and
  scenarios pooled jointly, identical domain-pooling rule to
  `heat_stress_processor`/`spei_processor`, same shared `GridMismatchError`
  guard). Tier: **Tier 3 only** -- `EXTREME_PRECIP_PERCENTILE = 95.0`
  (P95, ETCCDI "very wet days"/R95p convention, Zhang et al. 2011) and
  `WET_DAY_THRESHOLD_MM = 1.0` are sample-relative percentile-cutoff
  constants, not a cited absolute damage threshold. HAZUS-MH is not
  referenced as a threshold source anywhere in this module (confirmed by
  `tests/test_extreme_precipitation_processor.py::
  test_no_hazus_mh_used_as_a_threshold_source`), consistent with the Phase 0
  closure ("Extreme Precipitation downgraded Tier 1 -> Tier 3").
  `PRECIP_TEMPORAL_WINDOW` extends the Phase 1 `HAZARD_TEMPORAL_WINDOW`
  pattern (`src/index/risk_calculator.py`) -- same schema, asserted equal at
  import time -- without merging into that dict (see below).
- Reason: the methodology's Tier 3 fallback for Extreme Precipitation
  (`docs/rework/GEAR_v3_methodology_nature_format.md` Section 4) specifies
  "Percentiles P50/P75/P90/P95 of daily pr extremes," not a fixed physical
  threshold like Extreme Heat's 40 C -- there is no defensible absolute
  threshold at this tier (Phase 0 closure). The percentile-cutoff idea is
  therefore applied one level earlier than Extreme Heat's pattern: instead
  of counting days above a fixed mm value, each pixel's own P95 of its wet
  days defines what "extreme" means locally (a monsoon and a semi-arid pixel
  do not share one mm cutoff), and the raw indicator counts exceedance
  days/year against that local threshold -- structurally the same
  "mean days/year exceeding a threshold" shape as Extreme Heat's
  `days_per_year_with_tasmax_gt_40C`.
- **Not wired into the core, on purpose**: `risk_calculator.HAZARD_TERMS`
  and `HAZARD_TEMPORAL_WINDOW` are unchanged (verified:
  `test_not_wired_into_risk_calculator_hazard_terms_yet`,
  `test_precip_not_merged_into_the_core_hazard_temporal_window_dict`). This
  hazard is a Phase 2.5 correlation-gate candidate (against Water Stress and
  Drought) and is not in any bucket's applicable-hazard table -- both are
  Phase 3 decisions, not made here.
- References: `src/processors/extreme_precipitation_processor.py`,
  `tests/test_extreme_precipitation_processor.py` (11 tests),
  `docs/rework/GEAR_v3_methodology_nature_format.md` Sections 2/4/5,
  `docs/rework/GEAR_v3_work_plan.md` Phase 2.1.
- Status: active. Raw + normalised raster layer only. Correlation gate
  (Phase 2.5) and applicable-hazard-set inclusion (Phase 3) are open.

## [2026-09-11] GEAR v3 Phase 2.2: Wildfire deferred (data availability)
- Decision: Wildfire (FWI/EFFIS) is removed from the GEAR v3 core hazard
  checklist and repositioned as future work / a declared scope boundary --
  the same treatment already given to SLR (`docs/ARCHITECTURE.md` Section
  10, "What GEAR does not do": "SLR: excluded for lack of a defensible
  empirical basis... A natural extension once per-technology coefficients...
  are available"; formalized as a dedicated entry here is still pending per
  Phase 8 item 8.1 of `docs/rework/GEAR_v3_work_plan.md`). No processor was
  ever implemented for Wildfire (Phase 2.2 was never started), so this is a
  documentation-only closure -- no code to remove.
- Reason, two independent findings, both checked directly rather than
  assumed:
  1. **CDS catalogue gap (Tier: primary-source, direct catalogue query --
     `analysis/fwi_catalog_check.md`).** The Canadian FWI System needs daily
     near-surface relative humidity. `near_surface_relative_humidity` is not
     on the CDS `projections-cmip6` daily catalogue under any model. The
     fallback (`near_surface_specific_humidity` + `sea_level_pressure`, to
     derive RH) is not usable either: `near_surface_specific_humidity` is
     available only for gfdl_esm4/ssp126 and gfdl_esm4/ssp370 -- missing for
     gfdl_esm4/ssp585 and for miroc6 under all three scenarios. No path
     exists to compute FWI for the full gfdl_esm4 + miroc6 x 3-SSP matrix
     this pipeline requires from any CDS-catalogued daily variable.
  2. **ETH Zurich FWI-CMIP6 dataset ruled out on two independent grounds
     (Tier: primary-source, direct archive inspection).** Quilcaille et al.
     2023 (*ESSD* 15:2153-2177, DOI 10.3929/ethz-b-000583391) was checked as
     an alternative global, SSP-based, pre-computed source. (a) **Zero
     GFDL-ESM4 coverage**: the archive's `fwixd_hursmin.zip` (recommended
     hursmin version of the "extreme fire weather days" indicator, closest
     to a percentile-based use case) was inspected directly -- its ZIP
     central directory (1,318 internal filenames, read via HTTP range
     requests, no bulk download) lists MIROC6 under all three required
     scenarios (ssp126/ssp370/ssp585) but **no GFDL-ESM4 entry at all**,
     under any scenario including historical; the only GFDL-family model
     present is GFDL-CM4 (a different model), and only for
     historical/ssp245/ssp585. (b) **Structurally incompatible regardless of
     model coverage**: the dataset provides annual indicators only (no daily
     FWI time series, no EFFIS-style class output), and its "extreme" cutoff
     (`fwixd`) is defined as the local 95th percentile of FWI over the
     1850-1900 reference period, per grid cell -- a location-specific,
     historical-percentile-relative threshold, not the fixed, globally
     applied EFFIS absolute class boundaries (Low/Moderate/High/Very
     High/Extreme/Very Extreme) already confirmed as Tier 1 in the Phase 0
     closure ("FWI/EFFIS wildfire danger classes: 6-class system adopted").
     Using it would silently substitute a different classification
     philosophy for the one already decided.
- This is a **future-work deferral, not a silent omission**: the verified
  EFFIS 6-class boundaries and the FIRMS-is-not-a-hazard-input argument
  remain in `docs/rework/GEAR_v3_methodology_nature_format.md` Section
  10.1 ("Deferred hazards / future work"), citable if a data source (a
  third GCM with full RH coverage, a different global FWI product, or a
  future CDS catalogue addition) appears later.
- Consequence for Phase 2.5 (correlation gate): the Wildfire-related
  candidate pairs (Wildfire vs. Extreme Heat, Wildfire vs. Water Stress)
  are removed from the gate's scope along with the hazard. Only Extreme
  Precipitation (vs. Water Stress/Drought) remains as a gated candidate;
  the mandatory, non-gated Water Stress/Drought (ws/sv/iv) reporting is
  unaffected.
- References: `analysis/fwi_catalog_check.md`,
  `docs/rework/GEAR_v3_methodology_nature_format.md` Sections 2, 3, 5,
  10.1, `docs/rework/GEAR_v3_work_plan.md` Phase 2.2/2.5.
- Status: active. Deferred, not reopened without a new data source.

## [2026-09-11] GEAR v3 Phase 1.3: Thermal bucket implemented as homogeneous (no cooling-technology split)
- Decision: `risk_calculator.py` computes `Risk_i,h` for every plant in the
  `thermal` bucket uniformly -- no water-cooled/dry-cooled sub-bucket split
  is implemented in code.
- Reason: this is the code-level implementation of the Phase 0 data-
  availability finding ("GEM cooling-technology field: confirmed absent",
  above) -- distinct from that finding itself. Since no cooling-technology
  field exists in GEM under any name, a split is not implementable with
  current data; homogeneous treatment is the only option, and the resulting
  likely overstatement of water-stress risk for whatever dry-cooled
  fraction exists within Thermal is a declared limitation (methodology
  Section 3.2), not a silent gap. Tier: implementation consequence of a
  Tier-1 (primary-source-verified) data-availability finding, no new
  threshold introduced.
- Status: active.

## [2026-09-11] GEAR v3 Phase 2.3: Extreme Wind processor (ERA5 gust, dual-consumer threshold design)
- Decision: `src/downloaders/era5_wind_downloader.py` (new) downloads hourly
  ERA5 10 m instantaneous wind gust (`instantaneous_10m_wind_gust`, CDS
  dataset `reanalysis-era5-single-levels`), one request per country/year over
  `ERA5_WIND_BASELINE_PERIOD` (1991-2020). `src/processors/
  extreme_wind_processor.py` (new) reduces this to a single raw physical
  raster -- per-pixel mean annual maximum 10 m gust (m/s), the standard
  characteristic-gust metric in wind engineering -- on the same unified grid
  infrastructure as every other hazard (`cds_tasmax_downloader._resample_to_
  1km` onto the country's fixed 1 km grid, per-country Min-Max, shared
  `GridMismatchError` guard). `WIND_TEMPORAL_WINDOW` follows the
  `PRECIP_TEMPORAL_WINDOW` pattern: same schema as `risk_calculator.
  HAZARD_TEMPORAL_WINDOW`, asserted at import time, standalone (not merged).
  Tier: this module produces the raw+normalized raster and the reusable
  threshold-dispatch arithmetic only; it introduces no new empirical
  threshold value beyond the two already closed in Phase 0.4 (below).
- **One processor, two consumers, threshold logic as a parameter**: the raw
  layer is deliberately threshold-agnostic (unlike heat/precip's "days above
  X" indicator) because its two downstream consumers apply genuinely
  different, non-convergent threshold methods to the same physical quantity
  (Phase 0.4 closure, methodology Section 3.1/4): Wind bucket Tier 1 (IEC
  turbine cut-out, ~25 m/s, fixed) vs. Solar bucket Tier 3 (ERA5 gust
  percentiles P75/P90/P95/P99, final, not a placeholder). `WIND_BUCKET_
  THRESHOLD_SPEC` / `SOLAR_BUCKET_THRESHOLD_SPEC` are named-constant specs
  passed into one dispatcher, `classify_extreme_wind(values, threshold_spec)`
  -- not two copy-pasted processors or two hardcoded threshold branches
  scattered across the module.
- **Correlation-gate scope confirmed against the methodology draft, not
  assumed**: verified `docs/rework/GEAR_v3_methodology_nature_format.md`
  Section 2 ("Extreme Wind is not part of a single shared hazard core; it is
  assigned per bucket per the mechanistic rationale in Section 3") and
  Section 5, which names only Extreme Precipitation as a gated candidate
  (plus the report-only Water Stress/Drought pair). Extreme Wind is not
  listed in either place. This processor is therefore correctly NOT added to
  any Phase 2.5 correlation-gate candidate list -- confirming, not assuming,
  the work-plan's Phase 2.3 framing ("not part of the chronic-hazard
  correlation set"). **Numbering note, not a substance change**: the
  methodology draft was concurrently revised during this task to defer
  Wildfire for a data-availability reason unrelated to wind (see "GEAR v3
  Phase 2.2: Wildfire deferred", below) -- the checklist that used to read
  "six hazards" now reads "five", so Extreme Wind is the framework's 5th
  hazard, not the "dedicated 6th hazard" language used when this task was
  scoped. The correlation-gate exemption finding is unaffected either way:
  Extreme Wind was never a gate candidate under either count.
- **OPEN, flagged not silently decided -- ERA5 baseline period**: every other
  v3 hazard is a CMIP6 projection for the explicit 2041-2070 window; ERA5 is
  a historical reanalysis with no SSP/GCM axis and no 2050 horizon. The
  methodology draft names ERA5 as the Extreme Wind data source but does not
  specify or reconcile a baseline averaging period against the other
  hazards' mid-century framing -- unlike the Aqueduct/CMIP6 alignment note
  already declared in Methods Section 1.1. `ERA5_WIND_BASELINE_PERIOD =
  (1991-01-01, 2020-12-31)` (the current WMO 30-yr climate normal) is an
  engineering default chosen here, not a Phase-0-verified decision;
  `extreme_wind_processor.WIND_TEMPORAL_WINDOW_IS_PROJECTED = False` makes
  the asymmetry an explicit, queryable flag rather than a buried assumption.
  Pending the author's confirmation of either this period or an alternative,
  same status class as the still-open gas `age_factor` rate and the RNG-
  granularity question.
- Reason: Phase 0.4 already closed which threshold each bucket uses (this
  file, "Solar Extreme Wind: ERA5 gust percentile is final, not
  contingency", below); Phase 2.3 implements the acquisition/processing
  layer those two closed decisions consume, without pre-empting Phase 3.1's
  RiskBand assembly or Phase 3.1's applicable-hazard-table wiring.
- **Not wired into the core, on purpose**: `risk_calculator.HAZARD_TERMS`
  and `HAZARD_TEMPORAL_WINDOW` are unchanged (verified:
  `test_not_wired_into_risk_calculator_hazard_terms_yet`,
  `test_wind_not_merged_into_the_core_hazard_temporal_window_dict`). Not a
  correlation-gate candidate (see above); its applicable-hazard-table
  membership (Wind, Solar buckets) is a Phase 3.1 decision.
- References: `src/downloaders/era5_wind_downloader.py`,
  `src/processors/extreme_wind_processor.py`,
  `tests/test_extreme_wind_processor.py` (14 tests),
  `docs/rework/GEAR_v3_methodology_nature_format.md` Sections 2/3.1/4,
  `docs/rework/GEAR_v3_work_plan.md` Phase 2.3.
- Status: active. Raw + normalized raster layer and threshold-dispatch
  utility only. RiskBand assembly and applicable-hazard-set inclusion
  (Phase 3.1/3.2) are open; the ERA5 baseline-period choice above is open
  pending author confirmation.

## [2026-09-11] GEAR v3 Phase 2.4: Normalization module, neg-log transform confirmed to replace log1p (Methods Section 4.2 closed)
- Decision: `src/index/normalization.py` (new) is an isolated module
  (standing modularity rule) implementing the `FROZEN_BOUNDS` origin logic,
  the per-hazard normality/skewness check, and the structured bounds origin
  table (Methods Sections 4.2/4.3). It imports `risk_calculator.py`'s
  plant-loading/raster-sampling infrastructure (`load_plants`,
  `sample_raster`, `raster_path`, `WATER_TO_HEAT`, `COUNTRIES`, `BUCKETS`)
  unchanged and does **not** modify `risk_calculator.FROZEN_BOUNDS` or
  `transform_term` -- it produces an independent recommendation for Phase
  3.3 to apply later. Runs the identical procedure over
  `NORMALIZATION_CANDIDATE_TERMS = risk_calculator.HAZARD_TERMS +
  ("precip", "wind")` = `ws, heat, sv, iv, spei, precip, wind` -- the two
  Phase 2.1/2.3 additions and the Phase-1-flagged `sv`/`iv` terms get no
  special-casing, same check as every other term. Wildfire is absent by
  construction (deferred, Phase 2.2), not carried as a candidate anywhere.
- **Author-confirmed methodology extension, not assumed**: the task
  description named a third transform candidate, `f(x) = -ln(1-x)`,
  replacing the retired log-transform to fix tail compression -- but
  neither `docs/rework/GEAR_v3_methodology_nature_format.md` Section 4.2
  nor any prior `docs/DECISIONS.md`/`docs/memory/` entry documented this
  third option or a replacement decision; the methodology draft only
  described the binary choice (approximately-normal -> direct Min-Max;
  long-tailed -> log-transform). Per CLAUDE.md Section 3 (undecided
  methodology is a stop point, not something code resolves alone), this was
  put to the author before implementation. Confirmed: selection is a
  uniform per-hazard normality/skewness check across three candidates, and
  `-ln(1-x)` replaces `log1p` as the skewed-variable transform everywhere,
  not only for Extreme Heat -- log1p compresses a right-skewed variable's
  upper tail (large values pushed together near 1.0, exactly where a
  physically extreme plant should be most separated from a moderate one);
  `-ln(1-x)` expands it instead (`-> infinity` as `x -> 1`).
- Mechanics: `normality_check` uses Fisher-Pearson skewness
  (`scipy.stats.skew`) as the DECIDING criterion, `|skew| > 0.5` (Bulmer,
  1979, *Principles of Statistics*, "fairly symmetrical" convention;
  author-declared engineering threshold, not a hydrometeorology-specific
  literature value). Shapiro-Wilk (`scipy.stats.shapiro`, deterministically
  subsampled above 5000 points) is computed and reported in the origin
  table as a diagnostic only -- it does not override the skewness verdict,
  because at the sample sizes here (thousands of plant x scenario rows) it
  rejects exact normality for nearly any real geophysical sample, including
  mildly skewed ones, making it uninformative as a binary gate.
  `select_transform` returns `neg_log_minmax` if skewed, else
  `direct_minmax`; `log1p_minmax` (`transform_log1p_minmax`) is retired --
  kept only so the origin table can show the pre-redesign transform
  `ws`/`heat`/`spei` used in `risk_calculator.py`, never returned by
  selection.
- `transform_neg_log_minmax` arithmetic: preliminary scale `x_scaled =
  (raw - lo) / (padded_hi - lo)`, `padded_hi = hi +
  UPPER_TAIL_PADDING_FRACTION * (hi - lo)`, `UPPER_TAIL_PADDING_FRACTION =
  0.05` (author-declared engineering parameter, no cited source -- keeps
  the pooled maximum strictly below the `x=1` singularity of `-ln(1-x)`);
  then `transformed = -ln(1 - x_scaled)`, rescaled onto `[0,1]` by its
  closed-form maximum `ln(1 + 1/pad)` (independent of `lo`/`hi`).
- Origin table (`build_origin_table`): one row per term (per GCM for
  GCM-dependent terms `heat`/`spei`/`precip`), columns `hazard_term`,
  `hazard_label`, `gcm`, `origin_source`, `data_tier`, `lower_bound_raw`,
  `upper_bound_raw`, `pool_n`, `skewness`, `shapiro_stat`, `shapiro_p`,
  `shapiro_subsampled`, `is_skewed`, `transform_selected`,
  `transform_note`. `data_tier` is uniform ("empirical, pooled sample
  min/max, not a literature constant") -- the tier of the bound itself,
  distinct from the RiskBand threshold tier (Phase 3.2), a separate table.
- Reason: closes Methods Section 4.2/4.3's normalization-transform-choice
  methodology, as an isolated module per the standing modularity rule,
  without pre-empting Phase 3.3's decision to actually apply the
  recommendation (including to Extreme Heat specifically).
- References: `src/index/normalization.py`, `tests/test_normalization.py`
  (23 tests, pure-function only), `docs/memory/05-decisoes-tecnicas.md`
  item 31, `docs/rework/GEAR_v3_methodology_nature_format.md` Section 4.2/
  4.3, `docs/rework/GEAR_v3_work_plan.md` Phase 2.4.
- Status: active. Produces a recommendation only -- `risk_calculator.py`'s
  own `FROZEN_BOUNDS`/`transform_term` are unchanged and remain log1p-based
  until Phase 3.3 applies this module's output. Applicable-hazard-set
  inclusion for `sv`/`iv`/`precip`/`wind` (Phase 3.1) is unaffected, still
  open.

## [2026-09-11] Solar Extreme Wind: ERA5 gust percentile is final, not contingency (v3 Phase 0.4)
- Decision: GEAR v3's Solar bucket Extreme Wind hazard uses the ERA5 gust
  percentile method (P75/P90/P95/P99) as its Tier 3 basis, final -- not a
  fallback pending a Tier 1 structural threshold. Turbine cut-out speed
  (~25 m/s, IEC design standard) remains Wind-bucket-specific and is not
  shared with Solar.
- Reason: No single defensible Tier 1 value exists for solar tracker
  structural wind uplift. ASCE 7's design wind speed is inherently
  site-specific by construction (derived from location, Risk Category,
  Exposure Category, ASCE 7 Section 26), not a universal constant the way
  IEC turbine cut-out speed is. Manufacturer survival ratings vary by
  product generation -- observed range ~51-60+ m/s (115 mph vs. 135+ mph)
  across two data points from a single manufacturer alone, before
  accounting for the wider manufacturer landscape. This is not comparable
  in rigor to the turbine cut-out speed already used for the Wind bucket.
- Status: active. Closes v3 methodology Section 3.1/Section 4's Solar
  Extreme Wind entry.

## [2026-09-11] GEAR v3 Phase 2.3 follow-up: ERA5 temporal asymmetry retained (CMIP6 substitution investigated and rejected)
- Decision: Extreme Wind keeps ERA5 (`instantaneous_10m_wind_gust`,
  1991-2020 baseline) as its data source. The temporal/scenario asymmetry
  flagged open at Phase 2.3 closure (ERA5 historical reanalysis, no SSP
  axis, vs. every other v3 hazard's explicit CMIP6 2041-2070 projection
  under 3 SSPs) is retained and documented as a declared limitation, not
  resolved by switching source. No CMIP6 substitution is implemented.
  `extreme_wind_processor.WIND_TEMPORAL_WINDOW_IS_PROJECTED` stays `False`.
  No code changed by this entry -- documentation only.
- Reason: two independent findings, either one alone sufficient to reject
  a CMIP6 substitution -- investigated, not assumed.
  1. **Catalogue finding (Tier: primary-source, direct CDS catalogue
     query, `analysis/wind_catalog_check.py`/`.md`).** `near_surface_wind_speed`
     (sfcWind, daily MEAN near-surface wind speed) is confirmed available
     on the CDS `projections-cmip6` daily catalogue for both configured
     GCMs (gfdl_esm4, miroc6), all three active scenarios
     (ssp126/ssp370/ssp585), full 2041-2070 coverage -- re-verifying, at
     daily resolution and against this pipeline's exact tasmax/pr
     grid/download pattern, the same finding already recorded during the
     Phase 2.2 FWI investigation (`analysis/fwi_catalog_check.md`).
     However: no `daily_maximum_near_surface_wind_speed` (sfcWindmax)
     variant exists on the catalogue under any model/scenario -- unlike
     tasmax, where this pipeline already uses the daily-MAXIMUM CDS
     variable (`daily_maximum_near_surface_air_temperature`) specifically
     because a daily mean would understate the extreme. No such maximum
     variant exists for wind; only the daily mean is available. Separately,
     `instantaneous_10m_wind_gust` (the ERA5 quantity Phase 2.3 already
     uses) does not exist on the CMIP6 `projections-cmip6` catalogue under
     any name.
  2. **Physical-quantity incompatibility (structural/definitional finding,
     not a data-tier question).** CMIP6 `sfcWind` is a daily-mean
     sustained wind speed; ERA5 `instantaneous_10m_wind_gust` is an
     instantaneous short-duration peak superimposed on the mean flow --
     these are not the same physical quantity, and no trivial
     normalization bridges them. Converting one to the other requires an
     explicit gust-factor parameterization (wind-engineering codes give
     ~1.4-1.7 in open terrain, but the ratio is conditional on atmospheric
     stability, terrain roughness, and gust-generation mechanism --
     convective vs. synoptic -- not a universal constant), which the
     already-closed Phase 2.3 dispatcher design (`classify_extreme_wind`,
     IEC ~25 m/s cut-out for Wind, ERA5 gust percentiles P75/P90/P95/P99
     for Solar) does not implement and was not designed around. Applying
     those same thresholds to a daily-mean CMIP6 series without an
     explicit gust-estimation step would silently compare two different
     physical quantities under one threshold label.
  3. **Supporting, not decisive, Tier 2 literature on GCM-resolution
     underestimation of wind extremes** (peer-reviewed, not a primary
     threshold source; cited as directional corroboration of finding 2,
     not as an independent third ground): Shen et al. 2022 (*Ann. NY Acad.
     Sci.*, 22 CMIP6 models) and Morim et al. 2020 document non-trivial
     mean-wind bias against reanalysis (-1 to +1 m/s CMIP6 vs. ERA-Interim;
     -2 to +1.5 m/s CMIP5); a direct, quantified comparison (Copernicus/
     NHESS 2024, convection-permitting vs. ERA-Interim at ~0.75 deg -- a
     resolution comparable to or finer than the GCMs used here) found
     ERA-Interim significantly underestimates gust percentiles above P15,
     with an observed-maximum deficit of ~7 m/s, because severe convective
     gusts (downdrafts, mesoscale organized systems) operate at
     spatial/temporal scales coarse-resolution models parameterize rather
     than resolve; IPCC AR6 WGI Chapter 11 attributes "low confidence" to
     severe-wind trend assessment in most regions specifically because
     models "often do not have sufficient resolution or accurate
     parametrization." This means a converted CMIP6-based gust proxy would
     likely bias Extreme Wind risk downward in a known direction, not
     merely add noise -- but this point is corroborating, not the primary
     rejection ground; findings 1 and 2 already independently reject the
     substitution before this literature is invoked.
- Practical consequence, flagged for the manuscript: Extreme Wind's
  RiskBand does not vary by SSP scenario the way every other hazard's
  does (ERA5 has no SSP axis) -- a declared asymmetry in Section 9's
  cross-hazard comparability discussion, not a silent gap.
- References: `analysis/wind_catalog_check.py`/`.md`,
  `docs/rework/GEAR_v3_methodology_nature_format.md` Sections 2, 3.1, 4,
  9, `docs/memory/05-decisoes-tecnicas.md` item 32,
  `src/downloaders/era5_wind_downloader.py`,
  `src/processors/extreme_wind_processor.py` (unchanged by this entry).
- Status: active. Closes the open ERA5-baseline-period item flagged at
  Phase 2.3 closure -- resolved as "retained, declared limitation," not
  reopened pending a future data source. Revisit only if a CMIP6 daily
  gust or daily-maximum wind product is added to the catalogue in the
  future (finding 1's absence, not finding 2's physical-quantity mismatch,
  is the part any future catalogue addition could change).

## [2026-09-11] GCM pair (GFDL-ESM4, MIROC6) selection rationale -- retroactive documentation, not a new methodological choice

- Decision: no code or configuration change. This entry, and the new
  `docs/rework/GEAR_v3_methodology_nature_format.md` Section 2.1 ("GCM
  selection rationale (GFDL-ESM4, MIROC6)"), formally document the
  reasoning behind a GCM pair that has been in place and unquestioned
  since the V4 decision (`docs/DECISIONS.md`, "Second CMIP6 GCM: MIROC6
  (V4 closed)") and underlies every hazard verification run in Phases
  0-2.4. The pair is unchanged: still `["gfdl_esm4", "miroc6"]`, no third
  model added.
- Reason this entry exists now: the pair's justification had never been
  written down in one place, was never checked against actual ECS
  literature, and was at risk of being asserted in the manuscript with
  more confidence than the project's own history supports. This entry
  reconstructs what was actually decided and when, separates what was
  operational (catalogue/variant availability) from what is
  climatological (ECS standing in the CMIP6 ensemble), and states plainly
  where no formal justification exists rather than inventing one.
- Findings, with evidence tier stated per claim:
  1. **GFDL-ESM4 as the original/primary model: no justification found,
     Tier: none -- stated as "operational default," not invented.**
     `docs/memory/05-decisoes-tecnicas.md` records that the prior
     repository already had `CMIP6_SOURCE_ID_CDS = "gfdl_esm4"` before
     this project's own decision record begins. No commit, spec, or memory
     file in either repository gives a reason GFDL-ESM4 was the original
     single model. Do not backfill one in the manuscript; state it as an
     inherited operational default.
  2. **MIROC6 as the second model: operational selection, Tier 1/citable
     for what the repo record actually says (`docs/DECISIONS.md`, "Second
     CMIP6 GCM: MIROC6 (V4 closed)").** Of four candidates checked against
     the CDS catalogue, IPSL-CM6A-LR was excluded for missing
     SSP1-2.6/SSP5-8.5 coverage; CNRM-CM6-1 was passed over for its
     typical `r1i1p1f2` variant (parity break with GFDL-ESM4's
     `r1i1p1f1`); MIROC6 was chosen over the remaining MPI-ESM1-2-LR
     fallback for "greatest structural divergence" from GFDL-ESM4. That
     divergence claim was, at the time, a qualitative author judgment
     (distinct convection scheme, model lineage) -- not backed by a cited
     sensitivity metric. It is not reinterpreted here as having been an
     ECS-based choice; it was not one.
  3. **ECS standing: Tier 1/citable.** GFDL-ESM4 ECS = 2.6-2.7 K (Dunne
     et al., 2020, *JAMES*, DOI 10.1029/2019MS002015; cross-checked
     against Zelinka et al., 2020, *GRL*, DOI 10.1029/2019GL085782, whose
     published forcing/feedback/ECS table gives 2.65 K). MIROC6 ECS =
     2.6 K, stated explicitly in Tatebe et al. (2019, *GMD*,
     DOI 10.5194/gmd-12-2727-2019) as unchanged from MIROC5. CMIP6
     ensemble ECS range ~1.8-5.6 K, mean ~3.7 K (Zelinka et al., 2020;
     Meehl et al., 2020, *Science Advances*, DOI 10.1126/sciadv.aba1981).
     **Conclusion, stated without oversell: GFDL-ESM4 and MIROC6 are
     climatologically close to each other (~0.05-0.1 K apart in ECS) and
     both sit near the low end of the CMIP6 range. They do not act as a
     genuine sensitivity-bounding pair in the ECS sense.** Any prior
     phrasing in this project's history that implied a low-vs-high
     bounding design (informally motivated by the ~10-100x spread in this
     pipeline's own heat/wind/solar outputs,
     `analysis/ccrs_bucket_weighted_distribution.md`) is a description of
     structural/regional divergence, not of global climate sensitivity,
     and the manuscript text is written to keep those two claims
     separate.
  4. **Grid resolution and regional-bias literature: Tier 1/citable, but
     regional and non-exhaustive.** GFDL-ESM4 atmosphere ~1 deg x 1.25 deg
     cubed-sphere (Dunne et al., 2020); MIROC6 ~1.4 deg x 1.4 deg T85
     spectral (Tatebe et al., 2019) -- both already confirmed empirically
     by this project's own downloads (V4 update entry above). MIROC6
     flagged for wind-speed underestimation in a 22-model Mediterranean
     evaluation and as the worst-performing model of 13 for historical
     temperature over Thailand (Kamworapan, Thao, Gheewala, Pimonsree &
     Prueksakorn, 2021, *Heliyon* 7(11):e08263). These are single regional
     studies, cited at that weight -- not treated as a general verdict
     against MIROC6.
  5. **Data-completeness tally: Tier 1/citable, this project's own
     records.** Across Phase 0 (SPEI/Hargreaves), Phase 2.1 (Extreme
     Precipitation), Phase 2.2 (FWI/humidity), and Phase 2.3 (Extreme
     Wind) catalogue checks, exactly one model-specific gap exists in
     total: `gfdl_esm4` x `ssp370` x daily `tasmin`
     (`analysis/spei_catalog_check.md`), which is why Thornthwaite PET was
     chosen over Hargreaves PET for the drought term. MIROC6 has zero
     catalogue gaps across all four phases. The Phase 2.2 Wildfire
     blocker (relative humidity absent from the daily catalogue) is
     symmetric across both models, not model-specific, and Wildfire was
     deferred on that basis regardless of which model "caused" it
     (`docs/DECISIONS.md`, "GEAR v3 Phase 2.2: Wildfire deferred").
- Consequences: none to code, config, or existing outputs. The manuscript
  now states this pair's rationale as operational-plus-structural, not as
  an ECS-based bounding design; if a reviewer asks "why these two GCMs,"
  Section 2.1 is the citable answer, including the explicit admission
  that the "bounding" framing used informally in this project's own
  history is weaker than it sounds.
- References: `docs/rework/GEAR_v3_methodology_nature_format.md` Section
  2.1, `docs/DECISIONS.md` ("Second CMIP6 GCM: MIROC6 (V4 closed)"),
  `docs/memory/05-decisoes-tecnicas.md`, `analysis/spei_catalog_check.md`,
  `analysis/fwi_catalog_check.md`, `analysis/wind_catalog_check.md`,
  `analysis/gcm_catalog_check.md`, `analysis/ccrs_bucket_weighted_distribution.md`.
- Status: active. Documentation-only; does not reopen V4 and does not
  authorize adding, removing, or replacing either model.
- Addendum (2026-09-12): Section 2.1 now adds one paragraph, immediately
  after the findings above, framing the retrospective case for the pair's
  continued defensibility. It adds no new evidentiary claim beyond finding
  4 above -- same convection/resolution divergence, same two Kamworapan
  et al. (2021) regional flags -- it only makes explicit the framing that
  the original operational choice (finding 2) happens to hold up under
  that retrospective structural scrutiny. It explicitly does not claim the
  models were chosen for that structural contrast at selection time, so it
  does not contradict or reopen finding 2's operational account.

## [2026-09-11] GEAR v3 Extreme Wind: reframed as scenario-invariant structural exposure (not a data gap)

- Decision: no code, configuration, or data-source change. This entry
  reframes the existing Phase 2.3 finding -- ERA5 (1991-2020) retained as
  Extreme Wind's sole source, no CMIP6/SSP substitution -- from a
  "declared limitation" to a deliberate, settled position: Extreme Wind
  is a scenario-invariant structural exposure baseline, by design, not an
  unresolved data gap this project failed to close. Text updated in
  `docs/rework/GEAR_v3_methodology_nature_format.md` Section 3.1 (closing
  framing paragraph, appended after the existing investigation-and-
  rejection paragraph, which is kept verbatim) and Section 9 (new PSAE
  bullet stating the scenario-invariance explicitly, plus a Phase 7
  visualization requirement).
- Reason: the underlying investigation (`docs/DECISIONS.md`, "GEAR v3
  Phase 2.3 follow-up: ERA5 temporal asymmetry retained") already found,
  independently and sufficiently on either ground, that (1) no
  daily-maximum or gust wind variable exists on the CDS `projections-
  cmip6` catalogue for either configured GCM, and (2) the one daily
  variable that does exist (`sfcWind`, daily mean) is not the same
  physical quantity as the ERA5 instantaneous gust this hazard's
  threshold design uses, and converting between them would require an
  unvalidated, condition-dependent gust-factor parameterization already
  investigated and rejected. What this entry adds is the epistemic
  framing: IPCC AR6 WGI Chapter 11 itself assigns "low confidence" to
  projected changes in severe wind in most regions because current-
  generation GCMs "often do not have sufficient resolution or accurate
  parametrization" for the convective/mesoscale processes that generate
  damaging gusts -- the same limitation the Phase 2.3 investigation found
  directly on this project's own two GCMs. Manufacturing an SSP-varying
  wind trend via the rejected gust-factor conversion would therefore not
  have added information; it would have fabricated apparent precision
  about a quantity the physical climate science does not yet claim to
  project reliably at this resolution. A stable, directly observed
  historical baseline is the more epistemically honest choice given the
  current state of the science, not merely the more convenient one.
- Consequence for PSAE/comparability (Section 9): Extreme Wind's
  contribution to PSAE_i is identical across all three SSP columns by
  construction (computed once from ERA5, copied across the scenario
  axis), stated explicitly as "structural exposure to severe wind,
  scenario-independent" rather than left for a reader to infer from
  static columns. A requirement is recorded for Phase 7 (visualization/
  reporting, not yet built, no implementation here): any PSAE table or
  figure showing the ssp126/ssp370/ssp585 columns side by side must
  visually distinguish Extreme Wind (e.g., a footnote marker or distinct
  shading) so the figure does not visually imply a scenario sensitivity
  that does not exist.
- **This is a settled epistemic position, not a placeholder.** This entry
  explicitly closes the door on carrying this forward as a "TODO: find
  better wind data" item. It is not reopened by the future appearance of
  a CMIP6 daily-maximum or gust product on the catalogue in isolation --
  the Phase 2.3 follow-up entry already scoped that narrow condition
  (finding 1's absence) as the one thing that could change; even then,
  finding 2 (the physical-quantity mismatch and the unvalidated
  gust-factor conversion it would require) and the epistemic argument in
  this entry would still need to be independently revisited and closed
  before ERA5 is replaced. Absent that, this is not an open item.
- References: `docs/rework/GEAR_v3_methodology_nature_format.md`
  Sections 3.1, 9; `docs/DECISIONS.md`, "GEAR v3 Phase 2.3 follow-up: ERA5
  temporal asymmetry retained (CMIP6 substitution investigated and
  rejected)"; IPCC AR6 WGI Chapter 11 (severe wind projection
  confidence); `analysis/wind_catalog_check.md`.
- Status: active, closed. Documentation-only.

## [2026-09-11] Gas/oil-gas age_factor: pinned-neutral treatment confirmed final after a bounded literature search

- Decision: no code change. `src/index/age_factor.py`'s gas/oil-gas
  `age_factor = 1.0` (pinned neutral) is confirmed as a **final** design
  choice, not a still-open item awaiting a literature rate. This closes
  the "provisional/open" status carried since the 2026-09-04 age_factor
  entry.
- Reason: a bounded search (a handful of targeted queries, not an
  open-ended review) for a gas-turbine/combined-cycle age-degradation
  curve analogous to coal's Kim & Moon (2012)/Sagaf (2020) found no
  citable Tier 1/Tier 2 source of the required kind:
  1. Turbomachinery degradation literature (e.g. Diakunchak-style
     compressor-fouling studies) reports loss in **fired-operating-hours**
     terms, not calendar age -- typically ~5% output / ~2.5% efficiency
     loss around 20,000 fired hours, over two-thirds recoverable via
     routine compressor washing. This project has no per-plant
     operating-hours, capacity-factor history, or wash-schedule data to
     convert an hours-based curve into a `retention(calendar_age)` form
     the way `age = REFERENCE_YEAR - commissioning_year` requires; doing
     so without that data would fabricate a rate, not cite one.
  2. Fleet-level longitudinal evidence found the opposite sign from what
     a simple decay curve would assume: Grubert (2020, *IOPSciNotes*,
     "Same-plant trends in capacity factor and heat rate for US power
     plants, 2001-2018") reports that US natural-gas plants ran more, and
     more efficiently, as they aged (capacity-weighted fleet heat-rate
     CAGR direction improving), in direct contrast to coal, which
     declined -- attributed to retrofits, dispatch shifts, and vintage
     effects rather than an isolable per-plant aging mechanism. This is
     Tier 2/citable for the fleet-level *contrast* with coal, but is
     explicitly not usable as a per-plant retention curve: it does not
     isolate a %/year aging effect from confounding fleet-composition and
     retrofit trends, and its sign would argue for a neutral-to-positive
     adjustment, not a decay curve, if taken at face value -- which this
     entry does not do either, given how confounded the estimate is.
  3. No source combining a calendar-age index, a per-plant-comparable
     unit, and isolation from retrofit/dispatch confounds was found for
     gas or oil-gas thermal generation in this search.
- Consequence: gas/oil-gas keeps `age_factor = 1.0` in
  `src/index/age_factor.py` -- unchanged, no code touched by this entry.
  This is now documented as a **declared absence of evidence**, not
  evidence of no aging effect, and is not carried forward as a TODO. See
  `docs/LIMITATIONS.md` for the consolidated limitation-tracking entry.
- References: `src/index/age_factor.py` (comment there still reads
  "PROVISIONAL" and is a candidate for a small, separate follow-up edit to
  align the code comment with this closure -- not done here, out of
  scope for a documentation-only task); `docs/DECISIONS.md`, "age_factor:
  >=1 multiplier via `2 - retention(age)`, with corrected coal/hydro/wind
  retention curves (final)" (2026-09-04); `docs/LIMITATIONS.md`.
- Status: active, closed. Final -- not reopened by this entry's absence
  of a source; revisit only if a new calendar-age-indexed, per-plant-
  comparable source is published.

## [2026-09-12] GEAR v3 Phase 2.5: pre-registered correlation-gate tie-breaker rule

- Decision: before Phase 2.5's correlation gate is run against real data,
  a three-criterion tie-breaker hierarchy is fixed for deciding which
  variable is retained when a candidate pair fails the |r| >= 0.80 test
  (`docs/rework/GEAR_v3_methodology_nature_format.md` Section 5):
  1. **Mechanistic primacy** -- retain the variable with the more direct
     causal link to the specific technology-bucket failure mode already
     established in Section 3's H_b tables. Applied **per bucket**
     (author-confirmed scope, not global): the same failed pair can
     resolve to a different retained variable in different buckets when
     mechanistic relevance differs by bucket (e.g. Extreme Precipitation
     for Solar substation flooding vs. Drought for Hydro headloss). The
     gate's output table is structured per-bucket, not as one global
     verdict per pair.
  2. **Data-tier confidence** -- if mechanistic relevance is equal or
     ambiguous for a bucket, retain the variable from the higher-tier,
     lower-proxy-dependency dataset (Tier 1 > Tier 2 > Tier 3, this
     project's tier definitions as used throughout Section 4 and this
     file).
  3. **sv/iv-specific** -- if this pair fails the gate, iv (interannual
     variability) is retained over sv (seasonal variability), on
     convergent Tier 2 evidence for the mechanism, stated with that
     qualification and not as a single definitive causal study. PNNL
     (*Drought Impacts on Hydroelectric Power Generation in the Western
     United States*, PNNL-33212, and its companion FAQ) documents, via the
     Colorado River Hoover/Glen Canyon case, that reservoirs are managed
     to absorb seasonal drought as routine operation, while sustained
     interannual drought is a distinct structural threat: Lake Mead/Lake
     Powell levels have declined over two decades, with temporary wet
     periods within that multi-year drought insufficient to refill the
     reservoirs. Independently, Moghaddasi, Gavahi, Moftakhari &
     Moradkhani (2024), "Unraveling the hydropower vulnerability to
     drought in the United States," *Environmental Research Letters*
     19(8), find that larger reservoir storage capacity weakens the
     seasonal-drought/generation correlation -- carry-over storage
     measurably absorbs the seasonal shock. That second source establishes
     only the seasonal-buffering half on its own terms; the multi-year-
     depletion half rests on the PNNL case study, not on this paper. Read
     together they are convergent, mechanism-consistent Tier 2 evidence
     for treating the same buffering capacity that absorbs seasonal
     drought as exhaustible under sustained multi-year drought -- not one
     study proving both halves, and not upgraded to Tier 1 by this
     entry.
- **This is methodological pre-registration, stated as such.** The
  hierarchy above is fixed in the methodology text *before* Phase 2.5
  computes a single correlation coefficient on real data, specifically to
  avoid post-hoc/p-hacking bias in variable retention -- i.e., to prevent
  the tie-breaker criterion from being chosen, or reordered, after seeing
  which choice produces a cleaner narrative or a more favorable applicable-
  hazard set for any given bucket. This framing is a real safeguard for
  reviewers and is named as such, not left implicit.
- Correction made in the same edit, not deferred: the methodology's
  Section 5 previously grouped sv/iv into a "ws/sv/iv trio" parenthetical
  alongside the mandatory, non-gated Water Stress/Drought pair, implying
  sv/iv were exempt from the exclusion gate. Author-confirmed (2026-09-12):
  sv and iv are gated candidates, tested against Water Stress and against
  each other, like Extreme Precipitation -- not exempt. The stale
  parenthetical is corrected in the same edit as this tie-breaker addition,
  so the methodology text and the gate about to be implemented do not
  disagree. This does not resolve the separate, still-open Phase 3
  question of whether sv/iv belong in any bucket's H_b table at all (see
  "GEAR v3 Phase 1" entry, 2026-09-11, "sv/iv... an open question for the
  author") -- only their status as gated-vs-exempt within the correlation
  gate itself.
- Consequence: no code change. This closes the pre-registration
  prerequisite for Phase 2.5; the gate itself (computing r on harmonized
  real data and applying this hierarchy) is a separate, subsequent task.
- References: `docs/rework/GEAR_v3_methodology_nature_format.md` Section
  5; PNNL-33212, *Drought Impacts on Hydroelectric Power Generation in the
  Western United States*, and its companion FAQ (Pacific Northwest
  National Laboratory); Moghaddasi, Gavahi, Moftakhari & Moradkhani
  (2024), "Unraveling the hydropower vulnerability to drought in the
  United States," *Environmental Research Letters* 19(8); `docs/
  DECISIONS.md`, "GEAR v3 Phase 1" (2026-09-11, sv/iv open
  question), "CCRS global Min-Max bounds" (2026-09-04, ws/sv/iv bound
  pooling).
- Status: active. Tie-breaker hierarchy and sv/iv gated-candidate
  correction closed; sv/iv's Phase 3 H_b-membership question remains
  separately open.

## [2026-09-12] GEAR v3 Phase 2.5: correlation gate implemented and run -- every gated pair passed, no exclusion

- Decision/result: `src/index/correlation_gate.py` (new, isolated module,
  standing modularity rule -- no changes to `risk_calculator.py` or
  `normalization.py`) implements and runs the Section 5 correlation gate
  on RAW, pre-normalization hazard values, per the author's explicit
  confirmation that this gate does not consume `normalization.py`'s
  output. Six candidate pairs, exactly as specified, no others: Extreme
  Precipitation vs Water Stress (gated), Extreme Precipitation vs Drought/
  SPEI (gated), sv vs Water Stress (gated), iv vs Water Stress (gated), sv
  vs iv (gated), Water Stress vs Drought/SPEI (report-only, mandatory,
  never excluded). Extreme Wind and Wildfire are not part of this gate
  (unchanged from Section 5).
- **Spatial harmonization**: no new regridding/zonal-aggregation utility
  was written. Every candidate raster (`ws`/`sv`/`iv` via the Aqueduct
  processors, `spei` via `spei_processor`, `precip` via
  `extreme_precipitation_processor`) already shares one per-country 1 km
  reference grid by construction (`src/processors/_common.py`'s
  `_load_reference_grid`/`_resample_to_1km`, already used by every
  processor). The gate reuses `_common.py`'s existing `assert_consistent_
  grid` guard to verify this programmatically per pair/country/GCM before
  sampling, then reuses `risk_calculator.sample_raster`'s nearest-pixel
  extraction at the plant coordinate set -- a verification of an
  already-true invariant, not new regridding. See the module docstring
  for the full reasoning.
- **Pearson vs Spearman**: Pearson's r is the reported/decision statistic
  by default (every candidate is a continuous physical quantity, no
  ordinal-only variable); Spearman's rho is always computed alongside. An
  automated proxy (`flag_nonlinearity`: `|rho| - |r| > 0.10`, Tier 3,
  author-declared) substitutes Spearman as the operative decision
  statistic for a specific (pair, bucket, country, GCM) cell when the two
  diverge materially -- this fired for 4 of 48 real-data cells (Seasonal
  Variability vs Water Stress, Hydro, Portugal; Interannual Variability
  vs Water Stress, Hydro, Portugal and India; Water Stress vs Drought,
  Hydro, Brazil/MIROC6), each flagged in the output, not silently
  substituted.
- **Country/GCM handling**: `r` computed per country separately (never
  pooled for the gate decision); a `country == "pooled"` reference row is
  also computed and reported, carrying no gate verdict. Pairs with a
  GCM-dependent member (`spei`, `precip`) are reported per GCM, never
  blended (`ARCHITECTURE.md` Section 5.4's standing rule); `precip` vs
  `spei` is paired same-GCM only.
- **Empirical result: no exclusion anywhere.** Every one of the five
  gated pairs passed (`|r| < 0.80`) in every country/bucket/GCM cell where
  data existed. The pre-registered tie-breaker hierarchy (Criteria 1-3)
  was implemented and unit-tested (`tests/test_correlation_gate.py`,
  including a synthetic case forcing Criterion 3 to fire and correctly
  retain `iv`) but was never invoked on the real data -- the highest
  observed `|r|` was 0.702 (Seasonal vs Interannual Variability, Hydro,
  Portugal), still well under the 0.80 threshold. Full pairwise matrix
  (Pearson's r, Spearman's rho, n, decision method, verdict) written to
  `data/outputs/tables/correlation_gate.csv`, retained as a Phase 7
  supplementary-figure artifact. Confirmed independent per bucket
  (Section 3's H_b tables): Hydro keeps Drought, Water Stress, and
  Extreme Precipitation (Brazil-confirmed; see gap below); Thermal keeps
  Water Stress and Extreme Precipitation; sv and iv both remain
  independent, unexcluded candidates in Hydro and Thermal pending Phase
  3's separate, still-open decision on whether they belong in any H_b
  table at all.
- **Declared data gap, surfaced not absorbed**: Extreme Precipitation's
  raw processed raster (Phase 2.1) exists for Brazil only as of this run
  -- Portugal and India are not yet acquired/processed. Every Extreme-
  Precipitation-involving cell for those two countries came back
  `insufficient_data` (the module returns all-NaN for a missing raster
  and reports it as such, rather than crashing the whole gate run or
  silently treating it as `pass`). This means Extreme Precipitation's
  H_b inclusion is empirically confirmed for Brazil only; Portugal/India
  remain provisional pending Phase 2.1 completing acquisition for those
  countries. This is a Phase 2.1 data-completeness gap, not a defect in
  this gate -- the gate is re-runnable as-is once those rasters exist, no
  code change required.
- **Bug found and fixed during this task**: the flat-term GCM-axis
  placeholder was initially written as the literal string `"n/a"`. That
  string is one of pandas' default `read_csv` NA sentinels, so writing it
  to `correlation_gate.csv` and reading it back silently produced a real
  `NaN`, indistinguishable from missing data. Changed to
  `"not_gcm_dependent"` before this entry was written; caught by manually
  inspecting the round-tripped CSV, not by a test (no test asserts the
  on-disk CSV round-trips the `gcm` column faithfully -- a gap worth
  closing if this table sees more consumers).
- Consequence: `docs/rework/GEAR_v3_methodology_nature_format.md` Section
  3 gets a new subsection (3.3) stating this empirical result, the
  Brazil-only caveat, and the highest observed `|r|`, replacing the
  previously-provisional framing of the H_b table's Extreme Precipitation
  entries with an actual result. `docs/rework/GEAR_v3_work_plan.md`
  Phase 2.5 is marked closed (see that file for the substitution text).
- References: `src/index/correlation_gate.py`; `tests/
  test_correlation_gate.py`; `data/outputs/tables/correlation_gate.csv`;
  `docs/rework/GEAR_v3_methodology_nature_format.md` Sections 3.3, 5;
  `docs/DECISIONS.md`, "GEAR v3 Phase 2.5: pre-registered correlation-gate
  tie-breaker rule" (2026-09-12, the hierarchy this run applied).
- Status: active, closed for every pair/bucket/country/GCM combination
  where Extreme Precipitation data exists. Reopen only to add Portugal/
  India once Phase 2.1 processes their Extreme Precipitation rasters
  (rerun `python -m src.index.correlation_gate`, no code change
  expected).

## [2026-09-12] GEAR v3 Phase 2.5 follow-up: Portugal/India Extreme Precipitation processed, gate closed for all three countries

- **Question asked before acting, and answered first**: before reprocessing
  anything, the author was asked directly whether Portugal/India Extreme
  Precipitation had genuinely never been run, or had been run and lost/
  misplaced -- because the two have different next steps (reprocessing vs.
  debugging), and the previous entry's "no code change expected" claim is
  only true under the first. Author confirmed: never executed for those
  two countries, no prior attempt or failure on record.
- **Investigation, not assumption, before running anything**: confirmed
  (a) the native, pre-1km-resample Extreme Precipitation raster was also
  absent for Portugal/India (ruling out "computed but not saved to the
  right path" -- there was no output at any stage), (b) the raw `pr`
  CMIP6 input (both GCMs, all three scenarios) already existed on disk
  for both countries, identical in structure to Brazil's, and (c) SPEI
  (`drought_stress_raw_*`), which reuses this exact same `pr` series per
  `extreme_precipitation_processor.py`'s own docstring, was already
  computed successfully for all three countries. Together these rule out
  a data-availability gap or a country-specific pipeline defect and
  support "simply never executed for these two countries" -- the
  processor's own CLI (`process_all_countries`) iterates all of
  `COUNTRIES` by default and is not hardcoded to Brazil.
- **Action**: `python -m src.processors.extreme_precipitation_processor
  --countries Portugal India` -- clean success, 12/12 (2 countries x 2
  GCMs x 3 scenarios) combinations `"success": true`, no retries, no
  partial failures. No code touched in `extreme_precipitation_processor.py`
  or anywhere else -- this was reprocessing (Case A), not debugging.
  `tests/test_extreme_precipitation_processor.py` (11 tests) re-run
  unaffected, still 11/11.
- **Gate re-run in full** (`python -m src.index.correlation_gate`), not a
  partial/incremental recompute -- simpler and safer than adding
  selective-recompute logic to the module for a one-off. Brazil's 14 rows
  verified bit-identical before/after (`pearson_r`, `spearman_rho`, `n`,
  `gate_verdict` all equal), confirming the re-run did not disturb what
  was already valid.
- **Final empirical result, all three countries**: every gated pair still
  passes (`|r| < 0.80`) in every country/bucket/GCM cell -- no exclusion
  anywhere, tie-breaker still never invoked. Highest `|r|` unchanged at
  0.702 (Seasonal vs Interannual Variability, Hydro, Portugal) -- that
  pair does not involve Extreme Precipitation, so it was never affected by
  the gap. The previously-`insufficient_data` Extreme-Precipitation-vs-
  Water-Stress and Extreme-Precipitation-vs-Drought cells for Portugal/
  India now carry real values (e.g. Extreme Precipitation vs Water Stress,
  Hydro, India, GFDL-ESM4: r = -0.354; Extreme Precipitation vs Drought,
  Hydro, India, GFDL-ESM4: r = -0.495) -- all well under threshold.
  `data/outputs/tables/correlation_gate.csv` regenerated in place (56
  rows, same shape as before, no `insufficient_data` rows remaining for
  any gated pair).
- Consequence: `docs/rework/GEAR_v3_methodology_nature_format.md` Section
  3.3 updated to drop the Brazil-only caveat and state the process
  incident briefly instead (what happened, how it was resolved, pointer
  here for the full account) rather than erasing the record of the
  partial state. `docs/rework/GEAR_v3_work_plan.md` Phase 2.5 updated to
  "CLOSED, all 3 countries." `docs/LIMITATIONS.md` gets a new binding
  process convention (2026-09-12): a per-country-dependent phase closure
  must state its actual country coverage explicitly, never round up to
  unqualified "closed" -- this incident is the motivating case, named as
  such.
- References: `src/processors/extreme_precipitation_processor.py`
  (unchanged); `src/index/correlation_gate.py`; `data/outputs/tables/
  correlation_gate.csv`; `docs/rework/GEAR_v3_methodology_nature_format.md`
  Section 3.3; `docs/rework/GEAR_v3_work_plan.md` Phase 2.5;
  `docs/LIMITATIONS.md`; `docs/DECISIONS.md`, "GEAR v3 Phase 2.5:
  correlation gate implemented and run -- every gated pair passed, no
  exclusion" (2026-09-12, the entry this one closes out).
- Status: active, closed. Extreme Precipitation is now empirically
  confirmed independent (not excluded by the gate) for Brazil, Portugal,
  and India alike, in every bucket it is a candidate for.

## [2026-09-12] GEAR v3 Phase 3.1: hazard_scope.py reconciliation after parallel-session conflict

- **What happened, stated plainly**: two Claude Code sessions ran against
  `src/index/hazard_scope.py` at the same time -- one implementing Phase
  3.1 (this file's own deliverable, the per-bucket `H_b` applicable-hazard
  table), the other implementing Phase 3.2 (`RiskBand_{i,h}` threshold
  classification, which depends on `H_b` as an input) -- despite the
  explicit instruction to sequence Phase 3.1 before Phase 3.2. The Phase
  3.2 session wrote its own version of `hazard_scope.py` (a different
  module shape entirely: `HAZARD_BUCKET_TABLE` / `is_applicable` /
  `require_applicable` / `HazardNotApplicableError`, with no test file
  written against it) to unblock itself on a prerequisite file that did
  not yet exist from its point of view, overwriting the Phase 3.1 session's
  version on disk. That overwrite included `"thermal": (..., "sv", "iv")`
  -- Thermal's `H_b` including seasonal/interannual water variability --
  which directly contradicts the author's explicit, already-given decision
  that `sv`/`iv` belong in Hydro's `H_b` only, not Thermal's (see below).
  The Phase 3.2 session was paused and this reconciliation was run in the
  Phase 3.1 session alone, before either phase proceeds further.
- **Final `H_b` table (author-confirmed, restated here as the reconciled,
  authoritative version)**:
  - Hydro: Water Stress (`ws`), Drought/SPEI (`spei`), Extreme
    Precipitation (`precip`), Seasonal Variability (`sv`), Interannual
    Variability (`iv`) -- `|H_b| = 5`.
  - Thermal: Water Stress (`ws`), Extreme Heat (`heat`), Extreme
    Precipitation (`precip`) -- `|H_b| = 3`, unchanged from before this
    conflict. `sv`/`iv` explicitly excluded: both were gated as candidates
    in Thermal too (`correlation_gate.WATER_BUCKETS` includes Thermal) and
    passed there as well, but Phase 0 confirmed no cooling-technology field
    (once-through/recirculating/dry/hybrid) exists anywhere in the ingested
    GEM data, so there is no per-plant basis to justify a water-variability
    sensitivity *mechanism* for Thermal specifically -- adding sv/iv there
    would assume a mechanism the available data cannot support, and would
    contradict the already-closed Thermal-homogeneity decision
    (`docs/LIMITATIONS.md`, "2026-09-11 -- GEM cooling-technology field
    absent: Thermal bucket treated as homogeneous"). Hydro's inclusion of
    both `sv` and `iv` is the mirror decision: both passed the gate against
    Water Stress and against each other in Hydro, the tie-breaker never
    fired, and excluding either now would contradict that empirical result
    rather than honor it.
  - Wind: Extreme Wind (`wind`) only -- `|H_b| = 1`, unaffected by this
    conflict.
  - Solar: Extreme Heat (`heat`), Extreme Precipitation (`precip`), Extreme
    Wind (`wind`) -- `|H_b| = 3`, unaffected by this conflict.
  - Wildfire and SLR remain absent from every bucket's `H_b`
    (`docs/LIMITATIONS.md`, "2026-09-11 -- Wildfire (FWI/EFFIS) deferred,
    not implemented" and "2026-09-03 -- Sea-level rise (SLR) excluded from
    the hazard set").
- **API naming conflict, resolved on practical grounds, not technical
  merit**: two incompatible module shapes existed on disk for the same
  file. Resolved by keeping the Phase 3.1 session's original shape
  (`APPLICABLE_HAZARDS` dict, `applicable_hazards()` accessor) because it
  already had a complete, passing test file (`tests/test_hazard_scope.py`,
  11 tests) written against it; the competing shape
  (`HAZARD_BUCKET_TABLE`/`is_applicable`/`require_applicable`/
  `HazardNotApplicableError`) had zero tests written against it anywhere
  and nothing else in the codebase imported it. This is stated explicitly
  as a decision made to minimize rewritten test surface, not a judgment
  that one API shape is better-designed than the other -- had the
  competing shape had its own complete test file, that would have been a
  genuine trade-off to weigh instead of a tie-break by convenience.
- **Verification**: confirmed no other module (`risk_calculator.py`,
  `correlation_gate.py`, or anything else) imports either shape of
  `hazard_scope` yet, so no reconciliation was needed outside this one
  file and its own test file. `pytest tests/test_hazard_scope.py` --
  11/11 passing against the reconciled file.
- **Process lesson, not a blame entry**: see the new coordination
  convention added to `docs/LIMITATIONS.md` this same date -- a phase's
  primary deliverable file must not be written to by a dependent phase's
  session even to unblock itself; a session hitting a missing prerequisite
  should stop and report, not create a placeholder version of another
  phase's deliverable.
- References: `src/index/hazard_scope.py`; `tests/test_hazard_scope.py`;
  `docs/LIMITATIONS.md` (new 2026-09-12 coordination-convention entry);
  `docs/rework/GEAR_v3_methodology_nature_format.md` Section 3;
  `docs/DECISIONS.md`, "GEAR v3 Phase 2.5: correlation gate implemented and
  run -- every gated pair passed, no exclusion" (2026-09-12, the empirical
  result this entry's Hydro/Thermal sv/iv split is built on); "GEAR v3
  Phase 1" (2026-09-11, sv/iv H_b-membership originally left open).
- Status: active, closed. `hazard_scope.py` is now the single reconciled
  source of truth for `H_b`; the paused Phase 3.2 session is to be resumed
  separately and instructed to pull this exact commit and only ever read
  `hazard_scope.py` from that point on, never write to it.

## [2026-09-12] GEAR v3 Phase 3.2: RiskBand_i,h threshold classification, consolidated tier/threshold table

- **Decision**: implemented `src/index/risk_bands.py` (replacing the
  retired CCRS-era module of the same name -- `WaterRiskBand`/
  `HeatRiskBand`, which imported the now-deleted `ccrs_calculator.py` and
  could not express a per-hazard `RiskBand_{i,h}` anyway; deleted, not
  deprecated, exactly as Phase 1 retired `ccrs_calculator.py` itself).
  Classifies every plant into a discrete band per hazard, for every
  (hazard, bucket) combination `src/index/hazard_scope.py`'s
  `APPLICABLE_HAZARDS` (Phase 3.1) marks applicable, reading that table as
  the single source of truth and raising `HazardNotApplicableError` for
  any other combination -- never a silent default band.
- **Consolidated tier/threshold table** (pulled together here, per the
  author's request, since these were confirmed piecemeal across many
  earlier phases and Section 4 of the methodology draft on its own required
  chasing several other decisions to reconstruct):

  | Hazard | Bucket | Tier | Basis |
  |---|---|---|---|
  | Water Stress | Hydro, Thermal | 1 | WRI Aqueduct absolute cutoffs 0.1/0.4/0.8 |
  | Drought (SPEI) | Hydro | 3 | pooled P75/P90/P95 of months/yr SPEI<=-1.0 (P50 diagnostic) |
  | Extreme Precipitation | Hydro, Thermal, Solar | 3 | pooled P75/P90/P95 of days/yr pr>local-P95 (P50 diagnostic; bucket-invariant raw indicator, same cuts reused across all three buckets) |
  | Extreme Heat | Thermal | 3 | pooled P75/P90/P95 of days/yr tasmax>40C (P50 diagnostic) |
  | Extreme Heat | Solar | 3 (provisional) | SAME cuts as Thermal -- see "Solar Extreme Heat" below |
  | Seasonal Variability (sv) | Hydro | 3 | pooled P75/P90/P95 of raw sv (P50 diagnostic) -- new assignment, see below |
  | Interannual Variability (iv) | Hydro | 3 | same as sv |
  | Extreme Wind | Wind | 1 | IEC turbine cut-out ~25 m/s, binary (Low/Extreme only) |
  | Extreme Wind | Solar | 3 | pooled P90/P95/P99 of ERA5 mean annual max gust (P75 diagnostic), final per Phase 0.4 |

- **Band-count convention (new methodological decision this phase,
  author-confirmed 2026-09-12)**: every Tier 3 row above uses a 4-percentile
  cutoff set (P50/P75/P90/P95, or P75/P90/P95/P99 for Extreme Wind/Solar),
  but the framework overview names exactly 4 RiskBand labels
  (Low/Medium/High/Extreme). Four cuts naturally bound 5 zones. Resolved by
  dropping the LOWEST percentile of each set as a diagnostic statistic
  only (reported, never a band boundary) and using the remaining 3 cuts to
  bound the 4 canonical labels. Rejected alternative: a 5th label ("Very
  High") using every cut literally -- author's stated reason: this would
  inflate the band structure to accommodate an implementation detail, the
  same category of error already rejected once for HAZUS-MH's depth
  cutoffs. Tier 1 hazards need no such rule (Water Stress's 3 absolute
  cutoffs and Wind-bucket Extreme Wind's single binary cutoff already fit
  the 4-band/2-band schemes exactly).
- **Solar Extreme Heat -- provisional Tier 3 fallback, not an invented Tier
  1 number**: Methods Section 4 names a Tier 1 "PV efficiency-loss-per-degree
  engineering threshold" for this row, but no confirmed numeric value
  exists anywhere in this repo -- checked `docs/DECISIONS.md` and every
  processor, absent. Author-confirmed: do NOT invent the number (explicitly
  named as the same category of error already rejected once for HAZUS-MH --
  accepting an unsourced value because it fills a gap); instead fall back to
  the same Tier 3 percentile method as the Thermal row, flagged
  `provisional=True` in `risk_bands.THRESHOLD_REGISTRY` and in every report
  this module writes. A literature-backed value (industry panel thermal
  derating is commonly cited in the -0.3%/-0.5% per degC-above-25degC
  range, but requires a primary-source datasheet/paper, not an
  author-recalled figure) is left for a future bounded-search task, not
  fabricated here.
- **sv/iv RiskBand -- new Tier assignment, not in Section 4's original
  table**: Section 4 as drafted has no row for `sv`/`iv` at all (they are
  outside Section 2's five-hazard checklist). Now that Phase 3.1 added both
  to Hydro's `H_b` (correcting a text/decision synchronization gap --
  `docs/DECISIONS.md`, "GEAR v3 Phase 3.1: hazard_scope.py reconciliation
  after parallel-session conflict"), they need a RiskBand too. Assigned
  Tier 3 by extension of the same no-Tier-1-source percentile convention
  already used for Drought/Extreme Precipitation, same P50/P75/P90/P95 set
  -- author-confirmed 2026-09-12, on the grounds that introducing a third,
  different percentile scheme (e.g. reviving the retired CCRS module's
  P25/P75/P95 convention) for no stated reason would be an unforced
  inconsistency against the 4-cut convention this same phase already
  established for every other no-Tier-1-source hazard.
- **Percentile pooling**: computed live from the current plant sample
  every run (never frozen like `FROZEN_BOUNDS`) -- Section 4 states these
  are "sample-relative... not absolute physical thresholds" by design.
  Pooled globally (every configured bucket's plants, all countries, all
  water/heat scenarios), per GCM for GCM-dependent hazards (`heat`/`spei`/
  `precip`), never blended across GCMs -- consistent with
  `risk_calculator.compute_global_bounds`'s own pooling convention and the
  project's standing GFDL-ESM4/MIROC6 non-blending rule.
  `risk_bands.TIER3_COMPARABILITY_WARNING` states the non-comparability
  verbatim in every report.
- **Does not touch**: `normalization.py`'s transform recommendation,
  `risk_calculator.FROZEN_BOUNDS`/`transform_term` (both untouched, Phase
  3.3's job), `Risk_{i,h}` (Equation 1), or PSAE (Equation 2, Phase 4) --
  this module only produces the discrete per-hazard label those two
  consume/aggregate later.
- **Verification**: `tests/test_risk_bands.py`, 29 new tests (pure
  `percentile_band_cuts`/`_bandize` arithmetic; `classify_hazard` for one
  Tier 1 hazard -- Water Stress -- and one Tier 3 hazard -- Drought --
  end to end; the Wind-bucket binary scheme vs. Solar-bucket percentile
  scheme for the same raw hazard; every `THRESHOLD_REGISTRY` key checked
  1:1 against `hazard_scope.APPLICABLE_HAZARDS` in both directions; every
  hazard/bucket combination OUTSIDE `H_b` confirmed to raise
  `HazardNotApplicableError`, parametrized over 11 invalid combinations,
  never a silent default band; one monkeypatched pipeline-level test
  confirming `compute_risk_bands` only ever emits rows for applicable
  combinations). 303/303 passing outside the three remaining Phase-1-broken
  modules (`main.py`, `monte_carlo.py`, `src/visualization/` --
  `test_risk_bands.py` itself no longer one of them, down from four).
  `python -m src.index.risk_bands` run against real data: Extreme Wind
  comes back `insufficient_data` for both buckets (ERA5 acquisition, Phase
  2.3, has not yet produced a processed raster for any country) -- reported
  as such via a logged warning and an empty band distribution, not a crash
  or a silently-zero-filled band.
- References: `src/index/risk_bands.py`; `src/index/hazard_scope.py`;
  `tests/test_risk_bands.py`; `docs/rework/
  GEAR_v3_methodology_nature_format.md` Sections 4, 4.1 (new); `docs/
  DECISIONS.md`, "GEAR v3 Phase 3.1: hazard_scope.py reconciliation after
  parallel-session conflict"; "GEAR v3 Phase 0.4: Solar Extreme Wind: ERA5
  gust percentile is final, not contingency"; "GEAR v3 Phase 2.1: Extreme
  Precipitation processor (Tier 3, percentile-cutoff)".
- Status: active, closed for the classification logic. Open, flagged for a
  future task: (1) Solar Extreme Heat's real Tier 1 PV threshold value
  (bounded literature/datasheet search, not this session); (2) Extreme
  Wind has no processed raster yet for any country (Phase 2.3 acquisition
  status, independent of this phase) -- both `wind` rows in the
  consolidated table above will remain `insufficient_data` in any real run
  until that acquisition completes.

## [2026-09-12] GEAR v3 Phase 3.2 follow-up: Solar Extreme Heat Tier 1 PV threshold -- bounded search closed, Tier 3 confirmed final

- **Decision**: no defensible Tier 1 threshold exists for Extreme Heat in
  the Solar bucket. The Tier 3 percentile fallback already in place
  (`risk_bands.THRESHOLD_REGISTRY[("heat", "solar")]`, same pooled
  P75/P90/P95 cuts as Thermal) is now the FINAL treatment, not provisional
  -- `provisional` flipped `True` -> `False` in code, same closure pattern
  as the gas/oil-gas `age_factor` resolution (accept the fallback as final,
  document why, do not leave it dangling as "pending").
- **Bounded search performed** (3 targeted queries, not open-ended), per
  the author's three named checks:
  1. **IEC 61215/61730**: neither standard specifies a single temperature
     coefficient value. IEC 61215 (and its retired NOCT / current NMOT
     metric) defines HOW to measure a module's own coefficient under
     Standard Test Conditions (25 degC, 1000 W/m2); IEC 61730-1:2023 sets a
     module operating-temperature safety qualification limit (98th
     percentile <=70 degC) for long-term durability, not a performance-loss
     risk threshold -- and converting it to an ambient-air days/year metric
     would require an irradiance/wind-dependent NOCT-style offset this
     pipeline does not model (module temperature is not ambient
     temperature). Neither standard yields a Tier 1 absolute cutoff
     analogous to Wind's IEC ~25 m/s turbine cut-out.
  2. **Manufacturer datasheets**: typical Pmax temperature coefficient
     range confirmed but genuinely technology-dependent, not one number:
     crystalline silicon approximately -0.3 to -0.5%/degC (commonly cited
     -0.36 to -0.45%/degC on specific datasheets, e.g. Canadian Solar
     KuMax -0.36%/degC); CdTe thin-film approximately -0.21%/degC; CIGS
     thin-film approximately -0.2 to -0.45%/degC. This is a >2x spread
     between the best (CdTe) and worst (c-Si) cases -- picking any single
     value would misrepresent whichever technology sits on the other end.
     Separately and independently disqualifying: GEM records no per-plant
     PV module-technology field for any of the three countries, so even a
     single confirmed coefficient could not be assigned correctly per
     plant -- the same category of data gap already documented for
     Thermal's absent cooling-technology field (`docs/LIMITATIONS.md`,
     "2026-09-11 -- GEM cooling-technology field absent").
  3. **Peer-reviewed days/year-threshold study**: none found translating a
     PV temperature coefficient into a days-per-year-above-X-degC ambient
     risk threshold for utility-scale solar, comparable to how Extreme
     Heat's 40 degC cutoff is used for Thermal. Structural reason, not just
     an absent citation: PV power derating is continuous and linear in
     temperature deviation from 25 degC STC (a smooth `%/degC` curve with
     no natural step), whereas Thermal's 40 degC and Wind's 25 m/s are both
     genuine step-function engineering limits (a turbine cuts out, a
     cooling process crosses a design threshold). A categorical Tier 1
     cutoff does not map onto a continuous derating curve the way it maps
     onto a step-function limit -- this is a structural mismatch, not a
     literature gap that a wider search would likely close.
- **Consequence**: `risk_bands.THRESHOLD_REGISTRY[("heat", "solar")]`
  updated in place (`provisional=False`, note rewritten to state the
  closure and cite all three findings); module docstring's consolidated
  table and the `*`-footnote referencing "provisional" removed;
  `tests/test_risk_bands.py`'s
  `test_extreme_heat_solar_is_provisional_and_uses_thermal_style_cuts`
  renamed and updated to assert `provisional is False` for both Thermal
  and Solar. `docs/rework/GEAR_v3_methodology_nature_format.md` Section 4's
  Extreme Heat/Solar row rewritten from "not required"/"provisional
  fallback" framing to the closed rejection above.
- **Verification**: `tests/test_risk_bands.py` and `tests/
  test_hazard_scope.py`, 40/40 passing after the flag change (no test
  count change -- this is a value flip on an existing spec, not new
  classification logic).
- References: `src/index/risk_bands.py`; `docs/rework/
  GEAR_v3_methodology_nature_format.md` Section 4; `docs/DECISIONS.md`,
  "GEAR v3 Phase 3.2: RiskBand_i,h threshold classification, consolidated
  tier/threshold table" (2026-09-12, the entry this follow-up closes);
  "GEAR v3 Phase 0.2: FWI/EFFIS wildfire danger classes... Extreme
  Precipitation downgraded Tier 1 -> Tier 3" (the same "verified-rejected,
  not merely absent" evidentiary standard applied here); age_factor
  gas/oil-gas closure (the precedent resolution pattern this follows --
  accept the fallback as final rather than leave it open-ended).
- Status: active, closed. Not expected to be revisited unless a future GEM
  data release adds a per-plant PV module-technology field AND a
  peer-reviewed days/year-threshold study specific to utility-scale solar
  is published -- both conditions, not either alone (a technology field
  alone still lacks the days/year translation; a study alone still cannot
  be applied without knowing each plant's module technology).

## [2026-09-12] GEAR v3 Phase 3.2 follow-up: Extreme Wind data-gap investigation

- **What was checked, in order (investigate first, per standing
  instruction)**: (1) whether ERA5 gust input exists on disk for Brazil,
  Portugal, India; (2) if input exists but the processor was simply never
  invoked, run it; (3) if input itself is missing, report factually, no
  workaround without author confirmation.
- **Finding**: `data/raw/climate/` contains only `aqueduct/`, `cds_spei/`,
  `cds_tasmax/` -- **no `era5_wind/` directory exists for any of the three
  countries.** This is NOT the Phase 2.1 pattern (raw `pr` already on disk,
  processor simply never run for Portugal/India) -- here, step (1) itself
  never happened: the hourly ERA5 `instantaneous_10m_wind_gust` download
  (`era5_wind_downloader.py`) has not been executed for any country, so
  there is nothing for `extreme_wind_processor.py` to consume. `data/
  processed/climate/` correspondingly has no `extreme_wind_gust_raw_*`
  raster for any country either -- consistent, not a separate gap.
- **Was Phase 2.3's original closure entry honest about this, or did it
  overstate completeness?** Checked against the Phase 2.5 "partial
  closures must be labeled as such" convention, applied retroactively as
  instructed. Finding: **Phase 2.3 was already honestly scoped -- no
  correction needed.** Its `docs/DECISIONS.md` entry never used the word
  "closed" (status line: "active. Raw + normalized raster layer and
  threshold-dispatch utility only. RiskBand assembly and applicable-
  hazard-set inclusion (Phase 3.1/3.2) are open..."), the work plan
  (`docs/rework/GEAR_v3_work_plan.md` Phase 2.3) carries no "**CLOSED**"
  marker unlike 2.1/2.4/2.5, and `docs/memory/05-decisoes-tecnicas.md`
  item 30 explicitly logged "1 expected skip (real ERA5 data absent)" at
  the time -- i.e., the absence of real data was already known and stated,
  not discovered now for the first time. This entry is therefore a
  **follow-up, not a correction**: it makes the already-honest scope
  explicit in `docs/LIMITATIONS.md` for the first time (see the new
  2026-09-12 "ERA5 gust input not yet downloaded" row there), since the
  original entry predates `LIMITATIONS.md`'s existence-as-a-file (created
  later that same day) and was never backfilled into it.
- **No workaround attempted.** Per the author's explicit instruction and
  the same category of decision as prior HAZUS/RH/GCM investigations: this
  is reported factually, not silently worked around, and not started
  without confirmation. Completing the acquisition means running
  `python -m src.downloaders.era5_wind_downloader --country <name>` for
  each of Brazil/Portugal/India (no `--year` -> full 1991-2020 baseline,
  30 requests per country, 90 total), a real external CDS API call set
  using the credentials in `credentials.local`, of unknown but potentially
  long duration (ERA5 hourly single-level queue times are not
  deterministic) -- flagged for author authorization before being run, not
  executed automatically by this task.
- **Consequence for Phase 3.2's classification**: `risk_bands.py`'s
  `compute_risk_bands` output correctly shows `insufficient_data`-equivalent
  (no finite pooled sample, logged warning, empty band distribution -- not
  a crash) for both `("wind", "wind")` and `("wind", "solar")` in the
  current real-data run. This is confirmed to remain the case for this
  task -- re-running `python -m src.index.risk_bands` after this
  investigation (no data changed) reproduces the identical
  `insufficient_data` outcome for Extreme Wind in every country, verifying
  the gap is real and not a transient fluke of the first run.
- References: `src/downloaders/era5_wind_downloader.py`;
  `src/processors/extreme_wind_processor.py`; `src/index/risk_bands.py`;
  `docs/LIMITATIONS.md`, "2026-09-12 -- Extreme Wind: ERA5 gust input not
  yet downloaded for any country"; `docs/memory/
  05-decisoes-tecnicas.md` items 30, 37; `docs/DECISIONS.md`, "GEAR v3
  Phase 2.5: correlation gate implemented and run" (the Phase 2.1 pattern
  this finding was checked against and found NOT to match).
- Status: **open, blocked on author decision.** Two options on the table,
  neither taken unilaterally: (a) authorize the ERA5 download now (90 CDS
  requests across the three countries, duration unknown); (b) leave
  Extreme Wind as `insufficient_data` for the time being and revisit in a
  dedicated follow-up task. No RiskBand/PSAE output depends on this being
  resolved immediately -- every other hazard/bucket classification in
  Phase 3.2 is unaffected and already verified working on real data.

## [2026-09-12] GEAR v3 Phase 3.2 follow-up: ERA5 GRIB mislabeling bug fixed, 18 Brazil years recovered

- **Bug, stated plainly**: ``era5_wind_downloader._download_raw_year``'s
  ``except zipfile.BadZipFile`` fallback copied the raw CDS response bytes
  into a file literally named ``gust_hourly.nc`` whenever the response was
  not a valid zip -- without checking what the response actually was. In
  practice, every CDS response for ``reanalysis-era5-single-levels`` /
  ``instantaneous_10m_wind_gust`` is raw GRIB (magic bytes ``GRIB``), not a
  zip. This silently mislabeled 18 already-downloaded Brazil years
  (1991-2008) as NetCDF; ``xarray.open_dataset`` on any of them raised "did
  not find a match in any of xarray's currently installed IO backends" once
  checked directly. This is a data-integrity bug in the pipeline's own error
  handling, not a data-availability gap -- confirmed by inspecting the raw
  bytes (``head -c 4`` = ``GRIB`` on every one of the 18 files, and
  ``cmp``-identical to their would-be ``.zip`` sibling, i.e. the "zip" CDS
  sent back was never a zip either).
- **Fix**: ``_is_grib`` (magic-byte check) added.
  ``_download_raw_year``'s fallback now branches on the actual response
  format: a real GRIB response is saved as ``gust_hourly.grib`` (correct
  extension, never mislabeled); a response that is neither a valid zip nor
  GRIB fails loud (``success: False``, ``reason: unknown_response_format``,
  nothing saved under any extension) instead of guessing. ``open_gust_
  dataset`` (replaces ``_open_series``) selects the ``cfgrib`` engine or the
  default NetCDF engine by **inspecting the file's own magic bytes**, not
  its extension or name -- this is what let the 18 already-mislabeled
  Brazil files be recovered without re-downloading them: they are real GRIB
  content sitting in files still named ``.nc`` from before this fix (fixing
  the bug does not retroactively rename already-downloaded files), and
  content-based detection opens them correctly regardless of what they are
  named.
- **cfgrib/eccodes installed** (``requirements.txt``:
  ``cfgrib>=0.9.15``, ``eccodes>=2.48.0``) -- the Windows wheel bundles its
  own eccodes binary, no separate system-library install was needed.
- **Verification, real data, no re-download**: all 18 Brazil years
  (1991-2008) were run through the fixed ``ensure_year_annual_max`` --
  every one opened correctly via ``cfgrib``, reduced to its per-pixel
  annual maximum, and produced a valid ``annual_max.nc`` (18/18 succeeded;
  see the disk-footprint entry below for what "reduced" means and its
  space impact). No CDS request was re-issued for any of these 18 years --
  the already-paid-for queue time from the original run was fully
  recovered.
- **A second, related discovery made while fixing this**: real ``i10fg``
  (instantaneous 10 m wind gust) responses from this dataset have shape
  ``(time, step, lat, lon)`` -- an ECMWF forecast base-time-plus-lead-time
  structure, not the flat ``(time, lat, lon)`` shape this module's own
  synthetic test fixtures used and ``compute_mean_annual_max_gust``'s
  original reduction (``.max(dim="time")`` only) assumed. Confirmed via
  the ECMWF documentation and this project's own recovered files: "the
  gusts come from the short forecasts that connect analysis data
  assimilation windows" -- consistent with the Phase 3.2 literature-search
  finding (Solar Extreme Heat entry, above) that ERA5 gust fields are
  forecast-derived, not pure analysis fields. ``compute_annual_max_for_
  year``/``compute_mean_annual_max_gust`` now reduce over both ``time`` and
  ``step`` when present -- a real-data correctness fix, not only a
  disk-footprint one, and one that would have silently produced a wrong
  (still-``step``-dimensioned) raster before this task, independent of the
  GRIB-mislabeling bug. Also discovered: real coordinate names are
  ``latitude``/``longitude``, not this codebase's ``lat``/``lon``
  convention -- ``_normalize_dims`` renames them before any downstream
  ``.rio``/``_normalize_longitude`` call, which otherwise fails outright
  (``KeyError: "No variable named 'lon'"``).
- **Tests**: ``tests/test_era5_wind_downloader.py`` (new, 8 tests) --
  ``_is_grib`` magic-byte detection; a GRIB response saved as ``.grib``
  never ``.nc``; a genuine zip-of-NetCDF response unaffected by the fix; an
  unknown-format response failing loud with nothing saved; ``open_gust_
  dataset`` selecting engine by content, including the exact regression
  case (a ``.nc``-named file with GRIB content must not be opened via the
  plain NetCDF path). ``tests/test_extreme_wind_processor.py``: added
  ``test_compute_annual_max_for_year_reduces_time_and_step`` (the shape
  fix) and ``test_normalize_dims_renames_latitude_longitude``.
- References: ``src/downloaders/era5_wind_downloader.py``;
  ``src/processors/extreme_wind_processor.py``; ``requirements.txt``;
  ``tests/test_era5_wind_downloader.py``; ``docs/LIMITATIONS.md``,
  "2026-09-12 -- Extreme Wind: ERA5 gust input not yet downloaded for any
  country" (the entry this fix directly follows up on).
- Status: active, closed. The 18 Brazil years are recovered and usable;
  the mislabeling bug cannot recur for any future download (format is
  always positively identified, never assumed).

## [2026-09-12] GEAR v3 Phase 3.2 follow-up: ERA5 download disk-footprint restructuring

- **Problem, stated plainly**: ``era5_wind_downloader.download_country_
  baseline``/``download_all_era5_wind`` download every baseline year's raw
  hourly file for a country before any reduction happens, keeping all of
  them on disk simultaneously (~0.5-1 GB/year x 30 years/country, up to
  ~28 GB for a single country). This is what filled the disk to 0 bytes
  free mid-run in practice (GEAR v3 Phase 3.2 follow-up incident,
  "Extreme Wind data-gap investigation" entry above) and would recur for
  Portugal/India even after the disk cleanup that incident prompted, since
  nothing about the download shape itself had changed.
- **Fix**: ``src/processors/extreme_wind_processor.py`` gains the
  production entry point for acquiring this hazard's raw data --
  ``ensure_year_annual_max(country, year)`` downloads ONE year via
  ``era5_wind_downloader._download_raw_year``, reduces it immediately to
  that year's per-pixel maximum gust (``compute_annual_max_for_year``),
  writes the tiny result to ``annual_max_path`` (a 2D field, ~130 KB per
  year observed on real Brazil data -- roughly a 3,600x reduction from the
  ~470 MB raw file it replaces), then deletes the raw file (and cfgrib's
  ``.idx`` sidecar) before returning. ``ensure_all_years_annual_max``
  calls this once per baseline year; ``ensure_raw_raster``/``_compute_
  native`` now build the final mean-annual-max raster from the per-year
  ``annual_max_path`` cache instead of ever bulk-loading every year's raw
  hourly data into memory or onto disk at once.
- **Why the loop lives in ``extreme_wind_processor.py``, not ``era5_wind_
  downloader.py``** (the file named in the original task framing): this
  project's standing downloader/processor layering has the processor
  import from the downloader, never the reverse (every other hazard
  follows this pattern too) -- putting the per-year reduce step in the
  downloader module would require it to import the processor's reduction
  function, a circular import. ``era5_wind_downloader.py`` still owns the
  format/data-integrity fix (previous entry) and the single-year download
  primitive (``_download_raw_year``, unchanged in shape); the processor
  owns turning that primitive into a disk-safe multi-year acquisition
  loop, consistent with the existing boundary.
- **Old bulk functions kept, redirected**: ``download_country_baseline``/
  ``download_all_era5_wind`` are not deleted (still useful for deliberate
  manual/debugging use, e.g. inspecting one year's raw file by hand) but
  their docstrings now state plainly they are not the production path,
  pointing to ``ensure_all_years_annual_max`` instead.
- **Duplicate zip+nc storage fixed as part of this same restructuring**
  (a second, independent ~2x waste flagged in the same investigation): a
  successfully-extracted zip's own ``.zip`` file is now deleted immediately
  after extraction (``_download_raw_year``), not kept alongside the
  extracted ``.nc``. Combined with the process-then-delete restructuring,
  no raw payload of any kind survives past the year it belongs to.
- **Verified, real data**: peak per-year raw footprint observed while
  reducing the recovered 18 Brazil years was consistent with the original
  download sizes (~470-500 MB/year) and dropped to 0 immediately after
  each year's reduction -- confirmed by directory listing between years,
  never more than one year's raw file present at once. Total
  ``data/raw/climate/era5_wind/Brazil`` footprint after reducing all 18
  recovered years: ~2.3 MB (18 x ~130 KB), down from ~8.4 GB.
  Portugal/India were then run under this same restructured path for the
  remainder of the baseline (see the follow-up status entry for final
  per-country completion).
- **Tests**: ``tests/test_extreme_wind_processor.py`` -- ``ensure_year_
  annual_max`` deletes the raw file only after a successful write
  (monkeypatched, no real CDS calls); keeps the raw file if reduction
  fails (never lose data on a retry-able error); is idempotent when
  already cached (asserts ``_download_raw_year`` is never called again);
  propagates a download failure without producing a false cache entry;
  ``ensure_all_years_annual_max`` calls every baseline year; and
  ``test_peak_disk_never_holds_more_than_one_years_raw_file``, which
  asserts directly (not just infers from timing) that at no point during a
  multi-year run do two years' raw files coexist on disk.
- References: ``src/processors/extreme_wind_processor.py``;
  ``src/downloaders/era5_wind_downloader.py``; ``tests/
  test_extreme_wind_processor.py``; ``docs/DECISIONS.md``, "GEAR v3 Phase
  3.2 follow-up: ERA5 GRIB mislabeling bug fixed" (this task's other half,
  fixed first per the author's sequencing instruction since it recovered
  already-paid-for CDS queue time).
- Status: active, closed for the restructuring itself. See the follow-up
  status entry for the actual download completion state (Brazil remaining
  years, Portugal, India) once that run finishes.

## [2026-09-12] GEAR v3 Phase 3.2 follow-up: stale background download process ran on pre-fix code, Portugal partial re-corruption caught and cleaned

- **What happened, stated plainly**: the original bulk ERA5 wind download
  (launched earlier this same session, before the disk-full incident) was
  a long-running background process that, once started, never reloads its
  own module code. When the disk filled up, cleanup was done, and the
  GRIB-mislabeling bug (previous entry) was found and fixed **on disk**,
  that background process kept running the whole time -- unaffected by any
  of it, since a Python process holds its imported modules in memory from
  the moment it started, not the moment the corresponding `.py` file was
  last saved. It was still executing the ORIGINAL, buggy, bulk-download,
  zip+nc-duplicating code, and had moved on from the (already
  disk-full-interrupted) Brazil run to Portugal, producing 3 more years
  (1994-1996) with the exact same mislabeling/duplication defects the fix
  was written to eliminate -- entirely unnoticed until this task's
  per-year verification step for Brazil prompted a fresh ``ps aux`` check
  that surfaced the still-running process.
- **This is a coordination-failure mode, not a code bug** -- same family
  as, but the mirror image of, the ``hazard_scope.py`` parallel-session
  conflict (``docs/DECISIONS.md``, "GEAR v3 Phase 3.1: hazard_scope.py
  reconciliation after parallel-session conflict"): that incident was two
  sessions racing to write the same file; this one is a single session's
  own previously-launched process continuing to run stale, pre-fix code
  after the file it loaded from was changed underneath it. Fixing a
  source file on disk has no effect on a process that already imported it
  -- this sounds obvious stated plainly, but was missed in practice while
  attention was on the fix itself, not on whether anything from before the
  fix was still running.
- **Consequence and cleanup**: the stale process (Windows PID 11616) was
  force-stopped (``taskkill /F /PID 11616``, after an earlier attempt via
  PowerShell ``Stop-Process`` was blocked by the permission system and
  required an explicit retry). Its partial Portugal output
  (`data/raw/climate/era5_wind/Portugal/`: 3 corrupted/duplicated years
  plus a truncated 1993 and two empty stub years) was deleted in full
  rather than salvaged -- Portugal's raw files are small enough
  (~8 MB/year vs. Brazil's ~470-500 MB/year) that a clean re-download
  under the fixed pipeline was cheaper and safer than auditing which of
  the 3 "successful" years might also need the GRIB-recovery treatment.
  No Brazil data was affected -- the stale process had already moved past
  Brazil to Portugal before this task's Brazil-recovery work began, so the
  two never touched the same files.
- **Coordination convention added** (``docs/LIMITATIONS.md``, 2026-09-12,
  second entry in the parallel-session-conflict family): before editing a
  file a known background process is actively using, or before starting a
  fresh run of the same acquisition, confirm that process is actually
  stopped -- checking that the file is fixed is not the same as confirming
  nothing stale is still running against the old version of it.
- References: ``docs/LIMITATIONS.md``, new 2026-09-12 coordination
  convention (background-process-vs-fixed-code); ``docs/DECISIONS.md``,
  "GEAR v3 Phase 3.2 follow-up: ERA5 GRIB mislabeling bug fixed, 18 Brazil
  years recovered" (the fix this stale process was running an old copy
  of); "GEAR v3 Phase 3.1: hazard_scope.py reconciliation after
  parallel-session conflict" (the sibling incident in the same
  coordination-failure family).
- Status: active, closed. Stale process stopped, its corrupted partial
  output deleted, Portugal re-downloaded from a clean state under the
  fixed pipeline (see the follow-up completion-status entry).

## [2026-09-13] GEAR v3 Risk_i,h integration gap: precip wired in, wind still blocked on ERA5 acquisition

- **What was investigated, before any change**: manuscript preparation
  surfaced that `src/index/risk_calculator.py`'s `FROZEN_BOUNDS`/
  `HAZARD_TERMS` only covered `ws, sv, iv, heat, spei` -- Extreme
  Precipitation (`precip`) and Extreme Wind (`wind`) were absent, even
  though both already had closed processors (Phase 2.1/2.3) and closed
  RiskBand classification (Phase 3.2, `src/index/risk_bands.py`). Traced
  the actual code path rather than assuming: `risk_bands.py`'s own module
  docstring states plainly it does "not... compute Risk_{i,h} (Equation 1,
  continuous, risk_calculator.py)" -- RiskBand classification runs on raw
  physical values against absolute/percentile/binary thresholds, entirely
  independent of `risk_calculator.HAZARD_TERMS`. `data/outputs/tables/
  risk_by_hazard.csv` confirmed empirically: only `ws, heat, iv, spei, sv`
  ever appeared as `hazard_term` values. **Confirmed: `Risk_i,h` was
  silently absent for `precip`/`wind` for every bucket/country -- not
  computed through any other path.** This was a genuine Phase 1 scope gap
  (Phase 1's closing report explicitly ported the sampling/transform/
  bounds infrastructure "unchanged" and did not anticipate hazards whose
  processors did not exist yet), not a bug introduced later.
- **Data-readiness check, before wiring anything in** -- the task
  requesting this change assumed both hazards had "confirmed real data for
  all three countries"; that assumption did not survive a direct check:
  - `precip`: confirmed ready. `data/processed/climate/extreme_precip_raw_
    {country}_{model}_{scenario}_1km.tif` exists for all 3 countries x 2
    GCMs x 3 scenarios; `risk_bands.csv`'s existing `precip` rows are
    non-null for Brazil (12447), India (13344), and Portugal (675). The
    Phase 2.5 correlation gate already passed for every Extreme-
    Precipitation pair (max |r| = 0.702, `data/outputs/tables/
    correlation_gate.csv`).
  - `wind`: **NOT ready, contrary to the task's premise.** No country has
    a processed `extreme_wind_gust_raw_{country}_1km.tif` (zero files on
    disk). The underlying ERA5 per-year cache (`data/raw/climate/
    era5_wind/{country}/{year}/annual_max.nc`) is itself incomplete:
    Brazil has all 30 years (1991-2020), Portugal 12/30, India 2/30.
    `risk_bands.csv`'s `wind` rows are already known to be all-null for
    every country (consistent with the still-open 2026-09-12 LIMITATIONS
    entry on this acquisition). Wiring `wind` into `risk_calculator.py`
    now would require every plant's `Risk_i,h[wind]` to be computed from
    zero real values -- not attempted. This is reported factually, per
    standing instruction, not silently worked around.
- **Resolution -- precip wired in, wind explicitly left pending**:
  - `src/index/risk_calculator.py`: added `precip` to `HAZARD_TERMS`,
    `LIN_TERMS` (not `LOG_TERMS` -- see below), `GCM_DEPENDENT_TERMS`,
    `HAZARD_LABELS`, `V3_CORE_HAZARD_TERMS`, and `HAZARD_TEMPORAL_WINDOW`
    (imports `extreme_precipitation_processor.PRECIP_TEMPORAL_WINDOW`
    directly rather than duplicating its five values). `raster_path()`
    gained a `precip` branch. `FROZEN_BOUNDS["precip"]` was set from a
    real recompute (`compute_global_bounds()`), per-GCM: GFDL-ESM4
    `(0.36666667461395264, 13.800000190734863)`, MIROC6
    `(0.7666666507720947, 12.566666603088379)`. `BOUNDS_DATA_SNAPSHOT` is
    now a mixed-date string (`"2026-09-04 (ws/sv/iv/heat/spei), 2026-09-13
    (precip)"`) -- the other five terms' bounds are untouched, only
    `precip`'s is new. `--check-bounds` passes clean against this snapshot.
  - **Transform choice, stated plainly, and deliberately NOT
    `normalization.py`'s recommendation**: `precip`'s pooled skewness is
    GCM-dependent and, either way, not a case for `Tlog` (log1p): GFDL-
    ESM4 = -0.125 (already "fairly symmetrical", |skew| <= 0.5), MIROC6 =
    -0.586 (mildly skewed, but LEFT, not right). `Tlog` exists to compress
    a long RIGHT tail; applying it here would misuse the transform against
    data that, if anything, leans the other way. `precip` was therefore
    placed in `LIN_TERMS` (direct Min-Max), the same treatment as `sv`/
    `iv`, decided from the term's own empirical shape under
    `risk_calculator.py`'s existing two-transform scheme (`Tlog`/`Tlin`)
    -- **not** an adoption of `normalization.py`'s new `neg_log_minmax`
    recommendation (which, being magnitude-only, recommends `neg_log_minmax`
    for MIROC6's `precip` regardless of sign). That transform swap is
    Phase 3.3, explicitly still separate and not touched by this task.
  - A circular import surfaced during this change:
    `extreme_precipitation_processor.py` had imported `risk_calculator.
    HAZARD_TEMPORAL_WINDOW` only to assert its own `PRECIP_TEMPORAL_WINDOW`
    matched its schema, from back when `risk_calculator.py` did not depend
    on the processor at all. Now that the dependency runs the other way
    (`risk_calculator.py` imports the processor), that import was removed
    and the schema-keys check inlined as a local literal in the processor
    -- the processor no longer imports `risk_calculator` at all, breaking
    the cycle. The processor's module docstring section "Not yet an
    applicable hazard" was rewritten to "Wired into Risk_i,h -- correlation
    gate already passed (Phase 2.5)", reflecting the actual current state.
  - `wind` was deliberately left out of `HAZARD_TERMS`/`FROZEN_BOUNDS`.
    `risk_calculator.py`'s module docstring now states why in the same
    place it once said "Phase 2 acquisition work, not yet available":
    `risk_bands.py` already tolerates a missing raster (returns all-NaN,
    logged) for its classification pass, but `risk_calculator.py`
    deliberately does not adopt that tolerance for `Risk_i,h` -- a
    published continuous risk number, unlike a classification label,
    should not silently exist as a function of zero real observations.
    `sample_raster` still raises loudly on a missing file for every
    already-wired term; that behavior is preserved.
  - `src/index/hazard_scope.py`: added `PENDING_RISK_I_H_HAZARDS`, an
    explicit, reasoned exception set (currently just `{"wind": "..."}`)
    naming every H_b member that has no `Risk_i,h` entry yet and why --
    the standing mechanism that stops this specific gap (a hazard with a
    closed processor/RiskBand but never wired into `Risk_i,h`) from
    recurring silently for some future hazard. An entry must be removed
    from this dict in the same change that adds the corresponding
    `HAZARD_TERMS` entry, never left stale.
  - `src/index/normalization.py`: `sample_candidate_terms`'s wind sampling
    crashed outright (`rasterio.errors.RasterioIOError`) on the missing
    raster -- fixed with a `_sample_raster_or_nan` helper mirroring
    `risk_bands.py`'s already-established pattern for the identical
    problem, and `compute_normalization_recommendations` now skips (logs,
    does not crash) any candidate whose pooled sample has fewer than 3
    finite values. This is a robustness fix only -- it does not change
    `normalization.py`'s candidate list, its transform-selection
    methodology, or any already-computed recommendation for a term with
    real data.
- **Regression test added** (`tests/test_hazard_scope.py`,
  `test_every_h_b_member_has_a_risk_i_h_entry_or_a_documented_exception`):
  every hazard named in any bucket's H_b must be in either
  `risk_calculator.HAZARD_TERMS` or `hazard_scope.
  PENDING_RISK_I_H_HAZARDS`, never both, never neither. A companion test
  (`test_pending_risk_i_h_hazards_are_reasoned_not_bare`) rejects a bare/
  placeholder reason string. Existing tests updated for the new state:
  `tests/test_risk_calculator.py` (FROZEN_BOUNDS structure, LIN/GCM-
  dependent membership, temporal window, both `compute_risk_by_hazard`
  end-to-end fixtures), `tests/test_extreme_precipitation_processor.py`
  and `tests/test_extreme_wind_processor.py` (the "not wired in yet"
  guards flipped/updated to match precip's new state and wind's continued
  absence), `tests/test_normalization.py` (the "untouched by
  normalization.py" test re-scoped to what it actually verifies -- that
  `HAZARD_TERMS`/`FROZEN_BOUNDS` stay 1:1, not that `HAZARD_TERMS` is
  frozen forever). 327 of 328 relevant tests pass (the one pre-existing,
  unrelated failure -- `test_extreme_wind_processor.py::
  test_real_data_ensure_raw_raster`, an xarray concat error over the
  partial real ERA5 data -- reproduces identically with this task's
  changes stashed out, confirming it predates this task).
  `python -m src.index.risk_calculator` regenerated `risk_by_hazard.csv`
  end to end against real committed data: `precip` now has 64,710
  `Risk_i,h` rows (p50 = 2.9668, p95 = 96.0715, max = 8894.153) alongside
  the five pre-existing terms.
- **Normalization origin table generated** (Methods Section 4.3, promised
  but never produced before this task): `data/outputs/tables/
  normalization_origin_table.csv`, 9 rows (`ws`, `sv`, `iv` pooled;
  `heat`, `spei`, `precip` per GCM), columns `hazard_term, hazard_label,
  gcm, origin_source, data_tier, lower_bound_raw, upper_bound_raw, pool_n,
  skewness, shapiro_stat, shapiro_p, shapiro_subsampled, is_skewed,
  transform_selected, transform_note`. `wind` is absent from this table
  (logged, not silent) for the same data-readiness reason above -- it is
  not excluded by methodology, only by missing data. This table is
  `normalization.py`'s Phase 3.3 *recommendation* (it uses
  `neg_log_minmax` where skewed, by design) -- it is descriptive of what
  Phase 3.3 would apply, and is explicitly NOT what `risk_calculator.
  FROZEN_BOUNDS`/`transform_term` currently compute (still `Tlog`/`Tlin`,
  unchanged, per this task's own scope limit below).
- **Explicitly not done in this task** (per the task's own scope limit):
  Phase 3.3 (adopting `normalization.py`'s `neg_log_minmax` transform
  recommendation into `risk_calculator.py`) was NOT performed. `precip`'s
  `Tlin` treatment in `risk_calculator.py` and its `neg_log_minmax`
  recommendation (MIROC6 only) in `normalization_origin_table.csv` are
  both correct simultaneously -- they are two different modules answering
  two different questions (current production transform vs. a pending
  Phase 3.3 recommendation), not a contradiction.
- References: `src/index/risk_calculator.py`; `src/index/hazard_scope.py`;
  `src/index/normalization.py`; `src/index/risk_bands.py`;
  `src/processors/extreme_precipitation_processor.py`;
  `data/outputs/tables/risk_by_hazard.csv`;
  `data/outputs/tables/normalization_origin_table.csv`;
  `data/outputs/tables/correlation_gate.csv`; `docs/LIMITATIONS.md`,
  "2026-09-11 -- GEM retrofit/repowering field absent" and "2026-09-12 --
  Extreme Wind: ERA5 gust input not yet downloaded for any country"
  (both still accurate, unchanged by this task); `docs/DECISIONS.md`,
  "GEAR v3 Phase 3.2 follow-up: Extreme Wind data-gap investigation" (the
  ERA5 acquisition-status entry this task's wind findings are consistent
  with, not a correction of it).
- Status: **precip closed, final.** wind remains **open, blocked on
  author-authorized ERA5 acquisition completion** (Portugal 12/30 years,
  India 2/30 years, no country processed) -- same blocker already on
  record, now also reflected in `risk_calculator.py`/`hazard_scope.py`
  directly rather than only in `docs/LIMITATIONS.md`. Phase 3.3 (transform
  swap) remains separately open, untouched by this task.

## [2026-09-14] GEAR v3 Risk_i,h integration gap follow-up: ERA5 wind acquisition complete, Risk_i,h wiring still pending

- **What changed**: the ERA5 gust acquisition blocker named in the entry
  above is closed. Brazil (already 30/30), Portugal (was 12/30), and India
  (was 2/30) are now all 30/30 years cached at
  `data/raw/climate/era5_wind/{country}/{year}/annual_max.nc`, using the
  disk-safe one-year-at-a-time pipeline from the 2026-09-12 restructuring.
  Verified by direct filesystem count (90/90 files) and a scripted
  integrity pass: every file opens cleanly via `xarray.open_dataarray`, no
  all-NaN grids, no out-of-range gust values, grid shape consistent within
  each country across all 30 years, and inter-annual mean gust per country
  is stable and physically plausible (Brazil ~17.2 m/s, India ~19.8 m/s,
  Portugal ~25.2 m/s with visibly higher interannual spread, consistent
  with Atlantic extratropical storm exposure).
- **Incidents handled en route, no new acquisition bug found**: (1)
  running two download scripts concurrently briefly exceeded the CDS
  per-account queued-request limit, producing transient job rejections for
  a handful of India years (2017-2020) -- resolved by keeping to a single
  process at the already-documented 3-worker cap; (2) a machine suspend
  left the download process hung after resume (job accepted, no further
  log progress for several hours) -- caught via a stalled-log check,
  process killed and restarted, which resumed only the still-missing
  years without re-downloading completed ones (`ensure_years_concurrent`'s
  existing skip-if-exists behavior, unchanged).
- **Explicitly not done in this task**: `compute_mean_annual_max_gust()`
  has not been run for any country -- no `extreme_wind_gust_raw_{country}_
  1km.tif` exists yet. This is the actual remaining blocker for wiring
  `wind` into `risk_calculator.HAZARD_TERMS`/`FROZEN_BOUNDS`; it is a
  separate step from acquisition and was not attempted here.
- References: `data/raw/climate/era5_wind/{Brazil,Portugal,India}/`;
  `src/processors/extreme_wind_processor.py` (`ensure_years_concurrent`,
  `compute_mean_annual_max_gust`); `src/index/hazard_scope.py`,
  `PENDING_RISK_I_H_HAZARDS["wind"]` (counts updated to match this entry);
  `docs/LIMITATIONS.md`, "2026-09-14 -- Extreme Wind: ERA5 gust
  acquisition complete for all three countries (Risk_i,h gap unchanged,
  still open)".
- Status: **Acquisition sub-blocker closed.** The broader Risk_i,h
  integration gap (this entry's parent, above) remains **open** --
  `compute_mean_annual_max_gust()` has not been run and `wind` is still
  absent from `risk_calculator.HAZARD_TERMS`. Not to be read as "wind
  closed"; only the data-availability precondition changed.

## [2026-09-14] GEAR v3 wind-into-risk_calculator pre-wiring audit: three decision points extracted, none decided here

- **Purpose**: before `compute_mean_annual_max_gust()`/`ensure_raw_raster`
  is actually run and `wind` is wired into `risk_calculator.HAZARD_TERMS`,
  extract every choice that needs an author decision on record first --
  per standing instruction, an OPEN item is a stop point, not something
  this session resolves unilaterally. Three points were checked against
  `risk_calculator.py`/`normalization.py`/`correlation_gate.py` as they
  exist today; two turn out already closed by existing convention, one is
  genuinely open.

- **1. Normalization transform for `wind` -- OPEN, author decision needed.**
  Correction to the task's own premise: "parity with the hazards already
  integrated" is not one answer. Of the three real hazards currently in
  `HAZARD_TERMS`, `ws`/`heat`/`spei` use `Tlog` (log1p + Min-Max,
  `LOG_TERMS`), but `precip` -- the most recently integrated, same task
  that closed the "Risk_i,h integration gap" entry above -- was placed in
  `LIN_TERMS` (direct Min-Max, no log at all), because its *actual*
  empirical pooled skew (GFDL-ESM4 -0.125, MIROC6 -0.586) came back
  fairly-symmetrical-or-left-skewed, not the right-skew `Tlog` is designed
  to compress. So the precedent `precip` actually set is "run the same
  empirical `|skew| <= 0.5` check `normalization.py`'s `normality_check`
  already performs for every candidate, then classify into `LOG_TERMS` or
  `LIN_TERMS` on the *result*" -- never a preset transform chosen before
  the real distribution is seen. `wind`'s real skew is not yet known: it
  is `NEW_CANDIDATE_TERMS` in `normalization.py` already (line 123), but
  its sample is currently all-NaN there (`_sample_raster_or_nan` tolerant
  path, since `extreme_wind_gust_raw_*.tif` does not exist yet -- same gap
  Comando 2 found). `normalization.py`'s own newer `neg_log_minmax`
  recommendation (Phase 3.3) is a separate, still-not-adopted-into-
  production transform and is not a third option for this decision;
  `risk_calculator.py` only has `Tlog`/`Tlin` in production today.
  - **Option (a)** -- same procedure as `precip`: once the real raster
    exists, run `normality_check` on `wind`'s pooled sample, classify into
    `LOG_TERMS`/`LIN_TERMS` on the actual skewness, wire in with whichever
    result that gives. Matches the actual (not assumed) precedent; no
    change to Phase 3.3's separate, still-pending scope.
  - **Option (b)** -- wait for Phase 3.3 (the `neg_log_minmax` swap) to
    close first, and wire `wind` directly under whatever universal
    skewed-variable transform Phase 3.3 settles on, skipping `Tlog`/
    `Tlin` for this one term. Ties `wind`'s integration to a separately-
    scoped, not-yet-timed decision with no author-set deadline.
  - **Option (c)** -- force `Tlog` (log1p) regardless of `wind`'s measured
    skew, to match `ws`/`heat`/`spei` specifically (the literal reading of
    the task's original premise). Would apply `Tlog` without checking
    whether `wind`'s gust distribution actually has the right-skew shape
    `Tlog` exists to correct -- the same misuse `precip`'s closure
    explicitly rejected for itself.
  - **Recommendation**: **(a)**. It is not a new rule -- it is simply
    applying the rule `precip`'s own closure already established,
    consistently, to the next term. (b) blocks wind on an unrelated
    open-ended item; (c) repeats the exact reasoning error `precip`'s
    entry already flagged and rejected.

- **2. `FROZEN_BOUNDS` source for `wind` -- CONFIRMED by existing
  convention, not an open decision.** Every `FROZEN_BOUNDS` entry today is
  computed from real processed rasters via `compute_global_bounds()`,
  never a fixed/manually-chosen value without a data source (`precip`'s
  own bounds were added 2026-09-13 this same way, with the
  `BoundsRegressionError` guard enforcing deliberate, recorded updates --
  never a silent drift-and-accept). `wind` has no GCM/scenario axis
  (confirmed Comando 2/3: single ERA5 product) -- the same shape as `ws`/
  `sv`/`iv` (`FLAT_BOUND_TERMS`, one pooled bound across all countries),
  not `heat`/`spei`/`precip` (`GCM_DEPENDENT_TERMS`, per-GCM, because GCM
  magnitudes are not comparable to each other -- moot for `wind`, which
  has no GCM axis to begin with). No fixed bound without a source is
  needed or proposed: once `extreme_wind_gust_raw_{country}_1km.tif`
  exists for all three countries, `wind`'s bound is computed the same way
  as every `FLAT_BOUND_TERMS` entry already is. Not reopening how
  `FROZEN_BOUNDS` works -- confirming `wind` fits the existing rule
  without needing an exception.

- **3. Correlation-gate scope for `wind` -- CONFIRMED closed, not
  reopened.** `wind` does not appear anywhere in
  `src/index/correlation_gate.py` -- not in `CANDIDATE_PAIRS`, not in
  `WATER_BUCKETS`. Its exclusion is structural (a static tuple that would
  need an explicit, deliberate edit to add `wind`), not a runtime
  condition that wiring `wind` into `risk_calculator.HAZARD_TERMS` could
  incidentally flip. This matches the already-closed decision (module
  docstring, `extreme_wind_processor.py`: "Extreme Wind is not run through
  the Phase 2.5 correlation gate... Methods Section 5's gate is scoped by
  name to Extreme Precipitation only") and the v3 methodology's own
  Section 2 statement that Extreme Wind is assigned per-bucket by
  mechanistic rationale, never by inter-hazard correlation. Verified, not
  reopened: wiring `wind` into `HAZARD_TERMS` touches
  `risk_calculator.py`/`hazard_scope.py` only -- `correlation_gate.py` is
  a separate module with no dependency in either direction.

- References: `src/index/risk_calculator.py` (`LOG_TERMS`, `LIN_TERMS`,
  `FROZEN_BOUNDS`, `GCM_DEPENDENT_TERMS`, `FLAT_BOUND_TERMS`,
  `compute_global_bounds`); `src/index/normalization.py`
  (`normality_check`, `select_transform`, `NEW_CANDIDATE_TERMS`,
  `transform_neg_log_minmax`); `src/index/correlation_gate.py`
  (`CANDIDATE_PAIRS`, `WATER_BUCKETS`); `src/processors/
  extreme_wind_processor.py` module docstring ("Correlation gate: NOT a
  candidate"); this file, "GEAR v3 Risk_i,h integration gap: precip wired
  in, wind still blocked on ERA5 acquisition" (the `precip` Tlin
  precedent cited in point 1).
- Status: **Point 1 open, blocked on author decision (recommendation:
  option (a) above). Points 2 and 3 confirmed against existing code and
  not reopened -- no author input needed for those two.** None of this
  wires `wind` into `risk_calculator.HAZARD_TERMS` yet; that remains a
  separate follow-up task, gated on point 1's answer plus
  `compute_mean_annual_max_gust()` actually being run for all three
  countries.

## [2026-09-14] GEAR v3 wind Risk_i,h integration: empirical transform result, PENDING_RISK_I_H_HAZARDS closed

Executes the protocol approved for point 1 of the pre-wiring audit above
(option (a): real measured skew decides, never assumed parity). Reports the
actual result, not the protocol -- supersedes this entry's own prior
protocol-only draft (never committed as such).

- **Steps 1-3 (data pipeline, verified clean before touching code)**:
  reconfirmed no background process was running (`tasklist`, not assumed
  from a prior session's claim). `ensure_raw_raster` run for all three
  countries in the same session -- `compute_mean_annual_max_gust`/
  `_compute_native` (30-year mean-of-annual-max over the 90 already-
  verified `annual_max.nc` files) then `_resample_to_1km`, all three
  succeeded on the same pass. Verified individually before declaring this
  closed: CRS `EPSG:4326`, resolution `0.008333 deg` matching
  `config.RESOLUTION_TARGET_DEG` exactly, physically plausible gust range
  (Brazil 8.6-36.9 m/s, Portugal 21.6-31.1 m/s, India 9.0-32.2 m/s, all
  `>= 0`, all `< 150`), and grid shape/transform identical, per country, to
  the corresponding `heat_stress_processor` raster (same `_target_grid`).
- **Step 4 (the actual measurement)**: `normalization.normality_check` run
  on the real pooled sample (all three countries' `extreme_wind_gust_raw_
  {country}_1km.tif`, n=39,026,222 finite pixels). Result: **skewness =
  +0.6215 (right-skewed), `|skew| > 0.5` -> `is_skewed = True`**
  (Shapiro-Wilk subsampled, p < 1e-33, reported as a diagnostic only per
  the module's own stated convention, not the deciding statistic).
  `wind` moved from `normalization.NEW_CANDIDATE_TERMS` (now empty,
  `()`) into `risk_calculator.LOG_TERMS` -- **not** `LIN_TERMS` -- because
  the measured skew is significantly RIGHT-skewed, exactly the shape
  `Tlog` (log1p) is designed to compress. This is the same
  `normality_check` procedure that put `precip` in `LIN_TERMS` (`precip`'s
  measured skew was not right-skewed); the rule carried over identically,
  the outcome differs because the real data differs -- confirming this was
  never "parity with ws/heat/spei by assumption" (rejected option (c) of
  the pre-wiring audit) but the empirical result landing on the same side
  as ws/heat/spei this time.
- **Step 5**: `wind` added to `risk_calculator.HAZARD_TERMS` (now `ws,
  heat, sv, iv, spei, precip, wind`) and to `LOG_TERMS`. Fixed a circular
  import surfaced by this change: `extreme_wind_processor.py` previously
  imported `risk_calculator.HAZARD_TEMPORAL_WINDOW` only to assert its own
  `WIND_TEMPORAL_WINDOW` schema matched it; now that `risk_calculator.py`
  imports `WIND_TEMPORAL_WINDOW` from the processor (the same direction
  `precip`'s wiring already established), the processor asserts against a
  standalone schema-keys literal instead -- identical fix to `precip`'s own
  circular-import resolution, same direction (`risk_calculator` ->
  processor, never the reverse).
- **Step 6**: `FROZEN_BOUNDS["wind"] = (9.123578071594238,
  31.070894241333008)`, computed via `compute_global_bounds()`, in
  `FLAT_BOUND_TERMS` (no GCM axis -- confirmed already-closed, Comando 4
  point 2). Pooled over real plant locations in all three countries, same
  procedure as `ws`/`sv`/`iv`. `BOUNDS_DATA_SNAPSHOT` updated to record the
  2026-09-14 addition alongside the existing 2026-09-04/2026-09-13 dates.
- **Step 7**: `hazard_scope.PENDING_RISK_I_H_HAZARDS` is now `{}` --
  `wind` was its only member. Left as a named empty dict, not deleted, so
  the exception mechanism (`tests/test_hazard_scope.py`'s exhaustiveness
  guard) still has somewhere to register a future hazard's gap.
- **Tests**: `tests/test_extreme_wind_processor.py`'s "not wired in yet"
  guards flipped to their positive form (mirrors `precip`'s own flip when
  it was wired in). Three pre-existing `risk_calculator`/`precipitation`
  tests had hardcoded `HAZARD_TERMS`/`FROZEN_BOUNDS` snapshots that
  predated `wind` and needed the new member added (`test_frozen_bounds_
  structure_unchanged_from_retired_module`, `test_wired_into_risk_
  calculator_hazard_terms` in the precip test file) or an explicit
  exemption for `wind`'s by-design `horizon_year=None`
  (`test_every_hazard_term_declares_a_temporal_window`); one end-to-end
  fixture test needed a synthetic `wind` column/bound added
  (`test_compute_risk_by_hazard_end_to_end`). 333/333 relevant tests pass
  (`tests/test_main.py`, `test_monte_carlo.py`, `test_visualization.py`
  remain broken on collection for a pre-existing, unrelated reason --
  `ccrs_calculator` retirement -- confirmed already broken before this
  task, not caused by it).
- **Explicitly not done in this task**: the Etapa 9 manuscript-status
  update (`docs/rework/GEAR_v3_methodology_nature_format.md` and
  `GEAR_v3_work_plan.md`) was checked in full and found to carry no
  literal "wind not yet computed/pending acquisition" sentence to flip --
  both documents describe the methodology prospectively/normatively, as if
  `wind`'s `Risk_i,h` already existed, and track acquisition status
  nowhere in their own text (that status lived only in `docs/DECISIONS.md`/
  `docs/LIMITATIONS.md`, both already current). No manuscript edit was
  invented to satisfy this step; flagged for author confirmation that no
  action is actually needed there, rather than silently skipped.
- References: `src/index/risk_calculator.py` (`HAZARD_TERMS`, `LOG_TERMS`,
  `FROZEN_BOUNDS`, `BOUNDS_DATA_SNAPSHOT`, module docstring); `src/index/
  hazard_scope.py` (`PENDING_RISK_I_H_HAZARDS`); `src/index/
  normalization.py` (`NEW_CANDIDATE_TERMS`, `GCM_DEPENDENT_TERMS`);
  `src/processors/extreme_wind_processor.py` (module docstring,
  `_TEMPORAL_WINDOW_SCHEMA_KEYS`); `tests/test_risk_calculator.py`,
  `tests/test_extreme_wind_processor.py`,
  `tests/test_extreme_precipitation_processor.py`; this file, "GEAR v3
  wind-into-risk_calculator pre-wiring audit: three decision points
  extracted, none decided here" (the protocol this entry executes).
- Status: **Closed.** `wind` is a real, computable `Risk_i,h` term in all
  three countries as of this entry. `PENDING_RISK_I_H_HAZARDS` no longer
  names any hazard. Etapa 9 (manuscript status phrase) has no concrete
  action identified -- see above, author input welcome if a specific
  sentence was intended that this review missed.

## [2026-09-14] Phase 3.3 scope over `wind`: CLOSED -- Option B, `-ln(1-x)` applied to all of `LOG_TERMS`

- Scope: originally logged the same day as an open question while mapping
  where `-ln(1-x)` (`normalization.py`'s `neg_log_minmax`) was only a
  recommendation versus where `risk_calculator.py`'s real `Risk_i,h`
  computation still ran `log1p`, per the binding convention that a decision
  this file cannot make on its own must be logged as open, not assumed
  (`CLAUDE.md` Section 3/16). The author has now returned a verdict,
  closing that question -- see "Decision" below.
- State prior to this change (mapped, unchanged until this closing entry):
  - `src/index/risk_calculator.py:487-488` (`transform_term`, `LOG_TERMS`
    branch) is the only place a real `Risk_i,h` value is computed with
    `log1p`: `x, a, b = np.log1p(raw), np.log1p(lo), np.log1p(hi)`.
    `LOG_TERMS` (`risk_calculator.py:197`) = `{"ws", "heat", "spei",
    "wind"}` -- `wind` joined this set on 2026-09-14 (see "GEAR v3 wind
    Risk_i,h integration" above), on its own measured skew (+0.6215,
    right-skewed, `risk_calculator.py:191-196`; full readout at line 2792
    of this file). `LIN_TERMS` (`risk_calculator.py:198`) = `{"sv", "iv",
    "precip"}` -- direct Min-Max, never log1p.
  - `src/index/normalization.py` computes an independent recommendation
    per hazard, never applied to `risk_calculator.py`
    (`normalization.py:12-17`, `:65-73`). `select_transform`
    (`normalization.py:202-205`) returns `neg_log_minmax` for every term
    `normality_check` finds skewed and never returns the retired
    `log1p_minmax`. `NORMALIZATION_CANDIDATE_TERMS`
    (`normalization.py:130`) is `risk_calculator.HAZARD_TERMS` in full,
    so `wind` is already run through this check today and would today
    receive a `neg_log_minmax` recommendation on the same +0.6215 skew --
    but that recommendation is not wired into `risk_calculator.py` and
    changes nothing about `wind`'s actual `Risk_i,h` value.
  - Net: for `wind` specifically, both modules currently agree the
    variable is right-skewed and both currently apply/recommend a
    log-family compression -- but `risk_calculator.py`'s live computation
    uses `log1p` (tail-compressing, arguably the wrong direction for a
    right-skewed extremal hazard per `normalization.py:65-73`'s own
    stated rationale) while `normalization.py`'s recommendation is
    `neg_log_minmax` (tail-expanding). Phase 3.3 (`docs/rework/
    GEAR_v3_work_plan.md`) is the still-pending step that would apply any
    `neg_log_minmax` swap to `risk_calculator.py`'s real computation.
  - `wind` was not present in the codebase the last time Phase 3.3's own
    scope was framed (`normalization.py:32-34` names only `heat`'s
    tail-compression complaint as Phase 3.3's stated trigger); `wind` is a
    later, 2026-09-14 addition to `HAZARD_TERMS`/`LOG_TERMS`, arriving
    after that framing existed.
- Two options were put to the author, neither decided by the assistant:
  - **Option A -- Phase 3.3 swaps only the hazards already in `LOG_TERMS`
    before `wind` joined it** (i.e. `ws`, `heat`, `spei`). `wind` would
    keep `log1p` in `risk_calculator.py` unless and until a separate,
    later decision explicitly extends Phase 3.3 to cover it.
  - **Option B -- Phase 3.3 swaps every hazard currently in `LOG_TERMS`
    as of today, including `wind`** (i.e. `ws`, `heat`, `spei`, `wind`),
    on the grounds that `wind`'s own measured skew (+0.6215) already puts
    it through the identical `normality_check` -> `is_skewed` ->
    log-family-transform path as the original three, with no
    methodological difference in how it qualified.
- **Decision: Option B.** The author confirmed (2026-09-14) that Phase 3.3
  applies `-ln(1-x)` to the full current `LOG_TERMS` set -- `ws`, `heat`,
  `spei`, `wind` -- not only the three terms that predated `wind`'s wiring.
  `wind` is treated as any other `LOG_TERMS` member: its inclusion follows
  from its own measured skew via the same uniform `normality_check`, with
  no special-casing either way.
- Reason: `wind` qualified for `LOG_TERMS` through the identical empirical
  procedure as `ws`/`heat`/`spei` (skew +0.6215, `|skew| > 0.5`) --
  carving it out into a permanent `log1p` exception would need its own
  justification for treating `wind` differently from every other
  `LOG_TERMS` member, and none was identified; `normalization.py:65-73`'s
  own stated rationale (log1p compresses exactly where a right-skewed
  hazard's most extreme plants should be most separated) applies to
  `wind`'s distribution the same as to `heat`'s.
- Consequence (declared, not incidental): `wind`'s `Risk_i,h` numerically
  changes for every plant/country/scenario row -- it switches from
  `log1p` (tail-compressing) to `-ln(1-x)` (tail-expanding), changing
  which plants land near the top of `wind`'s normalized [0, 1] range and
  therefore `wind`'s contribution to the Wind and Solar buckets'
  `RiskBand_{i,h}`/PSAE downstream. This is a real change to
  already-published-shape `wind` results, not only to `ws`/`heat`/`spei`,
  and is the expected, intended effect of this decision, not a side
  effect to be minimized.
- Implementation: `risk_calculator.transform_term`'s `LOG_TERMS` branch no
  longer computes `np.log1p(raw)`/`np.log1p(lo)`/`np.log1p(hi)`. It now
  reproduces `normalization.transform_neg_log_minmax`'s mechanism directly
  (padded preliminary Min-Max -> `-ln(1-x)` -> second Min-Max), not
  imported from `normalization.py` (which imports `risk_calculator.py`,
  so the reverse import would be circular) -- new constant
  `TLOG_UPPER_TAIL_PADDING_FRACTION = 0.05`, matching `normalization.
  UPPER_TAIL_PADDING_FRACTION`. `FROZEN_BOUNDS` (raw, pre-transform
  min/max) is unchanged -- only the transform formula applied to those
  bounds changed, so no bounds recompute or regression-lock update was
  needed. `LIN_TERMS` (`sv`/`iv`/`precip`) is untouched. A cross-module
  parity test (`tests/test_risk_calculator.py::
  test_tlog_matches_normalization_neg_log_minmax`) asserts the two
  modules' implementations stay numerically identical.
- Tests updated: `tests/test_risk_calculator.py`'s
  `test_tlog_is_log1p_then_minmax` renamed to `test_tlog_is_neg_log_minmax`
  (same endpoint assertions, now documented as `-ln(1-x)`); added
  `test_tlog_matches_normalization_neg_log_minmax` (numeric parity with
  `normalization.transform_neg_log_minmax`), `test_tlog_no_longer_uses_
  log1p_directly_on_raw_and_bounds`, and `test_tlog_expands_upper_tail_
  relative_to_retired_log1p` (mirrors `normalization.py`'s own
  `test_neg_log_minmax_expands_upper_tail_relative_to_log1p`). Module
  docstring and section-header comments in both `tests/
  test_risk_calculator.py` and `src/index/risk_calculator.py`/`src/index/
  normalization.py` updated to stop stating `risk_calculator.py` still
  uses `log1p` in its live computation.
- Full suite: 336/336 passing (`python -m pytest -q`, 3 pre-existing
  collection errors excluded -- `tests/test_main.py`,
  `tests/test_monte_carlo.py`, `tests/test_visualization.py`, all broken
  on the retired `ccrs_calculator` import, confirmed already broken before
  this task per "GEAR v3 wind Risk_i,h integration" above, unrelated to
  this change). `tests/test_risk_calculator.py` +
  `tests/test_normalization.py` alone: 47/47 passing.
- References: `src/index/risk_calculator.py` (`transform_term`,
  `TLOG_UPPER_TAIL_PADDING_FRACTION`, module docstring "Phase 3.3"
  section); `src/index/normalization.py` (`transform_neg_log_minmax`,
  module docstring); `tests/test_risk_calculator.py`; this file, "GEAR v3
  wind Risk_i,h integration: empirical transform result,
  PENDING_RISK_I_H_HAZARDS closed" (2026-09-14, skew readout).
- Status: **Closed (2026-09-14).** `risk_calculator.py`'s `Tlog` branch is
  `-ln(1-x)` for `ws`/`heat`/`spei`/`wind`; `log1p` no longer appears in
  this module's real `Risk_{i,h}` computation. Not reopened without new
  data or an explicit author request.
- **Correction (2026-09-14, found during Phase 4/PSAE mapping):** the
  "Consequence" bullet above overstates this change's blast radius. It
  says wind's `Risk_i,h` change affects "the Wind and Solar buckets'
  `RiskBand_{i,h}`/PSAE downstream" -- that is **false**, confirmed by
  direct code read. `src/index/risk_bands.py`'s own module docstring
  states plainly that `RiskBand_{i,h}` classification "does **not** ...
  touch `normalization.py`'s transform recommendation or
  `risk_calculator.FROZEN_BOUNDS`/`transform_term` (Phase 3.3's job) ...
  classification here runs on RAW physical values ... never the
  Min-Max-normalized `Hazard_{i,h}` term" (`risk_bands.py:16-23`), and a
  grep of the module confirms neither `transform_term` nor
  `FROZEN_BOUNDS` is imported or called anywhere in it outside that prose.
  `RiskBand_{i,h}` is classified from the same raw physical values
  `correlation_gate.py` reads, independent of whichever `Tlog` formula
  `risk_calculator.py` applies. This Phase 3.3 entry's actual, correct
  blast radius is **`Risk_{i,h}` (Equation 1) only** -- `RiskBand_{i,h}`
  (Equation, Section 4) and therefore PSAE (Equation 2, Phase 4, not yet
  implemented) are unaffected by this change. Left as a correction rather
  than a silent edit, per this file's own convention of not rewriting
  closed entries. No code or test changed by this correction -- it is a
  documentation-accuracy fix only.

## [2026-09-14] Phase 4 (PSAE) input mapping; missing/NaN RiskBand handling in the PSAE denominator: CLOSED, complete-case

- Scope: mapping only, ahead of any Phase 4 implementation, per instruction
  not to write PSAE code before the input surface and any undocumented
  methodological gap are both on record. No `src/index/psae.py` (or
  equivalent) exists in this repository as of this entry (confirmed by
  directory listing of `src/index/`).
- **Six-hazard checklist, confirmed by direct code read, not by handoff**:
  `docs/rework/GEAR_v3_methodology_nature_format.md` Section 2 names
  exactly six core hazards: Water Stress, Extreme Heat, Drought, Extreme
  Precipitation, Wildfire, Extreme Wind. Reading `risk_calculator.
  HAZARD_TERMS` directly (`risk_calculator.py:214`, post Phase 3.3, commit
  `74915ea`): `("ws", "heat", "sv", "iv", "spei", "precip", "wind")`.
  Cross-referencing term to checklist name:
  - `ws` (Water Stress) -- present.
  - `heat` (Extreme Heat) -- present.
  - `spei` (Drought) -- present.
  - `precip` (Extreme Precipitation) -- present.
  - `wind` (Extreme Wind) -- present (Phase 3.3's subject, wired in
    2026-09-14).
  - Wildfire -- **absent**. Confirmed on two independent sources: (1) no
    `wildfire` term anywhere in `HAZARD_TERMS`; (2) `hazard_scope.
    DEFERRED_OR_EXCLUDED_HAZARDS = ("wildfire", "slr")`
    (`hazard_scope.py:117`) names it explicitly excluded, and
    `hazard_scope._validate()` (`hazard_scope.py:152-177`) asserts at
    import time that neither ever appears in any bucket's `H_b`.
    `docs/LIMITATIONS.md`, "Wildfire (FWI/EFFIS) deferred, not
    implemented" is the standing reference for why (CDS catalogue lacks
    the daily-humidity input needed for FWI on either configured GCM).
  - **Correction to this task's own premise**: the prompt states "os 6
    hazards centrais estão integrados... (incluindo wind)". By direct code
    read, that is 5 of the 6 named core hazards, not 6 -- Wildfire remains
    deferred, unchanged by Phase 3.3 or any other recent work. This is
    stated here rather than silently assumed, per the instruction not to
    take the handoff's hazard count at face value.
  - Two additional terms, `sv`/`iv` (water seasonal/interannual
    variability), are also present in `HAZARD_TERMS` with real `Risk_i,h`
    but are **not** among Section 2's six named hazards -- they are
    extension terms, already resolved into Hydro's `H_b`
    (`hazard_scope.APPLICABLE_HAZARDS["hydro"]`, author-confirmed
    2026-09-12, see "GEAR v3 Phase 3.1: hazard_scope.py reconciliation").
  - `hazard_scope.PENDING_RISK_I_H_HAZARDS` (`hazard_scope.py:143`) is
    `{}` (empty) -- confirms every hazard named in any bucket's `H_b` has
    a real `HAZARD_TERMS` entry; no hazard is silently missing a
    `Risk_i,h` computation path.
- **Where Phase 4 connects in the code, and what already exists**:
  - `src/index/risk_bands.py::compute_risk_bands(model=...)` (Phase 3.2,
    already closed for all hazards including `wind`) is the actual input
    surface, not `risk_calculator.py` directly. It returns a
    `RiskBandTable(frame, percentile_cuts, model)`; `frame` is long
    format, one row per plant x water_scenario x hazard_term, with a
    `band` column drawn from `BAND_LABELS = ("Low", "Medium", "High",
    "Extreme")` (`risk_bands.py:165`) for every hazard/bucket pair except
    Wind-bucket Extreme Wind, which uses `WIND_BUCKET_BAND_LABELS = ("Low",
    "Extreme")` (`risk_bands.py:166`) -- the same string tokens, not a
    parallel vocabulary, so `1[RiskBand_i,h >= High]` (Equation 2) is
    already directly implementable as `band in ("High", "Extreme")` for
    both schemes with no new mapping decision needed.
  - `src/index/hazard_scope.py::APPLICABLE_HAZARDS` (Phase 3.1, closed) is
    the `H_b` table Phase 4 groups by: `hydro` (`ws`, `spei`, `precip`,
    `sv`, `iv`, `|H_b|`=5), `thermal` (`ws`, `heat`, `precip`, `|H_b|`=3),
    `wind` (`wind`, `|H_b|`=1), `solar` (`heat`, `precip`, `wind`,
    `|H_b|`=3). No bucket currently has `|H_b|`=2, so the boundary between
    the four-band scheme (`|H_b|`>=3) and Wind's compressed scheme
    (`|H_b|`=1) never has to handle an in-between case with today's H_b
    table.
  - Nothing beyond this exists: no `src/index/psae.py`, no aggregation
    function, no classification dispatch (four-band vs. compressed), no
    comparability guard (`docs/rework/GEAR_v3_work_plan.md` Phase 4.2's
    "raises an explicit error rather than silently producing a misleading
    [cross-bucket] comparison" requirement). All of Phase 4.1/4.2 is
    unwritten.
- **What is already fully specified (checked so as not to mis-flag it as
  open)** -- confirmed sourced, not invented, so none of these are logged
  as open decisions:
  - Aggregation formula: unweighted count fraction, `Equation 2`
    (`GEAR_v3_methodology_nature_format.md:633`), with weighting and a
    continuous/ordinal alternative explicitly considered and rejected
    (`:658-661`, "reopens the continuous-weighting problem PSAE was
    designed to close").
  - Classification cut points (1.0/0.5/0.0 -> EXTREME/HIGH/MEDIUM/LOW) and
    Wind's compressed 2-label scheme: explicit, Tier 3 declared
    (`:641-656`).
  - Correlation between hazards: handled entirely upstream, by the
    already-closed Phase 2.5 correlation gate, which determines `H_b`
    membership itself (a hazard failing the gate is excluded from `H_b`
    before Phase 4 ever runs) -- Phase 4 does not re-touch correlation.
  - Cross-bucket comparability: explicit, Section 9 ("valid only within
    the same technology bucket... not valid across buckets, because
    `|H_b|` differs by bucket").
  - Per-scenario computation: PSAE inherits the same implicit
    per-scenario convention already established and consistently applied
    to `Risk_i,h`/`RiskBand_i,h` throughout the methodology text (neither
    carries an explicit `s` subscript in the document's own notation
    despite being computed per SSP/water-scenario in the actual code and
    output tables -- Section 9's "every hazard's `Risk_i,h`/RiskBand is
    computed per SSP scenario except Extreme Wind" is the documented
    source this extends by direct precedent, not a new PSAE-specific
    assumption).
  - Primary-GCM selection for buckets whose `H_b` mixes GCM-dependent
    (`heat`/`precip`) and GCM-independent (`ws`/`sv`/`iv`/`wind`) hazards:
    resolved by the already-established, repo-wide "GFDL-ESM4 primary,
    MIROC6 sensitivity panel, never blended" convention (this file, "CCRS
    replaces SCI/NAES as the unified risk architecture"), already
    implemented as `compute_risk_bands(model=...)`'s single-model-at-a-time
    signature -- not a new PSAE-specific decision to make.
- Question closed by this entry, originally logged open (no documented
  source found in `GEAR_v3_methodology_nature_format.md` Section 6,
  Equation 2's own definition, or anywhere else): missing/`NaN`
  `RiskBand_i,h` handling in the PSAE denominator. A plant can have a
  `None`/`NaN` band for one hazard in its bucket's `H_b` today
  (`risk_bands._bandize` maps `NaN` raw values to `None`,
  `risk_bands.py:367`; real causes already on record elsewhere in this
  file/`docs/LIMITATIONS.md` -- e.g. plants outside Aqueduct basin
  coverage, ERA5/CMIP6 raster gaps at specific coordinates). Three
  plausible readings were put on record, none decided at the time:
  (a) available-case (`|H_b|` shrinks per-plant to the count of hazards
  with a real band), (b) complete-case (`PSAE_i` undefined for that
  plant, `|H_b|` stays the bucket's full nominal count), (c)
  treat-as-not-High (missing hazard counts toward the denominator, never
  toward the numerator).
- **Decision: (b) complete-case.** When any hazard `h` in a plant's
  bucket `H_b` has a missing/`NaN` `RiskBand_{i,h}`, `PSAE_i` for that
  plant is **undefined** (`NaN`/null), not computed over a reduced
  denominator and not silently treated as "not High". `|H_b|` for a
  given bucket is always the bucket's full nominal count from
  `hazard_scope.APPLICABLE_HAZARDS` -- it is never shrunk per-plant to
  match whatever subset of hazards happens to have data for that
  specific plant.
- Reason:
  - **Avoids an implicit, per-plant-varying denominator.** Equation 2
    defines `|H_b|` as a property of the bucket (Section 3's H_b table),
    not of the individual plant's data completeness. Option (a) would
    make `|H_b|` silently plant-dependent -- two plants in the same
    bucket, both reported as bucket `X`, would be answering a
    structurally different question (one over 3 hazards, another over
    2) with no marker in the output distinguishing them, undermining the
    exact comparability property Section 9 relies on ("valid only within
    the same technology bucket") and that this bucket-level `|H_b|` is
    built to guarantee.
  - **Avoids systematic bias toward LOW for the worst-covered plants.**
    Option (c) would make every data gap silently read as "this hazard
    is not severe here" -- for a physical-exposure screening index
    specifically designed (Section 6) to flag severity, treating absence
    of measurement as evidence of absence of risk is the one reading most
    likely to understate `PSAE_i` exactly where the underlying data is
    weakest, with no signal in the output that this happened. This
    directly contradicts the standing "fail loud, not silently" project
    convention (`CLAUDE.md` Section 8) and the pattern already used
    throughout this pipeline for a missing/insufficient sample (e.g.
    `risk_bands.py`'s own `HazardNotApplicableError`, `_sample_raster_or_
    nan`'s explicit-NaN-plus-logged-warning convention, never a silent
    substitute value).
  - Complete-case is the only one of the three that neither invents a
    per-plant-varying scope for `|H_b|` (a) nor manufactures a severity
    judgment from an absence of data (c); it reports honestly that the
    physical-exposure question cannot be fully answered for that plant
    with the data on hand, which is consistent with how this project
    already treats other missing-data cases (e.g. `age_factor`'s
    "missing `commissioning_year`" rows: kept, flagged, never silently
    dropped or defaulted to a value that manufactures a result).
- Consequence for the output (binding on Phase 4's implementation, not
  optional styling):
  - A plant with `PSAE_i` = `NaN`/null under this rule is **never
    silently omitted** from the PSAE output table -- the row exists with
    an explicit null/`NaN` `psae` value, never dropped so the row count
    quietly shrinks with no trace.
  - The output must carry a non-strippable, explicit marker distinguishing
    "`PSAE_i` = 0.0 (LOW, computed, no hazard reached High)" from
    "`PSAE_i` = undefined (not computed, at least one hazard in `H_b` has
    no `RiskBand`)" -- these are not the same statement and must never
    collapse to the same value or the same blank cell. Concretely: a
    boolean/flag column (e.g. `psae_complete: bool`, or an explicit
    `missing_hazards: tuple[str, ...]` naming which member(s) of `H_b`
    were unavailable for that plant) alongside the `psae` value itself,
    not merely a `NaN` that a downstream reader could mistake for a
    zero or a dropped row.
  - A per-bucket, per-country coverage summary (count/fraction of plants
    with `PSAE_i` undefined, out of that bucket's total) must be part of
    Phase 4's report output, the same reporting posture already used
    elsewhere in this pipeline for partial data coverage (e.g.
    `age_factor_report.md`'s missing-`commissioning_year` counts per
    country, `risk_bands_report.md`'s per-hazard/bucket row counts).
    This is a reporting requirement, not merely a suggestion: a Phase 4
    output with undefined-`PSAE_i` rows and no visible coverage summary
    would satisfy "not silently omitted" at the row level while still
    hiding the scale of the gap from a reader.
  - This decision does not by itself specify the exact column names or
    file schema -- that remains an implementation detail for the Phase 4
    task that writes `psae.py`, constrained only by the two requirements
    above (explicit flag, not a bare NaN; a coverage summary in the
    report).
- Data: as of this entry, the real extent of missing-hazard plants per
  bucket has not been measured (this entry closes the methodological
  question, not a data audit) -- known contributing gaps already on
  record elsewhere in this file/`docs/LIMITATIONS.md` include Aqueduct
  basin non-matches for `ws`/`sv`/`iv` (India, Portugal) and any
  plant-coordinate a processed ERA5/CMIP6 raster does not cover for
  `heat`/`spei`/`precip`/`wind`. Quantifying how many plants per
  bucket/country this rule will mark `PSAE_i` undefined for is Phase 4
  implementation work, not this entry's scope.
- Action taken here: methodological decision only, per instruction -- no
  `psae.py` or other PSAE code was written by this entry.
- References: `src/index/risk_calculator.py:214` (`HAZARD_TERMS`);
  `src/index/hazard_scope.py:107-143` (`APPLICABLE_HAZARDS`,
  `PENDING_RISK_I_H_HAZARDS`, `DEFERRED_OR_EXCLUDED_HAZARDS`);
  `src/index/risk_bands.py:165-166`, `:353-420`, `:490-549` (`BAND_LABELS`,
  `_bandize`, `classify_hazard`, `compute_risk_bands`);
  `docs/rework/GEAR_v3_methodology_nature_format.md` Section 6 (Equation
  2), Section 9 (comparability); `docs/rework/GEAR_v3_work_plan.md`,
  "Phase 4: PSAE aggregation"; `docs/LIMITATIONS.md`, "Wildfire (FWI/EFFIS)
  deferred, not implemented"; `CLAUDE.md` Section 8 ("fail loud, not
  silently").
- Status: **Closed (2026-09-14).** Missing/NaN `RiskBand_i,h` for any
  hazard in a plant's `H_b` makes `PSAE_i` undefined for that plant
  (complete-case), reported explicitly (flag/coverage summary, never a
  silent drop or a bare NaN indistinguishable from a computed 0.0). Every
  other PSAE mechanic already confirmed sourced in this entry's mapping
  section above is unchanged and not reopened by this closure.

## [2026-09-14] Phase 6 (Sensitivity/uncertainty) input mapping: PHASE6_DESIGN.md read, Phase 2.5 closure verified by code, six OPEN items registered

- Scope: mapping only, ahead of any Monte Carlo/Sobol code, per instruction
  not to write Phase 6 code before its input surface and every
  undocumented methodological gap are on record. `psae.py` (commit
  `6b70a36`) is read as the actual Phase 4 interface Phase 6 will draw its
  PSAE-side parameters/outputs from.
- **`docs/rework/PHASE6_DESIGN.md` -- what it is, read in full for the
  first time in this entry (previously untracked, never read)**: a
  design-only research document, **not an approved plan**, by its own
  first line ("Design-only document. No code is implemented or run
  against this document.") and its own closing section (Section 5 lists
  six items explicitly needing "author confirmation before an
  implementation prompt is written"). It was written *ahead of* Phase 4
  and Phase 3.3 closing, on the explicit bet that writing the design early
  would keep it off the critical path once both closed -- and states its
  own limitation up front: "If either closes with a materially different
  shape..., the parameter inventories in Sections 1 and 2 need a re-check
  against the actual closed state before implementation -- this design is
  **not self-updating**." It is not committed to git (confirmed untracked
  by `git status` both when first noticed and as of this entry).
  - **What it got right, verified against the actual closed state**:
    - Phase 3.3 assumptions (post-swap `neg_log_minmax` design,
      `normalization.UPPER_TAIL_PADDING_FRACTION = 0.05`) match the real
      `risk_calculator.py`/`normalization.py` post-commit-`74915ea` state
      exactly -- confirmed by direct read of both files (this file's
      Phase 3.3 entries).
    - Its `age_factor` constant table (`COAL_DECAY_RATE = 0.0025`,
      `WIND_RELATIVE_RATE = 0.004`, `HYDRO_RETENTION_RATE = 0.0055`,
      `SOLAR_RETENTION_RATE = 0.007`, `COAL_OVERHAUL_CYCLE_YEARS = 5`,
      `COAL_OVERHAUL_RECOVERY = 0.70`) matches `age_factor.py:126-135`
      verbatim -- confirmed by direct grep of the module, not assumed
      from the design doc's own table.
    - Its `hazard_scope.APPLICABLE_HAZARDS` OAT table (Hydro 5, Thermal 3,
      Solar 3, Wind 1/0-meaningful) matches `hazard_scope.py:107-112`
      exactly.
    - Its `monte_carlo.py` mechanics description (`N_ITERATIONS = 1000`,
      `PERCENTILES = (2.5, 50.0, 97.5)`, `country_rng`'s
      `zlib.crc32`+`SeedSequence` construction) matches
      `monte_carlo.py:143-175` verbatim -- confirmed by direct grep, not
      assumed.
  - **What it got wrong or left stale, found in this entry**: Section 0
    still reads "Phase 4 (PSAE aggregation): not implemented... No
    `src/index/psae.py` (or equivalent) exists yet" -- stale as of commit
    `6b70a36`. More importantly, its own Section 2.2 (PSAE cut-point OAT
    design) was written **before** `psae.py`'s actual interface existed
    and, checked against that real interface now, is missing something
    the real module introduced that Section 2.2 has no provision for at
    all: `psae.py`'s complete-case mechanic (`psae_complete`,
    `missing_hazards`, this file's "Phase 4 (PSAE) input mapping... CLOSED,
    complete-case" entry above) is not mentioned anywhere in
    `PHASE6_DESIGN.md`, because it postdates the document. This is exactly
    the "materially different shape" re-check the document itself warned
    would be needed -- see the new open item below.
  - **Net assessment**: a thorough, well-sourced set of research notes and
    a defensible starting point for an implementation prompt -- but reading
    it as if it were an approved Phase 6 design, rather than as a draft
    still carrying six author-facing open questions plus the one gap found
    here, would be a mistake this entry is written to prevent.
- **Phase 2.5 (correlation gate) closure -- confirmed by code and real
  output data, not by trusting `PHASE6_DESIGN.md`'s own claim or the work
  plan's "Sequencing notes" line**:
  - `src/index/correlation_gate.py:181`: `GATE_THRESHOLD = 0.80`, matching
    the cited convention.
  - `data/outputs/tables/correlation_gate.csv` exists on disk (modified
    2026-09-12), a real output artifact, not just code -- 56 rows, all
    three countries present (`Brazil`, `Portugal`, `India`, plus a
    `pooled` row group), confirmed by direct `pandas.read_csv` in this
    entry.
  - Among the 44 gated rows, `decision_r.abs().max() == 0.7020788...`
    (Seasonal vs. Interannual Variability, Hydro) and
    `(gate_verdict == "fail").any() == False` -- every gated pair passed
    at the production `0.80` threshold, confirmed by direct computation on
    the real CSV in this entry, matching this file's "GEAR v3 Phase 2.5:
    correlation gate implemented and run" (2026-09-12) and "...follow-up:
    Portugal/India Extreme Precipitation processed, gate closed for all
    three countries" (2026-09-12) entries. **Phase 2.5 is closed,
    confirmed independently by code and data, not assumed from the work
    plan's "Phase 6 needs Phase 4 and Phase 2.5" line.**
- **Entry points Phase 6 will connect to, and what it varies**:
  - **Sobol/SALib (continuous parameters, work plan 6.2, methodology
    Section 8.1)**: `age_factor.py`'s named rate constants
    (`COAL_DECAY_RATE`, `WIND_RELATIVE_RATE`, `HYDRO_RETENTION_RATE`;
    `SOLAR_RETENTION_RATE`/`COAL_OVERHAUL_CYCLE_YEARS`/
    `COAL_OVERHAUL_RECOVERY` flagged, no literature range on record);
    `normalization.UPPER_TAIL_PADDING_FRACTION`; the Tier 3 RiskBand
    percentile-cut thresholds computed inside `risk_bands.
    percentile_band_cuts`/`classify_hazard` (the operative cuts are the
    non-diagnostic percentiles named in `risk_bands.THRESHOLD_REGISTRY`'s
    `percentiles` field per hazard/bucket).
  - **Scenario discovery / one-at-a-time (discrete parameters, work plan
    6.3, methodology Section 8.2)**: `hazard_scope.APPLICABLE_HAZARDS`
    (per-bucket hazard inclusion/exclusion); the PSAE cut points, now a
    concrete target -- `psae.classify_psae_fraction`'s inline `1.0`/`0.5`/
    `0.0` comparisons (not yet named constants, unlike every other
    perturbable parameter in this mapping, which are all named module-level
    constants); `correlation_gate.GATE_THRESHOLD`; `normalization.
    SKEWNESS_NORMAL_THRESHOLD` (discontinuous effect on transform
    selection, grouped here per `PHASE6_DESIGN.md` Section 2.5's
    reasoning, not with Sobol).
  - **Output statistic(s)**: methodology Section 8.1 says only "the
    summary statistic of interest" for Sobol (does not name `Risk_i,h`,
    `PSAE_i`, or both); Section 8.2 explicitly names "the resulting change
    in the distribution of PSAE/RiskBand outcomes" for the OAT analysis --
    resolved for 8.2, **not resolved for 8.1**. See open item below.
- **Items registered here (six total; the first four are `PHASE6_DESIGN.md`'s
  own Section 5 list, restated here as this project's open-decision record
  rather than left standing only in an untracked draft; items 5-6 are new,
  found in this entry). Update (2026-09-14, same day): items 1 and 2, and
  sub-items 4(a)/4(b), are now CLOSED (appended in place below, original
  open-item text left unedited per this file's append-only convention for
  reopened/updated entries). Items 3, 4(c), 5, and 6 remain open.**
  1. **Distribution family per perturbed parameter.** Neither
     `PHASE6_DESIGN.md` nor methodology Section 8 states what probability
     distribution each Sobol/Monte-Carlo-perturbed parameter is drawn
     from within its stated range -- only the range itself is given (e.g.
     coal decay rate 0.0019-0.0044/yr). The retired `monte_carlo.py` used
     `rng.uniform` for every one of its (now-retired) perturbed parameters
     (`monte_carlo.py:190-199`), but that precedent covers a different,
     superseded parameter set (thermal water/heat weight ratio,
     `EventMultiplier`'s `k`) and was never re-confirmed for the age_factor
     rates, RiskBand percentile cuts, or tail-padding fraction Phase 6
     actually needs. For the Sobol portion specifically, SALib's sampler
     supports a per-parameter `dists` argument (uniform is only its
     default, not a requirement) -- so "uniform for everything" is an
     available choice, not an already-made one.
     - **Closed (2026-09-14).** Default distribution for any perturbed
       parameter that has no better-sourced prior (a literature-cited
       distribution shape, if one exists for a specific parameter, takes
       precedence over this default and is not overridden by it): **uniform,
       ±20% around that parameter's current nominal value** (e.g. for
       `COAL_DECAY_RATE = 0.0025`/yr, the default draw range is
       `[0.002, 0.003]`, not the literature-backed `[0.0019, 0.0044]`
       already on record for that specific parameter -- the ±20% default
       applies only where no such literature range exists). This mirrors
       the retired `monte_carlo.py`'s own choice of `rng.uniform` as the
       sampling family (`monte_carlo.py:190-199`), extended with an
       explicit, symmetric width where the old module simply hardcoded a
       literature-sourced range per parameter and had no need for a
       general-purpose default. **Binding manuscript note**: any parameter
       perturbed under this ±20%-uniform default (as opposed to a
       literature-cited range) must be reported in the manuscript's
       limitations/methods text as a Tier 3, author-declared engineering
       default -- never presented as a calibrated or literature-backed
       distribution. This decision does not by itself enumerate every
       parameter this default applies to; `SOLAR_RETENTION_RATE` and
       `COAL_OVERHAUL_CYCLE_YEARS`/`COAL_OVERHAUL_RECOVERY` below are
       closed under it explicitly, as named applications, not the full set.
  2. **Monte Carlo N / convergence procedure (work plan 6.1).**
     Methodology Section 8.1 says only "N increased substantially above
     the current 1000, final value set by measured convergence of the
     summary statistic of interest" -- it does not specify a procedure.
     `PHASE6_DESIGN.md` Section 4.1 proposes a concrete doubling-sequence
     stabilization procedure (1000/2000/4000/8000/16000, <1% point-estimate
     tolerance, <5% CI-half-width tolerance, confirmed by one further
     doubling) -- this is that document's own proposal, not a sourced
     methodology requirement, and is one of the things a reader could
     mistake for already-decided if `PHASE6_DESIGN.md` is read as approved
     rather than as a draft (see the assessment above).
     - **Closed (2026-09-14).** `PHASE6_DESIGN.md` Section 4.1's proposed
       procedure is adopted as the actual Phase 6.1 convergence procedure,
       cited as its source: run at `N = 1000, 2000, 4000, 8000, 16000`
       (doubling from the current legacy value); at each `N`, record the
       point estimate and its 95% percentile CI (2.5/97.5); declare
       convergence at the smallest `N` where the point estimate's relative
       change from the previous `N` is `< 1%` **and** the 95% CI
       half-width's relative change from the previous `N` is `< 5%`;
       confirm by requiring the *next* doubling beyond that point to also
       satisfy both criteria before accepting it as converged (guards
       against a single-doubling fluke); report the Monte Carlo standard
       error (`SE = sample_std / sqrt(N)`) at the converged `N` as a
       secondary, corroborating statistic, never the primary criterion.
       Reference: `docs/rework/PHASE6_DESIGN.md` Section 4.1 (2026-09-14
       draft, this closure is what promotes that section from proposal to
       adopted procedure).
  3. **Seed/reproducibility and RNG granularity for the new parameter
     set.** `PHASE6_DESIGN.md` Section 3 already states this explicitly as
     unresolved (not this entry's own finding, restated here so it is not
     left standing only in the untracked draft): whether Phase 6's RNG
     streams are keyed per-country or per-country-scenario has no
     author-confirmed answer for the current (post-CCRS) parameter set --
     the old per-country approval was scoped to the retired
     `EventMultiplier`/bucket-weight parameters, not to age_factor rates or
     RiskBand percentile cuts. Whether `config.RANDOM_SEED` (the constant
     the retired module keyed off) is reused for Phase 6, or a new seed
     constant is introduced, is also not stated anywhere.
  4. **Which continuous parameters actually enter the Sobol dimension
     count `D`, and how finely the RiskBand percentile-cut family is
     grouped.** Three sub-points, all from `PHASE6_DESIGN.md` Sections 1.1
     -1.3/5, restated here: (a) `SOLAR_RETENTION_RATE`'s perturbation range
     has no cited source (the 0.7%/yr point value is sourced, no range is);
     (b) `COAL_OVERHAUL_CYCLE_YEARS`/`COAL_OVERHAUL_RECOVERY` are already
     logged elsewhere in this file as "ASSUMED... a modelling premise, not
     values taken from" their cited sources -- a perturbation range for an
     already-assumed point value would be an assumption stacked on an
     assumption, not decided here; (c) whether the RiskBand percentile-cut
     Sobol dimension is grouped one-per-hazard-family or one-per-hazard
     changes `D` from 2 to 6 for that family alone, directly changing the
     Saltelli evaluation budget (`N_0 * (2D + 2)`).
     - **(a) SOLAR_RETENTION_RATE -- Closed (2026-09-14).** Perturbation
       range is the item 1 default: **uniform, ±20% around the current
       nominal `SOLAR_RETENTION_RATE = 0.007`/yr**, i.e. `[0.0056,
       0.0084]`. No literature source backs this range (the 0.7%/yr point
       value is sourced -- Deline et al. 2020/2024, Boretti & Castellotto
       2024 -- a range around it is not, per this file's original
       `age_factor` entries). **Documented as a declared limitation**: the
       manuscript must state this range is a Tier 3, author-declared
       engineering default (item 1's binding note), not a literature-cited
       uncertainty band, wherever `SOLAR_RETENTION_RATE`'s Sobol result is
       reported.
     - **(b) COAL_OVERHAUL_CYCLE_YEARS / COAL_OVERHAUL_RECOVERY --
       Closed (2026-09-14).** Both enter the Sobol dimension count, each
       perturbed under the item 1 default around their current **ASSUMED**
       nominal values: `COAL_OVERHAUL_CYCLE_YEARS = 5`yr -> `[4, 6]`yr;
       `COAL_OVERHAUL_RECOVERY = 0.70` -> `[0.56, 0.84]`. Both point values
       are themselves already logged as "ASSUMED... a modelling premise,
       not values taken from" Kim & Moon (2012) or Sagaf (2020) (this
       file, age_factor final entry; `docs/LIMITATIONS.md`, "GEM
       retrofit/repowering field absent") -- this closure perturbs an
       already-assumed point, it does not newly assume one. **Binding
       note, not optional**: if the Sobol run finds a high sensitivity
       index (`S1`/`ST`) for either `COAL_OVERHAUL_CYCLE_YEARS` or
       `COAL_OVERHAUL_RECOVERY`, the final report **must** cite that the
       underlying parameter is an ASSUMED value (no real overhaul-history
       source exists for any GEM-tracked plant) at the point that finding
       is presented -- a high sensitivity index for this parameter is
       never to be presented as a confirmed empirical finding about coal
       plant behavior; it is a finding about how sensitive the model's
       output is to an admittedly unsourced modelling premise, and the
       distinction must survive into the manuscript text, not only into
       this decisions log.
     - **(c) RiskBand percentile-cut Sobol dimension grouping -- still
       open, not addressed by this closure.** Whether that family is one
       dimension or six remains undecided; `D`'s exact final value still
       depends on this sub-item (see this file's "Phase 3.1 CCRS global
       Min-Max bounds... Reopened... Closed" entry's `D = 6` floor
       calculation, which already treats this as unresolved and additive).
  5. **Whether methodology Section 8.1's "FROZEN_BOUNDS percentile
     choices" names the RiskBand percentile-cut thresholds (Phase 3.2) or
     something else.** Confirmed as a genuine textual ambiguity in this
     entry, not invented by `PHASE6_DESIGN.md`: the methodology text
     itself (`GEAR_v3_methodology_nature_format.md:722-723`) says
     verbatim "FROZEN_BOUNDS percentile choices," but `risk_calculator.
     FROZEN_BOUNDS` (confirmed by direct read, `risk_calculator.py:344
     -363`) contains empirical pooled min/max values with no percentile
     trimming anywhere in their computation -- the only percentile-based
     continuous-parameter family that actually exists in the pipeline is
     `risk_bands.py`'s Tier 3 RiskBand classification cuts, a different,
     already-separately-named thing in the same methodology document
     (Section 4 vs. Section 4.2). `PHASE6_DESIGN.md`'s reading (the
     RiskBand cuts are what was meant) is stated there as "the most
     defensible reading... not a confirmed mapping." Not resolved here.
  6. **PSAE `psae_complete=False` rows' treatment in the sensitivity
     analysis -- not addressed anywhere, found in this entry.**
     `PHASE6_DESIGN.md` predates `psae.py`'s actual complete-case mechanic
     (this file's "Phase 4 (PSAE) input mapping... CLOSED, complete-case"
     entry, closed after `PHASE6_DESIGN.md` was written) and has no
     provision for it in its Section 2.2 PSAE-cut-point OAT design. Three
     plausible readings, none written down anywhere: (a) restrict every
     Phase 6 PSAE-based statistic to `psae_complete=True` rows only,
     silently narrowing the plant sample the sensitivity analysis actually
     covers; (b) treat an incomplete row's contribution to any aggregate
     statistic (e.g. capacity-weighted PSAE-band fraction) as itself
     missing/NaN, propagating the gap into the reported statistic rather
     than silently dropping the plant; (c) something else not yet
     articulated. This is the same category of gap the Phase 4 entry above
     closed for PSAE's own denominator -- unresolved here for how Phase 6
     consumes PSAE's output.
- Action taken here: mapping and gap identification only, per instruction
  -- no Monte Carlo/Sobol code was written, and none of the six items
  above is decided by this entry.
- References: `docs/rework/PHASE6_DESIGN.md` (full read, this entry);
  `docs/rework/GEAR_v3_work_plan.md`, "Phase 6: Sensitivity and
  uncertainty" and "Sequencing notes"; `docs/rework/
  GEAR_v3_methodology_nature_format.md` Section 8; `src/index/
  correlation_gate.py:181` (`GATE_THRESHOLD`); `data/outputs/tables/
  correlation_gate.csv` (real output, read directly in this entry);
  `src/index/age_factor.py:126-135`; `src/index/hazard_scope.py:107-112`
  (`APPLICABLE_HAZARDS`); `src/index/monte_carlo.py:143-199` (legacy RNG/N
  mechanics, not carried forward as-is); `src/index/normalization.py`
  (`UPPER_TAIL_PADDING_FRACTION`, `SKEWNESS_NORMAL_THRESHOLD`);
  `src/index/risk_bands.py` (`THRESHOLD_REGISTRY`,
  `percentile_band_cuts`); `src/index/psae.py` (commit `6b70a36`,
  `classify_psae_fraction`, `psae_complete`, `missing_hazards`); this
  file, "GEAR v3 Phase 2.5: correlation gate implemented and run",
  "...follow-up: Portugal/India... gate closed for all three countries",
  "Phase 4 (PSAE) input mapping... CLOSED, complete-case".
- Status: **Partially closed (2026-09-14).** Items 1 (distribution
  default), 2 (convergence procedure), 4(a) (`SOLAR_RETENTION_RATE`
  range), and 4(b) (`COAL_OVERHAUL_*` range + binding manuscript note) are
  **Closed** -- see the appended resolutions in place above. Items 3
  (seed/RNG granularity), 4(c) (percentile-cut dimension grouping), 5
  (`FROZEN_BOUNDS percentile choices` mapping -- separately closed in this
  file's "CCRS global Min-Max bounds... Reopened... Closed" entry, not
  reopened here), and 6 (PSAE `psae_complete=False` treatment) remain
  **Open**, awaiting the author's input before a Phase 6 implementation
  prompt is written. Not to be resolved by inference or by a future
  implementation task picking defaults silently. Phase 2.5's closure and
  the entry points/parameter inventory mapped above are confirmed and not
  reopened by this entry.

## [2026-09-14] GEAR v3: spei reclassified from LOG_TERMS to LIN_TERMS (Phase 3.3 correction)

- Decision: `spei` (Drought) moves from `risk_calculator.LOG_TERMS` to
  `risk_calculator.LIN_TERMS` -- `Tlin` (direct Min-Max), not `Tlog`
  (`-ln(1-x)`), is now applied to it. `FROZEN_BOUNDS["spei"]` is
  **unchanged**: raw, pre-transform bounds are transform-independent (this
  project's established convention, unaffected by which transform function
  is later applied to them) -- only the transform function changes.
- Why: `spei`'s `LOG_TERMS` membership was inherited unchanged from the
  retired CCRS design (`ws`/`heat`/`spei` were `LOG_TERMS` from Phase 1
  onward) and was never re-evaluated against this project's own empirical
  skewness check (`normalization.normality_check`,
  `SKEWNESS_NORMAL_THRESHOLD = 0.5`, Bulmer 1979) -- unlike `precip` and
  `wind`, both of which were classified from their own measured pooled
  skew (this file, "Phase 3.3 scope over `wind`: closed" and the `precip`
  wiring entries). This is a real divergence between code and
  already-published methodology text, not a hypothetical: the published
  article's own Supplementary Table S3 (already cited in this file, "CCRS
  global Min-Max bounds... Reopened... Closed") reports Drought (SPEI)'s
  `Transform` column as **`direct Min-Max`** for both GCMs -- skew 0.36
  (GFDL-ESM4) and 0.13 (MIROC6), both under the `|skew| <= 0.5` "fairly
  symmetrical" threshold that selects `direct_minmax` over
  `neg_log_minmax` per `normalization.py`'s own selection rule. This
  correction applies the same empirical-skew rule already applied to
  `precip`/`wind` to `spei` for the first time, rather than inventing a
  new rule; it makes `spei`'s treatment consistent with `precip` and
  `wind`, which were already classified from their own measured skew
  rather than an inherited default.
- Scope confirmed, not assumed: grepped `src/` for every `LOG_TERMS`/
  `LIN_TERMS`/`spei` occurrence before making this change.
  `risk_bands.py` classifies `spei` on its **raw** values via a Tier 3
  percentile `ThresholdSpec` (`risk_bands.py:234-235`), never reading
  `risk_calculator.LOG_TERMS`/`LIN_TERMS` at all -- unaffected by
  construction. `psae.py` does not import `risk_calculator` at all
  (confirmed by grep, no `risk_calculator`/`rc` import in the file) --
  zero exposure, direct or indirect. `correlation_gate.py` operates on raw
  sampled raster values for its correlation statistics and never
  references `LOG_TERMS`/`LIN_TERMS` -- also unaffected. The only module
  outside `risk_calculator.py` carrying prose naming `spei` as a
  `LOG_TERMS` member was `normalization.py`'s module docstring (a
  historical description of what Phase 3.3 applied on 2026-09-14, before
  this same-day correction) -- updated in place to state the current
  membership and cite this entry, not left to silently drift from the
  code.
- Test coverage: `tests/test_risk_calculator.py`,
  `test_spei_is_linear_not_log_given_its_empirical_skew` (mirrors
  `test_precip_is_linear_not_log_given_its_empirical_skew`'s pattern;
  asserts membership in `LIN_TERMS`/absence from `LOG_TERMS` AND pins the
  Table S3 skew values themselves against
  `normalization.SKEWNESS_NORMAL_THRESHOLD`, not just a tautological
  membership check) and `test_spei_frozen_bounds_unchanged_by_the_ln_
  terms_reclassification` (pins `FROZEN_BOUNDS["spei"]` byte-for-byte
  against its pre-change value). Full suite: 365/365 passing (365 = the
  363 previously reported passing, plus these 2 new tests), excluding the
  same three pre-existing, unrelated `ccrs_calculator`-import failures
  already logged in this file (`test_main.py`/`test_monte_carlo.py`/
  `test_visualization.py`).
- References: `src/index/risk_calculator.py:59-99,224-249,517-518`
  (module docstring, `LOG_TERMS`/`LIN_TERMS`, `transform_term` docstring);
  `src/index/normalization.py:17-25` (docstring correction);
  `src/index/risk_bands.py:234-235` (`spei`'s Tier 3 `ThresholdSpec`,
  raw-value, unaffected); `src/index/psae.py` (no `risk_calculator`
  import, confirmed by grep); `src/index/correlation_gate.py` (raw-value
  correlation only, no `LOG_TERMS`/`LIN_TERMS` reference); `tests/
  test_risk_calculator.py` (two new tests, above); this file, "CCRS
  global Min-Max bounds... Reopened... Closed" (Table S3's original
  citation into this repository) and "Phase 3.3 scope over `wind`:
  closed" (the `-ln(1-x)` mechanism `spei` no longer uses).
- Status: **Closed (2026-09-14).** `spei` is `LIN_TERMS`; `FROZEN_BOUNDS`
  untouched; `risk_bands.py`/`psae.py`/`correlation_gate.py` confirmed
  unaffected, not merely assumed unaffected from the dependency graph;
  full test suite green.

## [2026-09-14] GEAR v3 Phase 6: partial-recomputation pipeline (raster caching + perturbed-chain recompute)

- Decision: `src/index/sensitivity_recompute.py` implements
  `PHASE6_DESIGN.md` Section 4.2's proposed architecture -- raster I/O and
  hazard-value sampling done ONCE and cached, the perturbation-sensitive
  chain (`age_factor` -> `Risk_i,h`, and RiskBand percentile cuts ->
  `RiskBand_i,h` -> `PSAE_i`) recomputed per draw from that cache -- so a
  future Sobol/Monte Carlo driver (not built here, out of this task's
  scope) does not re-read a single raster per draw. This task does not run
  Sobol, does not sample from SALib, and does not resolve any of Phase 6's
  three still-open items (RNG granularity, RiskBand percentile-cut
  dimension grouping, `psae_complete=False` treatment) -- those remain open
  exactly as this file's "Phase 6 (Sensitivity/uncertainty) input mapping"
  entry left them.
- Why: a naive "call `risk_calculator.compute_risk()` fully per Saltelli
  draw" approach was measured this session at ~29.7s/draw (3 countries,
  both GCMs) -- projecting to ~77 days at `D=6`, `N_0=16000`
  (`N_0*(2D+2) = 224000` evaluations, `PHASE6_DESIGN.md` Section 4.2's
  proposed Saltelli budget). Not viable. The expensive step is raster I/O +
  nearest-pixel sampling, which does not depend on any Sobol/Monte-Carlo
  parameter this project has identified (`PHASE6_DESIGN.md` Section 1) --
  raw hazard values sampled from a raster are the same regardless of
  `age_factor` rates or RiskBand percentile-cut choices.
- Architecture (module docstring has the full rationale):
  - `precompute(models=None) -> PrecomputedInputs`: runs
    `risk_calculator.sample_terms(model)` and
    `risk_bands.sample_hazard_terms(model)` ONCE per configured GCM (kept
    as two separate caches, not unified -- the two production sampling
    functions already exist independently with different missing-raster
    fallback behaviour; reconciling them is out of this task's scope), plus
    plant attributes for `age_factor`.
  - `recompute_risk_by_hazard(pre, model, bounds=None, rate_overrides=None)`:
    `risk_calculator.compute_risk_by_hazard`'s exact arithmetic
    (`transform_term`, `exposure_capacity_mw`, `risk_i_h`, `_term_bounds`,
    called directly, not reimplemented), fed from the cache.
  - `recompute_risk_bands(pre, model, percentile_overrides=None)`:
    `risk_bands.percentile_band_cuts`/`_bandize`/`classify_hazard` (called
    directly), fed from the cache; only Tier 3 percentile specs are
    perturbable (Section 1.2's named Sobol candidate), Tier 1
    absolute/binary cutoffs are not (not in scope per Section 1).
  - `psae.compute_psae` is called unmodified on the recomputed
    `RiskBandTable` -- zero duplication of any of the three modules'
    production logic.
  - The one necessary exception, not a violation of "call the existing
    function, don't duplicate it": `age_factor.age_factor()` is a scalar,
    per-row function that reads its rate constants from MODULE-LEVEL
    GLOBALS, not parameters, so it cannot be called with a perturbed rate
    without either monkeypatching module globals (not draw-parallel-safe)
    or a vectorised mirror. `retention_vector`/`age_factor_vector` follow
    the exact precedent the retired `monte_carlo.py` already established
    for this situation (its own `_retention_vector`/`_coal_retention_vec`,
    cross-checked against `age_factor.compute_age_factors()` row for row) --
    `monte_carlo.py` itself is not imported (it is currently broken,
    retired `ccrs_calculator` import, pre-existing and unrelated).
- Correctness verified FIRST, against real data, before any speed claim
  (task requirement, not optional): with every override omitted (nominal
  draw), `tests/test_sensitivity_recompute.py` confirms, over the real
  processed rasters and validated-plant CSVs:
  - `age_factor_vector(pre.attrs)` == `age_factor.compute_age_factors()`'s
    `age_factor` column, **exactly** (max abs diff `0.0`, not just within
    tolerance).
  - `recompute_risk_by_hazard(pre, model)` == `risk_calculator.
    compute_risk_by_hazard(model)`, `np.allclose` on `hazard_i_h`/
    `exposure_mw`/`age_factor`/`risk_i_h`, same 226,968 rows, same columns.
  - `recompute_risk_bands(pre, model)` == `risk_bands.
    compute_risk_bands(model)`, same 88,116 rows, identical `raw_value`,
    identical `risk_band` labels row-for-row, identical `percentile_cuts`
    (`band_cuts` and `all_cuts`) for every Tier 3 (hazard, bucket).
  - `psae.compute_psae` on the recomputed `RiskBandTable` == `psae.
    compute_psae` on the production `RiskBandTable`, identical `psae`/
    `psae_label`/`psae_complete` per row.
  - A perturbed draw (rates x3, percentile cuts shifted +10 points)
    measurably changes both `Risk_i,h` and `RiskBand_i,h` output -- guards
    against a pipeline that silently ignored its own override arguments.
  16 tests, all passing. Full project suite: 381/381 (365 previously
  reported + 16 new), same three pre-existing unrelated
  `ccrs_calculator`-import failures excluded as before.
- Real measured per-draw cost (not projected -- task requirement): 100 real
  draws, one GCM, both chains (`sensitivity_recompute.time_n_draws`,
  small illustrative jitter on every perturbable parameter, NOT a real
  Sobol/SALib sample -- picking real perturbation ranges is Phase 6.2's
  job, still open): **mean 8.27s/draw** (median 8.23s, min 8.12s, max
  9.07s, n=100). A further 20 real draws at the naive baseline's own scope
  (3 countries, both GCMs, nominal parameters) measured **mean 16.42s/draw**
  (16.11-17.81s range, n=20) against the ~29.7s/draw naive baseline --
  **a 1.81x real speedup**, projecting `D=6`/`N_0=16000` from ~77 days to
  **~42.6 days**. Still not viable for a real Sobol run.
- **Honest finding, not buried in the topline number: the raster-caching
  fix itself worked exactly as designed, but a DIFFERENT, pre-existing
  bottleneck this task was explicitly scoped not to touch now dominates.**
  `recompute_risk_by_hazard` + `recompute_risk_bands` together cost
  ~0.27s/model (0.137s + 0.133s, measured) -- **~110x faster** than the
  ~14.85s/model raster-sampling half of the naive baseline (29.7s / 2
  models) they replace. That part of this task's goal is fully achieved.
  But `psae.compute_psae` -- called unmodified, per this task's explicit
  instruction not to reimplement it -- costs **~7.9s per call on its own**
  (measured directly, `tests/test_sensitivity_recompute.py`'s timing probe
  and the `time_n_draws` breakdown), because its own implementation is a
  Python-level `groupby` + per-group `dict(zip(...))` loop over ~32,424
  (plant x water_scenario) groups (`psae.py:161-188`), not vectorised. At
  two GCMs this alone is ~15.8s of the measured 16.42s/draw total -- **96%
  of the remaining cost**, and the reason the real speedup (1.81x) is far
  short of what raster-caching alone would suggest. Fixing this is a
  genuinely separate task (vectorising `psae.compute_psae`, or accepting a
  Python loop at Sobol's evaluation count), explicitly out of this task's
  scope (instruction: do not inline/reimplement `psae.py`'s logic here) --
  **flagged as a new open item, not resolved by this entry**: Phase 6.2
  cannot be practically run against the current `psae.compute_psae`
  without a follow-up performance task on that function specifically, on
  top of (not instead of) the raster-caching fix this entry closes.
- Scope confirmed: this entry's module does not implement Sobol sampling,
  SALib integration, or any of Phase 6's three still-open items -- see
  this file's "Phase 6 (Sensitivity/uncertainty) input mapping" entry,
  unchanged and still open on those three points.
- References: `docs/rework/PHASE6_DESIGN.md` Section 4.2 (the proposed
  architecture this entry implements) and Section 1 (the parameter
  inventory `rate_overrides`/`percentile_overrides` are shaped against);
  `src/index/sensitivity_recompute.py` (new module, full docstring);
  `tests/test_sensitivity_recompute.py` (16 tests); `src/index/
  risk_calculator.py` (`sample_terms`, `compute_risk_by_hazard`,
  `transform_term`, `_term_bounds`, called not duplicated); `src/index/
  risk_bands.py` (`sample_hazard_terms`, `percentile_band_cuts`,
  `_bandize`, `classify_hazard`, `THRESHOLD_REGISTRY`, called not
  duplicated); `src/index/psae.py:161-188` (`compute_psae`'s groupby loop,
  the newly identified bottleneck); `src/index/age_factor.py` (retention
  curve constants/source functions `retention_vector` mirrors); this file,
  "Phase 6 (Sensitivity/uncertainty) input mapping" (the three items this
  entry does not resolve).
- Status: **Closed (2026-09-14) for this task's scope** (raster-caching
  recomputation pipeline, correctness-verified, real speedup measured).
  **New item opened, not closed**: `psae.compute_psae`'s own per-draw cost
  (~7.9s/call) is now the dominant remaining bottleneck and must be
  addressed before a real Phase 6.2 Sobol run is practically viable -- not
  attempted here, per this task's explicit scope.

## [2026-09-14] GEAR v3 Phase 5: contextual validator layer (broad-impact only, PARTIAL)

- Decision: `src/index/contextual_validators.py` implements the two-class,
  three-state validator taxonomy Methods Section 7 already specifies --
  `Corroborated`/`No Record`/`Not Applicable`, post-2000, per applicable
  hazard per asset -- for the **broad-impact class (Section 7.2, EM-DAT)
  only**. The **physical-occurrence class (Section 7.1) is NOT
  implemented**: grep-confirmed zero IBTrACS/FIRMS (or any other
  physical-occurrence source) acquisition code or data anywhere in this
  project (`grep -rl "IBTrACS\|ibtracs"` and the FIRMS equivalent both
  return nothing under `src/`; the only substring hits, in
  `tests/test_extreme_wind_processor.py`/`tests/test_visualization.py`, are
  "con**firms**" false positives, not `FIRMS` references). Per the standing
  rule against acquiring new data without author confirmation, and per this
  task's own explicit instruction, no acquisition was attempted --
  `compute_physical_occurrence_validation()` exists as a named, explicit
  `NotImplementedError` stop point, not a silent gap. **This is a PARTIAL
  Phase 5 implementation, not a closed phase**, per this project's own
  partial-closure convention -- labelled as such in the module docstring
  and here, not reported as done.
- Data-source availability, checked before writing any code (per this
  task's explicit instruction, not assumed):
  - **EM-DAT (broad-impact, Section 7.2)**: already acquired for all three
    countries, CCRS-era work (`src/downloaders/emdat_downloader.py`,
    `data/raw/validation/emdat_{country}.csv`, confirmed present on disk).
    Reused as-is, no new acquisition.
  - **IBTrACS/FIRMS/landslide/lightning (physical-occurrence, Section
    7.1)**: **not acquired anywhere in this project.** Author decision
    needed on which source(s) to acquire (IBTrACS for cyclone/storm-surge
    is the only one Section 7.1 names with a specific dataset; FIRMS,
    landslide, and lightning sources are named generically, "where
    available and physically applicable") before this class can be
    implemented.
- Not the retired `src/index/emdat_validation.py` (confirmed not reusable
  as-is, exactly as this task's brief stated): that module is a polygon-
  level Mann-Whitney diagnostic (admin-1 polygons with vs. without a
  geocoded event, hazard-raster zonal mean compared between the two
  groups) -- a genuinely different design from a per-asset three-state
  output, and currently broken besides (imports the retired
  `ccrs_calculator`, cannot even be imported). Its `GADM Admin Units`
  JSON-parsing logic and documented EM-DAT coverage caveats (point
  Latitude/Longitude: 5.3-12.1% event coverage, unusable for a per-asset
  radius search; structured `GADM Admin Units`: 50.3-52.6% coverage,
  enough for an admin-1-polygon overlay) are reproduced (not imported --
  cannot be) in the new module as the established, data-quality-driven
  operationalization of Section 7.3's "location/radius" phrase for this
  specific source. The ~47-50% of EM-DAT events with no structured
  geocoding at all remain excluded from every validator state -- the same
  real, non-random coverage gap (better-documented/urban disasters
  plausibly over-represented in the geocoded half), inherited unchanged,
  not re-investigated by this task.
- **Disaster-type -> hazard-term mapping: inherited UNCHANGED from the
  retired module, NOT re-derived -- flagged as an open item, not decided
  here.** `Extreme temperature -> heat`, `Drought -> spei`, `Flood -> ws`
  (approved by Douglas, 2026-09-04; `Flood -> ws` is the retired module's
  own acknowledged poor match -- water STRESS, not excess water -- kept
  only because no better v3 term existed at approval time). `Storm` stays
  excluded. v3 now has two hazard terms that did not exist when this
  mapping was approved and that plausibly fit better: `precip` (Extreme
  Precipitation, days/year exceeding local P95 wet-day threshold -- a much
  more direct "Flood" proxy than water stress) and `wind` (a real "Storm"
  target, wired in 2026-09-14, this file's "GEAR v3 wind Risk_i,h
  integration" entry). **Open item for author confirmation**: whether to
  extend the mapping to `Storm -> wind` and/or replace or supplement
  `Flood -> ws` with `Flood -> precip`. Not decided or silently extended by
  this task -- re-deriving a disaster-type/hazard-term mapping is a
  methodology judgment call Section 7 does not specify and this task's
  brief did not ask for.
- Architecture (module docstring has the full detail): `_load_admin1_
  boundaries`/`_resolve_admin1_gid`/`_admin1_gids_from_cell` (GADM parsing,
  reproduced from the retired module), `load_geocoded_emdat_events`
  (per-country EM-DAT events resolved to admin-1 GIDs + start year, no
  filter applied), `_plants_with_admin1` (point-in-polygon spatial join,
  `risk_calculator.load_plants` x GADM admin-1 layer, `gid_1=None` kept
  explicit for a spatial-join miss rather than dropped or guessed),
  `compute_broad_impact_validation` (the three-state assignment: `Not
  Applicable` for hazard terms with no EM-DAT mapping OR an unmatched
  plant; `Corroborated`/`No Record` by counting post-2000 geocoded events
  in the plant's `gid_1`). "Applicable hazard" (Section 7.3's phrase) is
  operationalized as `hazard_scope.APPLICABLE_HAZARDS[bucket]` -- the same
  H_b set RiskBand/PSAE already use, not a separately invented set.
- Read-only guarantee (task requirement, explicit, not just claimed):
  `tests/test_contextual_validators.py` computes
  `risk_calculator.compute_risk_by_hazard`, `risk_bands.
  compute_risk_bands`, and `psae.compute_psae` BEFORE running
  `contextual_validators.compute_contextual_validation`, runs it, then
  recomputes all three and asserts frame-level equality (numeric columns
  `np.allclose`, categorical columns exact) -- plus a structural test
  confirming the module's own source never imports `psae`/`risk_bands` at
  all. All three read-only tests pass. The module also never imports
  `risk_calculator.compute_risk_by_hazard`/`compute_risk`/`transform_term`
  -- only `load_plants` (a pure read) and `PLANT_UID`.
- Correctness verified against real data (all three countries): 29,372
  rows total (Brazil 13,961, India 14,431, Portugal 980 -- 5 hazards/hydro,
  3/thermal, 1/wind, 3/solar per plant, per `hazard_scope.
  APPLICABLE_HAZARDS`); state counts Brazil
  Not-Applicable/Corroborated/No-Record = 8971/3055/1935, India
  9244/5020/167, Portugal 698/267/15. 14 plants across all three countries
  had no admin-1 spatial-join match (`gid_1=None`) -- confirmed all their
  rows are `Not Applicable`, not silently mis-stated. Every row for a
  hazard term with no EM-DAT mapping (`precip`/`wind`/`sv`/`iv`) confirmed
  `Not Applicable` regardless of location.
- Test coverage: `tests/test_contextual_validators.py`, 19 tests -- pure
  GADM-GID parsing (no I/O, 6 tests), three-state assignment logic against
  real data (10 tests), the three explicit read-only guarantee tests, one
  structural import guard. Full project suite: 400/400 (381 previously
  reported + 19 new), same three pre-existing unrelated
  `ccrs_calculator`-import failures excluded as before.
- References: `docs/rework/GEAR_v3_methodology_nature_format.md` Section 7
  (7.1/7.2/7.3, read in full before writing code, per instruction); `docs/
  rework/GEAR_v3_work_plan.md` Phase 5; `src/index/contextual_validators.py`
  (new module, full docstring); `tests/test_contextual_validators.py` (19
  tests); `src/index/emdat_validation.py` (retired, not imported, GADM-
  parsing logic reproduced); `src/downloaders/emdat_downloader.py`
  (existing EM-DAT acquisition, reused); `src/index/hazard_scope.py`
  (`APPLICABLE_HAZARDS`, reused as the "applicable hazard" set); this file,
  "GEAR v3 wind Risk_i,h integration" (`wind`'s wiring date, relevant to
  the open disaster-type-mapping item above).
- Status: **PARTIAL, not closed.** Broad-impact class (Section 7.2):
  implemented, correctness- and read-only-verified against real data.
  Physical-occurrence class (Section 7.1): **not implemented, no acquired
  source** -- explicit `NotImplementedError`, author decision needed on
  which source(s) to acquire before it can proceed. Disaster-type/hazard-
  term mapping extension (`Storm -> wind`, `Flood -> precip`): **open,
  author confirmation needed**, not decided by this entry.
