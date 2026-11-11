import re, sys
from xml.sax.saxutils import escape

BASE = "https://example.org/ontologias/artefactos-audio"
XSD = "http://www.w3.org/2001/XMLSchema#"

# ------------------------------------------------------------------ CLASES (nombre, padre, comentario)
CLS = [
 ("Audio", None, "Grabacion de audio de voz sujeta a analisis forense."),
 ("AudioAutentico", "Audio", "Audio producido por la voz de una persona real (etiqueta de referencia)."),
 ("AudioSintetico", "Audio", "Audio generado o modificado por un modelo de sintesis de voz (etiqueta de referencia)."),
 ("AudioSinteticoPorVocoderGAN", "AudioSintetico", "Audio sintetico generado con un vocoder GAN."),
 ("AudioSinteticoPorTTS", "AudioSintetico", "Audio sintetico generado con sintesis de texto a voz."),
 ("AudioSinteticoPorClonacion", "AudioSintetico", "Audio sintetico generado con clonacion de voz."),
 ("AudioSinteticoPorConversion", "AudioSintetico", "Audio sintetico generado con conversion de voz."),
 ("AudioSospechoso", "Audio", "Audio con al menos una caracteristica que es indicio de deepfake (clasificado por razonador)."),
 ("AudioSospechosoDeVocoderGAN", "AudioSospechoso", "Audio sospechoso cuyos indicios apuntan a un vocoder GAN."),
 ("AudioConRasgosDeNaturalidad", "Audio", "Audio con al menos un rasgo compatible con voz humana natural."),
 ("AudioConEvidenciaContradictoria", "Audio", "Audio con indicios de deepfake y rasgos de naturalidad a la vez."),
 ("AudioQueRequiereRevisionHumana", "Audio", "Audio cuyo caso debe escalarse a un analista forense."),
 ("Caracteristica", None, "Medida extraida del audio (vector de caracteristicas)."),
 ("CaracteristicaEspectral", "Caracteristica", "Medida derivada del espectro o del espectrograma mel."),
 ("CentroideEspectral", "CaracteristicaEspectral", "Centro de masa del espectro."),
 ("PlanitudEspectral", "CaracteristicaEspectral", "Relacion entre media geometrica y aritmetica del espectro (0 a 1)."),
 ("EnergiaDeAltaFrecuencia", "CaracteristicaEspectral", "Proporcion de energia en bandas de alta frecuencia."),
 ("CaracteristicaProsodica", "Caracteristica", "Medida de entonacion, ritmo o microperturbaciones de la voz."),
 ("Jitter", "CaracteristicaProsodica", "Variacion ciclo a ciclo del periodo fundamental (fraccion)."),
 ("Shimmer", "CaracteristicaProsodica", "Variacion ciclo a ciclo de la amplitud (fraccion)."),
 ("VariabilidadDeF0", "CaracteristicaProsodica", "Coeficiente de variacion de la frecuencia fundamental."),
 ("CaracteristicaEstadistica", "Caracteristica", "Estadistico resumen del espectrograma mel."),
 ("EstadisticaPorBandaMel", "CaracteristicaEstadistica", "Estadistico calculado sobre una banda mel concreta."),
 ("CaracteristicaDePicosYMesetas", "Caracteristica", "Medida de picos y mesetas del espectro."),
 ("ProporcionDeMeseta", "CaracteristicaDePicosYMesetas", "Fraccion del espectro con comportamiento de meseta."),
 ("ConteoDePicos", "CaracteristicaDePicosYMesetas", "Numero de picos espectrales detectados."),
 ("IndicioDeDeepfake", "Caracteristica", "Caracteristica anomala asociada a tecnicas de sintesis."),
 ("PatronDeMeseta", "IndicioDeDeepfake", "Proporcion de meseta alta (>= 0.60)."),
 ("AnomaliaDeAltaFrecuencia", "IndicioDeDeepfake", "Energia en alta frecuencia anormalmente baja (< 0.02)."),
 ("JitterAnomalo", "IndicioDeDeepfake", "Jitter demasiado bajo, ausencia de perturbacion natural (< 0.002)."),
 ("ShimmerAnomalo", "IndicioDeDeepfake", "Shimmer demasiado bajo (< 0.01)."),
 ("PlanitudEspectralAnomala", "IndicioDeDeepfake", "Planitud espectral alta (>= 0.30)."),
 ("VariabilidadDeF0Anomala", "IndicioDeDeepfake", "Entonacion demasiado uniforme (< 0.05)."),
 ("RasgoDeNaturalidad", "Caracteristica", "Caracteristica compatible con voz humana natural."),
 ("JitterNatural", "RasgoDeNaturalidad", "Jitter en rango humano tipico [0.002, 0.02]."),
 ("ShimmerNatural", "RasgoDeNaturalidad", "Shimmer en rango humano tipico [0.01, 0.10]."),
 ("VariabilidadDeF0Natural", "RasgoDeNaturalidad", "Variabilidad de F0 en rango humano tipico [0.05, 0.50]."),
 ("TecnicaDeSintesis", None, "Tecnica o componente de generacion de voz sintetica."),
 ("SintesisTextoAVoz", "TecnicaDeSintesis", "Sintesis de texto a voz (TTS)."),
 ("ConversionDeVoz", "TecnicaDeSintesis", "Conversion de la voz de un hablante en la de otro."),
 ("ClonacionDeVoz", "TecnicaDeSintesis", "Clonacion de la voz de un hablante a partir de muestras."),
 ("VocoderNeuronal", "TecnicaDeSintesis", "Vocoder basado en redes neuronales."),
 ("VocoderGAN", "VocoderNeuronal", "Vocoder entrenado de forma adversaria (GAN)."),
 ("Persona", None, "Persona involucrada en el sistema."),
 ("Hablante", "Persona", "Persona cuya voz es producida o imitada (identificada de forma anonima)."),
 ("AnalistaForense", "Persona", "Experto humano que valida o corrige el conocimiento."),
 ("ModeloDeDeteccion", None, "Modelo automatico de clasificacion de audio."),
 ("ModeloCNNLSTM", "ModeloDeDeteccion", "Modelo CNN+LSTM del sistema base."),
 ("ResultadoDeModelo", None, "Salida de un modelo de deteccion para un audio."),
]
TOP = ["Audio", "Caracteristica", "TecnicaDeSintesis", "Persona", "ModeloDeDeteccion", "ResultadoDeModelo"]

# ------------------------------------------------------------------ PROPIEDADES DE OBJETO
OPS = [
 ("tieneCaracteristica", "Relaciona un audio con una de sus caracteristicas."),
 ("caracteristicaDe", "Inversa de tieneCaracteristica."),
 ("fueGeneradoPor", "Tecnica de sintesis con la que se genero un audio."),
 ("generaAudio", "Inversa de fueGeneradoPor."),
 ("producidoPor", "Hablante real que produjo un audio autentico."),
 ("produceAudio", "Inversa de producidoPor."),
 ("imitaA", "Hablante cuya voz imita un audio sintetico."),
 ("esImitadoPor", "Inversa de imitaA."),
 ("esIndicioDe", "Tecnica de sintesis a la que apunta un indicio."),
 ("tieneComoIndicio", "Inversa de esIndicioDe."),
 ("tieneIndicioDe", "Tecnica de sintesis sospechada en un audio (inferida por cadena)."),
 ("esTecnicaSospechadaEn", "Inversa de tieneIndicioDe."),
 ("correlacionaCon", "Dos caracteristicas que covarian (simetrica)."),
 ("derivaDe", "Una tecnica de sintesis deriva de otra (transitiva)."),
 ("esOrigenDe", "Inversa de derivaDe."),
 ("tieneResultadoDeModelo", "Resultado de un modelo para un audio."),
 ("esResultadoDeAudio", "Inversa de tieneResultadoDeModelo."),
 ("generadoPorModelo", "Modelo que produjo un resultado."),
 ("produceResultado", "Inversa de generadoPorModelo."),
 ("validadoPor", "Analista forense que valido el audio."),
 ("valida", "Inversa de validadoPor."),
]
# ------------------------------------------------------------------ PROPIEDADES DE DATOS
DPS = [
 ("valor", "Valor numerico de una caracteristica."),
 ("unidadDeMedida", "Unidad de medida de la caracteristica."),
 ("bandaMel", "Indice de la banda mel (1 a 128)."),
 ("tipoDeEstadistica", "Estadistico calculado: media, desviacion, asimetria o curtosis."),
 ("pesoDeEvidencia", "Peso del indicio para el arbitraje de conflictos [0,1]."),
 ("identificadorDeAudio", "Identificador unico del audio."),
 ("duracionEnSegundos", "Duracion del audio en segundos (> 0)."),
 ("frecuenciaDeMuestreoHz", "Frecuencia de muestreo en Hz."),
 ("formatoDeArchivo", "Formato del archivo (wav, flac, mp3...)."),
 ("fechaDeValidacion", "Fecha y hora de la validacion por un analista."),
 ("scoreDeConfianza", "Probabilidad que reporta el modelo de deteccion [0,1]."),
 ("versionDelModelo", "Version del modelo de deteccion."),
 ("anioDeAparicion", "Anio de aparicion de la tecnica de sintesis."),
 ("identificadorDeHablante", "Identificador anonimo del hablante."),
]

ACC = {"Caracteristica": "Característica", "Tecnica": "Técnica", "Sintesis": "Síntesis", "Prosodica": "Prosódica",
       "Estadistica": "Estadística", "Duracion": "Duración", "Conversion": "Conversión", "Clonacion": "Clonación",
       "Anio": "Año", "Version": "Versión", "Anomalia": "Anomalía", "Energia": "Energía", "Revision": "Revisión",
       "Autentico": "Auténtico", "Sintetico": "Sintético", "Deteccion": "Detección", "Anomala": "Anómala",
       "Anomalo": "Anómalo", "Validacion": "Validación", "Frecuencia": "Frecuencia", "Numerico": "Numérico",
       "Tecnica": "Técnica", "esTecnica": "esTécnica"}

def label(n):
    parts = re.split(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", n)
    out = []
    for i, p in enumerate(parts):
        p = ACC.get(p, p)
        if not p.isupper() and not re.fullmatch(r"[A-Z]\d", p):
            p = p.lower() if i > 0 else p[0].upper() + p[1:]
        out.append(p)
    return " ".join(out)

EXTRA = {"Grabacion": "Grabación", "Clasificacion": "Clasificación", "Relacion": "Relación", "Numero": "Número",
         "Fraccion": "Fracción", "Variacion": "Variación", "Entonacion": "Entonación", "Perturbacion": "Perturbación",
         "Generacion": "Generación", "Indice": "Índice", "Unico": "Único", "Analisis": "Análisis", "Diferenciacion": "Diferenciación",
         "Anio": "Año", "Frecuencia": "Frecuencia"}

def fix_comment(c):
    m = dict(ACC); m.update(EXTRA)
    for k, v in m.items():
        c = re.sub(r"\b%s\b" % k, v, c)
        c = re.sub(r"\b%s\b" % k.lower(), v.lower(), c)
    return c

# ------------------------------------------------------------------ helpers XML
def Cl(n): return '<Class IRI="#%s"/>' % n
def OP(n): return '<ObjectProperty IRI="#%s"/>' % n
def DP(n): return '<DataProperty IRI="#%s"/>' % n
def dt(t): return '<Datatype abbreviatedIRI="xsd:%s"/>' % t
def lit(v, t): return '<Literal datatypeIRI="%s%s">%s</Literal>' % (XSD, t, escape(str(v)))
def cx(x): return x if x.startswith("<") else Cl(x)
def facets(t, **kw):
    return "<DatatypeRestriction>%s%s</DatatypeRestriction>" % (
        dt(t), "".join('<FacetRestriction facet="%s%s">%s</FacetRestriction>' % (XSD, k, lit(v, t)) for k, v in kw.items()))
def dsome(dp, rng): return "<DataSomeValuesFrom>%s%s</DataSomeValuesFrom>" % (DP(dp), rng)
def osome(op, c): return "<ObjectSomeValuesFrom>%s%s</ObjectSomeValuesFrom>" % (OP(op), cx(c))
def inter(*xs): return "<ObjectIntersectionOf>%s</ObjectIntersectionOf>" % "".join(cx(x) for x in xs)
def ocard(kind, n, op, c): return '<Object%sCardinality cardinality="%d">%s%s</Object%sCardinality>' % (kind, n, OP(op), cx(c), kind)
def dcard(kind, n, dp, t=None): return '<Data%sCardinality cardinality="%d">%s</Data%sCardinality>' % (kind, n, DP(dp), kind)

AX = []
def sub(a, b): AX.append("<SubClassOf>%s%s</SubClassOf>" % (cx(a), cx(b)))
def eq(a, b): AX.append("<EquivalentClasses>%s%s</EquivalentClasses>" % (cx(a), cx(b)))
def disj(*names): AX.append("<DisjointClasses>%s</DisjointClasses>" % "".join(cx(n) for n in names))

CLS_BASE = list(CLS)
CAL = None          # reglas calibradas (dict del JSON); si es None se usan los umbrales iniciales

# rasgo extraido -> (clase base, clase de indicio, clase de naturalidad, tecnica sospechada, padre de la clase base)
FEATURE_ONT = {
    "spectral_centroid": ("CentroideEspectral", "CentroideEspectralAnomalo", "CentroideEspectralNatural", "VocoderNeuronal", None),
    "hf_energy": ("EnergiaDeAltaFrecuencia", "AnomaliaDeAltaFrecuencia", "EnergiaDeAltaFrecuenciaNatural", "VocoderNeuronal", None),
    "mel_kurt": ("CurtosisDelEspectrograma", "CurtosisMelAnomala", "CurtosisMelNatural", "VocoderNeuronal", "CaracteristicaEstadistica"),
    "f0_var": ("VariabilidadDeF0", "VariabilidadDeF0Anomala", "VariabilidadDeF0Natural", "SintesisTextoAVoz", None),
    "jitter": ("Jitter", "JitterAnomalo", "JitterNatural", "VocoderGAN", None),
    "shimmer": ("Shimmer", "ShimmerAnomalo", "ShimmerNatural", "VocoderNeuronal", None),
    "spectral_flatness": ("PlanitudEspectral", "PlanitudEspectralAnomala", "PlanitudEspectralNatural", "SintesisTextoAVoz", None),
    "plateau_ratio": ("ProporcionDeMeseta", "PatronDeMeseta", "ProporcionDeMesetaNatural", "VocoderGAN", None),
    "peak_count": ("ConteoDePicos", "ConteoDePicosAnomalo", "ConteoDePicosNatural", "VocoderGAN", None),
}

def _cal_rules():
    return [(ag, r) for ag in ("E", "Pr") for r in CAL.get(ag, [])]

def _apply_cal_classes():
    CLS[:] = CLS_BASE
    if not CAL: return
    idx = {n: i for i, (n, _, _) in enumerate(CLS)}
    def put(name, parent, comment):
        if name in idx: CLS[idx[name]] = (name, parent, comment)
        else: idx[name] = len(CLS); CLS.append((name, parent, comment))
    for _, r in _cal_rules():
        base, an, na, tech, bparent = FEATURE_ONT[r["feature"]]
        if bparent: put(base, bparent, "Curtosis de los valores del espectrograma mel (rasgo calibrado).")
        d = "alto" if r["fake_high"] else "bajo"
        put(an, "IndicioDeDeepfake", "Indicio calibrado con datos: %s con valor %s (en el audio sintetico el valor tiende a ser %s)." % (r["feature"], "mayor que %.6g" % r["t_ind"] if r["fake_high"] else "menor que %.6g" % r["t_ind"], d))
        put(na, "RasgoDeNaturalidad", "Rasgo de naturalidad calibrado con datos: %s con valor %s." % (r["feature"], "menor que %.6g" % r["t_nat"] if r["fake_high"] else "mayor que %.6g" % r["t_nat"]))

def build(tests=False):
    AX.clear()
    _apply_cal_classes()
    # --- jerarquia asertada
    for n, p, _ in CLS:
        if p: sub(n, p)
    disj(*TOP)

    # --- relaciones excluyentes (clases)
    disj("AudioAutentico", "AudioSintetico")
    disj("CaracteristicaEspectral", "CaracteristicaProsodica", "CaracteristicaEstadistica", "CaracteristicaDePicosYMesetas")
    disj("CentroideEspectral", "PlanitudEspectral", "EnergiaDeAltaFrecuencia")
    disj("Jitter", "Shimmer", "VariabilidadDeF0")
    disj("ProporcionDeMeseta", "ConteoDePicos")
    disj("IndicioDeDeepfake", "RasgoDeNaturalidad")
    disj("JitterNatural", "JitterAnomalo")
    disj("ShimmerNatural", "ShimmerAnomalo")
    disj("VariabilidadDeF0Natural", "VariabilidadDeF0Anomala")
    disj("Hablante", "AnalistaForense")

    # --- axiomas de diferenciacion: indicios de sintesis (umbrales iniciales, a calibrar con el dataset)
    anomalies = [
        ("PatronDeMeseta", "ProporcionDeMeseta", dict(minInclusive="0.60"), "VocoderGAN"),
        ("AnomaliaDeAltaFrecuencia", "EnergiaDeAltaFrecuencia", dict(maxExclusive="0.02"), "VocoderNeuronal"),
        ("JitterAnomalo", "Jitter", dict(maxExclusive="0.002"), "VocoderGAN"),
        ("ShimmerAnomalo", "Shimmer", dict(maxExclusive="0.01"), "VocoderNeuronal"),
        ("PlanitudEspectralAnomala", "PlanitudEspectral", dict(minInclusive="0.30"), "SintesisTextoAVoz"),
        ("VariabilidadDeF0Anomala", "VariabilidadDeF0", dict(maxExclusive="0.05"), "SintesisTextoAVoz"),
    ]
    naturals = [
        ("JitterNatural", "Jitter", dict(minInclusive="0.002", maxInclusive="0.02")),
        ("ShimmerNatural", "Shimmer", dict(minInclusive="0.01", maxInclusive="0.10")),
        ("VariabilidadDeF0Natural", "VariabilidadDeF0", dict(minInclusive="0.05", maxInclusive="0.50")),
    ]
    if CAL:
        for _, r in _cal_rules():
            base, an, na, tech, _p = FEATURE_ONT[r["feature"]]
            anomalies = [a for a in anomalies if a[0] != an]; naturals = [a for a in naturals if a[0] != na]
            fi, fn = ("minExclusive", "maxExclusive") if r["fake_high"] else ("maxExclusive", "minExclusive")
            anomalies.append((an, base, {fi: repr(r["t_ind"])}, tech))
            naturals.append((na, base, {fn: repr(r["t_nat"])}))
            disj(an, na)
    for name, base, fc, tech in anomalies:
        eq(name, inter(base, dsome("valor", facets("double", **fc))))
        sub(name, osome("esIndicioDe", tech))
    for name, base, fc in naturals:
        eq(name, inter(base, dsome("valor", facets("double", **fc))))

    # --- axiomas de clasificacion de audios
    eq("AudioSospechoso", inter("Audio", osome("tieneCaracteristica", "IndicioDeDeepfake")))
    eq("AudioSospechosoDeVocoderGAN", inter("Audio", osome("tieneIndicioDe", "VocoderGAN")))
    eq("AudioConRasgosDeNaturalidad", inter("Audio", osome("tieneCaracteristica", "RasgoDeNaturalidad")))
    eq("AudioConEvidenciaContradictoria", inter("AudioSospechoso", "AudioConRasgosDeNaturalidad"))
    sub("AudioConEvidenciaContradictoria", "AudioQueRequiereRevisionHumana")
    for n, t in [("AudioSinteticoPorVocoderGAN", "VocoderGAN"), ("AudioSinteticoPorTTS", "SintesisTextoAVoz"),
                 ("AudioSinteticoPorClonacion", "ClonacionDeVoz"), ("AudioSinteticoPorConversion", "ConversionDeVoz")]:
        eq(n, inter("AudioSintetico", osome("fueGeneradoPor", t)))

    # --- cardinalidades (propiedades de objeto)
    sub("AudioAutentico", ocard("Exact", 1, "producidoPor", "Hablante"))
    sub("AudioAutentico", ocard("Max", 0, "fueGeneradoPor", "TecnicaDeSintesis"))
    sub("AudioAutentico", ocard("Max", 0, "imitaA", "Hablante"))
    sub("AudioSintetico", ocard("Min", 1, "fueGeneradoPor", "TecnicaDeSintesis"))
    sub("AudioSintetico", ocard("Max", 1, "imitaA", "Hablante"))
    sub("Caracteristica", ocard("Exact", 1, "caracteristicaDe", "Audio"))
    sub("ResultadoDeModelo", ocard("Exact", 1, "esResultadoDeAudio", "Audio"))
    sub("ResultadoDeModelo", ocard("Exact", 1, "generadoPorModelo", "ModeloDeDeteccion"))
    # --- cardinalidades (propiedades de datos)
    sub("Audio", dcard("Exact", 1, "identificadorDeAudio", "string"))
    sub("Audio", dcard("Exact", 1, "duracionEnSegundos", "double"))
    sub("Audio", dcard("Max", 1, "frecuenciaDeMuestreoHz", "integer"))
    sub("Audio", dcard("Max", 1, "formatoDeArchivo", "string"))
    sub("Audio", dcard("Max", 1, "fechaDeValidacion", "dateTime"))
    sub("Caracteristica", dcard("Exact", 1, "valor", "double"))
    sub("Caracteristica", dcard("Max", 1, "unidadDeMedida", "string"))
    sub("EstadisticaPorBandaMel", dcard("Exact", 1, "bandaMel", "integer"))
    sub("EstadisticaPorBandaMel", dcard("Exact", 1, "tipoDeEstadistica", "string"))
    sub("IndicioDeDeepfake", dcard("Max", 1, "pesoDeEvidencia", "double"))
    sub("Hablante", dcard("Exact", 1, "identificadorDeHablante", "string"))
    sub("ResultadoDeModelo", dcard("Exact", 1, "scoreDeConfianza", "double"))
    sub("ModeloDeDeteccion", dcard("Exact", 1, "versionDelModelo", "string"))
    sub("TecnicaDeSintesis", dcard("Max", 1, "anioDeAparicion", "integer"))

    # --- axiomas de propiedades de objeto
    inv = [("tieneCaracteristica", "caracteristicaDe"), ("fueGeneradoPor", "generaAudio"), ("producidoPor", "produceAudio"),
           ("imitaA", "esImitadoPor"), ("esIndicioDe", "tieneComoIndicio"), ("tieneIndicioDe", "esTecnicaSospechadaEn"),
           ("derivaDe", "esOrigenDe"), ("tieneResultadoDeModelo", "esResultadoDeAudio"),
           ("generadoPorModelo", "produceResultado"), ("validadoPor", "valida")]
    for a, b in inv:
        AX.append("<InverseObjectProperties>%s%s</InverseObjectProperties>" % (OP(a), OP(b)))
    dr = [("tieneCaracteristica", "Audio", "Caracteristica"), ("fueGeneradoPor", "Audio", "TecnicaDeSintesis"),
          ("producidoPor", "Audio", "Hablante"), ("imitaA", "Audio", "Hablante"),
          ("esIndicioDe", "IndicioDeDeepfake", "TecnicaDeSintesis"), ("tieneIndicioDe", "Audio", "TecnicaDeSintesis"),
          ("correlacionaCon", "Caracteristica", "Caracteristica"), ("derivaDe", "TecnicaDeSintesis", "TecnicaDeSintesis"),
          ("tieneResultadoDeModelo", "Audio", "ResultadoDeModelo"), ("generadoPorModelo", "ResultadoDeModelo", "ModeloDeDeteccion"),
          ("validadoPor", "Audio", "AnalistaForense")]
    for p, d, r in dr:
        AX.append("<ObjectPropertyDomain>%s%s</ObjectPropertyDomain>" % (OP(p), Cl(d)))
        AX.append("<ObjectPropertyRange>%s%s</ObjectPropertyRange>" % (OP(p), Cl(r)))
    AX.append("<InverseFunctionalObjectProperty>%s</InverseFunctionalObjectProperty>" % OP("tieneCaracteristica"))
    AX.append("<FunctionalObjectProperty>%s</FunctionalObjectProperty>" % OP("caracteristicaDe"))
    AX.append("<InverseFunctionalObjectProperty>%s</InverseFunctionalObjectProperty>" % OP("tieneResultadoDeModelo"))
    AX.append("<FunctionalObjectProperty>%s</FunctionalObjectProperty>" % OP("esResultadoDeAudio"))
    AX.append("<FunctionalObjectProperty>%s</FunctionalObjectProperty>" % OP("generadoPorModelo"))
    AX.append("<SymmetricObjectProperty>%s</SymmetricObjectProperty>" % OP("correlacionaCon"))
    AX.append("<IrreflexiveObjectProperty>%s</IrreflexiveObjectProperty>" % OP("correlacionaCon"))
    AX.append("<TransitiveObjectProperty>%s</TransitiveObjectProperty>" % OP("derivaDe"))
    AX.append("<DisjointObjectProperties>%s%s</DisjointObjectProperties>" % (OP("producidoPor"), OP("imitaA")))
    AX.append("<SubObjectPropertyOf><ObjectPropertyChain>%s%s</ObjectPropertyChain>%s</SubObjectPropertyOf>" % (
        OP("tieneCaracteristica"), OP("esIndicioDe"), OP("tieneIndicioDe")))

    # --- axiomas de propiedades de datos (dominio, rango, funcional)
    dd = [("valor", "Caracteristica", dt("double")), ("unidadDeMedida", "Caracteristica", dt("string")),
          ("bandaMel", "EstadisticaPorBandaMel", facets("integer", minInclusive=1, maxInclusive=128)),
          ("tipoDeEstadistica", "EstadisticaPorBandaMel",
           "<DataOneOf>%s</DataOneOf>" % "".join(lit(s, "string") for s in ["media", "desviacion", "asimetria", "curtosis"])),
          ("pesoDeEvidencia", "IndicioDeDeepfake", facets("double", minInclusive="0.0", maxInclusive="1.0")),
          ("identificadorDeAudio", "Audio", dt("string")),
          ("duracionEnSegundos", "Audio", facets("double", minExclusive="0.0")),
          ("frecuenciaDeMuestreoHz", "Audio", facets("integer", minInclusive=1)),
          ("formatoDeArchivo", "Audio", dt("string")), ("fechaDeValidacion", "Audio", dt("dateTime")),
          ("scoreDeConfianza", "ResultadoDeModelo", facets("double", minInclusive="0.0", maxInclusive="1.0")),
          ("versionDelModelo", "ModeloDeDeteccion", dt("string")),
          ("anioDeAparicion", "TecnicaDeSintesis", facets("integer", minInclusive=1950)),
          ("identificadorDeHablante", "Hablante", dt("string"))]
    for p, d, r in dd:
        AX.append("<DataPropertyDomain>%s%s</DataPropertyDomain>" % (DP(p), Cl(d)))
        AX.append("<DataPropertyRange>%s%s</DataPropertyRange>" % (DP(p), r))
        AX.append("<FunctionalDataProperty>%s</FunctionalDataProperty>" % DP(p))

    if tests:
        for t in tests: AX.append(t)

    # --- ensamblado
    out = ['<?xml version="1.0"?>',
           '<Ontology xmlns="http://www.w3.org/2002/07/owl#" xml:base="%s" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
           'xmlns:xml="http://www.w3.org/XML/1998/namespace" xmlns:xsd="http://www.w3.org/2001/XMLSchema#" '
           'xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#" ontologyIRI="%s">' % (BASE, BASE),
           '<Prefix name="" IRI="%s#"/>' % BASE,
           '<Prefix name="owl" IRI="http://www.w3.org/2002/07/owl#"/>',
           '<Prefix name="rdf" IRI="http://www.w3.org/1999/02/22-rdf-syntax-ns#"/>',
           '<Prefix name="xml" IRI="http://www.w3.org/XML/1998/namespace"/>',
           '<Prefix name="xsd" IRI="http://www.w3.org/2001/XMLSchema#"/>',
           '<Prefix name="rdfs" IRI="http://www.w3.org/2000/01/rdf-schema#"/>',
           '<Annotation><AnnotationProperty abbreviatedIRI="rdfs:label"/><Literal xml:lang="es">Ontología de artefactos de audio</Literal></Annotation>',
           '<Annotation><AnnotationProperty abbreviatedIRI="rdfs:comment"/><Literal xml:lang="es">Ontología para diferenciar audios auténticamente humanos de audios sintéticos (deepfake) mediante axiomas sobre características espectrales, prosódicas, estadísticas y de picos/mesetas.</Literal></Annotation>']
    for n, _, _ in CLS: out.append('<Declaration><Class IRI="#%s"/></Declaration>' % n)
    for n, _ in OPS: out.append('<Declaration><ObjectProperty IRI="#%s"/></Declaration>' % n)
    for n, _ in DPS: out.append('<Declaration><DataProperty IRI="#%s"/></Declaration>' % n)
    out += AX
    def ann(kind, n, text, prop):
        return ('<AnnotationAssertion><AnnotationProperty abbreviatedIRI="rdfs:%s"/><IRI>#%s</IRI><Literal xml:lang="es">%s</Literal></AnnotationAssertion>'
                % (prop, n, escape(text)))
    for n, _, c in CLS:
        out.append(ann("c", n, label(n), "label")); out.append(ann("c", n, fix_comment(c), "comment"))
    for n, c in OPS + DPS:
        out.append(ann("p", n, label(n), "label")); out.append(ann("p", n, fix_comment(c), "comment"))
    out.append("</Ontology>")
    return "\n".join(out)

if __name__ == "__main__":
    import json
    if len(sys.argv) > 2: CAL = json.load(open(sys.argv[2], encoding="utf-8"))["reglas"]
    open(sys.argv[1], "w", encoding="utf-8").write(build())
    print("ok", len(CLS), len(OPS), len(DPS))
