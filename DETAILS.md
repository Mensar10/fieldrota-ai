# FieldRota-AI: technical details

The one-page write-up is in [README.md](README.md). This page has the longer version: every region, the full test design, every result table and the limits.

> Research prototype. It does not give agronomic advice. Every number here is a model estimate.

## The problem
Five of the world's groundwater hotspots grow a lot of crops: the Konya Plain (Türkiye), Kansas (Ogallala aquifer), Punjab (India), California's Central Valley and La Mancha (Spain). In all five, farms pump aquifers faster than rain refills them. The order in which a farmer plants crops, the **rotation**, sets how much well water a field needs, how healthy its soil stays and how well it handles the extra hot days that are coming. Farmers need a plan for *their* field, starting from what is in it today, that still works as the climate warms.

## What we built
**FieldRota** is our web app (`app/`). Its first version (v1) uses NASA POWER and NASA NEX-GDDP-CMIP6 data and Çumra's 2027 planting rules. It scores every 3-year rotation once, with the **average** climate, and suggests the best one.

**FieldRota-AI** (`fieldrota_ai.py`, `FieldRota_AI.ipynb`) replaces that one-off scoring with a **learned planting policy**. A tabular **Q-learning** agent looks at the last two crops on the field each year, plus the decade (or whether last year was wet or dry), and picks the next crop for the farmer's goal: save water, healthy soil, or balanced.

* **How it learns:** trial and error in a field simulator. The simulator turns FieldRota's calibrated averages into year-by-year values using **real NASA POWER daily weather**:
  * water need scales with each season's FAO-56 ET₀
  * rain and well irrigation follow the real season
  * climate fit drops with the real number of days ≥ 35 °C in each crop's most heat-sensitive month
* **Future climate:** for 2026–2060, each year follows a CMIP6 model's trend toward its 2041–2060 values, plus the ups and downs of a real past year.
* **Rules:** every move must follow FieldRota's rules, checked year by year:
  * the crop must be on the region's list
  * any 3 years in a row hold 3 different crops
  * no fallow on irrigated land
  * Konya: no two high-water crops back to back
  * the sowing date may not overlap the previous harvest
* **Reward:** FieldRota's own yearly score: well water, climate fit and soil health, weighted by the goal.
* **In the app:** section 5 shows the AI's plan from 2027 to 2060, starting from the crops the farmer enters, plus how it did on data it never saw.

## How we tested it

| | Train | Pick the best of 3 training runs (validation) | Test (never seen) |
|---|---|---|---|
| Real weather | 1986–2008 | 2009–2014 | **2015–2025** |
| Climate models, 2026–2060 | ACCESS-CM2, EC-Earth3, MPI-ESM1-2-HR | MRI-ESM2-0 | **GFDL-ESM4, IPSL-CM6A-LR** (41 weather sequences each) |

We compare against:
* the **farmers' common rotation** in each region
* **FieldRota v1** (best fixed 3-year rotation, average climate)
* a **myopic** planner that only looks at the current year
* the **exact optimum** from dynamic programming on the expected score

## Results (5 regions × 3 goals)
All scores are FieldRota's 0–100 yearly score for the chosen goal, averaged over the test years. The numbers come from `results/summary_*.csv`, produced by `export_ai.py`.

**On 2 climate models it never saw (2026–2060), over 15 region × goal pairs:**
* FieldRota-AI reaches **99.5 % of the exact optimum** on average (lowest: 98.5 %).
* It scores **+46.7 points above the farmers' common rotation** on average.
* Against FieldRota v1 it is **−0.05 points** on average (range −1.0 to +1.5): the two methods agree.

**On real weather it never saw (2015–2025):**
* **+44.1 points** above the farmers' common rotation.
* **−0.55 points** against v1 (range −3.8 to +1.8).

**Well water with the "save water" goal (m³ per decare per year, 1 m³/da = 1 mm):**

| Region | Farmers' common rotation | FieldRota-AI | Change | 2015–2025 real weather (farmers → AI) |
|---|---|---|---|---|
| Konya, Türkiye (maize → wheat → sugar beet) | 518 | 271 | **−48 %** | 488 → 269 |
| Kansas, USA (maize → maize → soybean) | 579 | 387 | **−33 %** | 510 → 375 |
| Punjab, India (rice–wheat every year) | 1066 | 409 | **−62 %** | 813 → 206 |
| California, USA (maize → tomato → cotton) | 880 | 151 | **−83 %** | 874 → 110 |
| La Mancha, Spain (maize → maize → barley) | 613 | 213 | **−65 %** | 605 → 207 |

The middle columns are the average over 2026–2060 on the two unseen climate models. Our numbers rest on simulation; real savings would depend on prices, markets and each farm.

**Score with the "save water" goal on the unseen climate models (2026–2060):**

| Region | Farmers | Myopic | FieldRota v1 | **FieldRota-AI** | Exact optimum |
|---|---|---|---|---|---|
| Konya | 36.3 | 66.8 | 70.3 | **70.4** | 70.4 |
| Kansas | 13.0 | 44.5 | 44.1 | **44.5** | 44.7 |
| Punjab | −10.3 | 56.8 | 56.8 | **56.6** | 56.8 |
| California | 24.3 | 87.0 | 87.1 | **87.1** | 87.1 |
| La Mancha | 31.6 | 78.3 | 78.2 | **78.3** | 78.3 |

**What the AI changes as the climate warms:** in Kansas (balanced goal) it grows winter canola, sunflower and soybean until about 2035. After that it drops sunflower, whose climate fit falls with more hot days, and brings in wheat. That puts it 1.5 points above v1's fixed rotation on the unseen models.

## Where it fails (honest notes)
* **The AI is not clearly better than FieldRota v1.** In most region/goal pairs the learned policy and v1's exhaustive search land on almost the same plan. The best plan really is close to a fixed rotation, because the climate trend is slow compared with a 3-year cycle. The AI still adds three things:
  * it starts from the farmer's real field history, including crops that are now banned (Konya's sugar beet)
  * it plans to 2060 and switches crops when the decades warm (Kansas: sorghum out, wheat in)
  * it reaches almost the same answer as v1 by a completely different method, which makes the advice more trustworthy
* **Learning from noisy years costs a little.** Single weather years are noisy, so the learned policy is sometimes 1–3 points below v1 or the optimum. This happens most in the soil-goal runs and on Kansas's real 2015–2025 weather.
* **Looking ahead matters.** A myopic planner usually matches the AI, but in Konya (save-water goal) it drifts into rotations that hurt the soil.
* **Not modelled:**
  * crop yields (climate fit stands in for them)
  * prices (Konya income is shown, not optimised)
  * pests and diseases beyond the soil score
  * soil moisture carried between seasons
  * double cropping, except Punjab's crop pairs
  * farmers' costs
* **Data limits:** the climate data covers about 50 km. NASA POWER rain outside Konya was not checked against weather stations. Future years use a delta method (trend plus real-year anomalies), not daily CMIP6 weather, and only one scenario (SSP2-4.5).

## Run it
* **Notebook:** open `FieldRota_AI.ipynb` in Google Colab and set `REPO_URL` in the first cell to this repository, then *Run all* (about 5 minutes; set `RUN_ALL = True` to retrain every region, about 25 minutes). It downloads NASA POWER live and falls back to the saved copy in `data/weather/` if the API is down.
* **Retrain everything:** `python export_ai.py` writes `ai/<region>.json` and `results/summary_*.csv`; then `python tools/build_app.py` copies the policies into the app and rebuilds `app/index.html` from `tools/index.src.html`.
* **Web app:**
  * Double-click `app/index.html`: it works offline and even on its own, because the map libraries and all data are packed inside it. Keep the `app/` folder next to it for the zoomed satellite photos and for clicking fields on them.
  * Or serve the folder: `app/start_local_server.bat` on Windows, or `python -m http.server` inside `app/`.
  * Or switch on GitHub Pages for this repository and open `https://<user>.github.io/fieldrota-ai/app/`.

## Files
| Path | What it is |
|---|---|
| `fieldrota_ai.py` | simulator, rules, Q-learning, baselines, dynamic-programming optimum, evaluation |
| `FieldRota_AI.ipynb` | end-to-end notebook with all tests |
| `export_ai.py` | trains every region and goal, exports results for the app |
| `data/regions/*.json` | FieldRota region data (crops, calibrated water and climate numbers, rules, soil scores, CMIP6 runs) |
| `data/weather/*.csv.gz` | saved NASA POWER daily weather, 1985–2025 |
| `ai/*.json`, `results/*.csv` | trained policies and test results |
| `app/` | FieldRota web app with the new AI section (section 5); `index.html` carries its own data, `app/img_js/` serves the satellite photos offline |
| `tools/` | `patch_app.py` adds section 5 to the app (`index.src.html`); `build_app.py` packs data and libraries into `app/index.html` |

## Credits
* **Data:**
  * NASA POWER daily agroclimatology (power.larc.nasa.gov)
  * NASA NEX-GDDP-CMIP6, SSP2-4.5, 6 models, as processed in FieldRota
  * NASA HLS and ESA Sentinel-2 imagery in the app
  * FAO-56 (Allen et al., 1998) for ET₀ and crop coefficients
  * Çumra crop water use, TAGEM–DSİ (2017)
  * Çumra 2027 planting rules and support payments, Türkiye Ministry of Agriculture and Forestry
  * crop prices as listed in the app
* **Libraries:** NumPy, pandas, Matplotlib; D3 and topojson-client in the web app.
* **AI tools:** Claude (Anthropic) helped write and debug code and text. The team reviewed every part and can explain it.
* **Hackathon note:** all code was written during the hackathon (14–15 November 2026). The FieldRota idea is also being developed for NASA Space Apps Challenge 2026.

