"""
FieldRota-AI: a reinforcement-learning rotation planner on top of FieldRota.

FieldRota (v1) scores every 3-year rotation once, with the AVERAGE climate of
2011-2025, and suggests the best one. FieldRota-AI learns a planting POLICY instead:
every year it looks at the last two crops on the field (and whether last year was wet
or dry) and picks the next crop. It learns by trial and error (tabular Q-learning) in
a field simulator driven by real NASA POWER weather: trained on 23 years (1986-2008),
best run picked on 2009-2014, tested on 11 years it never saw (2015-2025). A second
agent (state: last two crops + decade) is trained on 2026-2060 CMIP6 futures and is
the one exported to the web app.

The simulator reuses FieldRota's own calibrated region data, year by year:
  - crop water need   = FieldRota seasonal need x (this year's ET0 / 2011-2025 mean ET0)
  - season rainfall    = FieldRota seasonal rain x (this year's rain / 2011-2025 mean)
  - well irrigation    = need - effective rain (FieldRota's own effective-rain ratio)
  - climate fit        = FieldRota fit, shifted by this year's hot days (Tmax >= 35 C)
                         in the crop's most sensitive month; the sensitivity (points per
                         hot day) is fitted on FieldRota's 9 climate runs per crop
                         (past, now, 2041-2060 and 6 CMIP6 models)
  - soil health        = FieldRota soil score of the last 3 crops (sliding window)
  - rules              = FieldRota rules (Konya: Cumra 2027 list; elsewhere: no fallow,
                         no repeats within 3 years) and the sowing/harvest calendar clash check
Yearly score = FieldRota goal weights x (water, climate fit, soil), exactly like v1.
This is a research prototype, not agronomic advice.
"""
import itertools
import json

import numpy as np
import pandas as pd

GOALS = {"water": {"su": 7, "iklim": 2, "toprak": 1},
         "soil": {"su": 2, "iklim": 2, "toprak": 6},
         "bal": {"su": 4, "iklim": 3, "toprak": 3}}
NOW_YEARS = (2011, 2025)     # FieldRota "today" period
TRAIN_YEARS = (1986, 2008)   # agent learns on these harvest years
VAL_YEARS = (2009, 2014)     # used only to pick the best of several training runs
TEST_YEARS = (2015, 2025)    # never seen during training
HOT_C = 35.0                 # FieldRota hot-day threshold


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
KONYA_EN = {"bugday": "Wheat", "arpa": "Barley", "nohut": "Chickpea", "mercimek": "Lentil", "fig": "Vetch",
            "aspir": "Safflower", "kanola": "Canola", "aycicegi": "Sunflower", "kuru_fasulye": "Dry bean",
            "dane_misir": "Grain maize", "patates": "Potato", "kuru_sogan": "Onion", "yonca": "Alfalfa",
            "seker_pancari": "Sugar beet", "nadas": "Fallow"}


def load_region(path):
    with open(path, encoding="utf-8") as f:
        D = json.load(f)
    D["key"] = D.get("region", {}).get("key", "konya")
    for u, c in D["crops"].items():
        c.setdefault("en", KONYA_EN.get(u, u))
    return D


def names(D, crops):
    """English crop names for printing, e.g. names(D, ['bugday', 'arpa']) -> 'Wheat > Barley'."""
    if isinstance(crops, str):
        crops = crops.split(" > ")
    return " > ".join(D["crops"][u]["en"] for u in crops)


def fetch_power(lat, lon, start=1985, end=2025):
    """Daily T2M, T2M_MAX, T2M_MIN, PRECTOTCORR from the NASA POWER API (no key needed)."""
    import urllib.request
    url = ("https://power.larc.nasa.gov/api/temporal/daily/point?parameters=T2M,T2M_MAX,T2M_MIN,PRECTOTCORR"
           f"&community=AG&longitude={lon:.4f}&latitude={lat:.4f}&start={start}0101&end={end}1231&format=JSON")
    with urllib.request.urlopen(url, timeout=120) as r:
        p = json.loads(r.read().decode())["properties"]["parameter"]
    w = pd.DataFrame(p)
    w.index = pd.to_datetime(w.index, format="%Y%m%d")
    w = w.replace(-999.0, np.nan)
    w.columns = ["t", "tmax", "tmin", "rain"]
    return w.interpolate(limit_direction="both")


def load_weather(path):
    w = pd.read_csv(path, index_col=0, parse_dates=True)
    return w.interpolate(limit_direction="both")


def hargreaves_et0(w, lat):
    """FAO-56 Hargreaves reference evapotranspiration (mm/day)."""
    J = w.index.dayofyear.values
    phi = np.radians(lat)
    dr = 1 + 0.033 * np.cos(2 * np.pi * J / 365)
    dec = 0.409 * np.sin(2 * np.pi * J / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(dec), -1, 1))
    ra = (24 * 60 / np.pi) * 0.0820 * dr * (ws * np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.sin(ws))
    tr = np.clip(w["tmax"].values - w["tmin"].values, 0, None)
    return np.clip(0.0023 * 0.408 * ra * (w["t"].values + 17.8) * np.sqrt(tr), 0, None)


def is_fallow(D, u):
    return u in ("nadas", "fallow") or not D["crops"][u].get("sow")


def season_months(c, harvest_year):
    """(year, month) pairs from sowing to harvest for the crop harvested in harvest_year."""
    sow, harv = c["sow"], c["harvest"]
    y0 = harvest_year - 1 if sow > harv else harvest_year
    out, y, m = [], y0, sow
    while True:
        out.append((y, m))
        if (y, m) == (harvest_year, harv):
            return out
        m += 1
        if m > 12:
            y, m = y + 1, 1


# ----------------------------------------------------------------------------
# Year-by-year crop table (FieldRota numbers + real NASA POWER year-to-year variation)
# ----------------------------------------------------------------------------
def heat_slope(D, u):
    """Climate-fit points lost per extra hot day, fitted on FieldRota's own climate runs."""
    pts = []
    for per in ("past", "now", "f2040"):
        p = D["periods"].get(per, {}).get(u)
        if p and p.get("uygunluk") is not None:
            pts.append((p["sicak_gun_ay"], p["uygunluk"]))
    for m in D.get("models", {}).values():
        p = m.get(u)
        if p and p.get("uygunluk") is not None:
            pts.append((p["sicak_gun_ay"], p["uygunluk"]))
    if len(pts) < 3:
        return 0.0
    x, y = np.array(pts, dtype=float).T
    if np.ptp(x) < 0.5:
        return 0.0
    slope = np.polyfit(x, y, 1)[0]
    return float(min(0.0, slope))


def build_year_table(D, w, lat, period="now"):
    """Returns crops list and arrays [year, crop]: need, rain, irr, hot, fit (+ meta)."""
    w = w.copy()
    w["et0"] = hargreaves_et0(w, lat)
    w["hot"] = (w["tmax"] >= HOT_C).astype(int)
    mon = w.groupby([w.index.year, w.index.month]).agg(rain=("rain", "sum"), et0=("et0", "sum"), hot=("hot", "sum"))
    crops = list(D["crops"])  # all crops: rules decide what may be planted
    years = list(range(1986, 2026))
    P_now, P = D["periods"]["now"], D["periods"][period]
    shape = (len(years), len(crops))
    T = {k: np.zeros(shape) for k in ["need", "rain", "irr", "hot", "fit"]}
    meta = {}
    for j, u in enumerate(crops):
        c = D["crops"][u]
        if is_fallow(D, u):
            meta[u] = {"fallow": True}
            continue
        et0 = np.array([sum(mon.et0.get((y, m), np.nan) for y, m in season_months(c, Y)) for Y in years])
        rain = np.array([sum(mon.rain.get((y, m), np.nan) for y, m in season_months(c, Y)) for Y in years])
        months = season_months(c, 2020)
        now_mask = np.array([NOW_YEARS[0] <= Y <= NOW_YEARS[1] for Y in years])
        # most heat-sensitive month: the season month whose 2011-2025 hot-day mean matches FieldRota
        cand = []
        for k, (_, m) in enumerate(months):
            hy = np.array([mon.hot.get((y, mm), 0) for Y in years for (y, mm) in [season_months(c, Y)[k]]])
            cand.append((abs(hy[now_mask].mean() - P_now[u]["sicak_gun_ay"]), m, hy))
        _, sens_month, hot = min(cand, key=lambda x: x[0])
        p_now, p = P_now[u], P[u]
        # scale POWER to FieldRota's calibrated means, keep the year-to-year variation
        need = p["su_ihtiyaci"] * et0 / np.nanmean(et0[now_mask])
        rmean = np.nanmean(rain[now_mask])
        rain_s = p["yagis"] * (rain / rmean if rmean > 0 else np.ones_like(rain))
        eff = (p_now["su_ihtiyaci"] - p_now["sulama"]) / p_now["yagis"] if p_now["yagis"] > 0 else 0.0
        irr = np.maximum(0.0, need - eff * rain_s)
        # calibrate hot days to FieldRota's 2011-2025 mean, keep the year-to-year pattern,
        # then add the period shift (e.g. 2041-2060) to every real year
        hm = hot[now_mask].mean()
        hot_s = hot * (p_now["sicak_gun_ay"] / hm) if hm > 0.2 else hot + (p_now["sicak_gun_ay"] - hm)
        hot_s = hot_s + (p["sicak_gun_ay"] - p_now["sicak_gun_ay"])
        slope = heat_slope(D, u)
        base = p["uygunluk"] if p["uygunluk"] is not None else 0
        fit = np.clip(base + slope * (hot_s - np.mean(hot_s[now_mask])), 0, 100)
        for k, v in zip(["need", "rain", "irr", "hot", "fit"], [need, rain_s, irr, hot_s, fit]):
            T[k][:, j] = v
        meta[u] = {"fallow": False, "sensitive_month": int(sens_month), "heat_slope": round(slope, 2),
                   "eff_rain": round(eff, 2)}
    T["years"] = np.array(years)
    T["crops"] = crops
    T["meta"] = meta
    return T


# ----------------------------------------------------------------------------
# Rules and soil (straight from FieldRota)
# ----------------------------------------------------------------------------
def _span(D, u, i):
    c = D["crops"][u]
    if is_fallow(D, u):
        return (i * 12, i * 12 + 12)
    if c["sow"] > c["harvest"]:
        return ((i - 1) * 12 + c["sow"] - 1, i * 12 + c["harvest"])
    return (i * 12 + c["sow"] - 1, i * 12 + c["harvest"])


def clash(D, a, b):
    """FieldRota's calendar check: crop b (next year) is sown before crop a is harvested."""
    if is_fallow(D, a) or is_fallow(D, b):
        return False
    return _span(D, b, 1)[0] < _span(D, a, 0)[1] - 1


def window_ok(D, w3):
    """Can the newest crop w3[2] be planted after w3[0], w3[1]?
    FieldRota's rules, applied year by year (the app checks them on a repeating 3-year cycle):
      - the crop must be on the region's list (Konya: Cumra 2027 list)
      - irrigated land: no fallow, and the new crop must differ from the last two crops
        (so any 3 consecutive years hold 3 different crops)
      - Konya: two high-water crops may not follow each other (this also keeps them to at
        most 2 in any 4 years)
    The field's HISTORY may break today's rules (e.g. sugar beet or fallow before 2027);
    only the new decision has to follow them."""
    new = w3[2]
    if "|".join(w3) not in D["rotations"] or not D["crops"][new].get("allowed", True):
        return False
    if is_fallow(D, new) or new in (w3[0], w3[1]):
        return False
    if D["key"] == "konya" and D["crops"][w3[1]].get("high_water") and D["crops"][new].get("high_water"):
        return False
    return True


def soil_score(D, w3):
    return D["rotations"]["|".join(w3)]["soil"]


# ----------------------------------------------------------------------------
# Environment
# ----------------------------------------------------------------------------
class FieldEnv:
    def __init__(self, D, T, goal="water"):
        self.D, self.T, self.goal = D, T, goal
        self.crops = T["crops"]
        self.n = len(self.crops)
        self.w = GOALS[goal]
        # water score scale: the thirstiest crop's average well irrigation today (mm = m3/da)
        self.imax = max(1.0, max(D["periods"]["now"][u]["sulama"] for u in self.crops if not is_fallow(D, u)))
        self.fallow = [is_fallow(D, u) for u in self.crops]
        # allowed[a2, a1, a] : can crop a follow (a2, a1)?
        n = self.n
        self.allowed = np.zeros((n, n, n), bool)
        self.soil = np.zeros((n, n, n))
        for i, j, k in itertools.product(range(n), repeat=3):
            w3 = [self.crops[i], self.crops[j], self.crops[k]]
            if "|".join(w3) not in D["rotations"]:
                continue
            self.soil[i, j, k] = soil_score(D, w3)
            self.allowed[i, j, k] = window_ok(D, w3) and not clash(D, w3[1], w3[2])
        yrs = T["years"]
        tr = (yrs >= TRAIN_YEARS[0]) & (yrs <= TRAIN_YEARS[1])
        self.rain_median = float(np.median(self._annual_signal()[tr]))

    def _annual_signal(self):
        # wet/dry signal = mean scaled season rain across crops for that year
        r = self.T["rain"]
        return r.mean(axis=1)

    def wet(self, yi):
        if yi is None or yi < 0:
            return 0
        return int(self._annual_signal()[yi] > self.rain_median)

    def year(self, yi, a2, a1, a):
        """Outcome of planting crop a in (historical) year yi after (a2, a1)."""
        if self.fallow[a]:
            return self.score(a2, a1, a, 0.0, None, yi)
        return self.score(a2, a1, a, float(self.T["irr"][yi, a]), float(self.T["fit"][yi, a]), yi)

    def score(self, a2, a1, a, irr, fit, yi=None):
        """FieldRota's goal-weighted score for one year (water, climate fit, soil)."""
        w = self.w
        soil = self.soil[a2, a1, a]
        water = 100 * (1 - irr / self.imax)
        if fit is None:  # fallow: no crop, climate fit does not apply (as in FieldRota)
            sc = (w["su"] * water + w["toprak"] * soil) / (w["su"] + w["toprak"])
        else:
            sc = (w["su"] * water + w["iklim"] * fit + w["toprak"] * soil) / (w["su"] + w["iklim"] + w["toprak"])
        return dict(score=sc, irr=irr, water=water, fit=fit, soil=soil, income=self.income(a, irr, fit))

    def income(self, a, irr, fit):
        """Konya only: sales x climate-fit factor + 2027 support - well electricity (TL/da)."""
        E = self.D.get("econ")
        if not E:
            return None
        u = self.crops[a]
        c = self.D["crops"][u]
        if self.fallow[a]:
            return 0.0
        base = self.D["periods"]["now"][u]["uygunluk"] or 1
        yf = min(1.1, (fit or 0) / base)
        return c["yield_kg"] * yf * c["price"] + c["support"] - irr * E["kwh_per_m3"] * E["tl_per_kwh"]

    def valid_actions(self, a2, a1):
        return np.flatnonzero(self.allowed[a2, a1])

    def valid_starts(self):
        """(a2, a1) pairs that have at least one allowed next crop and are themselves plausible."""
        return [(i, j) for i in range(self.n) for j in range(self.n) if self.allowed[i, j].any()]


# ----------------------------------------------------------------------------
# Q-learning
# ----------------------------------------------------------------------------
def train_q(env, year_idx, episodes=60000, horizon=10, gamma=0.9, seed=0):
    rng = np.random.default_rng(seed)
    n = env.n
    Q = np.full((n, n, 2, n), -1e9)
    for i, j in itertools.product(range(n), repeat=2):
        Q[i, j, :, env.allowed[i, j]] = 0.0
    visits = np.zeros_like(Q)
    starts = env.valid_starts()
    year_idx = np.asarray(year_idx)
    curve = []
    for ep in range(episodes):
        eps = 0.05 + 0.95 * max(0.0, 1 - ep / (0.6 * episodes))
        a2, a1 = starts[rng.integers(len(starts))]
        k0 = rng.integers(len(year_idx))
        yprev, total = None, 0.0
        for t in range(horizon):
            yi = year_idx[(k0 + t) % len(year_idx)]
            wet = env.wet(yprev)
            acts = env.valid_actions(a2, a1)
            if len(acts) == 0:
                break
            a = rng.choice(acts) if rng.random() < eps else acts[np.argmax(Q[a2, a1, wet, acts])]
            r = env.year(yi, a2, a1, a)["score"]
            nwet = env.wet(yi)
            nxt = Q[a1, a, nwet]
            future = nxt.max() if env.allowed[a1, a].any() else 0.0
            visits[a2, a1, wet, a] += 1
            Q[a2, a1, wet, a] += visits[a2, a1, wet, a] ** -0.6 * (r + gamma * future - Q[a2, a1, wet, a])
            a2, a1, yprev = a1, a, yi
            total += r
        curve.append(total / horizon)
    return Q, np.array(curve)


# ----------------------------------------------------------------------------
# Policies and evaluation
# ----------------------------------------------------------------------------
def rl_policy(env, Q):
    def pol(a2, a1, wet, t):
        acts = env.valid_actions(a2, a1)
        return acts[np.argmax(Q[a2, a1, wet, acts])] if len(acts) else None
    return pol


def myopic_policy(env, year_idx):
    """Best expected score THIS year only (ignores what it does to the next years)."""
    cache = {}

    def pol(a2, a1, wet, t):
        if (a2, a1) not in cache:
            acts = env.valid_actions(a2, a1)
            vals = [np.mean([env.year(yi, a2, a1, a)["score"] for yi in year_idx]) for a in acts]
            cache[(a2, a1)] = acts[int(np.argmax(vals))] if len(acts) else None
        return cache[(a2, a1)]
    return pol


def cycle_policy(env, rot):
    idx = [env.crops.index(u) for u in rot]
    return lambda a2, a1, wet, t: idx[t % len(idx)]


def v1_suggestion(env, period="now"):
    """FieldRota v1: best fixed 3-year rotation by the average-climate score (same formula
    as the app's suggest(): water normalised by the largest rotation irrigation)."""
    D, P = env.D, env.D["periods"][period]
    seen, lst = set(), []
    for key, R in D["rotations"].items():
        rot = key.split("|")
        if R["rules"] or any(u not in env.crops for u in rot):
            continue
        canon = min("|".join(rot[i:] + rot[:i]) for i in range(3))
        if canon in seen:
            continue
        seen.add(canon)
        if D["key"] != "konya" and (any(is_fallow(D, u) for u in rot) or len(set(rot)) < 3):
            continue
        if any(clash(D, rot[i], rot[(i + 1) % 3]) for i in range(3)):
            continue
        per = [P[u] for u in rot]
        suits = [p["uygunluk"] for p in per if p.get("uygunluk") is not None]
        irr = round(sum((p.get("sulama") or 0) for p in per) / 3)
        lst.append(dict(rot=rot, irr=irr, suit=round(sum(suits) / len(suits)) if suits else 0, soil=R["soil"]))
    imax = max(r["irr"] for r in lst) or 1
    w = env.w
    sw = w["su"] + w["iklim"] + w["toprak"]
    for r in lst:
        r["total"] = (w["su"] * 100 * (1 - r["irr"] / imax) + w["iklim"] * r["suit"] + w["toprak"] * r["soil"]) / sw
    lst.sort(key=lambda r: -r["total"])
    return lst[0]["rot"]


def rollout(env, policy, year_idx, history):
    """Run a policy over consecutive real years. history = last two crops before year 1."""
    a2, a1 = [env.crops.index(u) for u in history]
    rows, yprev = [], None
    for t, yi in enumerate(year_idx):
        wet = env.wet(yprev)
        a = policy(a2, a1, wet, t)
        if a is None:
            break
        o = env.year(yi, a2, a1, a)
        rows.append(dict(year=int(env.T["years"][yi]), crop=env.crops[a], wet=wet,
                         allowed=bool(env.allowed[a2, a1, a]), **o))
        a2, a1, yprev = a1, a, yi
    return pd.DataFrame(rows)


def summarize(df):
    crops = df[~df.crop.isin(["nadas", "fallow"])]
    return dict(score=df.score.mean(), worst_year=df.score.min(), irrigation_m3_da=df.irr.mean(),
                climate_fit=crops.fit.mean(), soil=df.soil.mean(),
                income_tl_da=df.income.mean() if df.income.notna().all() else None,
                rule_breaks=int((~df.allowed).sum()), plan=" > ".join(df.crop))


def year_indices(T, span):
    y = T["years"]
    return np.flatnonzero((y >= span[0]) & (y <= span[1]))


def evaluate_region(D, w, lat, goal="water", period="now", episodes=60000, seeds=3):
    T = build_year_table(D, w, lat, period)
    env = FieldEnv(D, T, goal)
    tr, va, te = year_indices(T, TRAIN_YEARS), year_indices(T, VAL_YEARS), year_indices(T, TEST_YEARS)
    farmer0 = ((D.get("region") or {}).get("presets") or [["dane_misir", "bugday", "seker_pancari"]])[0]
    best = None
    for seed in range(seeds):  # several training runs; keep the one that is best on the VALIDATION years
        Qs, cs = train_q(env, tr, episodes=episodes, seed=seed)
        val = rollout(env, rl_policy(env, Qs), va, farmer0[-2:]).score.mean()
        if best is None or val > best[0]:
            best = (val, Qs, cs)
    _, Q, curve = best
    presets = (D.get("region") or {}).get("presets") or [
        ["dane_misir", "bugday", "seker_pancari"], ["bugday", "aycicegi", "dane_misir"],
        ["bugday", "seker_pancari", "patates"], ["bugday", "nadas", "bugday"]]
    v1 = v1_suggestion(env)
    farmer = presets[0]
    hist = farmer[-2:]  # the field's last two crops: the farmer's current rotation
    pols = {"FieldRota-AI (RL)": (rl_policy(env, Q), hist),
            "Myopic (best this year)": (myopic_policy(env, tr), hist),
            "FieldRota v1 suggestion": (cycle_policy(env, v1), v1[1:]),
            }
    for i, p in enumerate(presets):
        pols[f"Farmers: {' > '.join(p)}"] = (cycle_policy(env, p), p[1:])
    rows = []
    for name, (pol, h) in pols.items():
        for split, idx in [("train", tr), ("test", te)]:
            s = summarize(rollout(env, pol, idx, h))
            s.update(policy=name, split=split)
            rows.append(s)
    return dict(env=env, T=T, Q=Q, curve=curve, v1=v1, presets=presets, results=pd.DataFrame(rows))


# ----------------------------------------------------------------------------
# 2026-2060: adaptation pathways under CMIP6 climate models
# ----------------------------------------------------------------------------
FUTURE_YEARS = list(range(2026, 2061))
BUCKETS = [(2026, 2035), (2036, 2045), (2046, 2060)]  # what the agent knows: which decade it is
TRAIN_MODELS = ["ACCESS-CM2", "EC-Earth3", "MPI-ESM1-2-HR"]
VAL_MODELS = ["MRI-ESM2-0"]  # used only to pick the best of several training runs
TEST_MODELS = ["GFDL-ESM4", "IPSL-CM6A-LR"]


def bucket_of(year):
    return next(i for i, (a, b) in enumerate(BUCKETS) if a <= year <= b)


def future_tables(D, T, model):
    """Year-by-year irrigation and climate fit for 2026-2060 under one CMIP6 model.

    mean(year) moves linearly from FieldRota 'now' (2011-2025, centre 2018) to the model's
    2041-2060 values (centre 2050.5); on top of it we add the de-trended anomaly of a real
    1986-2025 NASA POWER year, so each future keeps realistic good and bad years.
    Returns irr, fit arrays [anomaly_year h, future_year t, crop]."""
    crops, years = T["crops"], T["years"]
    n_h, n_t, n = len(years), len(FUTURE_YEARS), len(crops)
    irr = np.zeros((n_h, n_t, n))
    fit = np.zeros((n_h, n_t, n))
    f = np.clip((np.array(FUTURE_YEARS) - 2018) / (2050.5 - 2018), 0, 1.35)[None, :]
    P_now, P_m = D["periods"]["now"], D["models"][model]

    def detrend(x):
        k = np.polyfit(years, x, 1)
        return x - np.polyval(k, years)

    for j, u in enumerate(crops):
        if is_fallow(D, u):
            continue
        pn, pm = P_now[u], P_m[u]
        eff = T["meta"][u]["eff_rain"]
        need = pn["su_ihtiyaci"] + f * (pm["su_ihtiyaci"] - pn["su_ihtiyaci"]) + detrend(T["need"][:, j])[:, None]
        rain = np.maximum(0, pn["yagis"] + f * (pm["yagis"] - pn["yagis"]) + detrend(T["rain"][:, j])[:, None])
        irr[:, :, j] = np.maximum(0, need - eff * rain)
        base_n = pn["uygunluk"] if pn["uygunluk"] is not None else 0
        base_m = pm["uygunluk"] if pm["uygunluk"] is not None else 0
        hot_anom = detrend(T["hot"][:, j])[:, None]
        fit[:, :, j] = np.clip(base_n + f * (base_m - base_n) + T["meta"][u]["heat_slope"] * hot_anom, 0, 100)
    return irr, fit


def train_q_future(env, tables, models, episodes=30000, gamma=0.9, seed=0):
    """Q-learning over 35-year futures. State = (two previous crops, decade)."""
    rng = np.random.default_rng(seed)
    n, nb, n_t = env.n, len(BUCKETS), len(FUTURE_YEARS)
    Q = np.full((n, n, nb, n), -1e9)
    for i, j in itertools.product(range(n), repeat=2):
        Q[i, j, :, env.allowed[i, j]] = 0.0
    visits = np.zeros_like(Q)
    starts = env.valid_starts()
    bks = [bucket_of(y) for y in FUTURE_YEARS]
    curve = []
    for ep in range(episodes):
        eps = 0.05 + 0.95 * max(0.0, 1 - ep / (0.6 * episodes))
        irr, fit = tables[models[rng.integers(len(models))]]
        h0 = rng.integers(irr.shape[0])
        a2, a1 = starts[rng.integers(len(starts))]
        t0 = rng.integers(n_t)  # start anywhere in 2026-2060 so every decade gets practice
        total, steps = 0.0, 0
        for t in range(t0, n_t):
            acts = env.valid_actions(a2, a1)
            if len(acts) == 0:
                break
            b = bks[t]
            a = rng.choice(acts) if rng.random() < eps else acts[np.argmax(Q[a2, a1, b, acts])]
            h = (h0 + t) % irr.shape[0]
            r = env.score(a2, a1, a, 0.0 if env.fallow[a] else irr[h, t, a],
                          None if env.fallow[a] else fit[h, t, a])["score"]
            if t + 1 < n_t and env.allowed[a1, a].any():
                future = Q[a1, a, bks[t + 1]].max()
            else:
                future = 0.0 if t + 1 >= n_t else -50.0  # dead end: no legal next crop
            visits[a2, a1, b, a] += 1
            Q[a2, a1, b, a] += visits[a2, a1, b, a] ** -0.6 * (r + gamma * future - Q[a2, a1, b, a])
            a2, a1 = a1, a
            total += r
            steps += 1
        curve.append(total / max(steps, 1))
    return Q, np.array(curve)


def future_rollout(env, policy, tables, model, h0, history):
    irr, fit = tables[model]
    a2, a1 = [env.crops.index(u) for u in history]
    rows = []
    for t, Y in enumerate(FUTURE_YEARS):
        a = policy(a2, a1, bucket_of(Y), t)
        if a is None:
            break
        h = (h0 + t) % irr.shape[0]
        o = env.score(a2, a1, a, 0.0 if env.fallow[a] else irr[h, t, a], None if env.fallow[a] else fit[h, t, a])
        rows.append(dict(year=Y, crop=env.crops[a], allowed=bool(env.allowed[a2, a1, a]), **o))
        a2, a1 = a1, a
    return pd.DataFrame(rows)


def future_myopic(env, tables, models):
    """Best expected score this year (averaged over the training models and weather years)."""
    cache = {}
    bks = [bucket_of(y) for y in FUTURE_YEARS]

    def pol(a2, a1, b, t):
        key = (a2, a1, t)
        if key not in cache:
            acts = env.valid_actions(a2, a1)
            best, bv = None, -1e9
            for a in acts:
                v = np.mean([env.score(a2, a1, a, 0.0 if env.fallow[a] else tables[m][0][:, t, a].mean(),
                                       None if env.fallow[a] else tables[m][1][:, t, a].mean())["score"] for m in models])
                if v > bv:
                    best, bv = a, v
            cache[key] = best
        return cache[key]
    return pol


def evaluate_future(D, w, lat, goal="water", episodes=100000, seeds=3,
                    train_models=None, test_models=None, val_models=None):
    T = build_year_table(D, w, lat, "now")
    env = FieldEnv(D, T, goal)
    train_models = train_models or TRAIN_MODELS
    test_models = test_models or TEST_MODELS
    val_models = val_models or VAL_MODELS
    tables = {m: future_tables(D, T, m) for m in D["models"]}
    farmer0 = ((D.get("region") or {}).get("presets") or [["dane_misir", "bugday", "seker_pancari"]])[0]
    best = None
    for seed in range(seeds):  # several training runs; keep the one that is best on the VALIDATION model
        Qs, cs = train_q_future(env, tables, train_models, episodes=episodes, seed=seed)
        pol = (lambda Qx: lambda a2, a1, b, t: (lambda acts: acts[np.argmax(Qx[a2, a1, b, acts])] if len(acts) else None)(env.valid_actions(a2, a1)))(Qs)
        val = np.mean([future_rollout(env, pol, tables, m, h0, farmer0[-2:]).score.mean() for m in val_models for h0 in range(len(T["years"]))])
        if best is None or val > best[0]:
            best = (val, Qs, cs)
    _, Q, curve = best
    presets = (D.get("region") or {}).get("presets") or [
        ["dane_misir", "bugday", "seker_pancari"], ["bugday", "aycicegi", "dane_misir"],
        ["bugday", "seker_pancari", "patates"], ["bugday", "nadas", "bugday"]]
    farmer = presets[0]
    v1_now, v1_fut = v1_suggestion(env, "now"), v1_suggestion(env, "f2040")
    rl = lambda a2, a1, b, t: (lambda acts: acts[np.argmax(Q[a2, a1, b, acts])] if len(acts) else None)(env.valid_actions(a2, a1))
    pols = {"FieldRota-AI (RL)": (rl, farmer[-2:]),
            "Myopic (best this year)": (future_myopic(env, tables, train_models), farmer[-2:]),
            "FieldRota v1, today's pick": (cycle_policy(env, v1_now), v1_now[1:]),
            "FieldRota v1, 2050s pick": (cycle_policy(env, v1_fut), v1_fut[1:]),
            f"Farmers: {' > '.join(farmer)}": (cycle_policy(env, farmer), farmer[1:])}
    rows, paths = [], {}
    n_h = len(T["years"])
    for name, (pol, hist) in pols.items():
        for split, ms in [("train models", train_models), ("test models", test_models)]:
            dfs = [future_rollout(env, pol, tables, m, h0, hist) for m in ms for h0 in range(n_h)]
            allyears = pd.concat(dfs)
            s = summarize(allyears)
            s.update(policy=name, split=split, worst_year=float(np.percentile(allyears.score, 5)),
                     irrigation_total_m3_da=allyears.irr.sum() / len(dfs))
            s["plan"] = " > ".join(dfs[0].crop)
            rows.append(s)
        paths[name] = list(future_rollout(env, pol, tables, test_models[0], 0, hist).crop)
    opt_train, _ = future_dp_optimum(env, tables, train_models, farmer[-2:])
    opt_test, _ = future_dp_optimum(env, tables, test_models, farmer[-2:])
    return dict(env=env, T=T, Q=Q, curve=curve, tables=tables, v1_now=v1_now, v1_fut=v1_fut,
                results=pd.DataFrame(rows), paths=paths, dp_opt={"train models": opt_train, "test models": opt_test})


def future_dp_optimum(env, tables, models, history):
    """Exact backward induction over 2026-2060 with the year-by-year EXPECTED score
    (averaged over the given climate models and weather years). This is the best any
    planner could do on average; used only to check how close Q-learning gets."""
    n, n_t = env.n, len(FUTURE_YEARS)
    R = np.full((n_t, n, n, n), -1e9)
    for t in range(n_t):
        irr = np.mean([tables[m][0][:, t, :].mean(0) for m in models], 0)
        fit = np.mean([tables[m][1][:, t, :].mean(0) for m in models], 0)
        for a2, a1 in itertools.product(range(n), repeat=2):
            for a in env.valid_actions(a2, a1):
                R[t, a2, a1, a] = env.score(a2, a1, a, 0.0 if env.fallow[a] else irr[a],
                                            None if env.fallow[a] else fit[a])["score"]
    V = np.zeros((n, n))  # value after the last year
    pol = np.zeros((n_t, n, n), int)
    for t in reversed(range(n_t)):
        Qt = R[t] + V[None, :, :]  # Qt[a2, a1, a] = reward + value of (a1, a) next year
        pol[t] = Qt.argmax(-1)
        V = Qt.max(-1)
    a2, a1 = [env.crops.index(u) for u in history]
    return V[a2, a1] / n_t, pol
