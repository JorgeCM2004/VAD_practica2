import json
import threading
import time
import urllib.parse
import urllib.request
from functools import lru_cache

URL_NOMINATIM = "https://nominatim.openstreetmap.org/search"
AGENTE = "VAD-NO2-Madrid/1.0 (cuadro de mando academico, UPM)"
VIEWBOX_MADRID = "-3.889,40.643,-3.518,40.312"
ESPERA_MINIMA_S = 1.0
TIMEOUT_S = 6
TAMANO_CACHE = 256


class Geocodificador:
    """Buscador de calles de Madrid con Nominatim (una petición por segundo como máximo y caché)."""

    def __init__(self):
        self._candado = threading.Lock()
        self._ultima_peticion = 0.0
        self._buscar_en_cache = lru_cache(maxsize=TAMANO_CACHE)(self._consultar)

    def buscar(self, texto):
        """Devuelve (lat, lon, nombre) o None. Lanza OSError si Nominatim no responde."""
        normalizado = " ".join(texto.split()).lower()
        return self._buscar_en_cache(normalizado) if normalizado else None

    def _consultar(self, texto):
        parametros = urllib.parse.urlencode({
            "q": texto, "format": "jsonv2", "limit": 1, "viewbox": VIEWBOX_MADRID, "bounded": 1,
            "countrycodes": "es", "accept-language": "es",
        })
        peticion = urllib.request.Request(f"{URL_NOMINATIM}?{parametros}", headers={"User-Agent": AGENTE})
        with self._candado:
            espera = ESPERA_MINIMA_S - (time.monotonic() - self._ultima_peticion)
            if espera > 0:
                time.sleep(espera)
            self._ultima_peticion = time.monotonic()
            with urllib.request.urlopen(peticion, timeout=TIMEOUT_S) as respuesta:
                resultados = json.load(respuesta)

        if not resultados:
            return None
        primero = resultados[0]
        return float(primero["lat"]), float(primero["lon"]), self._nombre_corto(primero["display_name"])

    @staticmethod
    def _nombre_corto(nombre_completo):
        partes = nombre_completo.split(", ")
        if len(partes) > 1 and partes[0].isdigit():
            partes[0], partes[1] = partes[1], partes[0]
        return ", ".join(partes[:2])
