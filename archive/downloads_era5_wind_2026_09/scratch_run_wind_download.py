import logging, json
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
from src.config import COUNTRIES
from src.processors import extreme_wind_processor as ew

result = {}
for country in COUNTRIES:
    print(f"=== {country} ===", flush=True)
    result[country] = ew.ensure_all_years_annual_max(country)
    ok = sum(1 for r in result[country].values() if r["success"])
    print(f"{country}: {ok}/{len(result[country])} years OK", flush=True)

with open("logs/era5_wind_reduce_result.json", "w") as f:
    json.dump(result, f, indent=2, default=str)
print("ALL DONE", flush=True)
