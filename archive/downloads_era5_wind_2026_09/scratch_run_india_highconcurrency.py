import logging, json, sys
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
from src.processors import extreme_wind_processor as ew

def missing_years(country):
    return [y for y in ew.BASELINE_YEARS if not ew.annual_max_path(country, y).exists()]

max_workers = int(sys.argv[1]) if len(sys.argv) > 1 else 5

pairs = [("India", y) for y in missing_years("India")]
print(f"Remaining: {len(pairs)} India years -- {pairs[:5]}... max_workers={max_workers}", flush=True)

results = ew.ensure_years_concurrent(pairs, max_workers=max_workers)

ok = sum(1 for r in results.values() if r["success"])
print(f"{ok}/{len(results)} pairs OK", flush=True)
failed = {k: v for k, v in results.items() if not v["success"]}
if failed:
    print("FAILED:", failed, flush=True)

with open("logs/era5_wind_india_highconcurrency_result.json", "w") as f:
    json.dump({str(k): v for k, v in results.items()}, f, indent=2, default=str)
print("INDIA HIGH-CONCURRENCY RUN DONE", flush=True)
