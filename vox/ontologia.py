# -*- coding: utf-8 -*-
"""Acceso a la ontologia OWL (.owx): umbrales leidos del propio archivo y razonamiento con HermiT.

 - umbrales(): lee del XML los axiomas  <Clase> == <ClaseBase> and valor(facet)  => el conocimiento vive en la ontologia.
 - clasificar_lote(): inserta cada audio y sus rasgos como individuos, ejecuta HermiT y devuelve las clases inferidas.
   Se usa mundo abierto (OWA): la ontologia infiere pertenencia a clases, el conteo de evidencia lo hace la politica."""
import math, re, threading
import xml.etree.ElementTree as ET
from functools import lru_cache
from .config import RUTA_ONTOLOGIA, cargar_umbrales

OWL = "{http://www.w3.org/2002/07/owl#}"
CLASES_AUDIO = ("AudioSospechoso", "AudioSospechosoDeVocoderGAN", "AudioConRasgosDeNaturalidad",
                "AudioConEvidenciaContradictoria", "AudioQueRequiereRevisionHumana")
_lock = threading.Lock()


def _seguro(s):
    return re.sub(r"[^A-Za-z0-9_]", "_", s)


@lru_cache(maxsize=4)
def umbrales(ruta=None):
    """Devuelve {clase_equivalente: (clase_base, facet, valor)} leyendo los axiomas EquivalentClasses del .owx."""
    ruta = ruta or str(RUTA_ONTOLOGIA)
    out = {}
    for eq in ET.parse(ruta).getroot().iter(OWL + "EquivalentClasses"):
        cl = [c for c in eq if c.tag == OWL + "Class"]
        inter = eq.find(OWL + "ObjectIntersectionOf")
        if len(cl) != 1 or inter is None: continue
        base = [c.get("IRI").lstrip("#") for c in inter if c.tag == OWL + "Class"]
        fr = inter.find(".//" + OWL + "FacetRestriction")
        if not base or fr is None: continue
        facets = {f.get("facet").split("#")[-1]: float(f.find(OWL + "Literal").text)
                  for f in inter.iter(OWL + "FacetRestriction")}
        out[cl[0].get("IRI").lstrip("#")] = (base[0], facets)
    return out


def regla_de(feature, cfg=None):
    """Regla de un rasgo: clases de indicio/naturalidad y sus umbrales, tomados de la ontologia."""
    cfg = cfg or cargar_umbrales()
    m = cfg["ontologia"][feature]; u = umbrales()
    return dict(feature=feature, base=m["base"], clase_indicio=m["indicio"], clase_naturalidad=m["naturalidad"],
                tecnica=m["tecnica"], umbral_indicio=u[m["indicio"]][1], umbral_naturalidad=u[m["naturalidad"]][1])


def _cumple(valor, facets):
    ok = True
    for k, v in facets.items():
        ok &= {"minExclusive": valor > v, "maxExclusive": valor < v, "minInclusive": valor >= v, "maxInclusive": valor <= v}[k]
    return ok


def evaluar_rasgo(feature, valor, cfg=None):
    """Evaluacion rapida (sin JVM) usando los umbrales de la ontologia. Devuelve 'indicio' | 'naturalidad' | 'sin_evidencia'."""
    if valor is None or (isinstance(valor, float) and math.isnan(valor)): return "sin_valor"
    r = regla_de(feature, cfg)
    if _cumple(valor, r["umbral_indicio"]): return "indicio"
    if _cumple(valor, r["umbral_naturalidad"]): return "naturalidad"
    return "sin_evidencia"


def _ancestros(ind):
    nombres = set()
    for c in ind.is_a:
        if hasattr(c, "ancestors"): nombres |= {a.name for a in c.ancestors() if hasattr(a, "name")}
    return nombres


def _aserciones(casos, cfg):
    """Axiomas de aserciones (individuos) en OWL/XML. Se usa xsd:double para que coincida con el rango de `valor`."""
    from xml.sax.saxutils import escape
    ind = lambda n: '<NamedIndividual IRI="#%s"/>' % n
    cls = lambda c: '<Class IRI="#%s"/>' % c
    xs, nombres = [], {}
    for cid, feats in casos.items():
        a = _seguro("audio_" + cid); nombres[cid] = (a, {}); grupo = [a]
        xs += ['<Declaration>%s</Declaration>' % ind(a), '<ClassAssertion>%s%s</ClassAssertion>' % (cls("Audio"), ind(a)),
               '<DataPropertyAssertion><DataProperty IRI="#identificadorDeAudio"/>%s<Literal datatypeIRI="http://www.w3.org/2001/XMLSchema#string">%s</Literal></DataPropertyAssertion>' % (ind(a), escape(cid))]
        for f, v in feats.items():
            if f not in cfg["ontologia"] or v is None or (isinstance(v, float) and math.isnan(v)): continue
            fi = _seguro("%s__%s" % (cid, f)); nombres[cid][1][f] = fi; grupo.append(fi)
            xs += ['<Declaration>%s</Declaration>' % ind(fi),
                   '<ClassAssertion>%s%s</ClassAssertion>' % (cls(cfg["ontologia"][f]["base"]), ind(fi)),
                   '<DataPropertyAssertion><DataProperty IRI="#valor"/>%s<Literal datatypeIRI="http://www.w3.org/2001/XMLSchema#double">%r</Literal></DataPropertyAssertion>' % (ind(fi), float(v)),
                   '<ObjectPropertyAssertion><ObjectProperty IRI="#tieneCaracteristica"/>%s%s</ObjectPropertyAssertion>' % (ind(a), ind(fi))]
        if len(grupo) > 1:       # distintos solo dentro de cada audio (evita el costo cuadratico en lotes grandes)
            xs.append('<DifferentIndividuals>%s</DifferentIndividuals>' % "".join(ind(n) for n in grupo))
    return "\n".join(xs), nombres


def clasificar_lote(casos, ruta=None, inferir_tecnicas=True):
    """casos: {id: {rasgo: valor}}. Inserta los individuos, ejecuta HermiT y devuelve por caso:
       {consistente, clases_audio, rasgos: {rasgo: {clase_inferida, indicio, naturalidad}}, n_indicios, n_naturalidad, tecnicas}"""
    import os, tempfile
    from owlready2 import World, sync_reasoner_hermit, OwlReadyInconsistentOntologyError
    cfg = cargar_umbrales(); ruta = str(ruta or RUTA_ONTOLOGIA)
    xml, nombres = _aserciones(casos, cfg)
    base = open(ruta, encoding="utf-8").read()
    texto = base.replace("</Ontology>", xml + "\n</Ontology>")
    with _lock, tempfile.TemporaryDirectory() as d:
        tmp = os.path.join(d, "instancia.owx"); open(tmp, "w", encoding="utf-8").write(texto)
        w = World(); o = w.get_ontology("file://" + tmp).load()
        try:
            with o: sync_reasoner_hermit(w, infer_property_values=inferir_tecnicas, debug=0)
        except OwlReadyInconsistentOntologyError:
            return {cid: dict(consistente=False) for cid in casos}
        res = {}
        for cid, (an, fis) in nombres.items():
            a = o[an]; anc = _ancestros(a); rasgos = {}
            for f, fn in fis.items():
                x = _ancestros(o[fn])
                rasgos[f] = dict(clase_inferida=[n for n in (cfg["ontologia"][f]["indicio"], cfg["ontologia"][f]["naturalidad"]) if n in x],
                                 indicio="IndicioDeDeepfake" in x, naturalidad="RasgoDeNaturalidad" in x)
            tec = sorted({t.name for t in (getattr(a, "tieneIndicioDe", None) or [])}) if inferir_tecnicas else []
            res[cid] = dict(consistente=True, clases_audio=sorted(c for c in CLASES_AUDIO if c in anc), rasgos=rasgos,
                            n_indicios=sum(r["indicio"] for r in rasgos.values()),
                            n_naturalidad=sum(r["naturalidad"] for r in rasgos.values()), tecnicas=tec)
        return res
