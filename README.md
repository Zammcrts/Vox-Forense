# VOX-Forense 

**Arquitectura híbrida multiagente y ontológica para la detección explicable de voz sintética.**

## Descripción

VOX-Forense es un prototipo de sistema multiagente que busca diferenciar audio humano de audio sintético mediante el análisis de características acústicas, el razonamiento ontológico y la coordinación entre agentes especializados.

El proyecto combina una arquitectura jerárquica implementada con **CrewAI**, un mecanismo de asignación de subtareas basado en el protocolo **Contract Net** y una ontología **OWL 2** que permite realizar inferencias lógicas verificables. También incorpora valores de **Shapley** para estimar la contribución individual de los agentes.

El sistema puede emitir uno de tres resultados: `SINTETICO`, `AUTENTICO` o `ESCALAR` el caso a revisión humana cuando la evidencia no es suficiente o presenta contradicciones.

## Autoras

- **Arantza García Vázquez**
- **Edna Samantha Cortés Carrisoza**

**Materia:** Agentes Inteligentes  
**Institución:** Universidad Iberoamericana Puebla

## Tecnologías y herramientas

- Python
- CrewAI
- OWL 2
- Owlready2
- HermiT (razonador ontológico)
- librosa
- Praat / Parselmouth
- NumPy, Pandas y SciPy
- scikit-learn
- FFmpeg

## Arquitectura del sistema

La arquitectura contempla un coordinador y cinco agentes especializados:

1. **Perceptor:** extrae, valida y normaliza las características del audio.
2. **Especialista Espectral:** analiza rasgos espectrales de la señal.
3. **Especialista Prosódico:** evalúa características como jitter, shimmer y variabilidad de F0.
4. **Razonador Ontológico:** consulta la ontología y ejecuta inferencias mediante HermiT.
5. **Explicador/Auditor:** construye una explicación respaldada por los hechos y reglas aplicados.

El coordinador utiliza el protocolo Contract Net para asignar subtareas a los especialistas. La ontología permite clasificar los indicios y detectar inconsistencias; cuando la evidencia no permite emitir una conclusión suficientemente respaldada, el sistema puede escalar el caso a revisión humana.

## Requisitos previos

Antes de instalar el proyecto, asegúrate de contar con:

- **Python 3** y `pip`.
- **Java (JRE)** instalado y disponible en la variable `PATH`, para ejecutar el razonador HermiT mediante Owlready2.
- **FFmpeg** instalado y disponible en la variable `PATH`, para leer y convertir archivos de audio.
- Una clave de API de un proveedor de modelos de lenguaje únicamente si se utilizará el modo `crew`.

> El archivo `requirements.txt` contiene las dependencias de Python. Java y FFmpeg son dependencias externas y deben instalarse por separado.

## Instalación

### 1. Clonar el repositorio

```bash
git clone URL_DEL_REPOSITORIO
cd Vox-Forense-main
```

Sustituye `URL_DEL_REPOSITORIO` por la dirección del repositorio.

### 2. Crear un entorno virtual

```bash
python -m venv .venv
```

### 3. Activar el entorno virtual

**Windows (PowerShell):**

```powershell
.venv\Scripts\Activate.ps1
```

**Windows (CMD):**

```cmd
.venv\Scripts\activate.bat
```

**Linux / macOS:**

```bash
source .venv/bin/activate
```

### 4. Instalar las dependencias

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Verificar Java y FFmpeg

En la terminal, ejecuta:

```bash
java -version
ffmpeg -version
```

Si alguno de los comandos no se reconoce, revisa que el programa correspondiente esté instalado y agregado a la variable `PATH`.

## Ejecución

Todos los comandos se ejecutan desde la carpeta raíz del proyecto, donde se encuentra `main.py`.

### 1. Analizar un audio individual

**Modo directo (sin API de LLM):**

```bash
python main.py analizar ruta/al/audio.mp3
```

También se puede indicar explícitamente el modo:

```bash
python main.py analizar ruta/al/audio.mp3 --modo directo
```

**Modo CrewAI:**

```bash
python main.py analizar ruta/al/audio.mp3 --modo crew
```

El modo `crew` requiere configurar una clave de API compatible con el proveedor y modelo seleccionados.

Para utilizar Anthropic desde PowerShell:

```powershell
$env:ANTHROPIC_API_KEY="TU_CLAVE_DE_API"
$env:VOX_LLM="anthropic/claude-sonnet-4-5"
```

Para Linux / macOS:

```bash
export ANTHROPIC_API_KEY="TU_CLAVE_DE_API"
export VOX_LLM="anthropic/claude-sonnet-4-5"
```

`VOX_LLM` es opcional; si no se especifica, el proyecto utiliza el modelo configurado por defecto. También se puede seleccionar otro modelo compatible con CrewAI y con el proveedor correspondiente.

El archivo `.env.example` sirve como referencia para estas variables. El código del proyecto no carga explícitamente un archivo `.env`; por ello, configura las variables de entorno en la terminal o en tu entorno de desarrollo antes de ejecutar el modo `crew`.

### 2. Procesar audios por lotes

**A partir de una carpeta de audios:**

```bash
python main.py lote --carpeta ruta/a/la/carpeta
```

**A partir de un CSV con características acústicas previamente extraídas:**

```bash
python main.py lote --csv datos/ejemplo_rasgos.csv
```

**Especificar la ubicación del archivo de resultados:**

```bash
python main.py lote --csv datos/ejemplo_rasgos.csv --salida salidas/resultados.csv
```

El archivo de resultados se guarda por defecto en `salidas/resultados_lote.csv`.

El procesamiento por lotes utiliza el modo directo, sin requerir una API de LLM. Los formatos de audio contemplados por el extractor incluyen MP3, M4A, WAV, FLAC, OGG y MP4.

### 3. Auditar las contribuciones de los agentes

Para calcular la auditoría de contribuciones mediante valores de Shapley sobre un CSV:

```bash
python main.py auditar datos/ejemplo_rasgos.csv
```

Por defecto, la auditoría utiliza el conjunto de prueba definido en la calibración. Para utilizar todos los audios del archivo:

```bash
python main.py auditar datos/ejemplo_rasgos.csv --todo
```

### 4. Calibrar los umbrales y regenerar la ontología

```bash
python main.py calibrar datos/ejemplo_rasgos.csv
```

Por defecto, la calibración utiliza la división por hablante definida en el proyecto. Para calibrar utilizando todos los registros:

```bash
python main.py calibrar datos/ejemplo_rasgos.csv --todo
```

Este proceso actualiza los umbrales en `config/umbrales_calibrados.json` y regenera la ontología calibrada en `ontologia/Ontologia_Artefactos_Audio_calibrada.owx`.

> **Importante:** la opción `--todo` utiliza todos los registros para calibrar; úsala únicamente cuando corresponda a tu procedimiento de evaluación.

## Estructura del proyecto

```text
Vox-Forense-main/
│
├── main.py
├── requirements.txt
├── .env.example
├── README.md
│
├── config/
│   └── umbrales_calibrados.json
│
├── datos/
│   └── ejemplo_rasgos.csv
│
├── evaluacion/
│   └── analizar_resultados.py
│
├── ontologia/
│   ├── Ontologia_Artefactos_Audio_calibrada.owx
│   └── gen_owx.py
│
└── vox/
    ├── agentes.py
    ├── auditoria.py
    ├── calibracion.py
    ├── casos.py
    ├── config.py
    ├── contract_net.py
    ├── crew.py
    ├── features.py
    ├── herramientas.py
    ├── ontologia.py
    ├── pipeline.py
    ├── politica.py
    └── tareas.py
```

## Evaluación del proyecto

El prototipo fue evaluado con un conjunto de 963 audios: 502 auténticos y 461 sintéticos, correspondientes a 21 voces.

La evaluación contempla la validación lógica de la ontología, el desempeño del sistema, la detección de contradicciones, el escalamiento a revisión humana y la contribución de los agentes mediante valores de Shapley.

En el conjunto de prueba reportado, el sistema emitió un veredicto en 120 de 273 audios y acertó en 118 de esos casos. Los demás casos se escalaron a revisión humana, de acuerdo con la política conservadora de decisión del sistema.

## Consideraciones

- Los resultados dependen de los umbrales calibrados con el corpus utilizado.
- La ausencia de indicios no implica necesariamente que un audio sea auténtico.
- El sistema contempla el escalamiento a revisión humana cuando la evidencia es insuficiente o contradictoria.
- Los resultados del prototipo no garantizan generalización a cualquier generador de voz sintética o condición de grabación.

---
**VOX-Forense | Materia: Agentes Inteligentes**  
Universidad Iberoamericana Puebla
