"""Train FieldRota-AI for every region and goal, test it, and export results for the web app.
Writes ai/<region>.json (policy + test results) and results/summary.csv."""
import json, os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fieldrota_ai as fa

REGIONS = ["konya", "kansas", "punjab", "california", "lamancha"]
LAT = {"konya": 37.57}
os.makedirs("ai", exist_ok=True); os.makedirs("results", exist_ok=True)
rows = []
regions = sys.argv[1].split(",") if len(sys.argv) > 1 else REGIONS
for k in regions:
    D = fa.load_region(f"data/regions/{k}.json"); w = fa.load_weather(f"data/weather/{k}.csv.gz")
    lat = LAT.get(k) or D["region"]["lat"]
    out = {"region": k, "crops": None, "buckets": fa.BUCKETS, "goals": {},
           "meta": {"train_years": fa.TRAIN_YEARS, "test_years": fa.TEST_YEARS,
                    "train_models": fa.TRAIN_MODELS, "val_models": fa.VAL_MODELS, "test_models": fa.TEST_MODELS, "val_years": fa.VAL_YEARS}}
    for g in ["water", "soil", "bal"]:
        t0 = time.time()
        h = fa.evaluate_region(D, w, lat, g)
        f = fa.evaluate_future(D, w, lat, g)
        env, Q = f["env"], f["Q"]
        out["crops"] = env.crops
        pol = {}
        for a2 in range(env.n):
            for a1 in range(env.n):
                acts = env.valid_actions(a2, a1)
                if len(acts):
                    pol[f"{env.crops[a2]}|{env.crops[a1]}"] = [env.crops[acts[np.argmax(Q[a2, a1, b, acts])]] for b in range(len(fa.BUCKETS))]
        def pack(R, split):
            R = R[R.split == split]
            return [{k2: (None if (isinstance(v, float) and np.isnan(v)) else (round(v, 1) if isinstance(v, (float, np.floating)) else v))
                     for k2, v in r.items() if k2 not in ("split",)} for r in R.to_dict("records")]
        curve = f["curve"]; step = max(1, len(curve) // 60)
        out["goals"][g] = {
            "policy": pol,
            "hist_test": pack(h["results"], "test"),
            "future_test": pack(f["results"], "test models"),
            "future_train": pack(f["results"], "train models"),
            "dp_opt": {s: round(float(v), 1) for s, v in f["dp_opt"].items()},
            "v1": f["v1_now"], "v1_2050": f["v1_fut"],
            "curve": [round(float(curve[i:i + step].mean()), 1) for i in range(0, len(curve), step)],
            "farmer": (D.get("region") or {}).get("presets", [["dane_misir", "bugday", "seker_pancari"]])[0],
        }
        for split, R in [("hist_test", h["results"][h["results"].split == "test"]),
                         ("future_test", f["results"][f["results"].split == "test models"])]:
            for r in R.to_dict("records"):
                rows.append(dict(region=k, goal=g, eval=split, **{c: r[c] for c in ["policy", "score", "worst_year", "irrigation_m3_da", "climate_fit", "soil", "income_tl_da", "rule_breaks"]}))
        rows.append(dict(region=k, goal=g, eval="future_test", policy="Best possible (exact DP, expected)", score=f["dp_opt"]["test models"]))
        print(f"{k}/{g} done in {time.time()-t0:.0f}s", flush=True)
    with open(f"ai/{k}.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
pd.DataFrame(rows).to_csv("results/summary_" + "_".join(regions) + ".csv", index=False)
print("saved")
