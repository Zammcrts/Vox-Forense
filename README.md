# VOX-Forense · Sistema multiagente (CrewAI) que consume la ontología

Detección **explicable** de voz sintética. Tres capas del diseño, ya implementadas:

| Capa | Dónde está | Qué hace |
|---|---|---|
| 1. CrewAI | `vox/agentes.py`, `vox/tareas.py`, `vox/crew.py` | Manager + 5 agentes (Perceptor, Espectral, Prosódico, Razonador, Explicador), tareas T1–T5, `Process.hierarchical` |
| 2. Contract Net | `vox/contract_net.py` + tool `contract_net_allocate` | Licitación de subtareas (U = 0.5·competencia + 0.3·cobertura + 0.2·(1−carga), τmin = 0.35; estados AWARDED/PARTIAL/NO_BIDS/ERROR) |
| 3. Shapley | `vox/auditoria.py` | Ablación de las 32 coaliciones y valores de Shapley de los 5 agentes |

## Cómo consume la ontología
* `ontologia/Ontologia_Artefactos_Audio_calibrada.owx` es la ontología original **más** las clases de indicio/naturalidad con los **umbrales calibrados** (generada por `ontologia/gen_owx.py` a partir de `config/umbrales_calibrados.json`). La ontología sin calibrar sigue siendo la que entregaron antes.
* **Los umbrales se leen del propio `.owx`** (`vox/ontologia.py → umbrales()`): los especialistas los usan para sus hallazgos preliminares.
* El **Razonador** inserta el audio y sus rasgos como individuos, ejecuta **HermiT** (vía owlready2) y toma de la ontología las clases inferidas (`IndicioDeDeepfake`, `RasgoDeNaturalidad`, `AudioSospechoso`, `AudioConEvidenciaContradictoria`, `AudioQueRequiereRevisionHumana`, técnicas sospechadas…). Si el razonamiento discrepa de los especialistas, lo reporta.
* El veredicto lo emite la herramienta determinista `decidir_veredicto` (`vox/politica.py`): **SINTÉTICO** si indicios ≥ 2 y naturalidad ≤ 1; **AUTÉNTICO** si naturalidad ≥ 2 e indicios = 0; si no, **ESCALAR** a un analista. (Bajo mundo abierto la ontología infiere pertenencia a clases; el conteo de evidencia se hace en esta política, no con cardinalidades máximas.)
* Los agentes se pasan solo un `case_id`; las cifras viven en `vox/casos.py`, así el LLM no puede alterarlas. En modo crew el resultado autoritativo es el del almacén de casos, no el texto libre del LLM.

## Instalación
```bash
pip install -r requirements.txt     # + Java (para HermiT) y ffmpeg en el PATH
cp .env.example .env                # solo para el modo crew: clave de API y modelo
```

## Uso
```bash
python main.py analizar audio.mp3                    # modo directo: sin LLM, mismo flujo T1–T5
python main.py analizar audio.mp3 --modo crew        # CrewAI con LLM (necesita clave de API)
python main.py lote --carpeta fragmentos/ --salida salidas/lote.csv     # carpeta de audios, sin LLM
python main.py lote --csv datos/ejemplo_rasgos.csv                      # rasgos ya extraídos
python main.py auditar rasgos.csv                    # Shapley + ablación (solo voces de prueba)
python main.py calibrar rasgos.csv                   # recalibra umbrales y regenera el .owx (--todo: usa todas las voces)
python -m pytest tests                               # 8 pruebas
```
En el modo crew, exporta antes la clave del proveedor (p. ej. `ANTHROPIC_API_KEY`) y, si quieres otro modelo, `VOX_LLM=proveedor/modelo`.

## Verificación hecha
* `pytest`: 8/8 (umbrales leídos de la ontología, política, Contract Net, **HermiT = lectura de umbrales en 40/40 audios**, flujo en lote, caso sin rasgos → ESCALAR, eficiencia de Shapley, construcción de la crew jerárquica).
* Sobre los **273 audios de prueba** (6 voces) el flujo completo vía HermiT reproduce el reporte: 120 resueltos, 118 aciertos, 2 errores, 153 escalados (56 %); la auditoría da Σφ = v(N) = 0.532 y el orden Perceptor > Razonador > Explicador > Espectral > Prosódico.
* Modo directo probado de punta a punta con un audio real (extracción → licitación → hallazgos → HermiT → veredicto → explicación).

## Límites que conviene conocer
* **El modo crew con LLM no se ejecutó de principio a fin** al desarrollar esto (no había clave de API en el entorno): se verificó que la crew se construye y que cada herramienta funciona, pero el comportamiento del LLM (delegación del manager, redacción) debe probarse con tu clave. Si el manager no delega como esperas, prueba con un modelo más capaz o baja `max_iter`.
* El razonamiento por HermiT en lote tarda ≈ 0.6 s por audio (273 audios ≈ 2.7 min). Para un audio suelto añade unos segundos de arranque de la JVM.
* Los umbrales se calibraron con un corpus propio (21 voces, audios sintéticos de un solo origen, 6 voces de prueba). Los rasgos espectrales podrían reflejar diferencias de grabación/códec. Recalibra con `calibrar` ante otros generadores.
* La latencia usa costos nominales de diseño (`vox/config.py`), no mediciones. La competencia inicial del Contract Net es el poder discriminante (AUC) de las reglas de cada agente.
* Las técnicas de síntesis sospechadas (`VocoderGAN`, etc.) son hipótesis de la ontología, no están validadas con datos.
