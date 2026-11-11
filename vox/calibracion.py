# -*- coding: utf-8 -*-
"""Calibra los umbrales con un CSV de rasgos y regenera la ontologia calibrada (.owx).
Uso: python main.py calibrar datos/rasgos.csv [--todo]
Por defecto calibra solo con el 70 % de las voces (misma division por hablante del reporte, semilla 42)."""
import json, sys
from datetime import date
import pandas as pd
from .config import RAIZ, RUTA_ONTOLOGIA, RUTA_UMBRALES

sys.path.insert(0, str(RAIZ / "evaluacion")); sys.path.insert(0, str(RAIZ / "ontologia"))
import analizar_resultados as A      # noqa: E402
import gen_owx                        # noqa: E402


def calibrar(csv, todo=False, semilla=42):
    df = pd.read_csv(csv)
    df["speaker"] = df.apply(A.speaker, axis=1)
    if todo:
        tr, te = df, df.iloc[0:0]
    else:
        tr, te = A.split_by_speaker(df, semilla)
    reglas = A.calibrate(tr)
    meta = dict(fecha=str(date.today()), n_audios=len(df), n_entrenamiento=len(tr), n_prueba=len(te),
                hablantes_entrenamiento=sorted(tr.speaker.unique().tolist()),
                hablantes_prueba=sorted(te.speaker.unique().tolist()) if len(te) else [],
                semilla=semilla, cuantil=A.Q, criterio="AUC en entrenamiento; zonas por cuantiles de la clase opuesta",
                nota="Umbrales derivados de un corpus propio; revisar antes de usar con otros generadores o grabaciones.")
    cfg = dict(meta=meta, reglas=reglas,
               ontologia={f: dict(zip(("base", "indicio", "naturalidad", "tecnica"), gen_owx.FEATURE_ONT[f][:4]))
                          for ag in reglas for f in (r["feature"] for r in reglas[ag])})
    RUTA_UMBRALES.parent.mkdir(parents=True, exist_ok=True)
    json.dump(cfg, open(RUTA_UMBRALES, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    generar_ontologia(reglas)
    return cfg


def generar_ontologia(reglas, destino=None):
    gen_owx.CAL = reglas
    texto = gen_owx.build()
    destino = destino or RUTA_ONTOLOGIA
    destino.parent.mkdir(parents=True, exist_ok=True)
    open(destino, "w", encoding="utf-8").write(texto)
    return destino
