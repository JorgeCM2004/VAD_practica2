import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.linear_model import LinearRegression

from src.configuracion import DATA_DIR

VIAS_PATH = DATA_DIR / "vias_principales.csv.gz"
VIAS_URBANAS = ["primary", "secondary"]
LAT_ORIGEN, LON_ORIGEN = 40.4168, -3.7038
KM_POR_GRADO_LAT = 110.574
KM_POR_GRADO_LON = 111.320 * math.cos(math.radians(LAT_ORIGEN))
MIN_ESTACIONES = 5
RADIO_ESTACION_KM = 0.2
CUANTILES_INTERVALO = [0.05, 0.95]
REINICIOS_OPTIMIZADOR = 3


@dataclass
class Estimacion:
    """Resultado de inferir(): la estimación, su intervalo del 90% y los pasos intermedios."""

    estimacion: float
    bajo: float
    alto: float
    nivel: float
    factor: float
    lur: float
    correccion: float
    peso_estacion: float
    estacion: int
    dist_via_km: float
    via: str
    estaciones: int


@dataclass
class Validacion:
    """Error medio (µg/m³) de cada método al dejar fuera una estación cada vez."""

    modelo: float
    lur: float
    media: float
    vecino: float
    dias: int


class ModeloNO2:
    """Estima el NO2 en cualquier punto de Madrid.

    NO2 = nivel medio de las estaciones x factor del entorno (LUR con la distancia a la vía
    principal más cercana), más un kriging de los residuos. A menos de unos 200 m de una
    estación la estimación se acerca a lo que mide esa estación.
    """

    def __init__(self, datos):
        self.estaciones = datos.estaciones
        vias = pd.read_csv(VIAS_PATH, keep_default_na=False)
        self._vias = vias[vias["clase"].isin(VIAS_URBANAS)].reset_index(drop=True)
        self._arbol_vias = cKDTree(self.a_km(self._vias["lat"].values, self._vias["lon"].values))

        self.x_estaciones = self.a_km(self.estaciones["lat"].values, self.estaciones["lon"].values)
        self.dist_via_estaciones = self._arbol_vias.query(self.x_estaciones)[0]
        self._dias = datos.no2_estacion["dia"].dropna().values

        self.regresion, self.limites = self._entrenar_lur(np.arange(len(self.x_estaciones)))
        self.factor_estaciones = self.regresion.predict(
            self._covariable(self.dist_via_estaciones, self.limites)
        )
        self.kernel_residuos = self._ajustar_kernel_residuos()
        self.alcance_km = float(self.kernel_residuos.k1.k2.length_scale)
        self.validacion, (self.q_bajo, self.q_alto) = self._validar()

    @staticmethod
    def a_km(lat, lon):
        """Pasa lat/lon a km tomando como origen la Puerta del Sol."""
        lat, lon = np.atleast_1d(lat), np.atleast_1d(lon)
        return np.column_stack([
            (lon - LON_ORIGEN) * KM_POR_GRADO_LON,
            (lat - LAT_ORIGEN) * KM_POR_GRADO_LAT,
        ])

    def via_cercana(self, lat, lon):
        """Distancia (km) y nombre de la vía principal más cercana."""
        distancia, indice = self._arbol_vias.query(self.a_km(lat, lon))
        return float(distancia[0]), self._vias["nombre"].iat[int(indice[0])]

    def distancias_km(self, lat, lon):
        """Distancia (km) del punto a cada estación."""
        return np.linalg.norm(self.x_estaciones - self.a_km(lat, lon), axis=1)

    def inferir(self, valores, lat, lon):
        """Estima el NO2 en (lat, lon) con lo que miden las estaciones. None si hay pocas con datos."""
        usadas = valores.notna().values
        if usadas.sum() < MIN_ESTACIONES:
            return None

        medidos = valores.values[usadas]
        nivel = float(medidos.mean())
        dist_via, via = self.via_cercana(lat, lon)
        factor = float(self.regresion.predict(self._covariable(np.array([dist_via]), self.limites))[0])
        lur = nivel * factor
        residuos = medidos - nivel * self.factor_estaciones[usadas]
        correccion = float(self._correccion(self.x_estaciones[usadas], residuos, self.a_km(lat, lon))[0])
        estimado = max(lur + correccion, 0.0)

        distancias = self.distancias_km(lat, lon)
        distancias[~usadas] = np.inf
        cercana = int(np.argmin(distancias))
        peso = math.exp(-(distancias[cercana] / RADIO_ESTACION_KM) ** 2)
        estimacion = peso * float(valores.iloc[cercana]) + (1 - peso) * estimado

        return Estimacion(
            estimacion=estimacion,
            bajo=estimacion - (1 - peso) * estimado * (1 - self.q_bajo),
            alto=estimacion + (1 - peso) * estimado * (self.q_alto - 1),
            nivel=nivel,
            factor=factor,
            lur=lur,
            correccion=correccion,
            peso_estacion=peso,
            estacion=cercana,
            dist_via_km=dist_via,
            via=via,
            estaciones=int(usadas.sum()),
        )

    @staticmethod
    def _covariable(distancia_km, limites):
        return np.log1p(np.clip(distancia_km, *limites)).reshape(-1, 1)

    @staticmethod
    def _patron(valores):
        return (valores / valores.mean(axis=1, keepdims=True)).mean(axis=0)

    def _entrenar_lur(self, indices):
        distancias = self.dist_via_estaciones[indices]
        limites = (distancias.min(), distancias.max())
        regresion = LinearRegression().fit(
            self._covariable(distancias, limites), self._patron(self._dias[:, indices])
        )
        return regresion, limites

    def _ajustar_kernel_residuos(self):
        residuos = self._dias - self._dias.mean(axis=1, keepdims=True) * self.factor_estaciones
        estandarizados = residuos / residuos.std(axis=1, keepdims=True)
        kernel = (
            ConstantKernel(1.0, (1e-2, 1e2))
            * Matern(length_scale=2.0, length_scale_bounds=(0.2, 30.0), nu=1.5)
            + WhiteKernel(0.5, (1e-3, 5.0))
        )
        proceso = GaussianProcessRegressor(
            kernel, n_restarts_optimizer=REINICIOS_OPTIMIZADOR, random_state=0
        )
        return proceso.fit(self.x_estaciones, estandarizados.T).kernel_

    def _correccion(self, x_observadas, residuos, x_objetivo):
        pesos = np.linalg.solve(
            self.kernel_residuos(x_observadas), self.kernel_residuos(x_objetivo, x_observadas).T
        )
        return residuos @ pesos

    def _validar(self):
        n = len(self.x_estaciones)
        entre_estaciones = np.linalg.norm(self.x_estaciones[:, None] - self.x_estaciones[None], axis=2)
        errores = {"modelo": [], "lur": [], "media": [], "vecino": []}
        cocientes = []

        for excluida in range(n):
            resto = np.flatnonzero(np.arange(n) != excluida)
            regresion, limites = self._entrenar_lur(resto)
            nivel = self._dias[:, resto].mean(axis=1)
            factor_resto = regresion.predict(self._covariable(self.dist_via_estaciones[resto], limites))
            factor = regresion.predict(self._covariable(self.dist_via_estaciones[[excluida]], limites))[0]
            lur = nivel * factor
            residuos = self._dias[:, resto] - nivel[:, None] * factor_resto
            estimado = lur + self._correccion(
                self.x_estaciones[resto], residuos, self.x_estaciones[[excluida]]
            )[:, 0]
            real = self._dias[:, excluida]
            vecino = self._dias[:, resto[np.argmin(entre_estaciones[excluida, resto])]]

            errores["modelo"].append(np.abs(estimado - real))
            errores["lur"].append(np.abs(lur - real))
            errores["media"].append(np.abs(nivel - real))
            errores["vecino"].append(np.abs(vecino - real))
            cocientes.append(real / estimado)

        validacion = Validacion(
            **{metodo: float(np.mean(e)) for metodo, e in errores.items()}, dias=len(self._dias)
        )
        return validacion, np.quantile(np.concatenate(cocientes), CUANTILES_INTERVALO)
