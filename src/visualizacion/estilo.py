INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e1e0d9"
FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

COLOR_TIPO = {"Urbana tráfico": "#b0605a", "Urbana fondo": "#7fa886", "Suburbana": "#5f7faf"}
ETIQUETA_TIPO = {"Urbana tráfico": "Tráfico", "Urbana fondo": "Fondo", "Suburbana": "Suburbana"}
COLOR_MEDIA = "#7a7a7a"
COLOR_SERIE = {**{ETIQUETA_TIPO[tipo]: color for tipo, color in COLOR_TIPO.items()}, "Media": COLOR_MEDIA}
TEXTO_SERIE = {"Tráfico": "#8a3f3a", "Fondo": "#4a7552", "Suburbana": "#3f5f8f", "Media": INK_2}
RAMPA_NO2 = ["#fef0d9", "#fdcc8a", "#fc8d59", "#e34a33", "#b30000"]

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


class Formato:
    """Formato en español de cifras, distancias y fechas."""

    @staticmethod
    def numero(valor, decimales=1):
        return f"{valor:.{decimales}f}".replace(".", ",")

    @staticmethod
    def distancia(km):
        return f"{round(km * 100) * 10:.0f} m" if km < 1 else f"{Formato.numero(km)} km"

    @staticmethod
    def mes(fecha):
        return f"{MESES[fecha.month - 1]} de {fecha.year}"

    @staticmethod
    def dia(fecha):
        return f"{DIAS[fecha.dayofweek]}, {fecha.day} de {Formato.mes(fecha)}"

    @staticmethod
    def tipo_dia(fecha):
        return "fin de semana" if fecha.dayofweek >= 5 else "laborable"

    @staticmethod
    def rango(inicio, fin):
        return f"{Formato.mes(inicio)} – {Formato.mes(fin)}"


class RampaNO2:
    """Escala de color secuencial del NO2 (ColorBrewer OrRd): claro es poco NO2 y oscuro, mucho.

    La comparten las estaciones del mapa, el monigote, la muestra del panel y la leyenda.
    """

    @staticmethod
    def color(valor, maximo):
        """Color de la rampa para un valor, interpolando linealmente entre sus tramos."""
        posicion = min(max(valor / maximo, 0.0), 1.0) * (len(RAMPA_NO2) - 1)
        tramo = min(int(posicion), len(RAMPA_NO2) - 2)
        inicio, fin = RampaNO2._rgb(RAMPA_NO2[tramo]), RampaNO2._rgb(RAMPA_NO2[tramo + 1])
        fraccion = posicion - tramo
        return "#" + "".join(f"{round(a + (b - a) * fraccion):02x}" for a, b in zip(inicio, fin))

    @staticmethod
    def gradiente_css():
        return f"linear-gradient(to right, {', '.join(RAMPA_NO2)})"

    @staticmethod
    def _rgb(hexadecimal):
        return tuple(int(hexadecimal[i:i + 2], 16) for i in (1, 3, 5))
