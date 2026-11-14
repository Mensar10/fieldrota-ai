# FieldRota-AI
**Track:** Climate  
**Team:** *names (add before submitting)*

**Live app:** https://mensar10.github.io/fieldrota-ai/app/ (section 5 is the AI planner)  
**Notebook with all results:** [open in Colab](https://colab.research.google.com/github/Mensar10/fieldrota-ai/blob/main/FieldRota_AI.ipynb)

# The problem
On the Konya Plain in Türkiye, irrigation wells are draining the aquifer faster than rain can refill it. NASA's GRACE satellites see the basin losing water every year, and hundreds of sinkholes have opened. Konya's 2027 planting rules (Çumra district) take sugar beet off the list and stop thirsty crops from following each other. That leaves a farmer with one question every autumn: *what do I plant next on this field, so that I pump less water now and in a hotter future?*

# What we built
**User:** a farmer with an irrigated field near Çumra, Konya, in the autumn when they choose next season's crop.

* **In:** the last crops on the field (e.g. wheat, then sugar beet) and a goal: save water, healthy soil, or balanced.
* **Out:** a year-by-year planting plan for 2027–2060 that follows the 2027 rules, with the expected well water use, climate fit and soil health. Example: for wheat → sugar beet with the *save water* goal, it plans barley → canola → vetch, repeating.

It runs as section 5 of our web app FieldRota (`app/index.html`) and in the notebook `FieldRota_AI.ipynb`.

# What we added
Our own idea, not a suggested project. As far as we know, using reinforcement learning to plan crop rotations against NASA weather and CMIP6 climate models, and testing it on years and models it never saw, is new.

# How it works
**Data:**
* 41 years of daily NASA POWER weather for Çumra, 1985–2025 (14,975 days: temperature, maximum and minimum temperature, rainfall).
* Our FieldRota crop table: 15 crops, with water use measured at Çumra (TAGEM–DSİ 2017), 2027 rules, a soil-health score for every 3-crop sequence, and 2041–2060 values from 6 NASA NEX-GDDP-CMIP6 models.
* We turned the averages into **year-by-year** values with the real weather: water need from each season's ET₀ (FAO-56), rain and irrigation from that season, and a climate-fit penalty for days ≥ 35 °C in each crop's most sensitive month.
* The check matches FieldRota's own averages exactly (0 mm difference).

**Model:**
* Tabular **Q-learning**. State = last two crops + decade, action = next crop (only moves allowed by the rules), reward = FieldRota's yearly score (well water, climate fit, soil).
* Why reinforcement learning: a rotation is a chain of decisions where this year's crop changes what is best next year, and the climate keeps changing.
* The agent practises on 23 real weather years (1986–2008) and 3 climate models. Of 3 training runs we keep the one that is best on 2009–2014 and a 4th model (validation).

# Results
**Test data the agent never saw:** real weather 2015–2025, and 2026–2060 under 2 other climate models (GFDL-ESM4, IPSL-CM6A-LR). Konya, *save water* goal; score is 0–100, higher is better.

| Plan | Score 2015–2025 | Score 2026–2060 | Well water (m³ per decare per year) |
|---|---|---|---|
| **Baseline: keep today's rotation** (maize → wheat → sugar beet) | 42.2 | 36.3 | 518 |
| Greedy: best crop for this year only | 71.9 | 66.8 | 262 |
| FieldRota v1: best fixed 3-year rotation, average climate | 70.7 | 70.3 | 274 |
| **FieldRota-AI (ours)** | **70.3** | **70.4** | **271 (−48 %)** |
| Best possible (exact dynamic programming) | – | 70.4 | – |

* The AI reaches **100 %** of the best possible score on the unseen climate models.
* It cuts well water by **48 %** against keeping today's rotation, with no rule breaks (today's rotation breaks the 2027 rules in about 2 of every 3 years).

**Does it hold up elsewhere?** The same method on four other groundwater hotspots: Kansas, Punjab, California and La Mancha. Across 15 region × goal tests it reaches 99.5 % of the optimum on average (98.5 % at worst). With the *save water* goal it uses 33–83 % less well water than each region's common rotation.

**Where it fails:**
1. **2025, the summer with the most days ≥ 35 °C in our 1985–2025 data.** The AI planted vetch. Its most heat-sensitive month (July) had about 13 days ≥ 35 °C instead of the usual 0–3, so climate fit fell to 54 and it was the worst year of the test (score 53.9). The AI decides in autumn and cannot know how hot the next summer will be.
2. **Not clearly better than FieldRota v1.** It is not clearly better than our simpler v1 search. In Konya the best plan is close to a fixed 3-year rotation, so the two methods agree. Elsewhere the AI is sometimes 1–4 points below v1 because it learns from noisy single years (e.g. Kansas, 2015–2025: 47.7 vs 51.5). It helps where the climate shifts: in Kansas it swaps sunflower for wheat after 2035 and beats v1 by 1.5 points.

# What we'd do next
1. Add a seasonal heat forecast to the agent's state, so it can avoid heat-sensitive crops before a hot summer like 2025.
2. Put real yields and prices into the reward, and test the plan with Çumra farmers and agricultural engineers.

# Sources
* **NASA POWER daily agroclimatology:** https://power.larc.nasa.gov
* **NASA NEX-GDDP-CMIP6 climate projections, SSP2-4.5, 6 models** (Thrasher et al., 2022): https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6
* **NASA GRACE groundwater context:** https://grace.jpl.nasa.gov
* **FAO-56, Crop evapotranspiration** (Allen et al., 1998): https://www.fao.org/3/x0490e/x0490e00.htm
* **Çumra crop water use:** *Türkiye'de Sulanan Bitkilerin Bitki Su Tüketimleri Rehberi*, TAGEM–DSİ (2017). Described in TAGEM's SUET guide: https://www.tarimorman.gov.tr/TAGEM/Belgeler/TAGEM_SUET_KullaniciKilavuzu.v.1.0.pdf
* **Çumra 2027 crop list, rotation rules and support payments:** Türkiye Ministry of Agriculture and Forestry, https://www.tarimorman.gov.tr
* **Konya income figures (shown, not optimised):**
  * yields from the Konya Provincial Directorate of Agriculture (2023–24)
  * prices from the Konya Commodity Exchange (https://www.ktb.org.tr), TMO (https://www.tmo.gov.tr) and TÜRKŞEKER (https://www.turkseker.gov.tr), autumn 2026
  * irrigation electricity tariff from EPDK (https://www.epdk.gov.tr)
  * well pumping energy from Topak et al. (2008), Selçuk University
* **Satellite images and maps in the app:**
  * NASA HLS: https://hls.gsfc.nasa.gov
  * NASA Blue Marble via GIBS: https://www.earthdata.nasa.gov/engage/open-data-services-software/earthdata-developer-portal/gibs-api
  * ESA Copernicus Sentinel-2: https://dataspace.copernicus.eu
  * Natural Earth: https://www.naturalearthdata.com
  * geoBoundaries: https://www.geoboundaries.org
* **Libraries:** NumPy (https://numpy.org), pandas (https://pandas.pydata.org), Matplotlib (https://matplotlib.org), D3 (https://d3js.org), topojson-client (https://github.com/topojson/topojson-client)
* **AI tools:** Claude by Anthropic (https://claude.ai) helped write and debug code and text. We reviewed every part and can explain it.
* **No pretrained models or tutorials were used.** All code was written during the hackathon (14–15 November 2026). The FieldRota idea is also our entry to NASA Space Apps Challenge 2026.

*Full results for all regions, test design and limits: [DETAILS.md](DETAILS.md). Code: `fieldrota_ai.py`; notebook: `FieldRota_AI.ipynb`.*
