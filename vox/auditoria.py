# -*- coding: utf-8 -*-
"""Auditoria de contribuciones con valores de Shapley (5 jugadores, 32 coaliciones) sobre un CSV de rasgos con etiqueta.
Usa los umbrales de la ontologia calibrada. La latencia usa costos nominales de diseno (no medidos)."""
import sys
import numpy as np, pandas as pd
from .config import RAIZ, NOMBRE_AGENTE, cargar_umbrales
sys.path.insert(0, str(RAIZ / "evaluacion"))
import analizar_resultados as A      # noqa: E402


def auditar(csv, solo_prueba=True):
    cfg = cargar_umbrales(); df = pd.read_csv(csv); df["speaker"] = df.apply(A.speaker, axis=1)
    if solo_prueba and cfg["meta"].get("hablantes_prueba"): df = df[df.speaker.isin(cfg["meta"]["hablantes_prueba"])]
    C = A.counts(df, cfg["reglas"]); M, V, phi = A.run(df, C)
    full = M[frozenset(A.AGENTS)]
    tabla = pd.DataFrame([dict(agente=NOMBRE_AGENTE[a], shapley=phi[a],
                               v_sin_agente=V[frozenset(x for x in A.AGENTS if x != a)],
                               exactitud_sin_agente=M[frozenset(x for x in A.AGENTS if x != a)]["acc"]) for a in A.AGENTS]).sort_values("shapley", ascending=False)
    return dict(n=len(df), tabla=tabla, suma_phi=float(sum(phi.values())), v_N=float(V[frozenset(A.AGENTS)]),
                exactitud_global=float(full["acc"]), escalados=float(full["esc_rate"]), errores=float(full["wrong"] / len(df)),
                exactitud_resueltos=float(full["correct"] / max(1, full["correct"] + full["wrong"])))
