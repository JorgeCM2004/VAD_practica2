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


class GraficoPlotly:
    """Layout común de las figuras de Plotly."""

    @staticmethod
    def layout(**ajustes):
        return {
            "font": dict(family=FONT, size=13, color=INK_2),
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "margin": dict(l=10, r=10, t=10, b=10),
            "hoverlabel": dict(bgcolor="white", font=dict(family=FONT, size=13, color=INK)),
            **ajustes,
        }


class GraficoHorario(GraficoPlotly):
    """Gráfico 1: NO2 por hora y tipo de estación, con la media en discontinua.

    Cada línea lleva su nombre al final para no depender solo del color. El eje Y es fijo en
    cada escala para que no salte con el Play.
    """

    def __init__(self, datos):
        self.y_max = {escala: math.ceil(maximo / 10) * 10 for escala, maximo in datos.no2_max.items()}
        self.rango = Formato.rango(datos.fecha_inicio, datos.fecha_fin)

    def titulo(self, escala, instante):
        if escala == "dia":
            return f"{Formato.dia(instante)} · {Formato.tipo_dia(instante)}"
        if escala == "mes":
            return Formato.mes(instante).capitalize()
        return f"Todo el periodo · {self.rango}"

    def figura(self, curvas, media, escala):
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
        """Una marca cada día 1 de mes, con texto solo en los meses impares para que no se solapen."""
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
    """Gráfico 2: máximo / mínimo de las 24 horas de cada línea.

    En la escala de día el eje se corta en 25 porque algunos días el mínimo es casi 0; esas
    barras llevan su valor real escrito encima.
    """

    def __init__(self, datos):
        self.tope = {
            "dia": TOPE_RATIO_DIA,
            "mes": math.ceil(datos.ratio_max["mes"]),
            "total": math.ceil(datos.ratio_max["total"]),
        }

    @staticmethod
    def titulo(amplitud):
        tipos = amplitud.drop(index="Media")["ratio"].dropna()
        if tipos.empty:
            return "Sin datos suficientes para este periodo"
        return f"{tipos.idxmax()} es la que más se multiplica: ×{Formato.numero(tipos.max())} del valle al pico"

    def figura(self, amplitud, escala):
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
                title="Pico ÷ valle", range=[0, tope * 1.12], gridcolor=GRID, zeroline=False,
                fixedrange=True, tickmode="array", tickvals=marcas,
                ticktext=["0" if v == 0 else f"×{Formato.numero(v, 0 if float(v).is_integer() else 1)}" for v in marcas],
            ),
        ))
        return figura
