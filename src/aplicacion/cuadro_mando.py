import pandas as pd
from dash import Dash, Input, Output, State, ctx, dcc, html, no_update

from src.configuracion import ASSETS_DIR
from src.datos import ESCALAS, DatosNO2
from src.modelo import ModeloNO2
from src.servicios import Geocodificador
from src.visualizacion import (
    ETIQUETA_TIPO, LUGAR_INICIAL, Formato, GraficoHorario, GraficoPicoValle, MapaNO2,
)

TITULO_PAGINA = "NO2 Madrid"
ESCALA_INICIAL = "dia"
INTERVALO_PLAY_MS = {"dia": 300, "mes": 1000}
TEXTO_PLAY = "▶ Play"
TEXTO_PAUSA = "❚❚ Pausa"
ALTURA_GRAFICO = "420px"
SIN_GRAFICO = {"displayModeBar": False}


class CuadroDeMando:
    """Página Dash con los dos gráficos y el mapa, sincronizados con el slider."""

    def __init__(self):
        self.datos = DatosNO2()
        self.modelo = ModeloNO2(self.datos)
        self.geocodificador = Geocodificador()
        self.horario = GraficoHorario(self.datos)
        self.pico_valle = GraficoPicoValle(self.datos)
        self.mapa = MapaNO2(self.datos, self.modelo)

        self.app = Dash(__name__, title=TITULO_PAGINA, assets_folder=str(ASSETS_DIR))
        self.app.index_string = self.app.index_string.replace("<html>", '<html lang="es">')
        self.app.layout = self._layout()
        self._registrar_callbacks()

    def _layout(self):
        return html.Main(className="page", children=[
            self._cabecera(),
            html.Section(className="principales", children=[self._tarjeta_horario(), self._tarjeta_pico_valle()]),
            self._tarjeta_mapa(),
        ])

    def _cabecera(self):
        rango = Formato.rango(self.datos.fecha_inicio, self.datos.fecha_fin)
        return html.Header(className="cabecera", children=[
            html.P("Demo Day 2 · Visualización Avanzada de Datos", className="eyebrow"),
            html.H1("Calidad del aire en Madrid"),
            html.P(f"Mediciones horarias de NO2 de las estaciones de la ciudad · {rango}", className="subtitulo"),
        ])

    def _tarjeta_horario(self):
        momentos = self.datos.instantes(ESCALA_INICIAL)
        return html.Article(className="card", children=[
            html.Div(className="card-cabecera", children=[
                html.Div([
                    html.P("NO2 hora a hora por tipo de estación", className="card-eyebrow"),
                    html.H2(id="titulo"),
                ]),
                dcc.RadioItems(
                    id="escala", value=ESCALA_INICIAL, inline=True, className="segmentado",
                    options=[{"label": nombre, "value": clave} for clave, nombre in ESCALAS.items()],
                ),
            ]),
            dcc.Graph(id="grafico", config=SIN_GRAFICO, style={"height": ALTURA_GRAFICO}),
            html.Div(id="reproductor", className="reproductor", children=[
                html.Button(TEXTO_PLAY, id="play", className="boton boton-play", n_clicks=0,
                            **{"aria-label": "Reproducir o pausar la evolución en el tiempo"}),
                html.Div(className="slider-fecha", children=dcc.Slider(
                    id="fecha", min=0, max=len(momentos) - 1, step=1, value=0, included=False,
                    allow_direct_input=False, updatemode="drag",
                    marks=self.horario.marcas_slider(momentos),
                )),
            ]),
            dcc.Interval(id="tic", interval=INTERVALO_PLAY_MS[ESCALA_INICIAL], disabled=True),
            dcc.Store(id="instante"),
        ])

    @staticmethod
    def _tarjeta_pico_valle():
        return html.Article(className="card card-barras", children=[
            html.P("Del valle al pico", className="card-eyebrow"),
            html.H2(id="titulo-barras"),
            dcc.Graph(id="barras", config=SIN_GRAFICO, responsive=True, className="grafico-flexible"),
        ])

    def _tarjeta_mapa(self):
        return html.Section(className="card card-mapa", children=[
            html.Div(className="card-cabecera", children=[
                html.Div([
                    html.P("Mapa · ¿qué NO2 respirarías?", className="card-eyebrow"),
                    html.H2(id="titulo-mapa"),
                ]),
                html.Div(className="buscador", role="search", children=[
                    html.Label("Buscar una calle de Madrid", htmlFor="busqueda", className="sr-only"),
                    dcc.Input(id="busqueda", type="search", placeholder="Busca una calle de Madrid",
                              autoComplete="off", n_submit=0),
                    html.Button("Buscar", id="buscar", className="boton", n_clicks=0),
                ]),
            ]),
            html.P(id="estado-busqueda", className="estado-busqueda", **{"aria-live": "polite"}),
            html.Div(className="mapa-cuerpo", children=[
                html.Div(className="mapa-columna", children=[
                    self.mapa.componente(),
                    html.Div(id="leyenda-mapa", className="leyenda"),
                ]),
                html.Aside(className="resultado", children=[
                    html.Div(id="resultado", **{"aria-live": "polite"}),
                    self.mapa.cabecera_motivos(),
                    html.Div(id="motivos", **{"aria-live": "polite"}),
                ]),
            ]),
            dcc.Store(id="lugar", data=LUGAR_INICIAL),
        ])

    def _registrar_callbacks(self):
        callback = self.app.callback
        callback(
            Output("fecha", "max"), Output("fecha", "marks"), Output("fecha", "value"),
            Output("reproductor", "hidden"), Output("tic", "interval"),
            Output("tic", "disabled", allow_duplicate=True), Output("play", "children", allow_duplicate=True),
            Input("escala", "value"), State("instante", "data"),
            prevent_initial_call=True,
        )(self._configurar_slider)
        callback(
            Output("tic", "disabled"), Output("play", "children"),
            Output("fecha", "value", allow_duplicate=True),
            Input("play", "n_clicks"), State("tic", "disabled"), State("fecha", "value"), State("fecha", "max"),
            prevent_initial_call=True,
        )(self._play_pausa)
        callback(
            Output("fecha", "value", allow_duplicate=True),
            Output("tic", "disabled", allow_duplicate=True), Output("play", "children", allow_duplicate=True),
            Input("tic", "n_intervals"), State("fecha", "value"), State("fecha", "max"),
            prevent_initial_call=True,
        )(self._avanzar)
        callback(
            Output("titulo", "children"), Output("grafico", "figure"),
            Output("instante", "data"),
            Output("titulo-barras", "children"), Output("barras", "figure"),
            Input("fecha", "value"), Input("escala", "value"),
        )(self._actualizar_graficos)
        callback(
            Output("monigote", "position"), Output("mapa", "viewport"), Output("lugar", "data"),
            Output("estado-busqueda", "children"),
            Input("mapa", "clickData"), Input("buscar", "n_clicks"), Input("busqueda", "n_submit"),
            State("busqueda", "value"),
            prevent_initial_call=True,
        )(self._mover_monigote)
        callback(
            Output("capa-estaciones", "children"), Output("leyenda-mapa", "children"),
            Input("fecha", "value"), Input("escala", "value"),
        )(self._actualizar_estaciones)
        callback(
            Output("titulo-mapa", "children"), Output("resultado", "children"),
            Output("motivos", "children"), Output("monigote", "icon"),
            Input("monigote", "position"), Input("fecha", "value"), Input("escala", "value"),
            State("lugar", "data"),
        )(self._inferir_no2)

    def _momento(self, indice, escala):
        momentos = self.datos.instantes(escala)
        return momentos[min(indice or 0, len(momentos) - 1)] if len(momentos) else None

    def _configurar_slider(self, escala, instante):
        if escala == "total":
            return 0, {}, 0, True, no_update, True, TEXTO_PLAY
        momentos = self.datos.instantes(escala)
        indice = 0
        if instante:
            objetivo = pd.Timestamp(instante)
            if escala == "mes":
                objetivo = objetivo.to_period("M").to_timestamp()
            indice = max(int(momentos.get_indexer([objetivo])[0]), 0)
        marcas = self.horario.marcas_slider(momentos)
        return len(momentos) - 1, marcas, indice, False, INTERVALO_PLAY_MS[escala], True, TEXTO_PLAY

    @staticmethod
    def _play_pausa(_clics, parado, valor, maximo):
        if not parado:
            return True, TEXTO_PLAY, no_update
        return False, TEXTO_PAUSA, 0 if valor >= maximo else no_update

    @staticmethod
    def _avanzar(_tics, valor, maximo):
        siguiente = (valor or 0) + 1
        if siguiente >= maximo:
            return maximo, True, TEXTO_PLAY
        return siguiente, no_update, no_update

    def _actualizar_graficos(self, indice, escala):
        instante = self._momento(indice, escala)
        curvas, media = self.datos.perfil_tipos(escala, instante)
        amplitud = self.datos.pico_valle(curvas, media).rename(index=ETIQUETA_TIPO)
        return (
            self.horario.titulo(escala, instante),
            self.horario.figura(curvas, media, escala),
            instante.isoformat() if instante is not None else no_update,
            self.pico_valle.titulo(amplitud),
            self.pico_valle.figura(amplitud, escala),
        )

    def _mover_monigote(self, clic, _clics, _enter, texto):
        if ctx.triggered_id == "mapa":
            lat, lon = clic["latlng"]["lat"], clic["latlng"]["lng"]
            return [lat, lon], no_update, {"lat": lat, "lon": lon, "nombre": None}, ""
        texto = (texto or "").strip()
        if not texto:
            return no_update, no_update, no_update, "Escribe una calle o un lugar de Madrid."
        try:
            encontrado = self.geocodificador.buscar(texto)
        except OSError:
            return (no_update, no_update, no_update,
                    "El buscador no responde ahora mismo: arrastra el monigote o haz clic en el mapa.")
        if encontrado is None:
            return no_update, no_update, no_update, f"No se ha encontrado «{texto}» en Madrid."
        lat, lon, nombre = encontrado
        return [lat, lon], self.mapa.viewport(lat, lon), {"lat": lat, "lon": lon, "nombre": nombre}, ""

    def _actualizar_estaciones(self, indice, escala):
        instante = self._momento(indice, escala)
        valores = self.datos.no2_estaciones(escala, instante)
        return self.mapa.marcadores(valores, escala), self.mapa.leyenda(escala)

    def _inferir_no2(self, posicion, indice, escala, lugar):
        lat, lon = self.mapa.latlon(posicion)
        valores = self.datos.no2_estaciones(escala, self._momento(indice, escala))
        estimacion = self.modelo.inferir(valores, lat, lon)
        return (
            self.mapa.titulo(estimacion, lugar, lat, lon),
            self.mapa.resumen(estimacion, escala),
            self.mapa.motivos(estimacion, valores, lat, lon),
            self.mapa.icono(estimacion, escala),
        )

