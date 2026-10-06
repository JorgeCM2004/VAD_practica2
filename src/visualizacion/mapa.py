import base64
import math

import dash_leaflet as dl
import numpy as np
import pandas as pd
from dash import html

from src.visualizacion.estilo import INK_2, RAMPA_NO2, Formato, RampaNO2

URL_TESELAS = (
    "https://www.ign.es/wmts/ign-base?layer=IGNBase-gris&style=default"
    "&tilematrixset=GoogleMapsCompatible&Service=WMTS&Request=GetTile&Version=1.0.0"
    "&Format=image/jpeg&TileMatrix={z}&TileCol={x}&TileRow={y}"
)
CREDITOS = "Mapa base: IGN España (CC BY 4.0) · Vías: © OpenStreetMap"
CENTRO = [40.435, -3.69]
ZOOM_INICIAL = 12
ZOOM_MAXIMO = 19
ZOOM_BUSQUEDA = 15
LUGAR_INICIAL = {"lat": 40.4168, "lon": -3.7038, "nombre": "Puerta del Sol"}
SITIO_SIN_NOMBRE = "el punto elegido"
TOLERANCIA_LUGAR_GRADOS = 2e-4
LEJOS_KM = 6
PESO_ANCLADA = 0.5
CORRECCION_VISIBLE = 0.5
RADIO_MARCADOR = 9
COLOR_SIN_ESTIMACION = "#d9d8d3"
SVG_MONIGOTE = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='32' height='48' viewBox='0 0 32 48'>"
    "<ellipse cx='16' cy='45' rx='8' ry='2.5' fill='rgba(0,0,0,0.28)'/>"
    "<circle cx='16' cy='8' r='6.5' fill='RELLENO' stroke='#2b2a28' stroke-width='1.8'/>"
    "<path d='M9.5 16.5h13a3 3 0 0 1 3 3v10a2 2 0 0 1-2 2h-1.5v10.5a2 2 0 0 1-2 2h-2.5v-9h-3v9"
    "h-2.5a2 2 0 0 1-2-2V31.5H8.5a2 2 0 0 1-2-2v-10a3 3 0 0 1 3-3z' fill='RELLENO' "
    "stroke='#2b2a28' stroke-width='1.8' stroke-linejoin='round'/></svg>"
)
MANEJADOR_ARRASTRE = {"variable": "vadMapa.soltarMonigote"}


class MapaNO2:
    """Mapa con las estaciones, el monigote y el panel con la estimación del modelo."""

    def __init__(self, datos, modelo):
        self.datos = datos
        self.modelo = modelo
        self.vmax = {escala: math.ceil(maximo / 10) * 10 for escala, maximo in datos.no2_estacion_max.items()}

    def componente(self):
        return dl.Map(
            id="mapa", center=CENTRO, zoom=ZOOM_INICIAL, className="mapa", attributionControl=False,
            children=[
                dl.TileLayer(url=URL_TESELAS, maxZoom=ZOOM_MAXIMO),
                dl.LayerGroup(id="capa-estaciones"),
                dl.Marker(
                    id="monigote", position=[LUGAR_INICIAL["lat"], LUGAR_INICIAL["lon"]],
                    draggable=True, icon=self.icono_monigote(RAMPA_NO2[2]), zIndexOffset=1000,
                    title="Arrástrame, o haz clic en el mapa para moverme",
                    eventHandlers={"dragend": MANEJADOR_ARRASTRE},
                ),
            ],
        )

    @staticmethod
    def viewport(lat, lon):
        return {"center": [lat, lon], "zoom": ZOOM_BUSQUEDA, "transition": "flyTo"}

    def marcadores(self, valores, escala):
        """Un círculo por estación con el color de su NO2 (blanco si no hay dato)."""
        marcadores = []
        for codigo, estacion in self.datos.estaciones.iterrows():
            valor = valores[codigo]
            if pd.isna(valor):
                estilo, lectura = {"fillColor": "#ffffff", "dashArray": "3"}, "sin datos"
            else:
                estilo = {"fillColor": RampaNO2.color(valor, self.vmax[escala])}
                lectura = f"{Formato.numero(valor)} µg/m³"
            marcadores.append(dl.CircleMarker(
                center=[estacion["lat"], estacion["lon"]], radius=RADIO_MARCADOR, color=INK_2,
                weight=1.5, fillOpacity=0.95,
                children=dl.Tooltip(f"{estacion['nombre']} ({estacion['tipo']}): {lectura}"), **estilo,
            ))
        return marcadores

    def leyenda(self, escala):
        vmax = self.vmax[escala]
        return [
            html.Span("NO2 medio en las estaciones", className="leyenda-titulo"),
            html.Div(className="leyenda-escala", children=[
                html.Div(className="leyenda-barra", style={"background": RampaNO2.gradiente_css()}),
                html.Div(className="leyenda-marcas", children=[
                    html.Span("0"), html.Span(f"{vmax / 2:.0f}"), html.Span(f"{vmax} µg/m³"),
                ]),
            ]),
            html.Span(className="leyenda-item", children=[
                html.Img(src=self.icono_monigote(RAMPA_NO2[2])["iconUrl"], alt="", height=22),
                "Punto estimado (su color es el NO2 estimado)",
            ]),
            html.Span(className="leyenda-item", children=[html.Span(className="punto-sindato"), "Sin datos"]),
            html.Span(CREDITOS, className="creditos"),
        ]

    def icono(self, estimacion, escala):
        if estimacion is None:
            return self.icono_monigote(COLOR_SIN_ESTIMACION)
        return self.icono_monigote(RampaNO2.color(estimacion.estimacion, self.vmax[escala]))

    def titulo(self, estimacion, lugar, lat, lon):
        if estimacion is None:
            return "No hay suficientes estaciones con datos para estimar"
        sitio = self._sitio(estimacion, lugar, lat, lon)
        return f"En {sitio} respirarías unos {Formato.numero(estimacion.estimacion)} µg/m³ de NO2"

    def resumen(self, estimacion, escala):
        if estimacion is None:
            return html.P("Elige otro día en el slider.", className="nota")
        return [
            html.P("NO2 estimado", className="resultado-etiqueta"),
            html.P(className="resultado-cifra", children=[
                html.Span(className="muestra", style={
                    "background": RampaNO2.color(estimacion.estimacion, self.vmax[escala]),
                }),
                html.Span(Formato.numero(estimacion.estimacion), className="resultado-valor"),
                html.Span(" µg/m³", className="resultado-unidad"),
            ]),
            html.P(
                f"Intervalo del 90 %: {Formato.numero(estimacion.bajo)} – {Formato.numero(estimacion.alto)} µg/m³",
                className="resultado-intervalo",
            ),
        ]

    def cabecera_motivos(self):
        # Va fuera de "motivos" para que el recuadro no se cierre al cambiar la estimación
        return html.Div(className="por-que", children=[
            html.H3("Por qué"),
            html.Details(className="info", children=[
                html.Summary("i", title="Cómo funciona el modelo", **{"aria-label": "Cómo funciona el modelo"}),
                html.P(self._explicacion_modelo(), className="info-contenido"),
            ]),
        ])

    def motivos(self, estimacion, valores, lat, lon):
        """Lista de por qué sale ese valor, con un aviso si el punto queda muy lejos."""
        if estimacion is None:
            return None
        distancias = self.modelo.distancias_km(lat, lon)
        anclada = estimacion.peso_estacion >= PESO_ANCLADA
        lejos = not anclada and (
            distancias.min() > LEJOS_KM or estimacion.dist_via_km > self.modelo.limites[1]
        )
        return [
            html.Ul(self._lista_motivos(estimacion, valores, distancias, anclada)),
            html.P("Lejos de las estaciones o de cualquier vía conocida: la estimación es poco fiable.",
                   className="aviso") if lejos else None,
        ]

    @staticmethod
    def latlon(posicion):
        # dash-leaflet a veces la da como lista y otras como diccionario
        if isinstance(posicion, dict):
            return float(posicion["lat"]), float(posicion.get("lng", posicion.get("lon")))
        return float(posicion[0]), float(posicion[1])

    @staticmethod
    def icono_monigote(relleno):
        svg = SVG_MONIGOTE.replace("RELLENO", relleno)
        return {
            "iconUrl": "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode(),
            "iconSize": [32, 48],
            "iconAnchor": [16, 45],
        }

    def _sitio(self, estimacion, lugar, lat, lon):
        buscado = (
            lugar and lugar.get("nombre")
            and abs(lat - lugar["lat"]) < TOLERANCIA_LUGAR_GRADOS
            and abs(lon - lugar["lon"]) < TOLERANCIA_LUGAR_GRADOS
        )
        if buscado:
            return lugar["nombre"]
        if estimacion.peso_estacion >= PESO_ANCLADA:
            return f"la estación {self.datos.estaciones.iloc[estimacion.estacion]['nombre']}"
        return SITIO_SIN_NOMBRE

    def _lista_motivos(self, estimacion, valores, distancias, anclada):
        ajuste = (estimacion.factor - 1) * 100
        sentido = "por encima" if ajuste >= 0 else "por debajo"
        via = estimacion.via or "una vía principal sin nombre"
        motivos = [
            html.Li(f"Nivel medio de las {estimacion.estaciones} estaciones: {Formato.numero(estimacion.nivel)} µg/m³."),
            html.Li(
                f"Vía principal más cercana: {via}, a {Formato.distancia(estimacion.dist_via_km)}. Por el "
                f"entorno, el modelo lo sitúa un {abs(ajuste):.0f} % {sentido} de ese nivel "
                f"({Formato.numero(estimacion.lur)} µg/m³)."
            ),
        ]
        if abs(estimacion.correccion) >= CORRECCION_VISIBLE:
            signo = "+" if estimacion.correccion > 0 else "−"
            motivos.append(html.Li(
                f"Corrección por lo que miden ahora las estaciones de alrededor: "
                f"{signo}{Formato.numero(abs(estimacion.correccion))} µg/m³."
            ))
        if anclada:
            ancla = self.datos.estaciones.iloc[estimacion.estacion]
            motivos.append(html.Li(
                f"Estás junto a la estación {ancla['nombre']} (a {Formato.distancia(distancias[estimacion.estacion])}): "
                f"la estimación se ancla a lo que mide, {Formato.numero(valores.iloc[estimacion.estacion])} µg/m³."
            ))
        else:
            cercana = int(np.argmin(distancias))
            medido = valores.iloc[cercana]
            lectura = "sin datos en este instante" if pd.isna(medido) else f"{Formato.numero(medido)} µg/m³ medidos"
            motivos.append(html.Li(
                f"Estación más cercana: {self.datos.estaciones.iloc[cercana]['nombre']}, a "
                f"{Formato.distancia(distancias[cercana])}: {lectura}."
            ))
        return motivos

    def _explicacion_modelo(self):
        validacion = self.modelo.validacion
        return (
            "Modelo: regresión de uso del suelo (LUR) con la distancia a las vías principales "
            "(OpenStreetMap) más kriging de lo que la LUR no explica; junto a una estación (~200 m) "
            f"manda su medición. Entrenado con {len(self.datos.estaciones)} estaciones y "
            f"{validacion.dias} días. Validación dejando fuera cada estación: error medio "
            f"{Formato.numero(validacion.modelo)} µg/m³, frente a {Formato.numero(validacion.media)} "
            f"con la media de las estaciones y {Formato.numero(validacion.vecino)} con la más cercana. "
            "No conoce el tráfico real de tu calle."
        )
