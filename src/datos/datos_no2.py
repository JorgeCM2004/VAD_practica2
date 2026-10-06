import pandas as pd

from src.configuracion import DATA_DIR

MEDICIONES_PATH = DATA_DIR / "calidad_aire_2025.csv"
ESTACIONES_PATH = DATA_DIR / "estaciones.csv"
MAGNITUD_NO2 = 8
MEDICION_VALIDA = "V"
TIPOS = ["Urbana tráfico", "Urbana fondo", "Suburbana"]
ESCALAS = {"dia": "Día", "mes": "Mes", "total": "Todo el periodo"}


class DatosNO2:
    """Carga las mediciones de NO2 validadas y calcula las medias por día, mes y periodo completo.

    Guarda las curvas horarias por tipo de estación (gráficos) y el NO2 medio de cada
    estación (mapa y modelo).
    """

    def __init__(self):
        mediciones = self._cargar_mediciones()
        self.estaciones = self._cargar_estaciones(mediciones["codigo"].unique())
        validas = mediciones[mediciones["valido"] == MEDICION_VALIDA].merge(
            self.estaciones[["tipo"]], left_on="codigo", right_index=True
        )
        validas["mes"] = validas["fecha"].dt.to_period("M").dt.to_timestamp()

        self.perfiles = {"dia": self._curvas(validas, "fecha"), "mes": self._curvas(validas, "mes")}
        self.perfil_total = validas.groupby(["tipo", "hora"])["valor"].mean()
        self.no2_estacion = {
            "dia": self._por_estacion(validas, "fecha"),
            "mes": self._por_estacion(validas, "mes"),
            "total": validas.groupby("codigo")["valor"].mean(),
        }
        self.fecha_inicio = self.perfiles["dia"].index.min()
        self.fecha_fin = self.perfiles["dia"].index.max()

        self.no2_max = {
            "dia": float(self.perfiles["dia"].max().max()),
            "mes": float(self.perfiles["mes"].max().max()),
            "total": float(self.perfil_total.max()),
        }
        self.no2_estacion_max = {
            "dia": float(self.no2_estacion["dia"].max().max()),
            "mes": float(self.no2_estacion["mes"].max().max()),
            "total": float(self.no2_estacion["total"].max()),
        }
        self.ratio_max = {
            "dia": float(self._ratios(self.perfiles["dia"]).max().max()),
            "mes": float(self._ratios(self.perfiles["mes"]).max().max()),
            "total": float(self.pico_valle(*self.perfil_tipos("total", None))["ratio"].max()),
        }

    def instantes(self, escala):
        """Días o meses del slider (vacío en "total")."""
        if escala == "total":
            return pd.DatetimeIndex([])
        return self.perfiles[escala].index

    def perfil_tipos(self, escala, instante):
        """Curva horaria de cada tipo y la media de los tres tipos.

        Se hace la media de los tipos y no de las estaciones para que Suburbana, que solo
        tiene tres, pese lo mismo que los demás.
        """
        fila = self.perfil_total if escala == "total" else self.perfiles[escala].loc[instante]
        curvas = pd.DataFrame({tipo: fila[tipo].reindex(range(24)) for tipo in TIPOS})
        return curvas, curvas.mean(axis=1, skipna=False)

    def no2_estaciones(self, escala, instante):
        """NO2 medio de cada estación en ese instante (NaN si no hay datos)."""
        tabla = self.no2_estacion[escala]
        valores = tabla if escala == "total" else tabla.loc[instante]
        return valores.reindex(self.estaciones.index)

    @staticmethod
    def pico_valle(curvas, media):
        """Pico, valle, sus horas y el cociente pico / valle de cada línea (vacío si el valle es 0)."""
        lineas = curvas.assign(Media=media)
        valle = lineas.min()
        return pd.DataFrame({
            "pico": lineas.max(),
            "hora_pico": lineas.idxmax(),
            "valle": valle,
            "hora_valle": lineas.idxmin(),
            "ratio": lineas.max() / valle.where(valle > 0),
        })

    @staticmethod
    def _cargar_mediciones():
        mediciones = pd.read_csv(MEDICIONES_PATH, sep=";", encoding="utf-8-sig", low_memory=False)
        no2 = mediciones[mediciones["MAGNITUD"] == MAGNITUD_NO2]

        horas = []
        for hora in range(1, 25):
            columna_valor, columna_validez = f"H{hora:02d}", f"V{hora:02d}"
            tabla = no2[["ESTACION", "ANO", "MES", "DIA", columna_valor, columna_validez]].rename(
                columns={columna_valor: "valor", columna_validez: "valido"}
            )
            tabla["hora"] = hora - 1
            horas.append(tabla)

        largo = pd.concat(horas, ignore_index=True)
        largo["fecha"] = pd.to_datetime(
            dict(year=largo["ANO"], month=largo["MES"], day=largo["DIA"]), errors="coerce"
        )
        largo = largo.dropna(subset=["fecha"]).drop(columns=["ANO", "MES", "DIA"])
        largo = largo.drop_duplicates(subset=["ESTACION", "fecha", "hora"])
        return largo.rename(columns={"ESTACION": "codigo"})

    @staticmethod
    def _cargar_estaciones(codigos_con_datos):
        estaciones = pd.read_csv(ESTACIONES_PATH, sep=";", encoding="utf-8-sig").rename(columns={
            "CODIGO_CORTO": "codigo", "ESTACION": "nombre", "NOM_TIPO": "tipo",
            "LATITUD": "lat", "LONGITUD": "lon", "DIRECCION": "direccion",
        })
        estaciones = estaciones[estaciones["codigo"].isin(codigos_con_datos)]
        columnas = ["codigo", "nombre", "tipo", "lat", "lon", "direccion"]
        return estaciones[columnas].set_index("codigo").sort_index()

    @staticmethod
    def _curvas(validas, clave):
        return (
            validas.groupby([clave, "tipo", "hora"])["valor"].mean()
            .unstack(["tipo", "hora"])
            .sort_index(axis=1)
        )

    @staticmethod
    def _por_estacion(validas, clave):
        return validas.groupby([clave, "codigo"])["valor"].mean().unstack("codigo")

    @staticmethod
    def _ratios(tabla):
        lineas = {tipo: tabla[tipo] for tipo in TIPOS}
        lineas["Media"] = sum(lineas.values()) / len(TIPOS)
        return pd.DataFrame({
            nombre: filas.max(axis=1) / filas.min(axis=1).where(lambda v: v > 0)
            for nombre, filas in lineas.items()
        })
