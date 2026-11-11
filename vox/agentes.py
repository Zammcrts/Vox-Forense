# -*- coding: utf-8 -*-
"""Agentes de CrewAI (fichas de la Seccion 1 del diseno): manager + 5 especialistas."""
from crewai import Agent, LLM
from .config import LLM_MODELO
from . import herramientas as H


def crear_llm(modelo=None):
    return LLM(model=modelo or LLM_MODELO, temperature=0)       # temperature=0: reproducibilidad para las replicas de Shapley


def crear_agentes(llm=None):
    llm = llm or crear_llm()
    comun = dict(llm=llm, verbose=True)
    manager = Agent(role="Coordinador Forense de Audio",
        goal="Descomponer cada caso de audio en subtareas de analisis, asignarlas al especialista mas competente mediante Contract Net, validar la coherencia de los resultados y decidir si el caso se resuelve o se escala a un analista humano.",
        backstory="Dirigio durante anos un laboratorio de analisis forense de audio. Sabe que ningun especialista domina todas las familias de rasgos y que una mala asignacion cuesta tiempo y errores. Delega con evidencia (propuestas y competencia historica), exige resultados trazables y prefiere escalar a un humano antes que cerrar un caso sin respaldo.",
        tools=[H.contract_net_allocate], allow_delegation=True, max_iter=8, **comun)
    perceptor = Agent(role="Analista de Percepcion de Audio",
        goal="Validar y normalizar el vector de caracteristicas del audio y convertirlo en hechos estructurados listos para la ontologia, senalando valores faltantes o fuera de rango.",
        backstory="Ingeniera de senales que paso de procesar espectrogramas a limpiar datos para sistemas de razonamiento. Desconfia de cualquier numero que no tenga unidad, rango esperado y procedencia.",
        tools=[H.extraer_y_validar_rasgos], allow_delegation=False, **comun)
    espectral = Agent(role="Especialista en Artefactos Espectrales",
        goal="Identificar patrones espectrales asociados a sintesis (centroide, energia de alta frecuencia, curtosis del espectrograma mel) y vincularlos con clases de la ontologia con un grado de evidencia.",
        backstory="Fonetista computacional que estudio como los vocoders dejan huellas en el espectro que el oido no percibe. Reporta siempre que evidencia observo y cual le falta.",
        tools=[H.buscar_patrones_espectrales], allow_delegation=False, **comun)
    prosodico = Agent(role="Especialista en Prosodia y Voz",
        goal="Evaluar jitter, shimmer y variabilidad de F0 para detectar una prosodia antinatural y asociar los hallazgos con clases de la ontologia con un grado de evidencia.",
        backstory="Logopeda forense reconvertida al analisis automatico. Sabe que una voz real es imperfecta de forma caracteristica y que la ausencia de ese ruido natural tambien es un indicio.",
        tools=[H.buscar_patrones_prosodicos], allow_delegation=False, **comun)
    razonador = Agent(role="Razonador Ontologico",
        goal="Insertar la instancia en la ontologia, ejecutar el razonador OWL, arbitrar conflictos entre reglas y determinar si el conocimiento es suficiente para emitir un veredicto.",
        backstory="Ingeniero de conocimiento obsesionado con la consistencia logica. Ante dos reglas que se contradicen no elige al azar: aplica prioridades y evidencia, y deja constancia de la decision. El veredicto lo emite siempre la herramienta decidir_veredicto.",
        tools=[H.razonar_con_ontologia, H.decidir_veredicto], allow_delegation=False, **comun)
    explicador = Agent(role="Explicador y Auditor de Decisiones",
        goal="Producir una explicacion en lenguaje natural con la cadena percepcion -> hechos -> reglas -> conclusion, verificar que cada afirmacion tenga respaldo en la traza y escalar al analista humano cuando el conocimiento sea insuficiente.",
        backstory="Auditora que traduce razonamientos formales a informes entendibles para analistas. No acepta una conclusion sin poder senalar la regla y el hecho que la sostienen.",
        tools=[H.construir_explicacion, H.escalar_a_analista], allow_delegation=False, **comun)
    return manager, perceptor, espectral, prosodico, razonador, explicador
