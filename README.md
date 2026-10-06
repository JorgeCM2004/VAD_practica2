# VAD Práctica 2: cuadro de mando NO2 Madrid

## Autor

Jorge Camacho Mejías.

## Contenido

Cuadro de mando interactivo (Dash) sobre las mediciones horarias de NO2 de las estaciones de
Madrid, con el dataset completo (enero 2025 – agosto 2026).

Desplegado en https://vad.cheesyrat.com.

**Gráfico principal 1: NO2 hora a hora por tipo de estación.** Muestra una línea por tipo
(tráfico, fondo, suburbana) y la media de los tres en gris discontinuo. Tiene tres escalas:

- **Día:** un slider recorre los 608 días y el botón Play los reproduce.
- **Mes:** 20 meses, con slider y Play.
- **Todo el periodo:** la media de cada hora en todo el dataset.

El eje Y es fijo dentro de cada escala, para que no salte al reproducir.

**Gráfico principal 2: del valle al pico.** A la derecha del anterior y actualizado con él, muestra
una barra por línea con cuántas veces se multiplica el NO2 entre su hora más baja y la más alta
(máximo ÷ mínimo de las 24 horas). En la escala Día el eje llega hasta ×25: algunos días el valle
baja de 1 µg/m³ y el cociente se dispara (hasta ×68). Esas barras, 19 de 2.432, se recortan y
muestran su valor real con ▲.

**Mapa: ¿qué NO2 respirarías?** Ocupa todo el ancho. Muestra las 23 estaciones coloreadas por su
NO2 medio en el instante elegido arriba (día, mes o periodo completo) y un monigote que se puede
arrastrar, colocar con un clic o llevar a una calle con el buscador. En la posición del monigote
se estima el NO2 con un modelo de ML (ver abajo), y la estimación se recalcula al cambiar la fecha.

## Modelo de inferencia (`src/modelo/modelo_no2.py`)

Es una **regresión de uso del suelo (Land Use Regression)**, la técnica estándar en epidemiología
para estimar la exposición a NO2 en un domicilio:

`NO2 estimado = nivel medio de las estaciones en ese instante × factor del entorno`

- **Factor del entorno:** una regresión lineal (scikit-learn), entrenada con 23 estaciones y 603
  días, aprende cómo cambia el nivel relativo persistente de cada estación con
  log(1 + distancia a la vía principal urbana más cercana). Las vías salen de OpenStreetMap
  (`src/datos/descarga_vias.py`, `data/vias_principales.csv.gz`).
- **Kriging de los residuos:** lo que la LUR no explica en cada estación ese día se interpola
  con un proceso gaussiano, cuyo alcance (~1,9 km) y ruido local se aprenden con todos los días.
- **Anclaje a las mediciones:** junto a una estación manda lo que mide (peso 1 encima de ella,
  que se desvanece hacia los 200 m). Así, encima de una estación la estimación coincide con
  su lectura y el intervalo se cierra.
- **Intervalo del 90%:** cuantiles del cociente real ÷ estimado en la validación.
- **Validación (dejando fuera cada estación):** error medio de 3,87 µg/m³ (3,95 con la LUR
  sola), frente a 4,48 si se usa la media de las estaciones y 5,6 si se usa la estación más
  cercana.
- **Descartado:** un proceso gaussiano (kriging) que usaba solo las coordenadas no mejoraba a la
  media de las estaciones. Las diferencias entre estaciones dependen de su entorno (monte,
  parque, nudo de tráfico), no de su posición.
- **Limitaciones:** no conoce el tráfico real de cada calle ni fuentes como el aeropuerto;
  lejos de las estaciones la estimación es poco fiable y el panel lo avisa.

El buscador usa Nominatim (OpenStreetMap), con una petición por segundo como máximo y caché.

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

`CuadroDeMando` crea una instancia de cada clase y conecta los callbacks: el instante elegido
en el slider (día, mes o todo el periodo) actualiza a la vez los dos gráficos y el mapa.

## Ejecución local

Requiere [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run app.py
```

La app queda en http://127.0.0.1:8050. Con `pip`:

```bash
pip install -r requirements.txt
python app.py
```

Para volver a descargar las vías de OpenStreetMap (no hace falta: el fichero ya está en `data/`):

```bash
uv run python -m src.datos.descarga_vias
```

## Despliegue (Docker)

```bash
docker compose up -d --build
```

Arranca gunicorn en el puerto 8050.

En el servidor, después de cada cambio:

```bash
git pull && docker compose up -d --build
```

Nginx Proxy Manager: *Proxy Host* → `vad.cheesyrat.com` → `http://<IP-de-la-VM>:8050`, con un
certificado de Let's Encrypt y *Force SSL*. Dash funciona sobre HTTP normal y no necesita
websockets.

## Datos

- Fuente: Portal de Datos Abiertos del Ayuntamiento de Madrid (calidad del aire, datos horarios) y
  metadatos de las estaciones.
- Grano: una medición horaria de NO2 por estación. Solo se usan las mediciones validadas (`V`).
- Vías principales: © colaboradores de OpenStreetMap (ODbL).
- Mapa base: IGNBase-gris del Instituto Geográfico Nacional (CC BY 4.0), sin API key.
- La media de la escala "Todo el periodo" cuenta dos veces los meses de enero a agosto (2025 y
  2026) y una sola vez los de septiembre a diciembre.

## Uso IA

Se ha usado IA generativa para:

- Desarrollo del cuadro de mando (Dash) y de la configuración de despliegue.
- Arreglo de bugs.
