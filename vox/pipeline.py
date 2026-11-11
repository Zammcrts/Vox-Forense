# -*- coding: utf-8 -*-
"""Modo directo (sin LLM): ejecuta el mismo flujo T1-T5 llamando a las funciones de las herramientas.
Sirve para evaluar en lote, reproducir resultados y probar sin clave de API."""
import glob, os
import pandas as pd
from . import casos as K
from . import herramientas as H
from .config import cargar_umbrales
from .contract_net import subtareas_por_defecto
from . import ontologia as O
import json

EXT = (".mp3", ".m4a", ".wav", ".flac", ".ogg", ".mp4")


def _flujo(audio_path, rasgos=None, resultado_lote=None):
    cid = H.case_id_de(audio_path)
    t1 = H.fn_extraer_y_validar_rasgos(audio_path, rasgos)
    if not t1["ok"]: return dict(case_id=cid, veredicto="ERROR", error=t1["error"])
    lic = H.fn_contract_net_allocate(json.dumps(subtareas_por_defecto()))
    ejecutores = {w["agent_id"] for w in lic["awards"].values()}
    if "agente_espectral" in ejecutores: H.fn_buscar_patrones_espectrales(cid)
    if "agente_prosodico" in ejecutores: H.fn_buscar_patrones_prosodicos(cid)
    t4 = H.fn_razonar_con_ontologia(cid, resultado_lote)
    if not t4["ok"]: return dict(case_id=cid, veredicto="ERROR", error=t4["error"])
    v = H.fn_decidir_veredicto(cid)
    ex = H.fn_construir_explicacion(cid)
    if v["veredicto"] == "ESCALAR": H.fn_escalar_a_analista(cid, v["motivo"])
    return dict(case_id=cid, licitacion=lic["status"], veredicto=v["veredicto"], regla=v["regla"], n_indicios=v["n_indicios"],
                n_naturalidad=v["n_naturalidad"], contradictoria=v["contradictoria"], explicacion=ex["explicacion"])


def analizar_directo(audio_path):
    K.limpiar(); return _flujo(audio_path)


def analizar_lote(carpeta=None, csv=None, salida=None):
    """Procesa una carpeta de audios o un CSV de rasgos ya extraidos. HermiT se ejecuta una sola vez para todo el lote."""
    cfg = cargar_umbrales(); K.limpiar(); usados = list(cfg["ontologia"])
    if csv:
        df = pd.read_csv(csv); filas = {r["file"]: r.to_dict() for _, r in df.iterrows()}
        origen = {k: k for k in filas}
    else:
        from .features import extraer
        archivos = sorted(f for f in glob.glob(os.path.join(carpeta, "**", "*"), recursive=True) if f.lower().endswith(EXT))
        filas = {}
        for f in archivos:
            try: filas[os.path.basename(f)] = extraer(f)
            except Exception as e: print("ERROR", f, e)           # noqa: E722
        origen = {os.path.basename(f): f for f in archivos}
    casos = {k: {c: r.get(c) for c in usados if c in r} for k, r in filas.items()}
    lote = O.clasificar_lote(casos)
    res = []
    for k, r in filas.items():
        out = _flujo(origen.get(k, k), rasgos=r, resultado_lote=lote[k]); out.pop("explicacion", None)
        if "label" in r: out["etiqueta_real"] = r["label"]
        res.append(out)
    df = pd.DataFrame(res)
    if salida: df.to_csv(salida, index=False)
    return df
