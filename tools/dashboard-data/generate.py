#!/usr/bin/env python3
"""
Deterministic synthetic panel generator for the "Vehicle Performance Dashboard" demo.

Reads ONLY: structure.csv, tiers.csv, series_models.csv (all beside this file; run extract_structure.py first).
Writes: synth_panel.csv (same directory).

Everything numeric is invented: per-entity latent parameters come from a seeded RNG plus
public-knowledge style baselines (segment price points, seasonality, rate environment) and the
coarse size-decile tiers. No real figure is used or reconstructed.

Pipeline
  1. parse structure.csv  -> row list, fill-mask, entity/cut keys
  2. build leaves (Model x fuel x class), Series<-Model map, Nameplate->OEM map
  3. simulate leaf x month latent panel (volume, inventory, prices, incentives, finance ...)
  4. rake volumes to an industry path, round leaves to integers
  5. aggregate leaves -> every (entity, cut) via sparse membership matrices
  6. round monthly values, apply fill-mask, roll up to quarterly / ytd / full_year
  7. shares, identity repair (sums to 100, dealer_profit), formatting, write csv
"""
import os
import re
import sys
import time
import numpy as np
import pandas as pd
import scipy.sparse as sp

SEED = 20261016
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_NAME = os.environ.get("SYNTH_OUT", "synth_panel.csv")
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------------------
# 0. constants
# --------------------------------------------------------------------------------------
T = 61                                   # months 2021-10 .. 2026-10
MONTHS = [f"{2021 + (9 + i) // 12}-{(9 + i) % 12 + 1:02d}" for i in range(T)]
MIDX = {m: i for i, m in enumerate(MONTHS)}
MOY = np.array([int(m[5:]) for m in MONTHS])
YEAR = np.array([int(m[:4]) for m in MONTHS])
TI = np.arange(T, dtype=float)
PARTIAL = 0.28                           # share of a normal month present in 2026-10
REF = np.arange(MIDX["2025-10"], MIDX["2026-09"] + 1)   # "last 12 complete months"


def A(pairs):
    """piecewise-linear macro path from (YYYY-MM, value) anchors over the month grid"""
    xs = [MIDX[p[0]] for p in pairs]
    ys = [p[1] for p in pairs]
    return np.interp(TI, xs, ys)


# ----- macro paths (invented, public-knowledge shape) -----
SEAS_M = np.array([0.82, 0.91, 1.12, 1.03, 1.05, 1.04, 0.95, 1.05, 1.00, 1.01, 0.97, 1.05])
SEAS_M = SEAS_M / SEAS_M.mean()
SEAS = SEAS_M[MOY - 1]

# annualised industry retail rate, millions
RATE = A([("2021-10", 12.6), ("2022-01", 13.2), ("2022-06", 12.6), ("2022-12", 13.7),
          ("2023-06", 14.5), ("2023-12", 15.0), ("2024-06", 15.3), ("2024-12", 15.6),
          ("2025-06", 15.7), ("2025-12", 15.6), ("2026-06", 15.5), ("2026-10", 15.4)])
# days supply (industry), days
DTS = A([("2021-10", 25), ("2022-01", 21), ("2022-07", 24), ("2023-01", 36), ("2023-07", 50),
         ("2024-01", 63), ("2024-07", 72), ("2025-01", 78), ("2025-07", 76), ("2026-01", 72),
         ("2026-07", 70), ("2026-10", 69)])
# average incentive as share of MSRP
INCP = A([("2021-10", 0.006), ("2022-06", 0.004), ("2022-12", 0.009), ("2023-06", 0.021),
          ("2023-12", 0.035), ("2024-06", 0.048), ("2024-12", 0.058), ("2025-06", 0.060),
          ("2025-12", 0.061), ("2026-10", 0.063)])
# market markup / scarcity premium over MSRP
MARKUP = A([("2021-10", 0.022), ("2022-04", 0.034), ("2022-10", 0.022), ("2023-04", 0.009),
            ("2023-10", 0.003), ("2024-04", 0.0), ("2026-10", 0.0)])
# MSRP inflation index
INFL = A([("2021-10", 0.965), ("2022-04", 0.985), ("2022-10", 1.005), ("2023-04", 1.020),
          ("2024-04", 1.035), ("2025-04", 1.050), ("2026-04", 1.065), ("2026-10", 1.070)])
# gross margin cycle (1.0 == 2025 level)
GMAC = A([("2021-10", 2.7), ("2022-04", 3.2), ("2022-10", 2.7), ("2023-04", 1.9), ("2024-01", 1.4),
          ("2024-07", 1.15), ("2025-01", 1.02), ("2026-10", 0.97)])
FIMAC = A([("2021-10", 0.86), ("2022-10", 0.93), ("2023-10", 1.0), ("2024-10", 1.05),
           ("2025-10", 1.08), ("2026-10", 1.10)])
# average finance APR (market, %)
APRM = A([("2021-10", 4.6), ("2022-06", 5.1), ("2022-12", 6.4), ("2023-06", 7.2), ("2023-12", 7.7),
          ("2024-06", 7.5), ("2024-12", 7.2), ("2025-06", 7.0), ("2025-12", 6.8), ("2026-10", 6.6)])
# lease share of sales (market base)
LEASEM = A([("2021-10", 17.5), ("2022-06", 17.0), ("2023-01", 18.5), ("2023-12", 21.5),
            ("2024-12", 23.5), ("2025-12", 25.0), ("2026-10", 25.0)])
CASHM = A([("2021-10", 31.0), ("2022-12", 29.5), ("2023-12", 26.5), ("2024-12", 24.5), ("2026-10", 23.5)])
RVM = A([("2021-10", 0.075), ("2022-10", 0.070), ("2023-06", 0.035), ("2024-01", 0.01),
         ("2024-12", 0.0), ("2026-10", 0.0)])
TRADEEQ = A([("2021-10", 0.030), ("2022-06", 0.036), ("2023-06", 0.012), ("2024-06", -0.004),
             ("2025-06", -0.008), ("2026-10", -0.008)])
TERMM = A([("2021-10", 0.0), ("2023-01", 0.8), ("2024-06", 1.6), ("2025-06", 2.0), ("2026-10", 2.1)])

# fuel-type trends (relative; normalised so the reference window averages 1)
def _norm(x):
    return x / x[REF].mean()

EV_TR = _norm(A([("2021-10", 0.45), ("2022-12", 0.72), ("2023-12", 0.92), ("2024-12", 1.05),
                 ("2025-07", 1.06), ("2025-09", 1.38), ("2025-10", 0.88), ("2026-02", 0.84),
                 ("2026-09", 0.97), ("2026-10", 0.97)]))
HY_TR = _norm(A([("2021-10", 0.55), ("2022-12", 0.72), ("2023-12", 0.86), ("2024-12", 0.96),
                 ("2025-12", 1.04), ("2026-10", 1.10)]))
IC_TR = _norm(A([("2021-10", 1.06), ("2023-12", 1.02), ("2025-10", 0.99), ("2026-10", 0.97)]))
EV_INC = A([("2021-10", 0.6), ("2022-12", 0.8), ("2023-06", 1.4), ("2024-06", 1.8), ("2025-06", 1.5),
            ("2025-10", 0.7), ("2026-06", 1.0), ("2026-10", 1.0)])
EV_DTS = A([("2021-10", 0.7), ("2022-12", 0.9), ("2023-12", 1.35), ("2024-12", 1.55), ("2025-09", 1.2),
            ("2026-10", 1.2)])
EV_LEASE = A([("2021-10", 14.0), ("2022-12", 18.0), ("2023-09", 40.0), ("2024-06", 50.0),
              ("2025-09", 52.0), ("2025-11", 32.0), ("2026-10", 30.0)])
EV_PRICE = A([("2021-10", 1.0), ("2022-12", 1.0), ("2023-09", 0.95), ("2024-09", 0.92), ("2026-10", 0.92)])

# industry-level events (multiplicative on the monthly industry level)
EVENTS = {"2022-12": 1.03, "2023-12": 1.02, "2024-06": 0.99, "2024-07": 0.93, "2024-08": 1.03,
          "2025-03": 1.05, "2025-04": 1.04, "2025-05": 0.97, "2025-06": 0.98, "2026-01": 0.97}

# segment table ---------------------------------------------------------------------
# base_msrp, premium, gross pct (of price @ 2025 cycle), F&I $, dts mult, incentive mult, lease adj, term adj
SEG = {
    "Small Car":                   (20500, 0, 0.022, 1450, 0.95, 1.20, -3, 1.0),
    "Compact Car":                 (25500, 0, 0.023, 1500, 0.95, 1.15, -2, 1.0),
    "Midsize Car":                 (31000, 0, 0.024, 1600, 1.00, 1.10, 0, 0.8),
    "Large Car":                   (39000, 0, 0.026, 1700, 1.05, 1.10, 0, 0.8),
    "Compact Sporty Car":          (33000, 0, 0.030, 1600, 1.20, 1.00, 0, 0.3),
    "Midsize Sporty Car":          (45000, 0, 0.034, 1750, 1.25, 0.95, 0, 0.3),
    "Compact MPV":                 (28500, 0, 0.026, 1500, 1.05, 1.10, -2, 1.0),
    "Small SUV":                   (28500, 0, 0.027, 1550, 0.95, 1.10, -1, 0.8),
    "Compact SUV":                 (35500, 0, 0.029, 1650, 0.95, 1.05, 1, 0.9),
    "Midsize SUV":                 (47000, 0, 0.032, 1850, 1.05, 1.00, 1, 1.1),
    "Large SUV":                   (65000, 0, 0.040, 2150, 1.10, 0.90, 1, 1.2),
    "Midsize Van":                 (42500, 0, 0.030, 1900, 1.00, 1.05, 2, 1.0),
    "Large Van":                   (53000, 0, 0.034, 1700, 1.15, 0.85, -6, 1.5),
    "Midsize Pickup":              (41000, 0, 0.034, 1950, 1.10, 1.00, -3, 1.6),
    "Large Pickup - LD":           (58500, 0, 0.038, 2250, 1.20, 1.10, -3, 1.8),
    "Large Pickup - HD":           (71000, 0, 0.042, 2350, 1.25, 0.95, -6, 2.0),
    "Small Premium Car":           (38500, 1, 0.034, 1850, 1.00, 1.05, 8, -1.8),
    "Compact Premium Car":         (53000, 1, 0.037, 1950, 1.05, 1.05, 10, -2.0),
    "Midsize Premium Car":         (71000, 1, 0.040, 2050, 1.15, 1.00, 9, -2.2),
    "Large Premium Car":           (108000, 1, 0.045, 2300, 1.35, 0.90, 7, -2.4),
    "Compact Premium Sporty Car":  (64000, 1, 0.042, 2000, 1.30, 0.90, 7, -2.2),
    "Midsize Premium Sporty Car":  (96000, 1, 0.046, 2200, 1.40, 0.85, 4, -2.4),
    "Small Premium SUV":           (43500, 1, 0.036, 1900, 1.00, 1.05, 10, -1.8),
    "Compact Premium SUV":         (57000, 1, 0.039, 2000, 1.05, 1.00, 10, -2.0),
    "Midsize Premium SUV":         (73000, 1, 0.042, 2100, 1.10, 0.95, 8, -2.2),
    "Large Premium SUV":           (99000, 1, 0.046, 2300, 1.20, 0.90, 5, -2.4),
    "Super Premium":               (400000, 1, 0.060, 6500, 2.10, 0.35, -2, -6.0),
}
SEGNAMES = sorted(SEG)
# popularity prior (rank inside a size tier) and rough segment shares of the market (invented)
SEG_POP = {"Large Pickup - LD": 1.0, "Compact SUV": 0.9, "Midsize SUV": 0.8, "Small SUV": 0.7,
           "Midsize Pickup": 0.65, "Compact Car": 0.6, "Midsize Car": 0.55, "Large Pickup - HD": 0.6,
           "Compact Premium SUV": 0.45, "Midsize Premium SUV": 0.45, "Large SUV": 0.4, "Midsize Van": 0.4,
           "Compact Premium Car": 0.35, "Small Car": 0.3, "Large Van": 0.35, "Small Premium SUV": 0.3,
           "Large Premium SUV": 0.3, "Super Premium": 0.05}
# well-known volume leaders get a small nudge inside their size tier (public-knowledge ranking prior)
FLAGSHIP = {"F-150": 0.6, "Silverado 1500": 0.5, "Ram 1500": 0.4, "RAV4": 0.3, "CR-V": 0.25, "Camry": 0.2,
            "Civic": 0.15, "Model Y": 0.12, "Tacoma": 0.1, "Equinox": 0.12, "Rogue": 0.12, "Corolla": 0.1,
            "Explorer": -0.3, "Traverse": -0.3, "Forester": -0.05, "CR-V Hybrid": -0.15, "Camry Hybrid": -0.1}
SEG_SHARE = {"Small Car": .8, "Compact Car": 5.3, "Midsize Car": 3.8, "Large Car": .9, "Compact Sporty Car": .5,
             "Midsize Sporty Car": .6, "Compact MPV": .15, "Small SUV": 9.0, "Compact SUV": 14.5,
             "Midsize SUV": 13.5, "Large SUV": 3.2, "Midsize Van": 1.8, "Large Van": 1.5, "Midsize Pickup": 3.8,
             "Large Pickup - LD": 11.5, "Large Pickup - HD": 3.0, "Small Premium Car": .45,
             "Compact Premium Car": 2.4, "Midsize Premium Car": 1.0, "Large Premium Car": .4,
             "Compact Premium Sporty Car": .1, "Midsize Premium Sporty Car": .4, "Small Premium SUV": 1.4,
             "Compact Premium SUV": 4.8, "Midsize Premium SUV": 6.0, "Large Premium SUV": 1.7,
             "Super Premium": .5}

# nameplate -> OEM group (public ownership structure, naming follows structure.csv)
OEM_OF = {
    "Ford": "Ford Group", "Lincoln": "Ford Group",
    "Chevrolet": "General Motors Group", "GMC": "General Motors Group", "Buick": "General Motors Group",
    "Cadillac": "General Motors Group",
    "Toyota": "Toyota Group", "Lexus": "Toyota Group",
    "Honda": "Honda Group", "Acura": "Honda Group",
    "Hyundai": "Hyundai Group", "Genesis": "Hyundai Group", "Kia": "Kia Motors",
    "Chrysler": "Stellantis", "Dodge": "Stellantis", "Jeep": "Stellantis", "RAM": "Stellantis",
    "Fiat": "Stellantis", "Alfa Romeo": "Stellantis",
    "Nissan": "Nissan Group", "Infiniti": "Nissan Group", "Mitsubishi": "Nissan Group",
    "Subaru": "Subaru Motors", "Mazda": "Mazda Motors",
    "Volkswagen": "Volkswagen Group", "Audi": "Volkswagen Group", "Porsche": "Volkswagen Group",
    "BMW": "BMW Group", "Mini": "BMW Group", "Rolls-Royce": "BMW Group",
    "Mercedes-Benz": "Daimler Group", "Mercedes-Benz Vans": "Daimler Group",
    "Tesla": "Tesla Motors", "Rivian": "Rivian Automotive", "Lucid": "Lucid Motors",
    "Karma": "Karma Automotive", "Jaguar": "JLR", "Land Rover": "JLR",
    "Volvo": "Geely Holding", "Polestar": "Geely Holding", "Lotus": "Geely Holding",
    "Maserati": "Maserati Motors",
    "Ferrari": "Super Premium", "Lamborghini": "Super Premium", "McLaren": "Super Premium",
    "Aston Martin": "Super Premium", "Bentley": "Super Premium",
}
# a few brand-level tweaks (direct-sales EV makers: no dealer margin, thin incentives)
DIRECT = {"Tesla", "Rivian", "Lucid", "Polestar"}

# size-decile boundaries (monthly units) per level; tier k spans [B[k], B[k+1]]
B_MODEL = np.array([2.5, 9, 29, 65, 135, 278, 603, 1300, 2500, 5900, 70000.0])
B_SERIES = np.array([5, 21, 76, 224, 642, 1200, 1900, 3200, 6000, 13700, 90000.0])
B_NAME = np.array([60, 250, 700, 1800, 4000, 6700, 11000, 20000, 38000, 78000, 210000.0])
B_OEM = np.array([500, 2500, 6000, 11000, 20000, 40000, 65000, 100000, 140000, 172000, 450000.0])


# --------------------------------------------------------------------------------------
# 1. structure
# --------------------------------------------------------------------------------------
META = ["level", "entity", "is_aggregate", "default_subject", "nameplate", "segment", "period_type",
        "month", "month_label", "fuel_type", "premium_flag"]


def load_structure():
    path = os.path.join(HERE, "structure.csv")
    with open(path) as fh:
        header = fh.readline().rstrip("\n")
        raw = fh.read().split("\n")
    if raw and raw[-1] == "":
        raw.pop()
    cols = header.split(",")
    S = pd.read_csv(path, dtype=str, keep_default_na=False)
    assert list(S.columns) == cols and len(S) == len(raw)
    mcols = cols[11:]
    M = (S[mcols].values == "1")
    # meta text exactly as in the file (first 11 comma-separated fields)
    meta_txt = [",".join(r.split(",", 11)[:11]) for r in raw]
    return S, M, cols, mcols, meta_txt, header


def period_table(S):
    """period id for every row; periods = 61 monthly + quarterly + ytd + full_year"""
    plist = [("monthly", m) for m in MONTHS]
    pidx = {p: i for i, p in enumerate(plist)}
    ptype = S.period_type.values
    label = S.month.values
    pid = np.full(len(S), -1, dtype=np.int64)
    for k in range(len(S)):
        if ptype[k] == "data_through":
            continue
        key = (ptype[k], label[k])
        j = pidx.get(key)
        if j is None:
            j = len(plist)
            plist.append(key)
            pidx[key] = j
        pid[k] = j
    # month membership of each period
    nP = len(plist)
    Pm = np.zeros((T, nP))
    for j, (pt, lab) in enumerate(plist):
        if pt == "monthly":
            Pm[MIDX[lab], j] = 1
        elif pt == "quarterly":
            y, q = int(lab[:4]), int(lab[-1])
            for t in range(T):
                if YEAR[t] == y and (MOY[t] - 1) // 3 + 1 == q:
                    Pm[t, j] = 1
        elif pt == "ytd":
            y = int(lab[:4])
            for t in range(T):
                if YEAR[t] == y and MOY[t] <= 10:
                    Pm[t, j] = 1
        elif pt == "full_year":
            y = int(lab)
            for t in range(T):
                if YEAR[t] == y:
                    Pm[t, j] = 1
        else:
            raise ValueError(pt)
    return plist, pid, Pm


# --------------------------------------------------------------------------------------
# 2. hierarchy : leaves, series map, memberships
# --------------------------------------------------------------------------------------
def _tok(name):
    n = name.lower().replace("-", " ").replace("+", " ")
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return n.split()


def _variants(tokens):
    out = set(tokens)
    for t in tokens:
        if re.match(r"^m\d", t):
            out.add(t[1:])
        if re.match(r"^[a-z]{1,3}\d", t):
            pass
    return out


def name_score(series_name, model_name):
    st = _tok(series_name)
    if not st:
        return 0.0
    mt = _variants(_tok(model_name))
    hit = 0
    for s_ in st:
        if any(m.startswith(s_) for m in mt):
            hit += 1
    sc = hit / len(st)
    if "".join(st) == "".join(_tok(model_name)):
        sc += 1.0
    return sc


def build_hierarchy(S, M):
    sm = pd.read_csv(os.path.join(HERE, "series_models.csv"), keep_default_na=False)
    base = S[S.level.isin(["Model", "Series", "Nameplate", "OEM"])]
    # --- leaves from Model rows with a specific (fuel, class) cut
    mm = base[(base.level == "Model") & (base.is_aggregate == "0") & (base.period_type == "monthly")]
    act_rows = mm[(mm.fuel_type != "All") & (mm.premium_flag != "All")]
    leaf_keys = sorted(set(zip(act_rows.entity, act_rows.nameplate, act_rows.segment,
                               act_rows.fuel_type, act_rows.premium_flag)))
    lid = {k: i for i, k in enumerate(leaf_keys)}
    L = len(leaf_keys)
    active = np.zeros((L, T), dtype=bool)
    ks = list(zip(act_rows.entity, act_rows.nameplate, act_rows.segment, act_rows.fuel_type,
                  act_rows.premium_flag))
    for k, m in zip(ks, act_rows.month.values):
        active[lid[k], MIDX[m]] = True
    # entity-level (model entity) activity for the series mapping heuristics
    ent_months = {}
    for (e, n, sg, f, p), i in lid.items():
        ent_months.setdefault((e, n, sg), np.zeros(T, bool))
        ent_months[(e, n, sg)] |= active[i]

    # --- series entities and mapping
    ser = base[(base.level == "Series") & (base.is_aggregate == "0") & (base.period_type == "monthly")
               & (base.fuel_type == "All") & (base.premium_flag == "All")]
    ser_months = {}
    for (e, n, sg), g in ser.groupby(["entity", "nameplate", "segment"]):
        v = np.zeros(T, bool)
        for m in g.month.values:
            v[MIDX[m]] = True
        ser_months[(e, n, sg)] = v
    series_keys = sorted(ser_months)
    mapped = {}
    for (se, n, sg), g in sm.groupby(["series", "nameplate", "segment"]):
        mapped[(se, n, sg)] = [(m, n, ms) for m, ms in zip(g.model, g.model_segment)]
    model_to_series = {}
    for sk, ml in mapped.items():
        if sk in ser_months:
            for mk in ml:
                if mk in ent_months:
                    model_to_series[mk] = sk
    # unmapped models: best series in the same (nameplate, segment) group
    groups = {}
    for sk in series_keys:
        if sk[2] != "(All Segments)":
            groups.setdefault((sk[1], sk[2]), []).append(sk)
    n_unmapped = 0
    for mk in sorted(ent_months):
        if mk in model_to_series:
            continue
        n_unmapped += 1
        cands = groups.get((mk[1], mk[2]), [])
        if not cands:
            continue
        mv = ent_months[mk]
        best, bsc = None, -1
        for sk in cands:
            sv = ser_months[sk]
            jac = (mv & sv).sum() / max(1, (mv | sv).sum())
            sc = 2.0 * name_score(sk[0], mk[0]) + 1.0 * jac
            if sk not in mapped:
                sc += 0.05
            if sc > bsc:
                best, bsc = sk, sc
        model_to_series[mk] = best
    # series left without any model: steal the best-overlapping model from a multi-model series
    members = {}
    for mk, sk in model_to_series.items():
        members.setdefault(sk, []).append(mk)
    for sk in series_keys:
        if sk[2] == "(All Segments)" or sk in members:
            continue
        sv = ser_months[sk]
        best, bsc = None, -1
        for mk in ent_months:
            if mk[1] != sk[1] or mk[2] != sk[2]:
                continue
            cur = model_to_series.get(mk)
            if cur is not None and len(members.get(cur, [])) <= 1:
                continue
            mv = ent_months[mk]
            jac = (mv & sv).sum() / max(1, (mv | sv).sum())
            if jac > bsc:
                best, bsc = mk, jac
        if best is not None and bsc > 0:
            cur = model_to_series.get(best)
            if cur is not None:
                members[cur].remove(best)
            model_to_series[best] = sk
            members.setdefault(sk, []).append(best)
    # light local repair: move a model to a sibling series when this removes lifecycle mismatches
    # (months where the series has a row but no member is active, or vice versa) and the new
    # series name matches the model name better than the old one
    def _cost(sk, mem):
        u = np.zeros(T, bool)
        for m_ in mem:
            u |= ent_months[m_]
        return int((u != ser_months[sk]).sum())

    changed = True
    while changed:
        changed = False
        for mk in sorted(model_to_series):
            cur = model_to_series[mk]
            if len(members.get(cur, [])) <= 1:
                continue
            for sk in groups.get((mk[1], mk[2]), []):
                if sk == cur or sk not in members:
                    continue
                ns_new, ns_old = name_score(sk[0], mk[0]), name_score(cur[0], mk[0])
                if not (ns_new > ns_old):
                    continue
                before = _cost(cur, members[cur]) + _cost(sk, members[sk])
                after = (_cost(cur, [x for x in members[cur] if x != mk]) +
                         _cost(sk, members[sk] + [mk]))
                if after + 1 < before:
                    members[cur].remove(mk)
                    members[sk].append(mk)
                    model_to_series[mk] = sk
                    changed = True
                    break
    log(f"hierarchy: leaves={L} model entities={len(ent_months)} unmapped-models={n_unmapped} "
        f"series={len(series_keys)} series-without-models="
        f"{sum(1 for sk in series_keys if sk[2] != '(All Segments)' and sk not in members)}")
    return dict(leaf_keys=leaf_keys, lid=lid, active=active, ent_months=ent_months,
                series_keys=series_keys, model_to_series=model_to_series, members=members,
                ser_months=ser_months)


def build_entities(S, H):
    """entity-cut table ("EC") + sparse membership matrix G (n_ec x L)"""
    lk = H["leaf_keys"]
    L = len(lk)
    leaf_ent = np.array([k[0] for k in lk])
    leaf_np = np.array([k[1] for k in lk])
    leaf_seg = np.array([k[2] for k in lk])
    leaf_fuel = np.array([k[3] for k in lk])
    leaf_prem = np.array([k[4] for k in lk])
    m2s = H["model_to_series"]
    # leaves of each series entity
    ent_idx = {}
    for i, k in enumerate(lk):
        ent_idx.setdefault((k[0], k[1], k[2]), []).append(i)
    ser_leaves = {}
    for mk, sk in m2s.items():
        ser_leaves.setdefault(sk, []).extend(ent_idx[mk])
    # "(All Segments)" series = sum of the sibling segment series of the same family
    for sk in H["series_keys"]:
        if sk[2] != "(All Segments)":
            continue
        prefix = sk[0].rsplit(" - ", 1)[0] + " - "
        sib = [k for k in H["series_keys"] if k[1] == sk[1] and k[2] != "(All Segments)"
               and k[0].startswith(prefix)]
        ser_leaves[sk] = sorted(set(i for k in sib for i in ser_leaves.get(k, [])))
    oem_of_np = {}
    for n in sorted(set(leaf_np)):
        oem_of_np[n] = OEM_OF[n]
    base = S[S.level.isin(["Model", "Series", "Nameplate", "OEM"])]
    ec_cols = ["level", "entity", "nameplate", "segment", "is_aggregate", "fuel_type", "premium_flag"]
    ecs = base[ec_cols].drop_duplicates().reset_index(drop=True)
    rr, cc = [], []
    n_empty = 0
    for j, (lv, ent, npn, seg, agg, fu, pr) in enumerate(ecs.itertuples(index=False)):
        if lv == "Model":
            if agg == "1":
                idx = np.where(leaf_seg == ent)[0]
            else:
                idx = np.array(ent_idx.get((ent, npn, seg), []), dtype=int)
        elif lv == "Series":
            if agg == "1":
                idx = np.where(leaf_seg == ent)[0]
            else:
                idx = np.array(ser_leaves.get((ent, npn, seg), []), dtype=int)
        elif lv == "Nameplate":
            idx = np.arange(L) if ent == "Industry" else np.where(leaf_np == ent)[0]
        else:  # OEM
            if ent == "Industry":
                idx = np.arange(L)
            else:
                idx = np.array([i for i in range(L) if oem_of_np[leaf_np[i]] == ent], dtype=int)
        if len(idx):
            ok = np.ones(len(idx), bool)
            if fu != "All":
                ok &= leaf_fuel[idx] == fu
            if pr != "All":
                ok &= leaf_prem[idx] == pr
            idx = idx[ok]
        if len(idx) == 0:
            n_empty += 1
        rr.append(np.full(len(idx), j))
        cc.append(idx)
    rr = np.concatenate(rr)
    cc = np.concatenate(cc)
    G = sp.csr_matrix((np.ones(len(rr)), (rr, cc)), shape=(len(ecs), L))
    log(f"entities: ec={len(ecs)} empty-membership={n_empty} nnz={G.nnz}")
    return ecs, G


# --------------------------------------------------------------------------------------
# 3. latent leaf simulation
# --------------------------------------------------------------------------------------
def ar1(rng, n, phi, sig):
    sig = np.broadcast_to(np.asarray(sig, dtype=float), (n,)).copy()
    e = rng.standard_normal((n, T))
    x = np.zeros((n, T))
    x[:, 0] = e[:, 0] * sig
    s2 = np.sqrt(1 - phi ** 2)
    for t in range(1, T):
        x[:, t] = phi * x[:, t - 1] + s2 * sig * e[:, t]
    return x


def tnorm(rng, size, sigma, k=1.8):
    return np.clip(rng.standard_normal(size), -k, k) * sigma


def loguni(rng, lo, hi, size=None):
    return np.exp(rng.uniform(np.log(lo), np.log(hi), size))


def pmt(af, apr, n):
    r = apr / 1200.0
    return af * r / (1.0 - (1.0 + r) ** (-n))


def industry_path(rng):
    """monthly industry retail units (full-month equivalent)"""
    noise = ar1(rng, 1, 0.5, 0.012)[0]
    lvl = RATE * 1e6 / 12.0 * SEAS * np.exp(noise)
    for m, f in EVENTS.items():
        lvl[MIDX[m]] *= f
    return lvl


def simulate_leaves(H, rng):
    lk = H["leaf_keys"]
    L = len(lk)
    act = H["active"]
    ent = np.array([k[0] for k in lk])
    npn = np.array([k[1] for k in lk])
    seg = np.array([k[2] for k in lk])
    fuel = np.array([k[3] for k in lk])
    prem = np.array([k[4] for k in lk])
    is_ev = fuel == "EV"
    is_hy = fuel == "Hybrid"
    is_pr = prem == "Premium"
    segs_u = np.array([SEG[s] for s in seg], dtype=float)           # (L, 8)
    base_msrp, seg_prem, seg_g, seg_fi, seg_dts, seg_inc, seg_lease, seg_term = segs_u.T
    names_u = sorted(set(npn))
    nid = {n: i for i, n in enumerate(names_u)}
    li = np.array([nid[n] for n in npn])
    NB = len(names_u)
    direct = np.array([n in DIRECT for n in npn])
    is_super = seg == "Super Premium"

    first = act.argmax(axis=1)
    last = T - 1 - act[:, ::-1].argmax(axis=1)
    nact = act.sum(axis=1)
    launched = first > 0
    ended = last < T - 2
    age = TI[None, :] - first[:, None]
    toend = last[:, None] - TI[None, :]
    ref_alive = act[:, REF].sum(axis=1)

    # ----------------------------------------------------------- sizes (monthly units, ref window)
    tiers = pd.read_csv(os.path.join(HERE, "tiers.csv"), keep_default_na=False)
    tmap = {}
    for r in tiers.itertuples(index=False):
        tmap[(r.level, r.entity, r.nameplate, r.segment)] = int(r.tier)
    ser_tier = {}
    for r in tiers[tiers.level == "Series"].itertuples(index=False):
        ser_tier[(r.entity, r.nameplate, r.segment)] = int(r.tier)
    np_tier = {r.entity: int(r.tier) for r in tiers[tiers.level == "Nameplate"].itertuples(index=False)}
    name_leaf = np.array([k[0] for k in lk])
    ent_key = list(zip(ent, npn, seg))
    ent_ids = {}
    for i, k in enumerate(ent_key):
        ent_ids.setdefault(k, []).append(i)
    ekeys = sorted(ent_ids)
    ne = len(ekeys)
    tier_e = np.array([tmap.get(("Model",) + k, -1) for k in ekeys])
    ent2series = H["model_to_series"]
    # popularity prior inside a tier: segment popularity + series tier + nameplate tier + noise
    pop = np.array([SEG_POP.get(k[2], 0.3) + FLAGSHIP.get(k[0], 0.0) for k in ekeys])
    st = np.array([max(ser_tier.get(ent2series.get(k), -1), 0) for k in ekeys]) / 9.0
    nt = np.array([max(np_tier.get(k[1], 0), 0) for k in ekeys]) / 9.0
    score = 0.55 * pop + 0.28 * st + 0.17 * nt + rng.normal(0, 0.035, ne)
    uq = np.zeros(ne)
    fake = rng.choice(9, size=ne, p=[.15, .17, .17, .15, .12, .09, .07, .05, .03])
    seg_e = np.array([k[2] for k in ekeys])
    cap_t = np.where(seg_e == "Super Premium", 3, np.where(pop < 0.45, 6, 8))
    fake = np.minimum(fake, cap_t)
    for tr in range(-1, 10):
        ids = np.where(tier_e == tr)[0]
        if len(ids) == 0:
            continue
        if tr == -1:
            uq[ids] = rng.uniform(size=len(ids))
        else:
            rk = np.argsort(np.argsort(score[ids]))
            uq[ids] = (rk + 0.5) / len(ids)
    lo_e = np.zeros(ne)
    hi_e = np.zeros(ne)
    tr_eff = np.where(tier_e >= 0, tier_e, fake)
    blo = B_MODEL[tr_eff]
    bhi = B_MODEL[tr_eff + 1]
    ref_alive_e = np.array([act[ent_ids[k]][:, REF].any(axis=0).sum() for k in ekeys]) / 12.0
    # tier 9 gets a skewed (heavy-tailed) position so the sum matches the market
    def draw(gam):
        pos = np.where(tr_eff == 9, uq ** gam, uq)
        return blo * (bhi / blo) ** pos
    market_ref = (RATE * 1e6 / 12.0 * SEAS)[REF].mean()
    t9 = (tr_eff == 9) & (tier_e >= 0)
    other = (S0_tmp := draw(1.0))[~t9] @ ref_alive_e[~t9]
    want9 = market_ref * 1.03 - other
    a_, b_ = 0.3, 8.0
    for _ in range(40):
        mid = 0.5 * (a_ + b_)
        tot9 = draw(mid)[t9] @ ref_alive_e[t9]
        if tot9 > want9:
            a_ = mid
        else:
            b_ = mid
    gamma = 0.5 * (a_ + b_)
    S0e = draw(gamma)
    lo_e = np.where(tier_e >= 0, blo * 0.92, 1.5)
    hi_e = np.where(tier_e >= 0, bhi * 1.08, 9000.0)
    log(f"tier-9 skew gamma={gamma:.2f}")
    if os.environ.get("SYNTH_DEBUG"):
        o = list(np.argsort(-S0e)[:6]) + [j for j in range(ne) if ekeys[j][0] in ("F-150", "Silverado 1500", "Ram 1500", "Explorer", "RAV4")]
        for j in o:
            log("init", ekeys[j][0], tier_e[j], round(S0e[j]), round(score[j], 2), round(pop[j], 2), round(st[j], 2), round(nt[j], 2))

    # split entity volume over its leaves
    S0 = np.zeros(L)
    for j, k in enumerate(ekeys):
        ids = ent_ids[k]
        if len(ids) == 1:
            S0[ids[0]] = S0e[j]
        else:
            w = np.zeros(len(ids))
            for t_, i in enumerate(ids):
                w[t_] = rng.uniform(0.12, 0.30) if fuel[i] == "Hybrid" else 0.0
            nz = [t_ for t_, i in enumerate(ids) if fuel[i] != "Hybrid"]
            rest = 1 - w.sum()
            if not nz:
                w = rng.dirichlet(np.ones(len(ids)) * 2.0)
            else:
                dd = rng.dirichlet(np.ones(len(nz)) * 3.0) * rest
                for q_, t_ in enumerate(nz):
                    w[t_] = dd[q_]
            S0[ids] = S0e[j] * w
    leaf_lo = np.zeros(L)
    leaf_hi = np.zeros(L)
    for j, k in enumerate(ekeys):
        for i in ent_ids[k]:
            share = S0[i] / S0e[j]
            leaf_lo[i] = lo_e[j] * share
            leaf_hi[i] = hi_e[j] * share
    # --- projection onto Series / Nameplate / Segment totals (soft)
    contrib_w = ref_alive / 12.0
    ser_members = {}
    for i, k in enumerate(ent_key):
        sk = ent2series.get(k)
        if sk is not None and ser_tier.get(sk, -1) >= 0:
            ser_members.setdefault(sk, []).append(i)
    ser_target = {}
    for sk, ids in ser_members.items():
        tr = ser_tier[sk]
        ser_target[sk] = loguni(rng, B_SERIES[tr], B_SERIES[tr + 1] * (1.0 if tr < 9 else 0.8))
    np_members = {n: [i for i in range(L) if npn[i] == n] for n in names_u}
    np_target = {}
    for n in names_u:
        tr = np_tier.get(n, -1)
        if tr < 0:
            continue
        np_target[n] = loguni(rng, B_NAME[tr], B_NAME[tr + 1] * (1.0 if tr < 9 else 0.9))
    tot = sum(np_target.values())
    top = [n for n in np_target if np_tier[n] == 9]
    if top:
        rest = tot - sum(np_target[n] for n in top)
        sc = (market_ref - rest) / sum(np_target[n] for n in top)
        for n in top:
            np_target[n] *= sc
    seg_members = {s_: np.where(seg == s_)[0] for s_ in SEGNAMES}
    sp_ = np.array([SEG_SHARE.get(s_, 0.01) for s_ in SEGNAMES])
    seg_target = dict(zip(SEGNAMES, sp_ / sp_.sum() * market_ref))
    def tilt(ids, target, strength=1.0):
        """scale S0[ids] by one factor so the alive-weighted sum hits target (respecting per-leaf bounds)"""
        ids = np.asarray(ids)
        ids = ids[contrib_w[ids] > 0]        # only leaves alive in the reference window are tilted
        if len(ids) == 0:
            return
        cw = contrib_w[ids]
        if (cw * S0[ids]).sum() <= 0 or target <= 0:
            return
        lo_f, hi_f = 1e-3, 1e3
        for _ in range(60):
            mid = np.sqrt(lo_f * hi_f)
            tot_ = (np.clip(S0[ids] * mid, leaf_lo[ids], leaf_hi[ids]) * cw).sum()
            if tot_ > target:
                hi_f = mid
            else:
                lo_f = mid
        f = np.sqrt(lo_f * hi_f)
        f = f ** strength
        S0[ids] = np.clip(S0[ids] * f, leaf_lo[ids], leaf_hi[ids])

    for s_, ids in seg_members.items():
        ids = np.asarray(ids)
        if len(ids):
            leaf_hi[ids] = np.maximum(np.minimum(leaf_hi[ids], 0.27 * seg_target[s_]), leaf_lo[ids])
            S0[ids] = np.minimum(S0[ids], leaf_hi[ids])
    for sweep in range(3):
        for s_, ids in seg_members.items():
            ids = np.array(ids)
            cur = (S0[ids] * contrib_w[ids]).sum()
            if cur > 0:
                tilt(ids, float(np.clip(cur, 0.75 * seg_target[s_], 1.35 * seg_target[s_])))
        for sk, ids in ser_members.items():
            ids = np.array(ids)
            cur = (S0[ids] * contrib_w[ids]).sum()
            tr = ser_tier[sk]
            lo_s, hi_s = B_SERIES[tr], B_SERIES[tr + 1] * (1.0 if tr < 9 else 0.8)
            if cur > 0:
                tilt(ids, float(np.clip(cur, lo_s, hi_s)))
        for n, tgt in np_target.items():
            ids = np.array(np_members[n])
            cur = (S0[ids] * contrib_w[ids]).sum()
            tr = np_tier[n]
            if tr == 9:
                tilt(ids, tgt)
            elif cur > 0:
                tilt(ids, float(np.clip(cur, B_NAME[tr], B_NAME[tr + 1])))
    if os.environ.get("SYNTH_DEBUG"):
        for n in ["Ford", "Toyota", "Honda", "Chevrolet"]:
            ids = np_members[n]
            log(n, "target", int(np_target[n]), "got", int((S0[ids] * contrib_w[ids]).sum()))
        for nm_ in ("F-150", "Explorer", "RAV4", "Silverado 1500"):
            for i in np.where(name_leaf == nm_)[0]:
                log("final", nm_, round(S0[i]), "hi", round(leaf_hi[i]), "lo", round(leaf_lo[i]))
    alive_sum = (S0 * contrib_w).sum()
    log(f"sizes: sum of leaf plateau volumes over ref window = {alive_sum:,.0f} "
        f"(market ref {market_ref:,.0f})")

    # ----------------------------------------------------------- volume
    ind = industry_path(rng)
    imacro = ind / SEAS / (ind[REF].mean() / SEAS[REF].mean())          # level without seasonality
    seg_amp = np.clip(1.0 + 0.30 * rng.standard_normal(L), 0.2, 2.0)
    seas_l = SEAS[None, :] ** seg_amp[:, None]
    ftr = np.where(is_ev[:, None], EV_TR[None, :], np.where(is_hy[:, None], HY_TR[None, :], IC_TR[None, :]))
    g_l = np.clip(rng.normal(0, 0.10, L), -0.25, 0.25)
    trend = np.exp(g_l[:, None] * (TI[None, :] - 55.0) / 12.0)
    ramp = np.where(launched[:, None], 1 - 0.62 * np.exp(-np.maximum(age, 0) / 5.5), 1.0)
    decl = np.where(ended[:, None], 0.30 + 0.70 * (1 - np.exp(-np.maximum(toend, 0) / 4.5)), 1.0)
    life = ramp * decl
    sigv = 0.045 + 0.17 / (1 + (S0 / 250.0) ** 0.6)
    noise = np.exp(ar1(rng, L, 0.55, sigv))
    raw = imacro[None, :] * seas_l * ftr * trend * life * noise
    Rm = act[:, REF]
    kk = np.zeros(L)
    for i in range(L):
        if Rm[i].any():
            kk[i] = S0[i] / raw[i, REF][Rm[i]].mean()
        else:
            am = act[i]
            kk[i] = S0[i] / (raw[i][am] / life[i][am]).mean()
    units = kk[:, None] * raw
    units = np.where(act, units, 0.0)
    # rake to the industry path
    tot_t = units.sum(axis=0)
    rake = ind / tot_t
    log(f"rake factor range {rake.min():.3f}..{rake.max():.3f}; ref mean {rake[REF].mean():.3f}")
    units = units * rake[None, :]
    u_full = np.where(act, np.maximum(np.rint(units), 1.0), 0.0)
    u_out = u_full.copy()
    u_out[:, T - 1] = np.where(act[:, T - 1], np.maximum(np.rint(u_full[:, T - 1] * PARTIAL), 1.0), 0.0)

    # ----------------------------------------------------------- static draws
    b_price = tnorm(rng, NB, 1.0) * np.where([any(prem[li == b]) for b in range(NB)], 0.075, 0.045)
    b_price = np.where(np.isin(names_u, ["Ferrari", "Lamborghini", "McLaren", "Aston Martin", "Bentley",
                                         "Rolls-Royce", "Lotus", "Karma"]),
                       rng.normal(0, 0.45, NB), b_price)
    b_inc = rng.normal(0, 0.25, NB)
    b_dts = rng.normal(0, 0.14, NB)
    b_apr = rng.normal(0, 0.60, NB)
    b_gross = rng.normal(0, 0.18, NB)
    b_lease = rng.normal(0, 5.0, NB)
    b_loy = rng.normal(50, 15, NB)

    # ----------------------------------------------------------- price block
    name_l = np.array([k[0] for k in lk])
    phev = np.array([bool(re.search(r"PHEV|Plug-In|Plug In|4xe|e-Hybrid|PHV|Prime", n)) for n in name_l])
    hyb_nm = np.array([bool(re.search(r"Hybrid|HEV", n)) for n in name_l])
    e_price = tnorm(rng, L, 1.0) * np.where(is_super, 0.30, 0.07)
    pt_mult = np.where(is_ev, np.where(is_pr, 1.09, 1.15),
                       np.where(phev, 1.20, np.where(is_hy | hyb_nm, 1.07, 1.0)))
    cls_mult = np.where((seg_prem == 0) & is_pr, 1.22, np.where((seg_prem == 1) & ~is_pr, 0.90, 1.0))
    pos = np.exp(b_price[li] + e_price)
    pos = np.where(is_super, pos, np.clip(pos, 0.85, 1.19))
    msrp0 = base_msrp * pos * pt_mult * cls_mult
    floor_ev = base_msrp * 1.04 * cls_mult
    msrp0 = np.where(is_ev, np.maximum(msrp0, floor_ev), msrp0)
    msrp0 = np.where(is_super, np.clip(msrp0, 60000, 800000), np.clip(msrp0, 0.62 * base_msrp, 1e7))
    # model-year steps
    off = rng.integers(0, 12, L)
    first_chg = (off - 0).astype(float)
    step_idx = np.floor((TI[None, :] - first_chg[:, None]) / 12.0)
    tq = np.maximum(first_chg[:, None] + 12.0 * step_idx, 0.0)
    infl = np.interp(tq, TI, INFL)
    evp = np.where(is_ev[:, None], np.interp(tq, TI, EV_PRICE), 1.0)
    nstep = int(step_idx.max()) + 2
    stepn = np.cumsum(rng.normal(0.004, 0.010, (L, nstep + 1)), axis=1)
    sidx = np.clip(step_idx + 1, 0, nstep).astype(int)
    stepf = np.exp(np.take_along_axis(stepn, sidx, axis=1))
    mixn = np.exp(ar1(rng, L, 0.6, 0.0035))
    msrp = msrp0[:, None] * infl * evp * stepf * mixn

    # ----------------------------------------------------------- inventory / days to turn
    e_dts = rng.normal(0, 0.40, L)
    sd = np.where(direct, 0.45, 1.0)
    dtt = (0.8 * DTS[None, :]) * (seg_dts * np.exp(e_dts + b_dts[li]) * sd)[:, None]
    dtt = dtt * np.where(is_ev[:, None], EV_DTS[None, :], 1.0)
    dtt = dtt * (SEAS[None, :] ** -0.35)
    dtt = dtt * np.clip((S0 / 400.0) ** -0.10, 0.6, 1.5)[:, None]
    dtt = dtt * np.where(launched[:, None], 1 - 0.45 * np.exp(-np.maximum(age, 0) / 3.0), 1.0)
    dtt = dtt * np.where(ended[:, None], 1 + 0.9 * np.exp(-np.maximum(toend, 0) / 3.5), 1.0)
    dtt = dtt * np.exp(ar1(rng, L, 0.85, 0.10))
    dtt = np.clip(dtt * 1.12, 3.0, 420.0)
    inv = dtt * u_full / 30.4 * 0.97 * np.exp(rng.normal(0, 0.025, (L, T)))
    inv = np.where(act, np.rint(inv), 0.0)
    inv = np.where(inv < 1.0, np.where(rng.uniform(size=(L, T)) < 0.35, 0.0, 1.0), inv)
    inv = np.where(act, inv, 0.0)
    prev = np.concatenate([np.zeros((L, 1)), inv[:, :-1]], axis=1)
    ws_full = u_full + (inv - prev) + rng.normal(0, 0.04, (L, T)) * u_full
    floor_ws = np.where(S0 < 60, -2.0, 0.0)[:, None]
    ws_full = np.maximum(ws_full, floor_ws)
    ws = np.where(act, np.rint(ws_full), 0.0)
    ws[:, T - 1] = np.where(act[:, T - 1], np.rint(ws_full[:, T - 1] * PARTIAL), 0.0)

    # ----------------------------------------------------------- sale mix / penetration / terms
    ev_t = is_ev[:, None]
    lease = (LEASEM[None, :] + seg_lease[:, None] + b_lease[li][:, None]
             + rng.normal(0, 9.0, L)[:, None] + ar1(rng, L, 0.9, 2.5))
    lease = np.where(ev_t, EV_LEASE[None, :] * 0.9 + 0.15 * lease + rng.normal(0, 5, L)[:, None] * 0.5, lease)
    lease = np.where(direct[:, None], lease * 0.35, lease)
    lease = np.clip(lease, 0.8, 80.0)
    cash_mult = np.where(is_super, 2.2, np.where(is_pr, 0.85, 1.0)) * np.where(is_ev, 0.6, 1.0)
    cash = CASHM[None, :] * cash_mult[:, None] * np.exp(rng.normal(0, 0.16, L))[:, None]
    cash = cash * np.exp(ar1(rng, L, 0.9, 0.06))
    cash = np.clip(cash, 3.0, 72.0)
    fin = 100 - lease - cash
    short = np.maximum(11.0 - fin, 0.0)
    scl = (lease + cash - short) / (lease + cash)
    lease, cash = lease * scl, cash * scl
    fin = 100 - lease - cash
    u_pl = rng.uniform(0.68, 0.95, L)[:, None]
    u_pf = np.exp(rng.normal(np.log(0.19), 0.55, L))[:, None]
    pen_lease = np.clip(lease * u_pl + rng.normal(0, 0.6, (L, T)), 0.0, 90.0)
    pen_fin = np.clip(np.minimum(fin * u_pf, 70.0) * (np.maximum(INCP, 0.004)[None, :] / 0.04) ** 0.3
                      * np.exp(rng.normal(0, 0.10, (L, T))), 0.0, 60.0)
    pen_cash = 100 - pen_lease - pen_fin
    over = np.maximum(15.0 - pen_cash, 0.0)
    pen_lease = pen_lease - over * pen_lease / (pen_lease + pen_fin + 1e-9)
    pen_fin = pen_fin - over * pen_fin / (pen_lease + pen_fin + 1e-9)
    pen_cash = 100 - pen_lease - pen_fin

    # incentives
    stance = np.exp(rng.normal(0, 0.55, L) + b_inc[li]) * np.where(direct, 0.25, 1.0)
    ratio_t = dtt / (0.8 * DTS[None, :])
    inc_t = (msrp * INCP[None, :] * stance[:, None] * np.clip(ratio_t, 0.15, 6.0) ** 0.9 * seg_inc[:, None]
             * np.where(ev_t, EV_INC[None, :], 1.0) * np.exp(ar1(rng, L, 0.8, 0.12)))
    inc_t = np.clip(inc_t, 0.0, 0.26 * msrp)
    wc = 0.14 * np.exp(rng.normal(0, 0.85, L))
    wf = 0.12 * np.exp(rng.normal(0, 0.45, L))
    wl = 0.60 * np.exp(rng.normal(0, 0.20, L))
    ws_sum = (wc + wf + wl) / 0.86
    wc, wf, wl = wc / ws_sum, wf / ws_sum, wl / ws_sum
    offer_cash = np.clip(wc[:, None] * inc_t / (np.maximum(pen_cash, 5.0) / 100.0), 0, 15000)
    offer_fin = np.clip(wf[:, None] * inc_t / (np.maximum(pen_fin, 2.5) / 100.0), 0, 15000)
    offer_lease = np.clip(wl[:, None] * inc_t / (np.maximum(pen_lease, 2.5) / 100.0), 0, 26000)
    badd = rng.uniform(0.03, 0.15, L)[:, None]
    inc = (pen_cash * offer_cash + pen_fin * offer_fin + pen_lease * offer_lease) / 100.0 * (1 + badd)

    # prices
    hot = np.clip(np.exp(rng.normal(0, 0.45, L)), 0.2, 3.0)
    scarce = np.clip(32.0 / dtt, 0.5, 2.5) ** 0.7
    e_cf = 0.028 * rng.standard_t(5, L)
    cf_ratio = (0.985 + MARKUP[None, :] * hot[:, None] * scarce - 0.75 * inc / msrp
                - 0.00045 * np.maximum(dtt - 40.0, 0.0) + e_cf[:, None]
                + ar1(rng, L, 0.7, 0.005))
    cf_ratio = np.clip(cf_ratio, 0.70, 1.20)
    cftp = msrp * cf_ratio
    rvp = np.clip(1.075 + rng.normal(0, 0.022, L)[:, None] + ar1(rng, L, 0.8, 0.004), 0.96, 1.16)
    vp = cftp * rvp

    # apr / terms
    seg_apr = {"Small Car": 0.7, "Compact Car": 0.5, "Compact MPV": 0.4, "Small SUV": 0.3, "Midsize Car": 0.2,
               "Super Premium": -0.9}
    sa = np.array([seg_apr.get(s, -0.35 if SEG[s][1] else 0.0) for s in seg])
    e_apr = rng.normal(0, 0.9, L)
    apr_f = (APRM[None, :] + b_apr[li][:, None] + e_apr[:, None] + sa[:, None]
             + np.where(ev_t, -0.35 * (YEAR[None, :] >= 2023), 0.0) - 0.028 * pen_fin
             + ar1(rng, L, 0.85, 0.22))
    apr_f = np.clip(apr_f, 0.9, 16.0)
    apr_l = (APRM[None, :] * 0.97 + 0.6 * b_apr[li][:, None] + rng.normal(0, 0.85, L)[:, None] + 0.6 * sa[:, None]
             + np.where(ev_t, -0.6, 0.0) - 0.025 * pen_lease + ar1(rng, L, 0.85, 0.25))
    apr_l = np.clip(apr_l, 0.5, 16.0)
    avg_term = (66.8 + TERMM[None, :] + seg_term[:, None] + rng.normal(0, 0.8, L)[:, None]
                + np.where(ev_t, -0.6, 0.0) + ar1(rng, L, 0.9, 0.35))
    avg_term = np.clip(avg_term, 57.0, 76.0)

    # payment walk inputs
    kN = {60: 0.87, 72: 1.08, 84: 1.28}
    dN = {60: 0.200, 72: 0.150, 84: 0.105}
    aN = {60: 0.100, 72: 0.047, 84: 0.000}
    pw = {}
    pay = {}
    afford = np.exp(rng.normal(0, 0.18, L)) * np.where(is_pr, 1.15, 1.0) * np.where(is_super, 2.2, 1.0)
    e_te = rng.normal(0, 0.02, L)
    drift = np.exp(rng.normal(np.log(2.4), 0.55, L))
    for N in (60, 72, 84):
        apr_n = np.clip(apr_f * kN[N] * np.exp(rng.normal(0, 0.05, L))[:, None]
                        * np.exp(ar1(rng, L, 0.8, 0.02)), 0.5, 18.0)
        down = vp * dN[N] * afford[:, None] * np.exp(ar1(rng, L, 0.7, 0.05))
        down = np.minimum(down, 0.6 * vp)
        te = vp * (aN[N] + TRADEEQ[None, :] + e_te[:, None] + ar1(rng, L, 0.7, 0.010))
        af = 1.2 * np.maximum(vp - down - te, 0.25 * vp) * np.exp(rng.normal(0, 0.012, (L, T)))
        if N == 84:
            term = np.clip(84.0 - drift[:, None] * np.exp(ar1(rng, L, 0.8, 0.12)), 72.5, 84.0)
        else:
            term = np.full((L, T), float(N))
        pw[N] = dict(term=term, apr=apr_n, trade=te, down=down, af=af)
        pay[N] = pmt(af, apr_n, term) * (1 + rng.normal(0, 0.003, (L, T)))

    # lease payment
    seg_rv = np.where(is_pr, 0.58, 0.60)
    seg_rv = np.where(np.isin(seg, ["Large Pickup - LD", "Large Pickup - HD", "Midsize Pickup"]), 0.62, seg_rv)
    seg_rv = np.where(is_super, 0.55, seg_rv)
    rv = (seg_rv[:, None] + RVM[None, :] + rng.normal(0, 0.022, L)[:, None]
          + np.where(ev_t, np.where(YEAR[None, :] >= 2023, -0.09, -0.04), 0.0))
    rv = np.clip(rv, 0.35, 0.78)
    cap = cftp - 0.3 * offer_lease * (pen_lease > 1)
    lp = (cap - rv * msrp) / 36.0 + (cap + rv * msrp) * (apr_l / 2400.0)
    lp = np.clip(lp, 0.0055 * msrp, 0.024 * msrp) * (1 + rng.normal(0, 0.008, (L, T)))

    # model-year mix
    nomy = (rng.uniform(size=L) < 0.22) | direct
    kmo = np.mod(TI[None, :] - off[:, None], 12.0)
    ou = rng.uniform(0.8, 1.2, L)[:, None]
    my_old = np.clip(100 * 0.62 ** (kmo + 1) * ou, 0, 100)
    jn = 12.0 - kmo
    nu = rng.uniform(0.6, 1.8, L)[:, None]
    my_new = np.where(jn == 1, 40 * nu, np.where(jn == 2, 14 * nu, np.where(jn == 3, 4 * nu, 0.0)))
    my_new = np.clip(my_new, 0, 80)
    my_old = np.where(nomy[:, None], 0.0, my_old)
    my_new = np.where(nomy[:, None], 0.0, my_new)
    # first model year of a new launch is all "current"
    my_old = np.where(launched[:, None] & (age < 2), 0.0, my_old)
    my_cur = 100 - my_old - my_new

    # gross / F&I
    e_g = rng.normal(0, 0.45, L)
    gp = (0.68 * seg_g[:, None] * GMAC[None, :] * np.exp(e_g[:, None] + b_gross[li][:, None])
          - 0.0006 * np.maximum(dtt - 55.0, 0.0) + ar1(rng, L, 0.6, 0.013))
    gp = gp * np.where(ev_t, 0.45, 1.0)
    gp = np.where(direct[:, None], 0.0 + ar1(rng, L, 0.6, 0.002), gp)
    gp = np.clip(gp, -0.07, 0.22)
    vgross = vp * gp
    fi = (seg_fi[:, None] * FIMAC[None, :] * np.exp(rng.normal(0, 0.20, L))[:, None]
          * (0.55 + 0.45 * (100 - cash) / 76.0) * np.where(ev_t, 0.6, 1.0)
          * np.where(direct[:, None], 0.4, 1.0) * np.exp(ar1(rng, L, 0.5, 0.04)))

    # loyalty
    seg_loy = np.where(np.isin(seg, ["Large Pickup - LD", "Large Pickup - HD", "Midsize Pickup"]), 27.0,
                       np.where(is_super, 8.0, np.where(is_pr, 14.0, 16.0)))
    smloy = (seg_loy * 1.2 * np.exp(rng.normal(0, 0.52, L)))[:, None] * np.where(ev_t, 0.6, 1.0)
    smloy = smloy * (1 + ar1(rng, L, 0.9, 0.06)) * (1 - 0.5 * np.exp(-np.maximum(age, 0) / 8.0) * launched[:, None])
    smloy = np.clip(smloy, 0.0, 62.0)
    npl = b_loy[li][:, None] + 0.5 * (smloy - seg_loy[:, None]) + rng.normal(0, 4.0, L)[:, None] + ar1(rng, L, 0.9, 1.5)
    npl = np.clip(np.maximum(npl, smloy + 3.0), 6.0, 92.0)

    V = {
        "retail_sales": u_out, "wholesales": ws, "retail_inventory": inv, "dtt": dtt,
        "msrp": msrp, "cftp": cftp, "cftp_pct_msrp": 100.0 * cf_ratio, "vehicle_price": vp,
        "incentive_unit": inc, "offer_cash": offer_cash, "offer_finance": offer_fin, "offer_lease": offer_lease,
        "pen_cash": pen_cash, "pen_finance": pen_fin, "pen_lease": pen_lease,
        "sale_mix_cash": cash, "sale_mix_finance": fin, "sale_mix_lease": lease,
        "apr_finance": apr_f, "apr_lease": apr_l, "average_finance_term": avg_term,
        "lease_monthly_payment": lp,
        "my_mix_current": my_cur, "my_mix_new": my_new, "my_mix_old": my_old,
        "vehicle_gross": vgross, "fi_income": fi, "dealer_profit": vgross + fi,
        "series_model_loyalty": smloy, "nameplate_loyalty": npl,
    }
    for N in (60, 72, 84):
        V[f"finance_monthly_payment_{N}"] = pay[N]
        V[f"pw{N}_term"] = pw[N]["term"]
        V[f"pw{N}_apr"] = pw[N]["apr"]
        V[f"pw{N}_trade_equity"] = pw[N]["trade"]
        V[f"pw{N}_cash_down"] = pw[N]["down"]
        V[f"pw{N}_amount_financed"] = pw[N]["af"]
    info = dict(S0=S0, ent=ent, npn=npn, seg=seg, fuel=fuel, prem=prem, first=first, last=last)
    return V, info


# --------------------------------------------------------------------------------------
# 4. column policy
# --------------------------------------------------------------------------------------
# rounding step per column (also fixes the number of decimals written)
STEP_OF = {
    "retail_share": 0.1, "my_mix_current": 1, "my_mix_new": 1, "my_mix_old": 1,
    "incentive_unit": 50, "cftp": 50, "vehicle_price": 50, "msrp": 50, "cftp_pct_msrp": 0.1,
    "retail_inventory": 1, "dtt": 1, "lease_monthly_payment": 10,
    "finance_monthly_payment_60": 10, "finance_monthly_payment_72": 10, "finance_monthly_payment_84": 10,
    "average_finance_term": 0.1,
    "pw60_term": 1, "pw60_apr": 0.05, "pw60_trade_equity": 100, "pw60_cash_down": 100,
    "pw60_amount_financed": 100,
    "pw72_term": 1, "pw72_apr": 0.05, "pw72_trade_equity": 100, "pw72_cash_down": 100,
    "pw72_amount_financed": 100,
    "pw84_term": 0.1, "pw84_apr": 0.05, "pw84_trade_equity": 100, "pw84_cash_down": 100,
    "pw84_amount_financed": 100,
    "series_model_loyalty": 1, "nameplate_loyalty": 1,
    "offer_cash": 50, "offer_finance": 50, "offer_lease": 50,
    "pen_cash": 1, "pen_finance": 1, "pen_lease": 1,
    "dealer_profit": 10, "sale_mix_cash": 0.5, "sale_mix_finance": 0.5, "sale_mix_lease": 0.5,
    "wholesales": 1, "retail_sales": 1, "fi_income": 10, "apr_finance": 0.05, "apr_lease": 0.05,
    "vehicle_gross": 10,
}
SUM_COLS = ["retail_sales", "wholesales"]
LAST_COLS = ["retail_inventory"]
PW_COLS = [f"pw{n}_{k}" for n in (60, 72, 84) for k in ("term", "apr", "trade_equity", "cash_down", "amount_financed")]
OFFER_PEN = {"offer_cash": "pen_cash", "offer_finance": "pen_finance", "offer_lease": "pen_lease"}
# columns that are tied by an identity and therefore share a roll-up month set
JOINT = [
    ["sale_mix_cash", "sale_mix_finance", "sale_mix_lease"],
    ["dealer_profit", "vehicle_gross", "fi_income"],
    ["pen_cash", "pen_finance", "pen_lease"],
    ["my_mix_current", "my_mix_new", "my_mix_old"],
    ["msrp", "cftp", "cftp_pct_msrp"],
]
EMPTY_COLS = ["consumer_exp", "lease_monthly_payment_48", "trade_volume"]
SIG_COLS = {"retail_inventory"}


if os.environ.get("SYNTH_STEPS"):
    import json
    STEP_OF.update(json.loads(os.environ["SYNTH_STEPS"]))


def dec_of(step):
    if step >= 1:
        return 0
    return {0.5: 1, 0.2: 1, 0.1: 1, 0.05: 2, 0.01: 2}[step]


def quant(x, step):
    return np.rint(x / step) * step


def quant_sig(x, sig=3):
    """round to `sig` significant digits (integers); small values stay exact"""
    x = np.asarray(x, dtype=float)
    mag = np.floor(np.log10(np.maximum(np.abs(x), 1.0)))
    st = np.maximum(10.0 ** (mag - (sig - 1)), 1.0)
    return np.rint(x / st) * st


def qcol(c, X):
    if c in SIG_COLS:
        return quant_sig(X, 3)
    if c in STEP_OF:
        return quant(X, STEP_OF[c])
    return X


def repair_identities(Q, steps_note=None):
    """Q: dict col -> array (any shape) already quantised.  Enforce exact sum-to-100 / dealer_profit."""
    # pens: lease is the remainder
    if "pen_cash" in Q:
        Q["pen_lease"] = np.round(100.0 - Q["pen_cash"] - Q["pen_finance"], 1)
    # model-year mix: current is the remainder
    Q["my_mix_current"] = np.round(100.0 - Q["my_mix_new"] - Q["my_mix_old"], 1)
    # sale mix: finance is the remainder
    Q["sale_mix_finance"] = np.round(100.0 - Q["sale_mix_cash"] - Q["sale_mix_lease"], 1)
    Q["dealer_profit"] = Q["vehicle_gross"] + Q["fi_income"]
    with np.errstate(invalid="ignore", divide="ignore"):
        Q["cftp_pct_msrp"] = np.round(100.0 * Q["cftp"] / Q["msrp"], 1)


def nan_ffill_bfill(X):
    df = pd.DataFrame(X)
    df = df.ffill(axis=1).bfill(axis=1)
    return df.values


def aggregate(V, H, G, R, rowfallback):
    """leaf (L,T) -> entity-cut (nEC,T), plus ghost handling"""
    act = H["active"].astype(float)
    w = V["retail_sales"] * act
    den = G @ w
    cnt = G @ act
    AG = {}
    for c, x in V.items():
        if c in SUM_COLS or c in LAST_COLS:
            AG[c] = G @ (x * act)
            continue
        if c in OFFER_PEN:
            wt = w * V[OFFER_PEN[c]] / 100.0
        else:
            wt = w
        d = G @ wt
        num = G @ (x * wt)
        with np.errstate(invalid="ignore", divide="ignore"):
            AG[c] = np.where(d > 1e-9, num / d, np.nan)
        if c in OFFER_PEN:   # fall back to sales-weighted when nobody uses the program
            with np.errstate(invalid="ignore", divide="ignore"):
                alt = np.where(den > 0, (G @ (x * w)) / den, np.nan)
            AG[c] = np.where(np.isnan(AG[c]), alt, AG[c])
    # finance payments of an entity follow the loan formula applied to its own aggregated walk inputs
    for N in (60, 72, 84):
        x = V[f"finance_monthly_payment_{N}"]
        af, apr, trm = V[f"pw{N}_amount_financed"], V[f"pw{N}_apr"], V[f"pw{N}_term"]
        leaf_ratio = x / pmt(af, apr, trm)
        d = G @ w
        with np.errstate(invalid="ignore", divide="ignore"):
            rat = np.where(d > 0, (G @ (leaf_ratio * w)) / d, 1.0)
        AG[f"finance_monthly_payment_{N}"] = (pmt(AG[f"pw{N}_amount_financed"], AG[f"pw{N}_apr"],
                                                 AG[f"pw{N}_term"]) * rat)
    # identity-style derived columns
    with np.errstate(invalid="ignore", divide="ignore"):
        AG["cftp_pct_msrp"] = 100.0 * AG["cftp"] / AG["msrp"]
    ghost = R & (cnt == 0)
    return AG, ghost, cnt


def rollup(MV, W, Pm, mode):
    """MV (nEC,T) with NaN = absent; W weights; returns (nEC,nP) with NaN where nothing present"""
    pres = ~np.isnan(MV)
    X = np.where(pres, MV, 0.0)
    cntp = pres.astype(float) @ Pm
    if mode == "sum":
        out = X @ Pm
        return np.where(cntp > 0, out, np.nan)
    if mode == "last":
        out = np.full((MV.shape[0], Pm.shape[1]), np.nan)
        for j in range(Pm.shape[1]):
            ms = np.where(Pm[:, j] > 0)[0]
            sub = pres[:, ms]
            anyp = sub.any(axis=1)
            idx = sub.shape[1] - 1 - np.argmax(sub[:, ::-1], axis=1)
            v = X[:, ms][np.arange(MV.shape[0]), idx]
            out[:, j] = np.where(anyp, v, np.nan)
        return out
    Wp = np.where(pres, W, 0.0)
    num = (X * Wp) @ Pm
    den = Wp @ Pm
    unw = X @ Pm
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(den > 0, num / den, np.where(cntp > 0, unw / np.maximum(cntp, 1), np.nan))
    return out


# --------------------------------------------------------------------------------------
# 5. assembly
# --------------------------------------------------------------------------------------
def fmt_col(vals, mask, dec):
    out = np.full(len(vals), "", dtype=object)
    v = vals[mask]
    if len(v) == 0:
        return out
    if dec == 0:
        out[mask] = np.rint(v).astype(np.int64).astype(str).astype(object)
    else:
        fm = "%." + str(dec) + "f"
        out[mask] = np.array([fm % x for x in (v + 0.0).tolist()], dtype=object)
    return out


def build_panel(S, M, mcols, H, ecs, G, V, plist, pid, Pm):
    N = len(S)
    nEC = len(ecs)
    nP = len(plist)
    base = S.level.isin(["Model", "Series", "Nameplate", "OEM"]).values
    ec_cols = ["level", "entity", "nameplate", "segment", "is_aggregate", "fuel_type", "premium_flag"]
    key = S.loc[base, ec_cols].reset_index(drop=True)
    e2 = ecs.copy()
    e2["ec"] = np.arange(nEC)
    mg = key.merge(e2, how="left", on=ec_cols)
    rowec = np.full(N, -1, dtype=np.int64)
    rowec[base] = mg.ec.values
    assert (rowec[base] >= 0).all()
    mon = (S.period_type.values == "monthly")
    mt = np.array([MIDX.get(m, -1) for m in S.month.values])
    R = np.zeros((nEC, T), bool)
    R[rowec[mon], mt[mon]] = True
    midx_c = {c: i for i, c in enumerate(mcols)}
    # cell presence per (ec, month, col)
    PM = {}
    for c in mcols:
        if c in EMPTY_COLS:
            continue
        a = np.zeros((nEC, T), bool)
        a[rowec[mon], mt[mon]] = M[mon, midx_c[c]]
        PM[c] = a
    fb = int(np.where((ecs.level == "OEM") & (ecs.entity == "Industry") & (ecs.fuel_type == "All")
                      & (ecs.premium_flag == "All"))[0][0])

    AG, ghost, cnt = aggregate(V, H, G, R, fb)
    log(f"aggregated: ghost cells={ghost.sum()}")
    rng = np.random.default_rng(SEED + 7)
    # ---- ghost handling and monthly quantisation
    MQ = {}
    for c, X in AG.items():
        if c in SUM_COLS:
            gv = rng.integers(1, 7, X.shape).astype(float)
            gv[:, T - 1] = 1.0
            X = np.where(ghost, gv, X)
        elif c in LAST_COLS:
            X = np.where(ghost, rng.integers(0, 9, X.shape).astype(float), X)
        else:
            X = np.where(ghost, np.nan, X)
            X = nan_ffill_bfill(X)
            if np.isnan(X).any():
                fbv = AG[c][fb]
                X = np.where(np.isnan(X), fbv[None, :], X)
        MQ[c] = qcol(c, X)
    repair_identities(MQ)
    log("monthly values quantised")
    # ---- period roll-ups
    W = np.where(R, MQ["retail_sales"], 0.0)
    FULL = {}
    joint_of = {}
    for g in JOINT:
        for c in g:
            joint_of[c] = g
    for c in AG:
        if c in PW_COLS:
            MVc = np.where(R, MQ[c], np.nan)
        else:
            MVc = np.where(R & PM[c], MQ[c], np.nan)
            if c in joint_of:
                jp = np.ones((nEC, T), bool)
                for cc in joint_of[c]:
                    jp &= (R & PM[cc])
                MVj = np.where(jp, MQ[c], np.nan)
        mode = "sum" if c in SUM_COLS else ("last" if c in LAST_COLS else "wmean")
        if c in joint_of and c not in PW_COLS:
            PV = rollup(MVj, W, Pm, mode)
            # no month carries every cell of the identity group: use all months of the entity so
            # that the identity (sum to 100 / dealer_profit) still closes
            PV2 = rollup(np.where(R, MQ[c], np.nan), W, Pm, mode)
            PV = np.where(np.isnan(PV), PV2, PV)
        else:
            PV = rollup(MVc, W, Pm, mode)
        miss = np.isnan(PV)
        if miss.any():
            PV3 = rollup(np.where(R, MQ[c], np.nan), W, Pm, mode)
            PV = np.where(miss, PV3, PV)
        FULL[c] = np.concatenate([MQ[c], PV[:, T:]], axis=1)
    # quantise period part and repair identities there
    PQ = {}
    for c in AG:
        P = FULL[c][:, T:]
        PQ[c] = qcol(c, P)
    repair_identities(PQ)
    for c in AG:
        FULL[c][:, T:] = PQ[c]
    log("period roll-ups done")
    # ---- pick values per row
    ok = pid >= 0
    r_ec = np.where(ok, rowec, 0)
    r_p = np.where(ok, pid, 0)
    ROW = {c: FULL[c][r_ec, r_p] for c in AG}
    # rows that carry payment-walk inputs: the finance payment is the loan payment of the emitted inputs
    midx_c = {c: i for i, c in enumerate(mcols)}
    for N in (60, 72, 84):
        has = M[:, midx_c[f"pw{N}_apr"]] & ok
        pm_ = pmt(ROW[f"pw{N}_amount_financed"], ROW[f"pw{N}_apr"], ROW[f"pw{N}_term"])
        ROW[f"finance_monthly_payment_{N}"] = np.where(has, np.round(pm_ / 5.0) * 5.0,
                                                       ROW[f"finance_monthly_payment_{N}"])
    # ---- shares from rolled sales
    sales = ROW["retail_sales"]
    gk = (S.level.astype(str) + "|" + S.segment.astype(str) + "|" + S.fuel_type.astype(str) + "|"
          + S.premium_flag.astype(str) + "|" + pd.Series(pid).astype(str)).values
    codes, _ = pd.factorize(gk)
    nonagg = (S.is_aggregate.values == "0") & ok
    denom = np.bincount(codes[nonagg], weights=sales[nonagg], minlength=codes.max() + 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.where(denom[codes] > 0, sales / denom[codes] * 100.0, 0.0)
    # largest-remainder rounding to 0.1 so each (level, segment, cut, period) group sums to exactly 100.0
    idx = np.where(nonagg & (denom[codes] > 0))[0]
    sh10 = share[idx] * 10.0
    fl = np.floor(sh10 + 1e-9)
    fr = sh10 - fl
    c = codes[idx]
    order = np.lexsort((-fr, c))
    c_s = c[order]
    ng = codes.max() + 1
    rem = np.rint(1000.0 - np.bincount(c, weights=fl, minlength=ng)).astype(np.int64)
    first_pos = np.r_[0, np.flatnonzero(np.diff(c_s)) + 1]
    sizes = np.diff(np.r_[first_pos, len(c_s)])
    rank = np.arange(len(c_s)) - np.repeat(first_pos, sizes)
    add = rank < np.clip(rem[c_s], 0, None)
    fl[order[add]] += 1.0
    share_q = quant(share, STEP_OF["retail_share"])
    share_q[idx] = fl / 10.0
    # segment-aggregate rows (Model / Series level) split the whole market: share of the sum over all
    # segment aggregates of the same level, cut and period (largest-remainder, sums to exactly 100.0)
    segagg = (S.is_aggregate.values == "1") & S.level.isin(["Model", "Series"]).values & ok
    ia = np.where(segagg)[0]
    gk2 = (S.level.values[ia].astype(str) + "|" + S.fuel_type.values[ia].astype(str) + "|"
           + S.premium_flag.values[ia].astype(str) + "|" + pid[ia].astype(str))
    c2, _ = pd.factorize(gk2)
    den2 = np.bincount(c2, weights=sales[ia], minlength=c2.max() + 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        v2 = np.where(den2[c2] > 0, sales[ia] / den2[c2] * 1000.0, 0.0)
    fl2 = np.floor(v2 + 1e-9)
    fr2 = v2 - fl2
    order2 = np.lexsort((-fr2, c2))
    c2s = c2[order2]
    rem2 = np.rint(1000.0 - np.bincount(c2, weights=fl2, minlength=c2.max() + 1)).astype(np.int64)
    fp2 = np.r_[0, np.flatnonzero(np.diff(c2s)) + 1]
    rk2 = np.arange(len(c2s)) - np.repeat(fp2, np.diff(np.r_[fp2, len(c2s)]))
    fl2[order2[rk2 < np.clip(rem2[c2s], 0, None)]] += 1.0
    share_q[ia] = fl2 / 10.0
    ROW["retail_share"] = share_q
    return ROW, rowec, ok, FULL


def write_panel(S, M, mcols, header, meta_txt, ROW, ok, out_path):
    N = len(S)
    meta = list(meta_txt)
    ti = np.where(S.level.values == "Trade-In")[0]
    assert len(ti) == 1
    parts = meta[ti[0]].split(",")
    parts[7], parts[8] = "2026-10-12", "10/12"
    meta[ti[0]] = ",".join(parts)
    midx_c = {c: i for i, c in enumerate(mcols)}
    chunk = 40000
    with open(out_path, "w", newline="\n") as fh:
        fh.write(header + "\n")
        for s0 in range(0, N, chunk):
            s1 = min(N, s0 + chunk)
            cols_ = []
            for c in mcols:
                if c in EMPTY_COLS:
                    cols_.append([""] * (s1 - s0))
                    continue
                mk = M[s0:s1, midx_c[c]] & ok[s0:s1]
                cols_.append(fmt_col(ROW[c][s0:s1], mk, dec_of(STEP_OF[c])).tolist())
            lines = [",".join(t) for t in zip(meta[s0:s1], *cols_)]
            fh.write("\n".join(lines) + "\n")


def main():
    rng = np.random.default_rng(SEED)
    S, M, cols, mcols, meta_txt, header = load_structure()
    log(f"structure rows={len(S)}")
    plist, pid, Pm = period_table(S)
    H = build_hierarchy(S, M)
    ecs, G = build_entities(S, H)
    V, info = simulate_leaves(H, rng)
    log("leaf simulation done")
    ROW, rowec, ok, FULL = build_panel(S, M, mcols, H, ecs, G, V, plist, pid, Pm)
    out = os.path.join(HERE, OUT_NAME)
    write_panel(S, M, mcols, header, meta_txt, ROW, ok, out)
    log(f"wrote {out}")


if __name__ == "__main__":
    main()
