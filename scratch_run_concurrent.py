import logging, json
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
from src.processors import extreme_wind_processor as ew

def missing_years(country):
    return [y for y in ew.BASELINE_YEARS if not ew.annual_max_path(country, y).exists()]

pairs = (
    [("Brazil", y) for y in missing_years("Brazil")]
    + [("Portugal", y) for y in missing_years("Portugal")]
    + [("India", y) for y in missing_years("India")]
)
print(f"Remaining: {len(pairs)} (country, year) pairs -- {pairs[:5]}...", flush=True)

results = ew.ensure_years_concurrent(pairs, max_workers=3)

ok = sum(1 for r in results.values() if r["success"])
print(f"{ok}/{len(results)} pairs OK", flush=True)
failed = {k: v for k, v in results.items() if not v["success"]}
if failed:
    print("FAILED:", failed, flush=True)

with open("logs/era5_wind_concurrent_result.json", "w") as f:
    json.dump({str(k): v for k, v in results.items()}, f, indent=2, default=str)
print("CONCURRENT RUN DONE", flush=True)
