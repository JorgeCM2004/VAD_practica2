import csv
import gzip
import json
import math
import urllib.parse
import urllib.request

from src.configuracion import DATA_DIR

SALIDA = DATA_DIR / "vias_principales.csv.gz"
SERVIDORES = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
AGENTE = "VAD-NO2-Madrid/1.0 (cuadro de mando academico, UPM)"
BBOX = (40.28, -3.92, 40.66, -3.48)
CLASES = "motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary"
PASO_M = 25
TIMEOUT_S = 200
METROS_POR_GRADO_LAT = 110_574
METROS_POR_GRADO_LON = 111_320
CONSULTA = f"""
[out:json][timeout:180];
way["highway"~"^({CLASES})$"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
out geom;
"""


class DescargaVias:
    """Descarga una sola vez la red de vías principales de Madrid desde OpenStreetMap (Overpass).

    Guarda en data/vias_principales.csv.gz un punto cada ~25 m a lo largo de cada vía, con su
    clase y su nombre; el modelo los usa para medir la distancia de cualquier punto a la vía
    principal más cercana. Si el servidor principal está saturado prueba con un espejo.
    Datos © colaboradores de OpenStreetMap (ODbL). Uso: uv run python -m src.datos.descarga_vias
    """

    def ejecutar(self):
        """Descarga las vías, las muestrea y guarda el fichero comprimido."""
        vias = self._descargar()
        puntos = self._guardar(vias)
        print(f"{len(vias)} vías -> {puntos} puntos en {SALIDA}")

    @staticmethod
    def _descargar():
        cuerpo = urllib.parse.urlencode({"data": CONSULTA}).encode()
        for servidor in SERVIDORES:
            peticion = urllib.request.Request(servidor, data=cuerpo, headers={"User-Agent": AGENTE})
            try:
                with urllib.request.urlopen(peticion, timeout=TIMEOUT_S) as respuesta:
                    return json.load(respuesta)["elements"]
            except OSError as error:
                print(f"{servidor}: {error}")
        raise SystemExit("No se pudo descargar la red de vías de ningún servidor Overpass")

    def _guardar(self, vias):
        puntos = 0
        with gzip.open(SALIDA, "wt", newline="", encoding="utf-8") as fichero:
            escritor = csv.writer(fichero)
            escritor.writerow(["lat", "lon", "clase", "nombre"])
            for via in vias:
                if "geometry" not in via:
                    continue
                clase = via["tags"]["highway"].replace("_link", "")
                nombre = via["tags"].get("name", "")
                for lat, lon in self._muestrear(via["geometry"]):
                    escritor.writerow([f"{lat:.6f}", f"{lon:.6f}", clase, nombre])
                    puntos += 1
        return puntos

    @staticmethod
    def _muestrear(geometria):
        vertices = [(punto["lat"], punto["lon"]) for punto in geometria]
        muestras = [vertices[0]]
        for inicio, fin in zip(vertices, vertices[1:]):
            tramos = max(1, round(DescargaVias._distancia_m(inicio, fin) / PASO_M))
            for paso in range(1, tramos + 1):
                fraccion = paso / tramos
                muestras.append((
                    inicio[0] + (fin[0] - inicio[0]) * fraccion,
                    inicio[1] + (fin[1] - inicio[1]) * fraccion,
                ))
        return muestras

    @staticmethod
    def _distancia_m(inicio, fin):
        lat_media = math.radians((inicio[0] + fin[0]) / 2)
        dy = (fin[0] - inicio[0]) * METROS_POR_GRADO_LAT
        dx = (fin[1] - inicio[1]) * METROS_POR_GRADO_LON * math.cos(lat_media)
        return math.hypot(dx, dy)


if __name__ == "__main__":
    DescargaVias().ejecutar()
