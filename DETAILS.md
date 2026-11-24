# FieldRota-AI: technical details

The one-page write-up is in [README.md](README.md). This page has the longer version: every region, the full test design, every result table and the limits.

> Research prototype. It does not give agronomic advice. Every number here is a model estimate.

## The problem
Five of the world's groundwater hotspots grow a lot of crops: the Konya Plain (Türkiye), Kansas (Ogallala aquifer), Punjab (India), California's Central Valley and La Mancha (Spain). In all five, farms pump aquifers faster than rain refills them. The order in which a farmer plants crops, the **rotation**, sets how much well water a field needs, how healthy its soil stays and how well it handles the extra hot days that are coming. Farmers need a plan for *their* field, starting from what is in it today, that still works as the climate warms.

## What we built
**FieldRota** is our web app (`app/`). Its first version (v1) uses NASA POWER and NASA NEX-GDDP-CMIP6 data and Çumra's 2027 planting rules. It scores every 3-year rotation once, with the **average** climate, and suggests the best one.

**FieldRota-AI** (`fieldrota_ai.py`, `FieldRota_AI.ipynb`) replaces that one-off scoring with a **learned planting policy**. A tabular **Q-learning** agent looks at the last two crops on the field each year and picks the next crop for the farmer's goal: save water, healthy soil, or balanced. We train two versions with the same simulator, rules and reward: a **real-weather agent** that also sees whether last year was wet or dry (trained on 1986–2008), and a **climate-model agent** that also sees the decade (trained on 2026–2060 futures). The app uses the climate-model agent.

* **How it learns:** trial and error in a field simulator. The simulator turns FieldRota's calibrated averages into year-by-year values using **real NASA POWER daily weather**:
  * water need scales with each season's FAO-56 ET₀
  * rain and well irrigation follow the real season
  * climate fit drops with the real number of days ≥ 35 °C in each crop's most heat-sensitive month
* **Future climate:** for 2026–2060, each year follows a CMIP6 model's trend toward its 2041–2060 values, plus the ups and downs of a real 1986–2025 year (the same 40 real years are used for every model).
* **Rules:** every move must follow FieldRota's rules, checked year by year:
  * the crop must be on the region's list
  * any 3 years in a row hold 3 different crops
  * no fallow on irrigated land
  * Konya: no two high-water crops back to back
  * the sowing date may not overlap the previous harvest
* **Reward:** FieldRota's own yearly score: well water, climate fit and soil health, weighted by the goal.
* **In the app:** section 5 shows the AI's plan from 2027 to 2060, starting from the crops the farmer enters, plus how both agents did on their test data.

## How we tested it

| | Train | Pick the best of 3 training runs (validation) | Test (never seen) |
|---|---|---|---|
| Real weather (real-weather agent) | 1986–2008 | 2009–2014 | **2015–2025** |
| Climate models, 2026–2060 (climate-model agent) | ACCESS-CM2, EC-Earth3, MPI-ESM1-2-HR | MRI-ESM2-0 | **GFDL-ESM4, IPSL-CM6A-LR** (40 weather sequences each) |

We compare against:
* the **farmers' common rotation** in each region
* **FieldRota v1** (best fixed 3-year rotation, average climate)
* a **myopic** planner that only looks at the current year
* the **exact optimum** from dynamic programming on the expected score

## Results (5 regions × 3 goals)
All scores are FieldRota's yearly score (up to 100; it can drop below 0 when a plan needs more well water than the region's thirstiest crop) for the chosen goal, averaged over the test years. The numbers come from `results/summary_*.csv`, produced by `export_ai.py`.

**On 2 climate models it never saw (2026–2060), over 15 region × goal pairs:**
* FieldRota-AI reaches **99.5 % of the exact optimum** on average (lowest: 98.5 %).
* It scores **+46.7 points above the farmers' common rotation** on average.
* Against FieldRota v1 it is **−0.05 points** on average (range −1.0 to +1.5): the two methods agree.

**On real weather it never saw (2015–2025):**
* **+44.1 points** above the farmers' common rotation.
* **−0.55 points** against v1 (range −3.7 to +1.8).

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

**What the AI changes as the climate warms:** in Kansas (balanced goal) it grows winter canola, sunflower and soybean until about 2035. After that it drops sunflower, whose climate fit falls with more hot days, and brings in wheat. That puts it 1.5 points above v1's fixed rotation on the unseen models (0.7 above v1's 2050s pick).

## Keep-my-crops mode (`keep_mode.py`)
Farmers rarely want to drop the crops they know. In this mode the agent's actions are limited to the farmer's own crops (today's common rotation, minus any crop the local rules ban) plus **one** extra crop. The extra crop is the one whose exact optimum is best on the **training** climate models, so the validation and test models stay unseen. Everything else follows the climate-model recipe above: 3 runs of 100,000 practice episodes on the 3 training models, the best run picked on MRI-ESM2-0, and the final test on GFDL-ESM4 and IPSL-CM6A-LR (40 weather sequences each), compared with the exact optimum for the same crop set. Goal: save water.

| Region | Kept | Added | Repeating plan | AI score = exact optimum | Well water, today → AI (m³/da/yr) |
|---|---|---|---|---|---|
| Konya | maize, wheat (sugar beet banned) | barley | barley → wheat → maize | 52.8 = 52.8 | 518 → 369 (−29 %) |
| La Mancha | maize, barley | pea | pea → maize → barley | 58.4 = 58.4 | 613 → 402 (−34 %) |
| Kansas | maize, soybean | canola | canola → maize → soybean | 28.7 = 28.7 | 579 → 495 (−15 %) |
| California | maize, tomato, cotton | chickpea | chickpea → tomato → maize (cotton dropped) | 49.7 = 49.7 | 880 → 575 (−35 %) |

Our presentation uses the Konya run with **vetch** fixed as the extra crop (`python keep_mode.py konya water fig`): vetch → wheat → maize, score 53.2 = exact optimum, 518 → 402 m³/da (−22 %). On the training models, which decide the extra crop, barley scores higher (53.1 vs 52.4); on the unseen test models vetch scores slightly higher (53.2 vs 52.8), while barley needs less well water. Punjab is left out because its common rotation is a single crop pair (rice–wheat) repeated every year. Results: `results/keep_mode.csv` and `results/keep/<region>_<goal>.json` (policy table, plan and the candidate extras with their training-model optimum).

## Where it falls short (honest notes)
The README explains, for each point, why it happens and how we plan to fix it.
* **The AI is not clearly better than FieldRota v1.** In most region/goal pairs the learned policy and v1's exhaustive search land on almost the same plan. The best plan really is close to a fixed rotation, because the climate trend is slow compared with a 3-year cycle. The AI still adds three things:
  * it starts from the farmer's real field history, including crops that are now banned (Konya's sugar beet)
  * it plans to 2060 and switches crops when the decades warm (Kansas, balanced goal: sunflower out, wheat in)
  * it reaches almost the same answer as v1 by a completely different method, which makes the advice more trustworthy
* **Learning from noisy years costs a little.** Single weather years are noisy, so the learned policy is sometimes 1–4 points below v1 or the optimum. This happens most in the soil-goal runs and on Kansas's real 2015–2025 weather.
* **Looking ahead matters.** A myopic planner usually matches the AI, but in Konya (save-water goal, 2026–2060) it drifts into rotations that hurt the soil (soil score 32 vs 84). On 2015–2025 real weather the myopic planner scores 1.6 points above the AI: it grows the same three crops in another order and so had canola, not vetch, in the 2025 heat.
* **Farmers earn less.** Income is shown, not optimised. In Konya (2015–2025 weather) the AI plan earns about 7,700 TL/da a year, against 16,400 for today's rotation (which the 2027 rules end) and 10,700 for the legal wheat → sunflower → maize rotation. Against that legal rotation the AI still uses 42 % less well water.
* **Not modelled:**
  * crop yields (climate fit stands in for them)
  * prices (Konya income is shown, not optimised)
  * pests and diseases beyond the soil score
  * soil moisture carried between seasons
  * double cropping, except Punjab's crop pairs
  * farmers' costs
* **Data limits:** the climate data covers about 50 km. Crop water use comes from the TAGEM–DSİ (2017) Çumra guide, except canola (ministry value) and safflower (nearby stations). The simulator is calibrated to FieldRota's 2011–2025 means (overlapping the test years), and the heat-sensitivity slope is fitted on 9 climate runs including all 6 CMIP6 models (also the validation and test models); it is part of the simulator, not of what the agent learns. The climate-model test reuses the same 40 real-year weather swings as training; only the models' trends differ. The year-by-year irrigation check (0 mm difference) holds by construction; climate fit is clipped to 0–100, which shifts some averages (potato 54 vs 42, vetch 93 vs 98). NASA POWER rain outside Konya was not checked against weather stations. Future years use a delta method (trend plus real-year anomalies), not daily CMIP6 weather, and only one scenario (SSP2-4.5).

## Run it
* **Notebook:** open `FieldRota_AI.ipynb` in Google Colab and choose *Run all* (about 5 minutes; set `RUN_ALL = True` to retrain every region, about 25 minutes). It downloads NASA POWER live and falls back to the saved copy in `data/weather/` if the API is down.
* **Retrain everything:** `python export_ai.py` writes `ai/<region>.json` and `results/summary_*.csv`; then `python tools/build_app.py` copies the policies into the app and rebuilds `app/index.html` from `tools/index.src.html`.
* **Web app:**
  * Double-click `app/index.html`: it works offline and even on its own, because the map libraries and all data are packed inside it. Keep the `app/` folder next to it for the zoomed satellite photos and for clicking fields on them.
  * Or serve the folder: `app/start_local_server.bat` on Windows, or `python -m http.server` inside `app/`.
  * Or open the live copy on GitHub Pages: https://mensar10.github.io/fieldrota-ai/app/

## Files
| Path | What it is |
|---|---|
| `fieldrota_ai.py` | simulator, rules, Q-learning, baselines, dynamic-programming optimum, evaluation |
| `FieldRota_AI.ipynb` | end-to-end notebook with all tests |
| `export_ai.py` | trains every region and goal, exports results for the app |
| `keep_mode.py` | keep-my-crops mode: the farmer's own crops plus one extra crop |
| `data/regions/*.json` | FieldRota region data (crops, calibrated water and climate numbers, rules, soil scores, CMIP6 runs) |
| `data/weather/*.csv.gz` | saved NASA POWER daily weather, 1985–2025 |
| `ai/*.json`, `results/*.csv` | trained policies and test results |
| `app/` | FieldRota web app with the new AI section (section 5); `index.html` carries its own data, `app/img_js/` serves the satellite photos offline |
| `presentation/` | interactive presentation (https://mensar10.github.io/fieldrota-ai/presentation/) |
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
* **Full source list with links:** see the Sources section of README.md (data, imagery, map outlines, fonts, prices).
* **Related work:** Turchetta et al. (2022), *Learning Long-Term Crop Management Strategies with CyclesGym*, NeurIPS Datasets and Benchmarks.
* **AI tools:** Claude (Anthropic), used through Claude Code, helped write and debug code and text at our direction. We chose the problem, data, method and tests, checked the results and can explain every part.
* **Timeline note:** the first version of all code, including the FieldRota web app (v1), was built on 14–15 November 2026.

