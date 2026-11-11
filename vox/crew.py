# -*- coding: utf-8 -*-
"""Ensamblado de la crew jerarquica (manager fuera de `agents`) y ejecucion de un caso."""
from crewai import Crew, Process
from . import casos as K
from .agentes import crear_agentes, crear_llm
from .tareas import crear_tareas
from .herramientas import case_id_de


def _traza_tarea(out):
    K.TRAZA.append({"evento": "task_callback", "resumen": str(getattr(out, "summary", ""))[:200]})


def construir_crew(llm=None, verbose=True):
    manager, perceptor, espectral, prosodico, razonador, explicador = crear_agentes(llm)
    tareas = crear_tareas(perceptor, razonador, explicador)
    return Crew(agents=[perceptor, espectral, prosodico, razonador, explicador], tasks=tareas,
                process=Process.hierarchical, manager_agent=manager, verbose=verbose,
                task_callback=_traza_tarea)


def analizar_con_crew(audio_path, llm=None, verbose=True):
    """Ejecuta la crew sobre un audio. El veredicto autoritativo es el que dejo la herramienta decidir_veredicto en el almacen
    de casos (no el texto libre del LLM); el texto del LLM se devuelve como `informe_llm`."""
    cid = case_id_de(audio_path)
    crew = construir_crew(llm or crear_llm(), verbose)
    salida = crew.kickoff(inputs={"audio_path": audio_path, "case_id": cid})
    c = K.caso(cid); v = c.get("veredicto")
    return dict(case_id=cid, veredicto=v["veredicto"] if v else None, detalle=v, explicacion=c.get("explicacion"),
                informe_llm=str(salida), coincide_con_herramienta=bool(v) and v["veredicto"] in str(salida).upper().replace("SINTÉTICO", "SINTETICO").replace("AUTÉNTICO", "AUTENTICO"))
