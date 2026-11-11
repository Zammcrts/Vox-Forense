# -*- coding: utf-8 -*-
"""
analizar_resultados.py - Evaluacion del sistema VOX-Forense sobre rasgos reales (rasgos.csv)
 - Division 70/30 POR HABLANTE (evita fuga de informacion entre fragmentos de una misma voz)
 - Calibracion de umbrales solo con entrenamiento; evaluacion solo con prueba
 - Reglas de la ontologia (indicio de sintesis / rasgo de naturalidad / escalamiento)
 - Ablacion de agentes (32 coaliciones) y valores de Shapley
Uso: python analizar_resultados.py rasgos.csv
"""
import sys, json, itertools, re
from math import factorial
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

SEED = 42
Q = 0.20                       # cuantil que define las zonas de indicio y de naturalidad
TEST_FRAC = 0.30
AGENTS = ["P", "E", "Pr", "R", "X"]          # Perceptor, Espectral, Prosodico, Razonador, Explicador
NOMBRE = {"P": "Perceptor", "E": "Espectral", "Pr": "Prosódico", "R": "Razonador", "X": "Explicador"}
FEAT = {"E": ["spectral_flatness", "spectral_centroid", "hf_energy", "plateau_ratio", "peak_count",
              "mel_mean", "mel_std", "mel_skew", "mel_kurt"],
        "Pr": ["jitter", "shimmer", "f0_var"]}
W = dict(acc=.40, cov=.20, cons=.15, expl=.20, lat=.05)
LAT = {"P": 0.4, "E": 1.2, "Pr": 1.1, "R": 1.5, "X": 1.8}; TMAX = 6.0   # costos nominales de diseno (no medidos)


def shapley(players, v):
    n = len(players); phi = {}
    for i in players:
        others = [p for p in players if p != i]; tot = 0.0
        for k in range(len(others) + 1):
            w = factorial(k) * factorial(n - k - 1) / factorial(n)
            for S in itertools.combinations(others, k):
                S = frozenset(S); tot += w * (v[S | {i}] - v[S])
        phi[i] = tot
    return phi


def speaker(row):
    f = re.sub(r"_?\d+\.[A-Za-z0-9]+$", "", row.file)
    k = (f[:-2] if f.endswith("IA") else f.split("-")[-1]).lower()
    return "anap" if k == "anapau" else k          # voz real "anaPau" y su clon "AnaPIA" son la misma voz


def split_by_speaker(df, seed):
    rng = np.random.default_rng(seed)
    sp = df.speaker.unique(); n = df.speaker.nunique()
    for _ in range(1000):
        te = set(rng.choice(sp, size=max(1, round(TEST_FRAC * n)), replace=False))
        m = df.speaker.isin(te)
        if 0.26 <= m.mean() <= 0.34 and df[m].label.nunique() == 2 and df[~m].label.nunique() == 2:
            return df[~m].copy(), df[m].copy()
    raise RuntimeError("no se logro una division valida")


def calibrate(tr, nfeat=3, min_gap=0.10):
    """Elige por agente los rasgos con mayor poder (AUC en entrenamiento) y fija umbrales por cuantiles."""
    y = (tr.label == "fake").astype(int)
    rules = {"E": [], "Pr": []}
    for ag, cols in FEAT.items():
        sc = []
        for c in cols:
            ok = tr[c].notna()
            if ok.sum() < 30 or y[ok].nunique() < 2: continue
            auc = roc_auc_score(y[ok], tr.loc[ok, c]); sc.append((abs(auc - .5), auc, c))
        for gap, auc, c in sorted(sc, reverse=True)[:nfeat]:
            if gap < min_gap: continue
            fake_high = auc > .5
            real, fake = tr.loc[tr.label == "real", c].dropna(), tr.loc[tr.label == "fake", c].dropna()
            if fake_high: t_ind, t_nat = real.quantile(1 - Q), fake.quantile(Q)
            else: t_ind, t_nat = real.quantile(Q), fake.quantile(1 - Q)
            if (fake_high and t_nat > t_ind) or ((not fake_high) and t_nat < t_ind):   # zonas solapadas -> punto medio
                t_ind = t_nat = (t_ind + t_nat) / 2
            rules[ag].append(dict(feature=c, auc=round(float(auc), 3), fake_high=bool(fake_high),
                                  t_ind=float(t_ind), t_nat=float(t_nat)))
    return rules


def counts(te, rules):
    out = {}
    for ag in ("E", "Pr"):
        ind = np.zeros(len(te), int); nat = np.zeros(len(te), int)
        for r in rules[ag]:
            x = te[r["feature"]].to_numpy(float); ok = ~np.isnan(x)
            if r["fake_high"]: i, n = x > r["t_ind"], x < r["t_nat"]
            else: i, n = x < r["t_ind"], x > r["t_nat"]
            ind += (i & ok); nat += (n & ok)
        out[ag] = (ind, nat)
    return out


def counts_iniciales(te):
    """Umbrales iniciales de la ontologia (propuestos antes de ver datos)."""
    g = lambda c: te[c].to_numpy(float)
    E_ind = (g("plateau_ratio") >= .60).astype(int) + (g("hf_energy") < .02) + (g("spectral_flatness") >= .30)
    j, s, f = g("jitter"), g("shimmer"), g("f0_var")
    P_ind = (j < .002).astype(int) + (s < .01) + (f < .05)
    P_nat = ((j >= .002) & (j <= .02)).astype(int) + ((s >= .01) & (s <= .10)) + ((f >= .05) & (f <= .50))
    return {"E": (E_ind, np.zeros(len(te), int)), "Pr": (P_ind, P_nat)}


def evalS(S, te, C):
    S = set(S); n = len(te); real = (te.label == "real").to_numpy()
    ind = np.zeros(n, int); nat = np.zeros(n, int)
    if "P" in S:
        for ag in ("E", "Pr"):
            if ag in S: ind += C[ag][0]; nat += C[ag][1]
    have_R = ("R" in S) and ("P" in S) and (("E" in S) or ("Pr" in S))
    cov = have_R & ((ind + nat) > 0)
    fake_v = cov & (ind >= 2) & (nat <= 1)
    real_v = cov & (nat >= 2) & (ind == 0) & ~fake_v
    esc = cov & ~fake_v & ~real_v
    decisive = fake_v | real_v
    correct = ("X" in S) & ((fake_v & ~real) | (real_v & real))
    wrong = ("X" in S) & ((fake_v & real) | (real_v & ~real))
    conflict = (ind >= 1) & (nat >= 1)
    cons = np.where(conflict & ("X" not in S), 0.0, 1.0)
    c = 2 * ("P" in S) + (cov & True).astype(int) * 1 + (cov & ("X" in S)).astype(int)
    par = max([LAT[a] for a in S if a in ("E", "Pr")] or [0])
    lat = sum(LAT[a] for a in S if a not in ("E", "Pr")) + par
    m = dict(acc=correct.mean(), cov=cov.mean(), cons=cons.mean(), expl=(c / 4).mean(), lat=min(1, lat / TMAX),
             lat_s=lat, wrong=wrong.mean(), esc=(esc | (~cov & have_R) | ~("X" in S) * decisive).mean() if False else None)
    m["esc_rate"] = float((~decisive).mean()) if "X" in S else 1.0
    m["decisive"] = int(decisive.sum()); m["correct"] = int(correct.sum()); m["wrong"] = int(wrong.sum())
    m["fake_v"], m["real_v"], m["n"] = int(fake_v.sum()), int(real_v.sum()), n
    m["_pred"] = np.where(fake_v, "fake", np.where(real_v, "real", "esc"))
    return m


def u_of(m, w=W): return w["acc"] * m["acc"] + w["cov"] * m["cov"] + w["cons"] * m["cons"] + w["expl"] * m["expl"] - w["lat"] * m["lat"]


def run(te, C, w=W):
    M = {}
    for k in range(6):
        for S in itertools.combinations(AGENTS, k): M[frozenset(S)] = evalS(S, te, C)
    u0 = u_of(M[frozenset()], w)
    V = {S: u_of(m, w) - u0 for S, m in M.items()}
    return M, V, shapley(AGENTS, V)


def main(path):
    df = pd.read_csv(path)
    df["speaker"] = df.apply(speaker, axis=1)
    print("Audios:", len(df), df.label.value_counts().to_dict(), "| hablantes:", df.speaker.nunique())
    tr, te = split_by_speaker(df, SEED)
    print(f"Entrenamiento: {len(tr)} audios ({tr.speaker.nunique()} hablantes) | Prueba: {len(te)} audios ({te.speaker.nunique()} hablantes)")
    print(" prueba por clase:", te.label.value_counts().to_dict(), "| hablantes prueba:", sorted(te.speaker.unique()))
    rules = calibrate(tr)
    print("\nReglas calibradas (solo entrenamiento):")
    for ag in rules:
        for r in rules[ag]: print(f"  {NOMBRE[ag]:10s} {r['feature']:18s} AUC={r['auc']:.3f} falso_{'alto' if r['fake_high'] else 'bajo'} t_indicio={r['t_ind']:.5g} t_natural={r['t_nat']:.5g}")
    C = counts(te, rules)
    M, V, phi = run(te, C)
    full = M[frozenset(AGENTS)]
    print("\nSISTEMA COMPLETO (prueba):", {k: round(float(v), 3) for k, v in full.items() if not k.startswith("_") and k not in ("esc",) and v is not None})
    conf = pd.crosstab(te.label.to_numpy(), full["_pred"], rownames=["real"], colnames=["veredicto"])
    print(conf)
    resolved = full["correct"] + full["wrong"]
    print(f"  exactitud global={full['acc']:.3f} | escalados={full['esc_rate']:.3f} | errores={full['wrong']/len(te):.3f} | exactitud en resueltos={full['correct']/max(1,resolved):.3f}")
    print("\nABLACION y Shapley:")
    for nm, rem in [("Sistema completo", None), ("Sin Perceptor", "P"), ("Sin Razonador", "R"), ("Sin Explicador", "X"), ("Sin Prosódico", "Pr"), ("Sin Espectral", "E")]:
        S = frozenset(AGENTS) if rem is None else frozenset(a for a in AGENTS if a != rem); m = M[S]
        print(f"  {nm:18s} acc={m['acc']:.3f} cov={m['cov']:.3f} expl={m['expl']:.3f} lat={m['lat_s']:.1f}s v={V[S]:.3f}" + ("" if rem is None else f" | phi={phi[rem]:.3f}"))
    print("  suma phi =", round(sum(phi.values()), 3), " v(N) =", round(V[frozenset(AGENTS)], 3))
    solo = {a: M[frozenset(["P", "R", "X", a])] for a in ("E", "Pr")}
    for a, m in solo.items(): print(f"  Solo {NOMBRE[a]} (+P,R,X): acc={m['acc']:.3f} cov={m['cov']:.3f} errores={m['wrong']/len(te):.3f}")

    # --- umbrales iniciales de la ontologia, sin calibrar
    C0 = counts_iniciales(te); M0, V0, phi0 = run(te, C0); f0 = M0[frozenset(AGENTS)]
    print(f"\nUMBRALES INICIALES (sin calibrar): acc={f0['acc']:.3f} escalados={f0['esc_rate']:.3f} errores={f0['wrong']/len(te):.3f}")

    # --- linea base: modelos de aprendizaje automatico con los mismos rasgos (referencia)
    cols = FEAT["E"] + FEAT["Pr"]
    Xtr, Xte = tr[cols].fillna(tr[cols].median()), te[cols].fillna(tr[cols].median())
    ytr = (tr.label == "fake").astype(int); yte = (te.label == "fake").astype(int)
    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)).fit(Xtr, ytr)
    rf = RandomForestClassifier(n_estimators=300, random_state=SEED).fit(Xtr, ytr)
    base = {"logreg": float((lr.predict(Xte) == yte).mean()), "rf": float((rf.predict(Xte) == yte).mean())}
    print("LINEAS BASE (todos los rasgos, sin abstencion):", {k: round(v, 3) for k, v in base.items()})

    # --- sensibilidad a pesos (+-25 %) en la division fija
    rng = np.random.default_rng(1); ranks = []
    for _ in range(200):
        w = {k: W[k] * rng.uniform(.75, 1.25) for k in W}; s = sum(w.values()); w = {k: v / s for k, v in w.items()}
        _, _, p = run(te, C, w); ranks.append(tuple(sorted(AGENTS, key=lambda a: -p[a])))
    from collections import Counter
    rc = Counter(ranks).most_common(3)
    print("\nRankings Shapley bajo perturbacion de pesos (200):", [([NOMBRE[a] for a in r], n) for r, n in rc])

    # --- 100 divisiones por hablante (robustez)
    accs, escs, errs, accres, base_lr = [], [], [], [], []; PH = {a: [] for a in AGENTS}
    for s in range(100):
        try: a_tr, a_te = split_by_speaker(df, 1000 + s)
        except RuntimeError: continue
        rr = calibrate(a_tr); CC = counts(a_te, rr); MM, VV, pp = run(a_te, CC); ff = MM[frozenset(AGENTS)]
        accs.append(ff["acc"]); escs.append(ff["esc_rate"]); errs.append(ff["wrong"] / len(a_te))
        accres.append(ff["correct"] / max(1, ff["correct"] + ff["wrong"]))
        for a in AGENTS: PH[a].append(pp[a])
        Xa, Xb = a_tr[cols].fillna(a_tr[cols].median()), a_te[cols].fillna(a_tr[cols].median())
        m_ = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)).fit(Xa, (a_tr.label == "fake").astype(int))
        base_lr.append(float((m_.predict(Xb) == (a_te.label == "fake").astype(int)).mean()))
    f = lambda x: f"{np.mean(x):.3f} ± {np.std(x):.3f}"
    print(f"\n{len(accs)} DIVISIONES POR HABLANTE: exactitud {f(accs)} | escalados {f(escs)} | errores {f(errs)} | exactitud en resueltos {f(accres)} | reg.logística {f(base_lr)}")
    print("  Shapley medio ± sd:", {NOMBRE[a]: f(PH[a]) for a in AGENTS})
    order = Counter(tuple(sorted(AGENTS, key=lambda a, i=i: -PH[a][i])) for i in range(len(accs))).most_common(3)
    print("  Rankings más frecuentes:", [([NOMBRE[a] for a in r], n) for r, n in order])
    out = dict(n=len(df), n_tr=len(tr), n_te=len(te), rules=rules,
               full={k: (float(v) if isinstance(v, (int, float, np.floating)) else v) for k, v in full.items() if not k.startswith("_") and v is not None},
               conf=conf.to_dict(), phi={a: float(p) for a, p in phi.items()}, V={"".join(sorted(S)): float(v) for S, v in V.items()},
               abl={nm: dict(acc=float(M[frozenset(a for a in AGENTS if a != rem)]["acc"]), cov=float(M[frozenset(a for a in AGENTS if a != rem)]["cov"]),
                             expl=float(M[frozenset(a for a in AGENTS if a != rem)]["expl"]), v=float(V[frozenset(a for a in AGENTS if a != rem)]))
                    for nm, rem in [("sin_P", "P"), ("sin_R", "R"), ("sin_X", "X"), ("sin_Pr", "Pr"), ("sin_E", "E")]},
               base=base, inicial=dict(acc=float(f0["acc"]), esc=float(f0["esc_rate"]), wrong=float(f0["wrong"] / len(te))),
               rep=dict(acc=[float(np.mean(accs)), float(np.std(accs))], esc=[float(np.mean(escs)), float(np.std(escs))],
                        err=[float(np.mean(errs)), float(np.std(errs))], acc_res=[float(np.mean(accres)), float(np.std(accres))],
                        lr=[float(np.mean(base_lr)), float(np.std(base_lr))], phi={a: [float(np.mean(PH[a])), float(np.std(PH[a]))] for a in AGENTS}))
    json.dump(out, open("resultados.json", "w"), ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "rasgos.csv")
