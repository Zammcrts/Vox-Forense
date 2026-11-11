# -*- coding: utf-8 -*-
"""Rutas y configuracion compartida. Todo el conocimiento (umbrales) sale de la ontologia .owx."""
import json, os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUTA_ONTOLOGIA = Path(os.getenv("VOX_ONTOLOGIA", RAIZ / "ontologia" / "Ontologia_Artefactos_Audio_calibrada.owx"))
RUTA_UMBRALES = RAIZ / "config" / "umbrales_calibrados.json"
RUTA_ESCALAMIENTOS = RAIZ / "salidas" / "escalamientos.jsonl"
LLM_MODELO = os.getenv("VOX_LLM", "anthropic/claude-sonnet-4-5")

# Costos nominales de diseno (segundos). NO son mediciones; solo alimentan el termino de latencia de la utilidad.
LATENCIA_NOMINAL = {"P": 0.4, "E": 1.2, "Pr": 1.1, "R": 1.5, "X": 1.8}
NOMBRE_AGENTE = {"P": "Perceptor", "E": "Espectral", "Pr": "Prosódico", "R": "Razonador", "X": "Explicador"}

# Rasgos que cada agente puede evaluar (los que tengan regla calibrada se usan)
RASGOS_ESPECTRALES = ["spectral_flatness", "spectral_centroid", "hf_energy", "plateau_ratio", "peak_count",
                      "mel_mean", "mel_std", "mel_skew", "mel_kurt"]
RASGOS_PROSODICOS = ["jitter", "shimmer", "f0_var"]

# Rangos fisicamente plausibles para validar el vector de caracteristicas (agente Perceptor)
RANGOS = {"jitter": (0, 1), "shimmer": (0, 1), "f0_var": (0, 5), "hf_energy": (0, 1), "spectral_flatness": (0, 1),
          "spectral_centroid": (0, 8000), "plateau_ratio": (0, 1), "peak_count": (0, 64), "duration_s": (0.5, 3600)}


def cargar_umbrales(ruta=None):
    with open(ruta or RUTA_UMBRALES, encoding="utf-8") as f:
        return json.load(f)
