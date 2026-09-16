import logging, json
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
from src.processors import extreme_wind_processor as ew

result = ew.ensure_all_years_annual_max("India")
ok = sum(1 for r in result.values() if r["success"])
print(f"India: {ok}/{len(result)} years OK", flush=True)
with open("logs/era5_wind_india_result.json", "w") as f:
    json.dump(result, f, indent=2, default=str)
print("INDIA DONE", flush=True)
