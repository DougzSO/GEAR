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

## [2026-09-03] Heat stress raw layer is a passthrough of the downloader output
- Decision: `heat_stress_processor.raw_raster_path()` returns `cds_tasmax_downloader.resampled_raster_path()` — the raw heat layer is the `extreme_heat_days_*_1km.tif` the downloader already wrote, not a new file. The processor references it, never copies or recomputes it.
- Reason: Ported. Unlike water, the raw physical value for heat (days/year with tasmax > 40 C) already exists on disk on the exact grid the processor normalises. Unit: `days_per_year_with_tasmax_gt_40C`.
- Status: active

## [2026-09-03] Hazard combination — linear sum retained, interaction term rejected
- Scope: index architecture / open question (ARCHITECTURE.md Section 6), not a resolved decision. The index layer is not built yet; this records a direction and a rejected alternative, not an implemented result.
- Decision: `Risk_i` keeps the linear form `w_water · WaterStress_i + w_heat · HeatStress_i`. No non-linear interaction term between water and heat is introduced.
- Reason: `analysis/normalization_diagnostics.md` task 4 found plant-level Spearman correlations between the two hazards (3-scenario pooled pairing: ssp126/opt + ssp585/pes + ssp370/bau) of about -0.45 (Brazil), +0.08 (Portugal), +0.41 (India) — India moderately compounding (the same plants tend to face both), Brazil moderately offsetting, Portugal largely independent. These reflect geographic co-location of arid/hot regions, not a documented physical mechanism by which water stress amplifies heat sensitivity (or vice versa) for a given power plant. Fitting an interaction term to this sample-specific correlation would be a category error — mistaking spatial correlation for causal compounding — and would either break cross-country comparability (if the term were country-specific) or ignore the observed country differences (if fixed).
- Status: active — open to revision only if literature-based (not sample-derived) evidence of physical compound risk for energy infrastructure is found during the methodology revisit.
- Companion note: per-hazard decomposition (water-only and heat-only contribution to `Risk_i`) will be considered as an auxiliary diagnostic output alongside the combined SCI, not as a replacement for it — final decision deferred to the Section 5/6 methodology revisit.
- Note: this entry may be revisited if `Risk_i`'s formulation changes under the unified climate-risk-score redesign (see forthcoming DECISIONS.md entry).

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
- Status: active

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
