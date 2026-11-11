# -*- coding: utf-8 -*-
"""Herramientas del sistema. Cada una es una funcion pura (fn_*) mas un envoltorio @tool de CrewAI.
Los agentes intercambian un `case_id`; los datos viven en vox.casos (no se pasan cifras por el LLM)."""
import json, math, os
from . import casos as K
from .config import RANGOS, RUTA_ESCALAMIENTOS, cargar_umbrales
from .contract_net import TASK_TYPES, contract_net, build_registry
from . import ontologia as O
from .politica import decidir

NEXT_ACTION = {"AWARDED": "DELEGAR_A_GANADORES", "PARTIAL": "DELEGAR_ASIGNADAS_Y_MARCAR_BRECHA", "NO_BIDS": "ESCALAR_A_ANALISTA_HUMANO"}


def _fmt(facets):
    op = {"minExclusive": ">", "maxExclusive": "<", "minInclusive": ">=", "maxInclusive": "<="}
    return " y ".join("%s %.6g" % (op[k], v) for k, v in facets.items())


def case_id_de(audio_path):
    return os.path.basename(audio_path)


def _j(x): return json.dumps(x, ensure_ascii=False, default=float)


def _rasgos_de(ag, cfg):
    return [r["feature"] for r in cfg["reglas"][ag]]


# ------------------------------------------------------------------ Perceptor
def fn_extraer_y_validar_rasgos(audio_path, rasgos=None):
    """Extrae (o recibe ya calculados) los rasgos acusticos, los valida y los guarda como hechos del caso."""
    cid = case_id_de(audio_path)
    try:
        if rasgos is None:
            from .features import extraer
            rasgos = extraer(audio_path)
    except Exception as e:                      # noqa: BLE001
        K.registrar(cid, "error_percepcion", error=str(e)); return dict(case_id=cid, ok=False, error=str(e))
    facts, faltantes, avisos = {}, [], []
    for k, v in rasgos.items():
        if k in ("file", "label"): continue
        if v is None or (isinstance(v, float) and math.isnan(v)):
            faltantes.append(k); continue
        v = float(v); facts[k] = v
        if k in RANGOS and not (RANGOS[k][0] <= v <= RANGOS[k][1]): avisos.append("%s=%.6g fuera de rango %s" % (k, v, RANGOS[k]))
    K.registrar(cid, "percepcion", audio_path=audio_path, facts=facts, faltantes=faltantes, avisos=avisos)
    return dict(case_id=cid, ok=True, n_rasgos=len(facts), faltantes=faltantes, avisos=avisos, duracion_s=facts.get("duration_s"))


# ------------------------------------------------------------------ Manager (Contract Net)
def fn_contract_net_allocate(subtasks_json, deadline_ms=2000):
    try:
        subtasks = json.loads(subtasks_json)["subtasks"]
        if deadline_ms <= 0 or not subtasks: raise ValueError("deadline_ms debe ser > 0 y subtasks no vacio")
        cfps = []
        for s in subtasks:
            if s["task_type"] not in TASK_TYPES: raise ValueError("task_type invalido: %s" % s["task_type"])
            cfps.append({**s, "deadline_ms": deadline_ms})
        result = contract_net(cfps, build_registry()); result["next_action"] = NEXT_ACTION[result["status"]]
    except (KeyError, ValueError, TypeError) as exc:
        result = {"status": "ERROR", "error": str(exc), "next_action": "CORREGIR_ENTRADA_Y_REINTENTAR"}
    return result


# ------------------------------------------------------------------ Especialistas
def _hallazgos(case_id, ag, clave):
    cfg = cargar_umbrales(); c = K.caso(case_id); facts = c.get("facts")
    if facts is None: return dict(case_id=case_id, ok=False, error="El caso no tiene hechos: ejecuta primero la percepcion.")
    out = []
    for f in _rasgos_de(ag, cfg):
        r = O.regla_de(f, cfg); auc = next(x["auc"] for x in cfg["reglas"][ag] if x["feature"] == f)
        v = facts.get(f); estado = O.evaluar_rasgo(f, v, cfg)
        out.append(dict(rasgo=f, valor=None if v is None else round(v, 6), estado=estado,
                        clase_ontologica=(r["clase_indicio"] if estado == "indicio" else r["clase_naturalidad"] if estado == "naturalidad" else None),
                        peso_evidencia=round(abs(auc - .5) * 2, 3), tecnica_sospechada=r["tecnica"] if estado == "indicio" else None))
    K.registrar(case_id, "hallazgos_" + clave, **{"hallazgos_" + clave: out})
    return dict(case_id=case_id, ok=True, agente=clave, hallazgos=out,
                n_indicios=sum(h["estado"] == "indicio" for h in out), n_naturalidad=sum(h["estado"] == "naturalidad" for h in out),
                sin_evidencia=[h["rasgo"] for h in out if h["estado"] in ("sin_evidencia", "sin_valor")])


def fn_buscar_patrones_espectrales(case_id): return _hallazgos(case_id, "E", "espectral")
def fn_buscar_patrones_prosodicos(case_id): return _hallazgos(case_id, "Pr", "prosodico")


# ------------------------------------------------------------------ Razonador
def fn_razonar_con_ontologia(case_id, resultado_lote=None):
    """Inserta el caso como individuos de la ontologia, ejecuta HermiT y guarda las clases inferidas.
    `resultado_lote` permite reutilizar un razonamiento por lotes ya hecho (modo --lote)."""
    cfg = cargar_umbrales(); c = K.caso(case_id); facts = c.get("facts")
    if facts is None: return dict(case_id=case_id, ok=False, error="El caso no tiene hechos.")
    usados = {f: facts[f] for f in cfg["ontologia"] if f in facts}
    inf = resultado_lote or O.clasificar_lote({case_id: usados})[case_id]
    if not inf.get("consistente", False):
        K.registrar(case_id, "ontologia_inconsistente", ontologia=inf); return dict(case_id=case_id, ok=False, error="Ontologia inconsistente con los hechos del caso.")
    previos = (c.get("hallazgos_espectral") or []) + (c.get("hallazgos_prosodico") or [])
    disc = []
    for h in previos:
        if h["estado"] == "sin_valor": continue
        r = inf["rasgos"].get(h["rasgo"], {})
        if (h["estado"] == "indicio") != r.get("indicio", False) or (h["estado"] == "naturalidad") != r.get("naturalidad", False):
            disc.append(h["rasgo"])
    K.registrar(case_id, "razonamiento", ontologia=inf, discrepancias_agentes=disc)
    return dict(case_id=case_id, ok=True, consistente=True, clases_audio=inf["clases_audio"], n_indicios=inf["n_indicios"],
                n_naturalidad=inf["n_naturalidad"], tecnicas_sospechadas=inf["tecnicas"], discrepancias_con_especialistas=disc)


def fn_decidir_veredicto(case_id):
    c = K.caso(case_id); inf = c.get("ontologia")
    if not inf: return dict(case_id=case_id, ok=False, error="Falta el razonamiento ontologico.")
    d = decidir(inf["n_indicios"], inf["n_naturalidad"])
    d.update(n_indicios=inf["n_indicios"], n_naturalidad=inf["n_naturalidad"], contradictoria="AudioConEvidenciaContradictoria" in inf["clases_audio"])
    K.registrar(case_id, "veredicto", veredicto=d)
    return dict(case_id=case_id, ok=True, **d)


# ------------------------------------------------------------------ Explicador / Auditor
def fn_construir_explicacion(case_id):
    c = K.caso(case_id); v = c.get("veredicto"); inf = c.get("ontologia")
    if not v or not inf: return dict(case_id=case_id, ok=False, error="Faltan veredicto u ontologia: no se puede explicar sin respaldo.")
    cfg = cargar_umbrales(); hs = (c.get("hallazgos_espectral") or []) + (c.get("hallazgos_prosodico") or [])
    lineas = []
    for h in hs:
        if h["estado"] in ("indicio", "naturalidad"):
            r = O.regla_de(h["rasgo"], cfg)
            lineas.append("%s = %s -> %s (clase %s; indicio si valor %s, naturalidad si valor %s)" % (h["rasgo"], h["valor"], h["estado"], h["clase_ontologica"],
                          _fmt(r["umbral_indicio"]), _fmt(r["umbral_naturalidad"])))
    sin = [h["rasgo"] for h in hs if h["estado"] not in ("indicio", "naturalidad")]
    etiqueta = {"SINTETICO": "voz SINTETICA", "AUTENTICO": "voz AUTENTICA", "ESCALAR": "ESCALADO a analista humano"}[v["veredicto"]]
    txt = ["Veredicto: %s (regla %s)." % (etiqueta, v["regla"]), "Motivo: " + v["motivo"],
           "Hechos y reglas aplicadas:"] + ["  - " + l for l in lineas]
    if sin: txt.append("Rasgos sin evidencia (zona intermedia o sin valor): " + ", ".join(sin) + ".")
    if v["contradictoria"]: txt.append("La ontologia clasifico el audio como AudioConEvidenciaContradictoria: hay indicios de sintesis y rasgos de naturalidad a la vez.")
    if inf["tecnicas"]: txt.append("Tecnicas de sintesis sospechadas (hipotesis de la ontologia, no validadas): " + ", ".join(inf["tecnicas"]) + ".")
    if c.get("faltantes"): txt.append("Rasgos no disponibles: " + ", ".join(c["faltantes"]) + ".")
    txt.append("Limite: umbrales calibrados con un corpus propio; no se garantiza generalizacion a otros generadores o grabaciones.")
    K.registrar(case_id, "explicacion", explicacion="\n".join(txt))
    return dict(case_id=case_id, ok=True, explicacion="\n".join(txt))


def fn_escalar_a_analista(case_id, motivo):
    RUTA_ESCALAMIENTOS.parent.mkdir(parents=True, exist_ok=True)
    reg = dict(case_id=case_id, motivo=motivo, veredicto=K.caso(case_id).get("veredicto"))
    with open(RUTA_ESCALAMIENTOS, "a", encoding="utf-8") as f: f.write(_j(reg) + "\n")
    K.registrar(case_id, "escalamiento", escalado=True, motivo_escalamiento=motivo)
    return dict(case_id=case_id, ok=True, escalado=True, registro=str(RUTA_ESCALAMIENTOS))


# ================================================================== envoltorios CrewAI
try:
    from crewai.tools import tool
except ImportError:           # permite usar el modo directo sin instalar crewai
    tool = None

if tool is not None:
    @tool("extraer_y_validar_rasgos")
    def extraer_y_validar_rasgos(audio_path: str) -> str:
        """Extrae y valida el vector de rasgos acusticos de un audio y lo guarda como hechos del caso.
        Args: audio_path: ruta del archivo de audio (mp3, m4a, wav...). Returns: JSON con case_id, rasgos validos, faltantes y avisos."""
        return _j(fn_extraer_y_validar_rasgos(audio_path))

    @tool("contract_net_allocate")
    def contract_net_allocate(subtasks_json: str, deadline_ms: int = 2000) -> str:
        """Asigna subtareas de analisis forense al agente especialista mas competente con el protocolo Contract Net.
        Args: subtasks_json: JSON {"subtasks":[{"task_type":"SPECTRAL|PROSODIC|PLATEAU_STATS","required_features":["..."]}]};
        deadline_ms: plazo maximo por subtarea en ms (> 0). Returns: JSON con status, awards, unassigned, log y next_action."""
        return _j(fn_contract_net_allocate(subtasks_json, deadline_ms))

    @tool("buscar_patrones_espectrales")
    def buscar_patrones_espectrales(case_id: str) -> str:
        """Evalua los rasgos espectrales del caso contra las clases de la ontologia (indicio de sintesis / naturalidad) con su peso de evidencia.
        Args: case_id: identificador del caso devuelto por la percepcion. Returns: JSON con hallazgos."""
        return _j(fn_buscar_patrones_espectrales(case_id))

    @tool("buscar_patrones_prosodicos")
    def buscar_patrones_prosodicos(case_id: str) -> str:
        """Evalua los rasgos prosodicos (jitter, variabilidad de F0...) del caso contra las clases de la ontologia.
        Args: case_id: identificador del caso. Returns: JSON con hallazgos."""
        return _j(fn_buscar_patrones_prosodicos(case_id))

    @tool("razonar_con_ontologia")
    def razonar_con_ontologia(case_id: str) -> str:
        """Inserta el caso en la ontologia OWL, ejecuta el razonador HermiT y devuelve las clases inferidas, el conteo de indicios y de rasgos de naturalidad.
        Args: case_id: identificador del caso. Returns: JSON con clases_audio, n_indicios, n_naturalidad y discrepancias."""
        return _j(fn_razonar_con_ontologia(case_id))

    @tool("decidir_veredicto")
    def decidir_veredicto(case_id: str) -> str:
        """Aplica la politica de decision (SINTETICO / AUTENTICO / ESCALAR) sobre lo inferido por la ontologia. Es determinista: no la sustituyas por tu criterio.
        Args: case_id: identificador del caso. Returns: JSON con veredicto, regla y motivo."""
        return _j(fn_decidir_veredicto(case_id))

    @tool("construir_explicacion")
    def construir_explicacion(case_id: str) -> str:
        """Construye la cadena percepcion -> hechos -> reglas -> conclusion con respaldo en la traza del caso.
        Args: case_id: identificador del caso. Returns: JSON con la explicacion."""
        return _j(fn_construir_explicacion(case_id))

    @tool("escalar_a_analista")
    def escalar_a_analista(case_id: str, motivo: str) -> str:
        """Registra el caso para revision de un analista forense humano (usar cuando el veredicto sea ESCALAR).
        Args: case_id: identificador del caso; motivo: razon del escalamiento. Returns: JSON de confirmacion."""
        return _j(fn_escalar_a_analista(case_id, motivo))
