# ERA5 Wind Download Scripts — Archived 2026-09-16

Estes scripts foram usados para download único dos dados ERA5 extreme wind
gust em setembro de 2026. Download confirmado completo em
`data/raw/climate/era5_wind/{Brazil,India,Portugal}/` (30 anos cada,
1991-2020, `BASELINE_YEARS` de `era5_wind_downloader.py`) e nos rasters
processados `data/processed/climate/extreme_wind_gust_raw_{país}_{native,1km}.tif`.

**Motivo do arquivamento:** tarefa de download concluída, scripts não
necessários para o pipeline de produção (dados já persistidos em disco).

**Se precisar re-download:** usar
`src/downloaders/era5_wind_downloader.py` (módulo oficial integrado,
última atualização 2026-09-13).

**Arquivos arquivados:**
- `scratch_run_concurrent.py`
- `scratch_run_india_download.py`
- `scratch_run_india_highconcurrency.py`
- `scratch_run_wind_download.py`

Última modificação original: 2026-09-15 (commit `417a500`).
