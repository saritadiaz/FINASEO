"""
Modelo financiero de la empresa tipo prestadora del servicio de aseo.

Este archivo es el MOTOR del aplicativo: aquí se hacen todas las cuentas.
La inteligencia artificial nunca calcula cifras; solo interpreta las que
salen de este modelo.

Todas las cifras están en millones de pesos colombianos (COP) y son
SINTÉTICAS: no corresponden a ninguna empresa real.
"""

from dataclasses import dataclass, asdict, replace
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# 1. SUPUESTOS Y DRIVERS
# ---------------------------------------------------------------------------
@dataclass
class Supuestos:
    # Ingresos
    usuarios: int = 450_000                 # suscriptores facturados
    tarifa_promedio: float = 0.025          # millones COP por usuario al mes (25.000 COP)
    crecimiento_usuarios_anual: float = 0.015
    # Recaudo (la factura del mes t se cobra en los meses siguientes)
    tasa_recaudo: float = 0.92              # porción de lo facturado que finalmente se recauda
    porcion_mes_siguiente: float = 0.76     # de lo recaudado, cuánto llega en t+1 (el resto en t+2)
    # Operación
    toneladas_mes: float = 55_000
    costo_disposicion_ton: float = 0.045    # millones COP por tonelada
    nomina_operativa: float = 3_600
    combustible: float = 1_350
    mantenimiento_flota: float = 700
    gastos_administrativos: float = 900
    otros_pagos: float = 300
    poliza_semestral: float = 1_200         # se paga en abril y octubre
    # Financiación, inversión e impuestos
    servicio_deuda: float = 450             # cuota mensual de créditos (capital e intereses)
    inversion_flota: float = 250            # reposición mensual de vehículos y contenedores
    impuesto_renta_anual: float = 2_400     # se paga en 3 cuotas: febrero, abril y junio
    # Macro y tesorería
    inflacion_anual: float = 0.05
    caja_inicial: float = 3_000
    caja_minima: float = 1_000


ESCENARIOS = {
    "Base": {"tasa_recaudo": 1.00, "porcion_mes_siguiente": 1.00, "combustible": 1.00},
    "Pesimista": {"tasa_recaudo": 0.985, "porcion_mes_siguiente": 0.85, "combustible": 1.10},
    "Optimista": {"tasa_recaudo": 1.04, "porcion_mes_siguiente": 1.05, "combustible": 0.95},
}

DESCRIPCION_ESCENARIOS = {
    "Base": "Supuestos tal como se definieron.",
    "Pesimista": "Recaudo 1,5% menor, cobro más lento y combustible 10% más caro.",
    "Optimista": "Recaudo 4% mayor, cobro más rápido y combustible 5% más barato.",
}

MESES_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def aplicar_escenario(s: Supuestos, escenario: str) -> Supuestos:
    f = ESCENARIOS[escenario]
    return replace(
        s,
        tasa_recaudo=min(s.tasa_recaudo * f["tasa_recaudo"], 0.995),
        porcion_mes_siguiente=min(s.porcion_mes_siguiente * f["porcion_mes_siguiente"], 1.0),
        combustible=s.combustible * f["combustible"],
    )


# ---------------------------------------------------------------------------
# 2. PROYECCIÓN DEL FLUJO DE CAJA POR DRIVERS
# ---------------------------------------------------------------------------
def proyectar(s: Supuestos, escenario: str = "Base", meses: int = 12,
              anio_inicio: int = 2027, caja_inicial: float | None = None,
              mes_inicio: int = 1, facturado_previo: list | None = None) -> pd.DataFrame:
    """Proyecta mes a mes la facturación, el recaudo, los egresos y el saldo de caja.
    mes_inicio (1 = enero) permite empezar la proyección en cualquier mes, por ejemplo
    el mes siguiente al último dato real cargado desde Excel.
    facturado_previo: lo realmente facturado en los dos meses anteriores [t-2, t-1];
    si se conoce, el recaudo de los primeros meses se calcula con esas cifras reales."""
    s = aplicar_escenario(s, escenario)
    inf_m = (1 + s.inflacion_anual) ** (1 / 12) - 1
    crec_m = (1 + s.crecimiento_usuarios_anual) ** (1 / 12) - 1

    # Facturación de los dos meses previos (necesaria para el recaudo con rezago)
    facturado_base = s.usuarios * s.tarifa_promedio
    hist = [facturado_base / (1 + crec_m + inf_m) ** 2, facturado_base / (1 + crec_m + inf_m)]
    if facturado_previo is not None:
        hist = [float(facturado_previo[0]), float(facturado_previo[1])]

    saldo = s.caja_inicial if caja_inicial is None else caja_inicial
    filas = []
    for i in range(meses):
        posicion = mes_inicio - 1 + i
        mes_num = posicion % 12
        ajuste = (1 + inf_m) ** i
        usuarios = s.usuarios * (1 + crec_m) ** i
        facturado = usuarios * s.tarifa_promedio * ajuste

        recaudo = s.tasa_recaudo * (s.porcion_mes_siguiente * hist[-1]
                                    + (1 - s.porcion_mes_siguiente) * hist[-2])
        hist.append(facturado)

        disposicion = s.toneladas_mes * s.costo_disposicion_ton * ajuste
        nomina = s.nomina_operativa * ajuste
        combustible = s.combustible * ajuste
        mantenimiento = s.mantenimiento_flota * ajuste
        administrativos = s.gastos_administrativos * ajuste
        otros = s.otros_pagos * ajuste
        poliza = s.poliza_semestral if mes_num in (3, 9) else 0.0
        deuda = s.servicio_deuda
        flota = s.inversion_flota * ajuste
        impuestos = s.impuesto_renta_anual / 3 if mes_num in (1, 3, 5) else 0.0

        egresos = (disposicion + nomina + combustible + mantenimiento + administrativos + otros
                   + poliza + deuda + flota + impuestos)
        flujo = recaudo - egresos
        saldo += flujo
        filas.append({
            "mes": f"{MESES_ES[mes_num]} {anio_inicio + posicion // 12}",
            "facturado": facturado, "recaudo": recaudo,
            "disposicion_final": disposicion, "nomina": nomina, "combustible": combustible,
            "mantenimiento": mantenimiento, "administrativos": administrativos,
            "otros": otros, "poliza": poliza, "servicio_deuda": deuda,
            "inversion_flota": flota, "impuestos": impuestos, "egresos": egresos,
            "flujo_neto": flujo, "saldo_caja": saldo,
        })
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------
# 3. PRESUPUESTO FRENTE A EJECUTADO
# ---------------------------------------------------------------------------
RUBROS = {
    "recaudo": "Recaudo de tarifa",
    "disposicion_final": "Disposición final",
    "nomina": "Nómina operativa",
    "combustible": "Combustible",
    "mantenimiento": "Mantenimiento de flota",
    "administrativos": "Gastos administrativos",
    "poliza": "Póliza de flota",
    "servicio_deuda": "Servicio de la deuda",
    "inversion_flota": "Reposición de flota",
    "impuestos": "Impuesto de renta",
}
COLUMNAS_EGRESOS = ["disposicion_final", "nomina", "combustible", "mantenimiento", "administrativos",
                    "otros", "poliza", "servicio_deuda", "inversion_flota", "impuestos"]
COSTOS_OPERATIVOS = ["disposicion_final", "nomina", "combustible", "mantenimiento",
                     "administrativos", "otros", "poliza"]


def ejecutado_sintetico(presupuesto: pd.DataFrame, meses_cerrados: int = 9, semilla: int = 7) -> pd.DataFrame:
    """Simula lo ejecutado con desviaciones típicas del sector (datos ficticios)."""
    rng = np.random.default_rng(semilla)
    ej = presupuesto.head(meses_cerrados).copy()
    for col in ["recaudo", "disposicion_final", "nomina", "combustible", "mantenimiento", "administrativos"]:
        ej[col] = ej[col] * (1 + rng.normal(0, 0.015, len(ej)))
    # Eventos típicos: rezago en el giro del recaudo en marzo y alza de combustible desde mayo
    ej.loc[2, "recaudo"] = presupuesto.loc[2, "recaudo"] * 0.912
    ej.loc[4:, "combustible"] = presupuesto.loc[4:meses_cerrados - 1, "combustible"] * 1.104
    ej["egresos"] = ej[COLUMNAS_EGRESOS].sum(axis=1)
    ej["flujo_neto"] = ej["recaudo"] - ej["egresos"]
    return ej


def tabla_desviaciones(presupuesto: pd.DataFrame, ejecutado: pd.DataFrame, mes_idx: int) -> pd.DataFrame:
    filas = []
    for col, nombre in RUBROS.items():
        p, e = presupuesto.loc[mes_idx, col], ejecutado.loc[mes_idx, col]
        if p == 0 and e == 0:
            continue
        desv = (e - p) / p if p else 0.0
        es_ingreso = col == "recaudo"
        desfavorable = desv < -0.03 if es_ingreso else desv > 0.03
        filas.append({"Rubro": nombre, "Presupuestado": p, "Ejecutado": e,
                      "Desviación %": desv * 100,
                      "Estado": "Desfavorable" if desfavorable else "Dentro del rango"})
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------
# 4. INDICADORES
# ---------------------------------------------------------------------------
def indicadores(df: pd.DataFrame, s: Supuestos) -> dict:
    costos_operativos = df[COSTOS_OPERATIVOS].sum().sum()
    facturado = df["facturado"].sum()
    idx_min = int(df["saldo_caja"].idxmin())
    cartera_final = df["facturado"].iloc[-1] * s.tasa_recaudo + df["facturado"].iloc[-2] * s.tasa_recaudo * (1 - s.porcion_mes_siguiente)
    dias_cartera = cartera_final / (facturado / 12) * 30
    return {
        "caja_minima_proyectada": float(df["saldo_caja"].min()),
        "mes_critico": df.loc[idx_min, "mes"],
        "meses_bajo_minimo": int((df["saldo_caja"] < s.caja_minima).sum()),
        "margen_ebitda_pct": float((facturado - costos_operativos) / facturado * 100),
        "recaudo_sobre_facturado_pct": float(df["recaudo"].sum() / facturado * 100),
        "dias_cartera": float(dias_cartera),
        "cobertura_caja_meses": float(df["saldo_caja"].iloc[-1] / df["egresos"].mean()),
        "saldo_final": float(df["saldo_caja"].iloc[-1]),
    }


# ---------------------------------------------------------------------------
# 5. BACKTESTING: MODELO POR DRIVERS FRENTE A PROYECCIÓN TRADICIONAL
# ---------------------------------------------------------------------------
CAJA_INICIAL_HISTORIA = 5_000


def historia_sintetica(s: Supuestos, semilla: int = 42) -> pd.DataFrame:
    """Genera 36 meses 'reales' (2023-2025) con choques aleatorios. Se conoce la respuesta correcta."""
    rng = np.random.default_rng(semilla)
    base = proyectar(s, "Base", meses=36, anio_inicio=2023, caja_inicial=CAJA_INICIAL_HISTORIA)
    real = base.copy()
    real["recaudo"] = base["recaudo"] * (1 + rng.normal(0, 0.015, 36))
    real.loc[[2, 14, 26], "recaudo"] *= 0.90            # rezagos de giro en marzo
    real["combustible"] = base["combustible"] * (1 + rng.normal(0, 0.04, 36))
    real["egresos"] = base["egresos"] - base["combustible"] + real["combustible"]
    real["egresos"] *= (1 + rng.normal(0, 0.005, 36))
    real["flujo_neto"] = real["recaudo"] - real["egresos"]
    real["saldo_caja"] = CAJA_INICIAL_HISTORIA + real["flujo_neto"].cumsum()
    return real


def mape(real, pronostico) -> float:
    real, pronostico = np.asarray(real), np.asarray(pronostico)
    return float(np.mean(np.abs((real - pronostico) / real)) * 100)


def backtesting(s: Supuestos, semilla: int = 42) -> tuple[pd.DataFrame, dict]:
    """Pronostica 2025 con información hasta diciembre de 2024 y compara contra lo 'real'."""
    real = historia_sintetica(s, semilla)
    r24, r25 = real.iloc[12:24].reset_index(drop=True), real.iloc[24:36].reset_index(drop=True)
    saldo_dic24 = real.loc[23, "saldo_caja"]

    # Método tradicional en hoja de cálculo: flujo del mismo mes del año anterior + inflación
    flujo_trad = r24["flujo_neto"] * (1 + s.inflacion_anual)
    saldo_trad = saldo_dic24 + flujo_trad.cumsum()

    # Modelo por drivers: proyecta 2025 con los drivers, partiendo del saldo real de dic-2024
    s25 = replace(s, usuarios=s.usuarios * (1 + s.crecimiento_usuarios_anual) ** 2,
                  tarifa_promedio=s.tarifa_promedio * (1 + s.inflacion_anual) ** 2,
                  costo_disposicion_ton=s.costo_disposicion_ton * (1 + s.inflacion_anual) ** 2,
                  nomina_operativa=s.nomina_operativa * (1 + s.inflacion_anual) ** 2,
                  combustible=s.combustible * (1 + s.inflacion_anual) ** 2,
                  mantenimiento_flota=s.mantenimiento_flota * (1 + s.inflacion_anual) ** 2,
                  gastos_administrativos=s.gastos_administrativos * (1 + s.inflacion_anual) ** 2,
                  otros_pagos=s.otros_pagos * (1 + s.inflacion_anual) ** 2,
                  inversion_flota=s.inversion_flota * (1 + s.inflacion_anual) ** 2)
    modelo = proyectar(s25, "Base", meses=12, anio_inicio=2025, caja_inicial=saldo_dic24)

    # El modelo aprende la estacionalidad del recaudo de 2023 y 2024 (por ejemplo, el rezago
    # recurrente del giro en marzo) y la aplica a 2025.
    base = proyectar(s, "Base", meses=24, anio_inicio=2023, caja_inicial=CAJA_INICIAL_HISTORIA)
    ratio = (real["recaudo"].iloc[:24].values / base["recaudo"].values).reshape(2, 12).mean(axis=0)
    modelo["recaudo"] = modelo["recaudo"] * ratio
    modelo["flujo_neto"] = modelo["recaudo"] - modelo["egresos"]
    modelo["saldo_caja"] = saldo_dic24 + modelo["flujo_neto"].cumsum()

    comp = pd.DataFrame({
        "mes": r25["mes"],
        "Real": r25["saldo_caja"],
        "Modelo por drivers": modelo["saldo_caja"],
        "Método tradicional": saldo_trad.values,
    })
    res = {
        "mape_modelo": mape(comp["Real"], comp["Modelo por drivers"]),
        "mape_tradicional": mape(comp["Real"], comp["Método tradicional"]),
    }
    return comp, res


def supuestos_a_dict(s: Supuestos) -> dict:
    return asdict(s)


def backtesting_repetido(s: Supuestos, repeticiones: int = 50) -> pd.DataFrame:
    """Repite el backtesting con distintas simulaciones para probar la hipótesis H1."""
    filas = []
    for semilla in range(repeticiones):
        _, r = backtesting(s, semilla)
        filas.append({"simulacion": semilla + 1, **r,
                      "gana_modelo": r["mape_modelo"] < r["mape_tradicional"]})
    return pd.DataFrame(filas)
