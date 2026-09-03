# V6 — computable NAES/SCI denominator per country

Source files: `data/processed/assets/gem_validated_plants_{country}.csv` (Stage 1/2 output — GEM units already aggregated to plants, filtered to `Status == operating`). “Computable” = the plant has a usable coordinate **and** a `commissioning_year`, the two inputs a per-plant age/exposure score needs. Descriptive only.

| country | plants | total declared capacity_mw | plants w/o coord | plants w/o commissioning_year | capacity_mw w/o year | computable plants | computable capacity_mw | computable / total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Brazil | 5275 | 218,286.4 | 0 | 97 | 3,886.9 | 5178 | 214,399.5 | 0.9822 |
| Portugal | 450 | 21,802.8 | 0 | 11 | 89.0 | 439 | 21,713.8 | 0.9959 |
| India | 5083 | 483,110.5 | 0 | 494 | 20,131.8 | 4589 | 462,978.7 | 0.9583 |

Highest computable fraction: **Portugal 0.9959**. Lowest: **India 0.9583**. Spread: **3.76 percentage points**.

Every plant in all three tables has a coordinate (`plants w/o coord` = 0); the only limiter on the denominator is a missing `commissioning_year`.
