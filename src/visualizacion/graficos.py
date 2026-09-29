import math

import pandas as pd
import plotly.graph_objects as go

from src.datos import TIPOS
from src.visualizacion.estilo import (
    COLOR_MEDIA, COLOR_SERIE, COLOR_TIPO, ETIQUETA_TIPO, FONT, GRID, INK, INK_2, MESES,
    TEXTO_SERIE, Formato,
)

HORAS = list(range(24))
HORAS_MARCADAS = list(range(0, 24, 3))
SEPARACION_ETIQUETAS = 0.045
TOPE_RATIO_DIA = 25
NOTA_PICO_VALLE = "Máximo ÷ mínimo de las 24 horas de cada línea"


class GraficoPlotly:
    """Base de los gráficos Plotly del cuadro de mando: tipografía, fondo transparente y tooltip."""

    @staticmethod
    def layout(**ajustes):
        """Layout común de todas las figuras, con los ajustes propios de cada una encima."""
        return {
            "font": dict(family=FONT, size=13, color=INK_2),
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "margin": dict(l=10, r=10, t=10, b=10),
            "hoverlabel": dict(bgcolor="white", font=dict(family=FONT, size=13, color=INK)),
            **ajustes,
        }


class GraficoHorario(GraficoPlotly):
    """Gráfico principal 1: NO2 hora a hora por tipo de estación y la media de los tres tipos.

    Colores RGB poco saturados para no competir con el mensaje; rojo y verde cambian también de
    luminosidad y cada línea lleva una etiqueta directa, para distinguirlas con daltonismo. Las
    etiquetas comparten `legendgroup` con su línea, así que se ocultan juntas desde la leyenda.
    El eje Y es fijo en cada escala (máximo histórico redondeado a la decena) para que no salte
    al reproducir.
    """

    def __init__(self, datos):
        self.y_max = {escala: math.ceil(maximo / 10) * 10 for escala, maximo in datos.no2_max.items()}
        self.rango = Formato.rango(datos.fecha_inicio, datos.fecha_fin)
        self.notas = {
            "dia": "Media de las estaciones de cada tipo en cada hora del día · línea discontinua: "
                   f"media de los tipos · eje fijo al máximo diario del histórico ({self.y_max['dia']} µg/m³)",
            "mes": "Media de cada hora a lo largo del mes, laborables y fines de semana · línea "
                   f"discontinua: media de los tipos · eje fijo al máximo mensual ({self.y_max['mes']} µg/m³)",
            "total": "Media de cada hora en todo el dataset · línea discontinua: media de los tipos · "
                     f"eje fijo a {self.y_max['total']} µg/m³",
        }

    def titulo(self, escala, instante):
        """Día, mes o periodo que se está viendo."""
        if escala == "dia":
            return f"{Formato.dia(instante)} · {Formato.tipo_dia(instante)}"
        if escala == "mes":
            return Formato.mes(instante).capitalize()
        return f"Todo el periodo · {self.rango}"

    def figura(self, curvas, media, escala):
        """Una línea por tipo de estación, la media discontinua y sus etiquetas directas."""
        y_max = self.y_max[escala]
        series = [(ETIQUETA_TIPO[tipo], curvas[tipo], COLOR_TIPO[tipo], "solid", 2.5) for tipo in TIPOS]
        series.append(("Media", media, COLOR_MEDIA, "dash", 2))

        figura = go.Figure()
        for nombre, valores, color, trazo, ancho in series:
            figura.add_trace(go.Scatter(
                x=HORAS, y=valores, name=nombre, uid=nombre, legendgroup=nombre, mode="lines",
                line=dict(color=color, width=ancho, dash=trazo),
                hovertemplate=f"{nombre}: %{{y:.0f}} µg/m³<extra></extra>",
            ))

        finales = {nombre: valores.dropna().iloc[-1] for nombre, valores, *_ in series if valores.notna().any()}
        for nombre, y in self._separar_etiquetas(finales, y_max * SEPARACION_ETIQUETAS).items():
            figura.add_trace(go.Scatter(
                x=[HORAS[-1]], y=[y], text=[nombre], mode="text", textposition="middle right",
                textfont=dict(color=TEXTO_SERIE[nombre], size=12), legendgroup=nombre,
                showlegend=False, hoverinfo="skip", cliponaxis=False, uid=f"etiqueta-{nombre}",
            ))

        figura.update_layout(**self.layout(
            margin=dict(l=10, r=90, t=30, b=10),
            hovermode="x unified",
            uirevision="grafico",
            legend=dict(orientation="h", x=0, y=1.02, yanchor="bottom", bgcolor="rgba(0,0,0,0)"),
            xaxis=dict(
                title="Hora del día", tickmode="array", tickvals=HORAS_MARCADAS,
                ticktext=[f"{hora} h" for hora in HORAS_MARCADAS], range=[-0.3, 23.3],
                gridcolor=GRID, zeroline=False, fixedrange=True, unifiedhovertitle=dict(text="%{x}:00"),
            ),
            yaxis=dict(title="NO2 (µg/m³)", range=[0, y_max], gridcolor=GRID, zeroline=False, fixedrange=True),
        ))
        return figura

    @staticmethod
    def marcas_slider(fechas):
        """Una marca el día 1 de cada mes, con texto solo en los meses impares para que no se
        amontonen, y el año en enero y en la primera marca."""
        marcas = {}
        for indice, fecha in enumerate(fechas):
            if fecha.day != 1 and indice != 0:
                continue
            etiqueta = ""
            if fecha.month % 2 == 1 or indice == 0:
                etiqueta = MESES[fecha.month - 1][:3]
                if fecha.month == 1 or indice == 0:
                    etiqueta += f" {fecha.year}"
            marcas[indice] = etiqueta
        return marcas

    @staticmethod
    def _separar_etiquetas(posiciones, hueco):
        ajustadas, anterior = {}, None
        for nombre, y in sorted(posiciones.items(), key=lambda par: par[1]):
            if anterior is not None and y - anterior < hueco:
                y = anterior + hueco
            ajustadas[nombre] = anterior = y
        return ajustadas


class GraficoPicoValle(GraficoPlotly):
    """Gráfico principal 2: cuántas veces se multiplica el NO2 del valle al pico en cada línea.

    Cada barra es el máximo entre el mínimo de las 24 horas de su línea, con el mismo color y
    siempre en el mismo orden para que no bailen al reproducir. El eje es fijo por escala; en
    "dia" se recorta en ×25 porque algunos días el valle baja de 1 µg/m³ y el cociente se
    dispara (hasta ×68): esas pocas barras se cortan en el tope y muestran su valor real con ▲.
    """

    def __init__(self, datos):
        self.tope = {
            "dia": TOPE_RATIO_DIA,
            "mes": math.ceil(datos.ratio_max["mes"]),
            "total": math.ceil(datos.ratio_max["total"]),
        }
        self.notas = {escala: NOTA_PICO_VALLE for escala in self.tope}

    @staticmethod
    def titulo(amplitud):
        """Qué tipo de estación se multiplica más del valle al pico."""
        tipos = amplitud.drop(index="Media")["ratio"].dropna()
        if tipos.empty:
            return "Sin datos suficientes para este periodo"
        return f"{tipos.idxmax()} es la que más se multiplica: ×{Formato.numero(tipos.max())} del valle al pico"

    def figura(self, amplitud, escala):
        """Barras pico ÷ valle con su valor escrito y el detalle de pico y valle en el tooltip."""
        tope = self.tope[escala]
        nombres = list(amplitud.index)
        ratio = amplitud["ratio"]
        textos = [
            "sin dato" if pd.isna(valor) else f"×{Formato.numero(valor)}" + (" ▲" if valor > tope else "")
            for valor in ratio
        ]
        detalle = [
            f"<b>{nombre}</b><br>Pico ({int(fila['hora_pico'])} h): {Formato.numero(fila['pico'], 0)} µg/m³"
            f"<br>Valle ({int(fila['hora_valle'])} h): {Formato.numero(fila['valle'], 0)} µg/m³"
            f"<br>Pico ÷ valle: {texto}"
            for (nombre, fila), texto in zip(amplitud.iterrows(), textos)
        ]

        figura = go.Figure(go.Bar(
            x=nombres, y=ratio.clip(upper=tope),
            marker=dict(color=[COLOR_SERIE[nombre] for nombre in nombres], cornerradius=4),
            text=textos, textposition="outside", cliponaxis=False, textfont=dict(color=INK_2, size=13),
            hovertext=detalle, hovertemplate="%{hovertext}<extra></extra>",
        ))

        paso = 5 if tope > 12 else (1 if tope > 4 else 0.5)
        marcas = [i * paso for i in range(int(tope / paso) + 1)]
        figura.update_layout(**self.layout(
            margin=dict(l=10, r=10, t=30, b=10),
            bargap=0.35,
            uirevision="barras",
            xaxis=dict(fixedrange=True, tickfont=dict(color=INK, size=13)),
            yaxis=dict(
                title="Pico ÷ valle (veces)", range=[0, tope * 1.12], gridcolor=GRID, zeroline=False,
                fixedrange=True, tickmode="array", tickvals=marcas,
                ticktext=["0" if v == 0 else f"×{Formato.numero(v, 0 if float(v).is_integer() else 1)}" for v in marcas],
            ),
        ))
        return figura
