# -*- coding: utf-8 -*-
"""Contract Net en Python puro (solo biblioteca estandar). Utilidad U = 0.5*competencia + 0.3*cobertura + 0.2*(1-carga), tau_min = 0.35."""
from .config import cargar_umbrales, LATENCIA_NOMINAL

TASK_TYPES = ("SPECTRAL", "PROSODIC", "PLATEAU_STATS")
WEIGHTS = {"competence": 0.5, "coverage": 0.3, "availability": 0.2}
TAU_MIN = 0.35
ALPHA = 0.1


class Contractor:
    def __init__(self, agent_id, competence, rules_index, base_latency_ms, load=0.0):
        self.agent_id, self.competence, self.rules_index = agent_id, dict(competence), rules_index
        self.base_latency_ms, self.load = base_latency_ms, load

    def evaluate_cfp(self, cfp, extra_load=0.0):
        t = cfp["task_type"]; required = set(cfp["required_features"])
        covered = self.rules_index.get(t, set()) & required
        if t not in self.competence or not required or not covered: return None
        load = min(1.0, self.load + extra_load)
        est = self.base_latency_ms * (1.0 + load)
        if est > cfp["deadline_ms"]: return None
        return {"agent_id": self.agent_id, "task_type": t, "competence": self.competence[t],
                "coverage": len(covered) / len(required), "load": load, "est_latency_ms": round(est, 1)}


def utility(p):
    return WEIGHTS["competence"] * p["competence"] + WEIGHTS["coverage"] * p["coverage"] + WEIGHTS["availability"] * (1.0 - p["load"])


def contract_net(cfps, contractors, tau_min=TAU_MIN):
    extra = {c.agent_id: 0.0 for c in contractors}
    awards, unassigned, log = {}, [], []
    for cfp in cfps:
        props = []
        for c in contractors:
            p = c.evaluate_cfp(cfp, extra[c.agent_id])
            if p is not None:
                p["utility"] = round(utility(p), 4); props.append(p)
        valid = [p for p in props if p["utility"] >= tau_min]
        log.append({"task_type": cfp["task_type"], "n_bids": len(props), "n_valid": len(valid)})
        if not valid:
            unassigned.append(cfp["task_type"]); continue
        valid.sort(key=lambda p: (-p["utility"], p["est_latency_ms"], p["agent_id"]))
        w = valid[0]
        awards[cfp["task_type"]] = {"agent_id": w["agent_id"], "utility": w["utility"],
                                    "runner_up": valid[1]["agent_id"] if len(valid) > 1 else None}
        extra[w["agent_id"]] += cfp.get("cost", 0.2)
    status = "NO_BIDS" if not awards else ("PARTIAL" if unassigned else "AWARDED")
    return {"status": status, "awards": awards, "unassigned": unassigned, "log": log}


def update_competence(contractor, task_type, success):
    old = contractor.competence.get(task_type, 0.5)
    contractor.competence[task_type] = (1 - ALPHA) * old + ALPHA * (1.0 if success else 0.0)


# ---- tarea -> rasgos requeridos (derivado de las reglas calibradas)
TAREA_DE_RASGO = {"mel_kurt": "PLATEAU_STATS", "plateau_ratio": "PLATEAU_STATS", "peak_count": "PLATEAU_STATS",
                  "mel_mean": "PLATEAU_STATS", "mel_std": "PLATEAU_STATS", "mel_skew": "PLATEAU_STATS",
                  "spectral_flatness": "SPECTRAL", "spectral_centroid": "SPECTRAL", "hf_energy": "SPECTRAL",
                  "jitter": "PROSODIC", "shimmer": "PROSODIC", "f0_var": "PROSODIC"}


def subtareas_por_defecto(cfg=None):
    cfg = cfg or cargar_umbrales(); req = {}
    for ag in ("E", "Pr"):
        for r in cfg["reglas"][ag]: req.setdefault(TAREA_DE_RASGO[r["feature"]], []).append(r["feature"])
    return {"subtasks": [{"task_type": t, "required_features": f} for t, f in req.items()]}


def build_registry(cfg=None):
    """Contratistas con competencia historica = poder discriminante (max(AUC, 1-AUC)) medio de sus reglas calibradas."""
    cfg = cfg or cargar_umbrales(); comp = {"E": {}, "Pr": {}}; idx = {"E": {}, "Pr": {}}
    for ag in ("E", "Pr"):
        por_tarea = {}
        for r in cfg["reglas"][ag]:
            t = TAREA_DE_RASGO[r["feature"]]; por_tarea.setdefault(t, []).append(r)
        for t, rs in por_tarea.items():
            comp[ag][t] = sum(max(r["auc"], 1 - r["auc"]) for r in rs) / len(rs)
            idx[ag][t] = {r["feature"] for r in rs}
    return [Contractor("agente_espectral", comp["E"], idx["E"], LATENCIA_NOMINAL["E"] * 1000),
            Contractor("agente_prosodico", comp["Pr"], idx["Pr"], LATENCIA_NOMINAL["Pr"] * 1000)]
