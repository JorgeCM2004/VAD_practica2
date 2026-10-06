# VAD Práctica 2: cuadro de mando NO2 Madrid

## Autor

Jorge Camacho Mejías.

## Contenido

Cuadro de mando en Dash con las mediciones horarias de NO2 de las estaciones de Madrid, de enero
de 2025 a agosto de 2026.

Desplegado en https://vad.cheesyrat.com.

### Gráfico 1: NO2 hora a hora por tipo de estación

Una línea por tipo de estación (tráfico, fondo y suburbana) y otra discontinua con la media de
los tres. Se puede ver por día, por mes o la media de todo el periodo. En día y mes hay un slider
y un botón Play para ir pasando las fechas. El eje Y no cambia dentro de cada escala para que no
salte al reproducir.

### Gráfico 2: del valle al pico

Está al lado del anterior y cambia con él. Para cada línea muestra cuántas veces es mayor la hora
más contaminada que la menos contaminada (máximo / mínimo de las 24 horas). En la escala de día el
eje se corta en 25, porque hay días en los que el mínimo baja de 1 µg/m³ y el cociente llega a 68.
Solo pasa en 19 de las 2432 barras, y en esas se escribe encima el valor real.

### Mapa

Las 23 estaciones coloreadas según su NO2 medio en la fecha elegida arriba, y un monigote que se
puede arrastrar, mover haciendo clic o llevar a una calle con el buscador (Nominatim de
OpenStreetMap, como mucho una petición por segundo). En el sitio del monigote se estima el NO2 con
el modelo de abajo.

## Modelo

Está en `src/modelo/modelo_no2.py`. Es una regresión de uso del suelo (LUR), lo que se suele usar
para estimar el NO2 en un punto donde no hay estación:

```
NO2 estimado = nivel medio de las estaciones ese día x factor del entorno
```

El factor del entorno sale de una regresión lineal (scikit-learn) entre el nivel relativo de cada
estación y log(1 + distancia a la vía principal más cercana). Se entrena con las 23 estaciones y
los 603 días en los que todas tienen datos. Las vías se descargaron de OpenStreetMap con
`src/datos/descarga_vias.py` y están guardadas en `data/vias_principales.csv.gz`.

Lo que la regresión no explica en cada estación se interpola con un proceso gaussiano (kriging de
los residuos), con un alcance de unos 1,9 km. Cerca de una estación (a menos de unos 200 m) la
estimación se acerca a lo que mide esa estación, y justo encima coincide con ella. El intervalo
del 90% se calcula con los errores de la validación.

Validación dejando fuera una estación cada vez (error medio en µg/m³):

| Método                  | Error |
| ----------------------- | ----- |
| Modelo completo         | 3,87  |
| Solo LUR                | 3,95  |
| Media de las estaciones | 4,48  |
| Estación más cercana    | 5,60  |

También se probó un kriging solo con las coordenadas, pero no mejoraba a la media de las
estaciones: lo que diferencia a unas estaciones de otras es lo que tienen alrededor (parque, monte,
tráfico) y no dónde están.

El modelo no sabe cuánto tráfico tiene cada calle ni tiene en cuenta otras fuentes como el
aeropuerto. Lejos de las estaciones la estimación es poco fiable, y en ese caso el panel lo avisa.

## Estructura del proyecto

```
├── 📁 assets
│   ├── 🎨 estilo.css
│   └── 📄 mapa.js
├── 📁 data
│   ├── 📄 calidad_aire_2025.csv
│   ├── 📄 estaciones.csv
│   └── 📦 vias_principales.csv.gz
├── 📁 src
│   ├── 📁 aplicacion
│   │   ├── 🐍 __init__.py
│   │   └── 🐍 cuadro_mando.py
│   ├── 📁 datos
│   │   ├── 🐍 __init__.py
│   │   ├── 🐍 datos_no2.py
│   │   └── 🐍 descarga_vias.py
│   ├── 📁 modelo
│   │   ├── 🐍 __init__.py
│   │   └── 🐍 modelo_no2.py
│   ├── 📁 servicios
│   │   ├── 🐍 __init__.py
│   │   └── 🐍 geocodificador.py
│   ├── 📁 visualizacion
│   │   ├── 🐍 __init__.py
│   │   ├── 🐍 estilo.py
│   │   ├── 🐍 graficos.py
│   │   └── 🐍 mapa.py
│   ├── 🐍 __init__.py
│   └── 🐍 configuracion.py
├── ⚙️ .dockerignore
├── ⚙️ .gitignore
├── 🐳 Dockerfile
├── 📝 README.md
├── 🐍 app.py
├── ⚙️ docker-compose.yml
├── ⚙️ pyproject.toml
├── 📄 requirements.txt
└── 📄 uv.lock
```

`CuadroDeMando` crea los datos, el modelo y los gráficos y registra los callbacks. Al mover el
slider se actualizan a la vez los dos gráficos y el mapa.

## Ejecución local

Requiere [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run app.py
```

La app se abre en http://127.0.0.1:8050. Con `pip`:

```bash
pip install -r requirements.txt
python app.py
```

Para volver a descargar las vías de OpenStreetMap (no hace falta, el fichero ya está en `data/`):

```bash
uv run python -m src.datos.descarga_vias
```

## Despliegue

```bash
docker compose up -d --build
```

Levanta la app con gunicorn en el puerto 8050.

## Datos

- Calidad del aire (datos horarios) y estaciones: Portal de Datos Abiertos del Ayuntamiento de
  Madrid. Solo se usan las mediciones validadas (`V`).
- Vías principales: OpenStreetMap (ODbL).
- Mapa base: IGNBase-gris del IGN (CC BY 4.0).
- En "Todo el periodo" los meses de enero a agosto cuentan dos veces (2025 y 2026) y los de
  septiembre a diciembre solo una.

## Uso IA

Se ha usado IA generativa para:

- Desarrollo del cuadro de mando (Dash) y de la configuración de despliegue.
- Arreglo de bugs.
