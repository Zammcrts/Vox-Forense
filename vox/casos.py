# -*- coding: utf-8 -*-
"""Almacen de casos: los agentes intercambian solo un case_id corto; las cifras viven aqui (evita que el LLM las altere)."""
import threading
_lock = threading.Lock(); CASOS = {}; TRAZA = []

def caso(case_id):
    with _lock: return CASOS.setdefault(case_id, {"case_id": case_id})

def registrar(case_id, evento, **datos):
    with _lock:
        CASOS.setdefault(case_id, {"case_id": case_id}).update(datos)
        TRAZA.append({"case_id": case_id, "evento": evento, **{k: v for k, v in datos.items() if k != "facts"}})

def limpiar():
    with _lock: CASOS.clear(); TRAZA.clear()
