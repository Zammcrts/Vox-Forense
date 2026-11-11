# -*- coding: utf-8 -*-
"""Tareas T1-T5 del flujo. Los marcadores {audio_path} y {case_id} se rellenan con kickoff(inputs=...)."""
import json
from crewai import Task
from .contract_net import subtareas_por_defecto


def crear_tareas(perceptor, razonador, explicador):
    plan = json.dumps(subtareas_por_defecto(), ensure_ascii=False)
    t1 = Task(description="Percepcion. Usa extraer_y_validar_rasgos con audio_path='{audio_path}'. Reporta el case_id, los rasgos faltantes y los avisos de rango. Usa SIEMPRE ese case_id en las tareas siguientes.",
              expected_output="JSON breve con case_id, numero de rasgos validos, faltantes y avisos.", agent=perceptor)
    t2 = Task(description="Asignacion y analisis espectral. Con contract_net_allocate usando subtasks_json=" + plan + " y deadline_ms=2000, obtén la adjudicacion. "
                          "Delega al agente que gane la tarea SPECTRAL (y PLATEAU_STATS) la busqueda de patrones espectrales del case_id '{case_id}'.",
              expected_output="Resultado de la licitacion (status, ganadores y utilidades) y los hallazgos espectrales con clase ontologica y peso de evidencia.", context=[t1])
    t3 = Task(description="Analisis prosodico. Delega al agente que gane la tarea PROSODIC la busqueda de patrones prosodicos del case_id '{case_id}'. Si la licitacion termino en PARTIAL o NO_BIDS, indicalo como brecha de conocimiento.",
              expected_output="Hallazgos prosodicos con clase ontologica y peso de evidencia, o la declaracion explicita de brecha.", context=[t2])
    t4 = Task(description="Razonamiento ontologico. Ejecuta razonar_con_ontologia y luego decidir_veredicto para el case_id '{case_id}'. Reporta tal cual el veredicto, la regla, los conteos y cualquier discrepancia con los especialistas. No cambies el veredicto de la herramienta.",
              expected_output="JSON con clases inferidas por la ontologia, conteos, discrepancias y veredicto (SINTETICO, AUTENTICO o ESCALAR) con su regla.", agent=razonador, context=[t2, t3])
    t5 = Task(description="Explicacion y auditoria. Ejecuta construir_explicacion para el case_id '{case_id}'. Si el veredicto es ESCALAR, ejecuta tambien escalar_a_analista con el motivo. Redacta un informe breve en espanol que use SOLO hechos presentes en la traza.",
              expected_output="Informe en espanol: veredicto, cadena percepcion -> hechos -> reglas -> conclusion y limites. Si se escalo, el registro del escalamiento.", agent=explicador, context=[t1, t2, t3, t4])
    return [t1, t2, t3, t4, t5]
