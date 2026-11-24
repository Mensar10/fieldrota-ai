"""Keep-my-crops mode: the farmer keeps the crops they already grow, and FieldRota-AI may add ONE extra crop.

Farmers rarely want to drop the crops they know. Here the agent's action set is limited to the
farmer's own crops (minus any crop the local rules ban) plus one extra crop. Everything else is the
same recipe as the main agent: Q-learning on 2026-2060 futures from the 3 training climate models,
best of 3 runs picked on the validation model, final test on the 2 unseen climate models, and the
exact optimum for the same crop set computed with dynamic programming.

The extra crop is chosen on the TRAINING climate models only (the one whose exact optimum is best),
so the test models stay unseen.

Usage:  python keep_mode.py                      # konya, lamancha, kansas, california, goal "water"
        python keep_mode.py konya water           # one region and goal
        python keep_mode.py konya water fig       # force the extra crop (here vetch, the example in our presentation)
Writes results/keep_mode.csv and results/keep/<region>_<goal>.json (about 1 minute per region).
"""
import json, os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fieldrota_ai as fa

REGIONS = ["konya", "lamancha", "kansas", "california"]
LAT = {"konya": 37.6}
EPISODES = 100000


def farmer_rotation(D, region):
    """Today's common rotation for the region (the same one used as the baseline in ai/<region>.json)."""
    if region == "konya":
        return ["dane_misir", "bugday", "seker_pancari"]  # maize > wheat > sugar beet
    return D["region"]["presets"][0]


def restrict(env, base, crops):
    mask = np.zeros(env.n, bool)
    mask[[env.crops.index(c) for c in crops]] = True
    env.allowed = base & mask[None, None, :]


def run(region, goal="water", force_extra=None):
    t0 = time.time()
    D = fa.load_region(f"data/regions/{region}.json")
    w = fa.load_weather(f"data/weather/{region}.csv.gz")
    lat = LAT.get(region) or D["region"]["lat"]
    T = fa.build_year_table(D, w, lat, "now")
    env = fa.FieldEnv(D, T, goal)
    tables = {m: fa.future_tables(D, T, m) for m in D["models"]}
    farmer = farmer_rotation(D, region)
    hist = farmer[-2:]
    base = env.allowed.copy()

    # crops the farmer keeps: their own crops that the local rules still allow
    kept = [c for c in sorted(set(farmer)) if c in env.crops and D["crops"][c].get("allowed", True)]

    # 1) choose the one extra crop on the TRAINING climate models (exact optimum for each candidate)
    cand = []
    for c in env.crops:
        if c in farmer or env.fallow[env.crops.index(c)] or not D["crops"][c].get("allowed", True):
            continue
        restrict(env, base, kept + [c])
        try:
            v, _ = fa.future_dp_optimum(env, tables, fa.TRAIN_MODELS, hist)
        except Exception:
            continue
        if v is not None and v > -1e8:
            cand.append((float(v), c))
    cand.sort(reverse=True)
    extra = force_extra or cand[0][1]
    crops = kept + [extra]
    restrict(env, base, crops)

    # 2) train: 3 runs on the training models, keep the best on the validation model
    n_h = len(T["years"])
    greedy = lambda Q: (lambda a2, a1, b, t: (lambda acts: acts[np.argmax(Q[a2, a1, b, acts])] if len(acts) else None)(env.valid_actions(a2, a1)))
    best = None
    for seed in range(3):
        Q, _ = fa.train_q_future(env, tables, fa.TRAIN_MODELS, episodes=EPISODES, seed=seed)
        val = np.mean([fa.future_rollout(env, greedy(Q), tables, m, h0, hist).score.mean()
                       for m in fa.VAL_MODELS for h0 in range(n_h)])
        if best is None or val > best[0]:
            best = (val, Q, seed)
    Q = best[1]

    # 3) final test on the 2 unseen climate models, and the exact optimum for the same crop set
    dfs = [fa.future_rollout(env, greedy(Q), tables, m, h0, hist) for m in fa.TEST_MODELS for h0 in range(n_h)]
    a = pd.concat(dfs)
    opt, _ = fa.future_dp_optimum(env, tables, fa.TEST_MODELS, hist)
    base_rec = [r for r in json.load(open(f"ai/{region}.json"))["goals"][goal]["future_test"]
                if r["policy"].startswith("Farmers")][0]

    policy = {}
    for a2 in range(env.n):
        for a1 in range(env.n):
            acts = env.valid_actions(a2, a1)
            if len(acts):
                policy[f"{env.crops[a2]}|{env.crops[a1]}"] = [env.crops[acts[np.argmax(Q[a2, a1, b, acts])]] for b in range(len(fa.BUCKETS))]
    out = dict(region=region, goal=goal, farmer_rotation=farmer, kept=kept, extra=extra,
               extra_chosen_by="fixed by hand" if force_extra else "exact optimum on the training climate models",
               extra_candidates_train_models=[[c, round(v, 2)] for v, c in cand],
               best_seed=int(best[2]), ai_score=round(float(a.score.mean()), 1), exact_optimum=round(float(opt), 1),
               ai_well_water_m3_da=round(float(a.irr.mean())), today_well_water_m3_da=round(base_rec["irrigation_m3_da"]),
               plan_2026_2060=list(dfs[0].crop), policy=policy, seconds=round(time.time() - t0))
    out["saving_pct"] = round(100 * (1 - out["ai_well_water_m3_da"] / out["today_well_water_m3_da"]))
    os.makedirs("results/keep", exist_ok=True)
    tag = f"_{force_extra}" if force_extra else ""
    json.dump(out, open(f"results/keep/{region}_{goal}{tag}.json", "w"), ensure_ascii=False)
    return out


if __name__ == "__main__":
    regions = sys.argv[1].split(",") if len(sys.argv) > 1 else REGIONS
    goal = sys.argv[2] if len(sys.argv) > 2 else "water"
    force = sys.argv[3] if len(sys.argv) > 3 else None
    rows = []
    for r in regions:
        o = run(r, goal, force)
        rows.append({k: o[k] for k in ["region", "goal", "kept", "extra", "extra_chosen_by", "ai_score", "exact_optimum",
                                       "today_well_water_m3_da", "ai_well_water_m3_da", "saving_pct"]})
        print(rows[-1], f"({o['seconds']} s)", flush=True)
    df = pd.DataFrame(rows)
    df["kept"] = df["kept"].map(lambda x: " + ".join(x))
    path = "results/keep_mode.csv"
    if len(regions) < len(REGIONS) and os.path.exists(path):
        old = pd.read_csv(path)
        same = old.region.isin(regions) & (old.goal == goal) & (old.extra.isin(df.extra))
        df = pd.concat([old[~same], df])
    df.to_csv(path, index=False)
