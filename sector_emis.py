"""
Comparación con el sector: estados financieros anuales de los operadores de aseo de Bogotá (EMIS),
diagnóstico, validación del modelo con datos reales y calibración de sus supuestos.

Todas las cifras están en millones de pesos colombianos (COP).
La inteligencia artificial no calcula nada aquí: todas las cuentas salen de este archivo.
"""

import io
import re
import unicodedata

import numpy as np
import pandas as pd
from scipy import stats

# ---------------------------------------------------------------------------
# 1. CAMPOS QUE SE LEEN DE EMIS
# ---------------------------------------------------------------------------
CAMPOS = {
    "ingresos": "Ingresos operacionales",
    "costo_ventas": "Costo de ventas y prestación del servicio",
    "gastos_admin": "Gastos de administración y ventas",
    "depreciacion": "Depreciación y amortización",
    "utilidad_operacional": "Utilidad operacional",
    "gastos_financieros": "Gastos financieros",
    "utilidad_neta": "Utilidad neta",
    "efectivo": "Efectivo y equivalentes",
    "deudores": "Cuentas por cobrar comerciales (cartera)",
    "inventarios": "Inventarios",
    "proveedores": "Cuentas por pagar a proveedores",
    "deuda_financiera": "Obligaciones financieras",
    "activo_total": "Activo total",
    "patrimonio": "Patrimonio",
    "activo_corriente": "Activo corriente",
    "pasivo_corriente": "Pasivo corriente",
    "pasivos_totales": "Pasivo total",
}
OBLIGATORIOS = ["ingresos", "costo_ventas"]

# Palabras con que EMIS y Supersociedades suelen nombrar cada cuenta (en español e inglés).
SINONIMOS = {
    "ingresos": ["total ingreso operativo", "ingresos de actividades ordinarias", "ingresos operacionales", "ingresos operativos",
                 "ventas netas", "ingresos", "revenue", "net sales", "total revenue", "operating revenue"],
    "costo_ventas": ["costo de mercancias vendidas", "costo de ventas", "costos de ventas", "costo de prestacion", "costo de la prestacion",
                     "cost of sales", "cost of goods sold", "cost of revenue"],
    "gastos_admin": ["gastos de administracion", "gastos administrativos", "gastos de ventas",
                     "administrative expenses", "selling general", "operating expenses"],
    "depreciacion": ["depreciacion", "amortizacion", "depreciation", "amortization"],
    "utilidad_operacional": ["ganancia operativa", "utilidad operacional", "ganancia operacional", "resultado operacional",
                             "ganancias por actividades de operacion", "operating profit", "operating income", "ebit"],
    "gastos_financieros": ["gastos financieros", "costos financieros", "finance costs", "financial expenses",
                           "interest expense"],
    "utilidad_neta": ["utilidad neta", "ganancia neta", "resultado del ejercicio", "ganancia (perdida)",
                      "net income", "net profit", "profit for the year"],
    "efectivo": ["efectivo y equivalentes", "efectivo", "cash and cash equivalents", "cash"],
    "deudores": ["deudores comerciales", "cuentas comerciales por cobrar", "cuentas por cobrar",
                 "trade receivables", "accounts receivable", "trade and other receivables"],
    "inventarios": ["inventarios", "inventories", "inventory"],
    "proveedores": ["proveedores", "cuentas comerciales por pagar", "cuentas por pagar comerciales",
                    "trade payables", "accounts payable", "trade and other payables"],
    "deuda_financiera": ["obligaciones financieras", "pasivos financieros", "prestamos", "deuda financiera",
                         "borrowings", "financial liabilities", "loans", "total debt"],
    "activo_corriente": ["activos corrientes", "activo corriente", "total activos corrientes", "current assets"],
    "pasivo_corriente": ["pasivos corrientes", "pasivo corriente", "total pasivos corrientes", "current liabilities"],
    "pasivos_totales": ["pasivos totales", "total pasivos", "pasivo total", "total de pasivos", "total liabilities"],
    "activo_total": ["activos totales", "total activos", "activo total", "total de activos", "total assets"],
    "patrimonio": ["total de patrimonio", "total patrimonio", "patrimonio total", "patrimonio", "total equity", "equity"],
}

# IPC de Colombia (variación anual a diciembre, DANE). Se usa para la proyección tradicional.
IPC = {2019: 0.0380, 2020: 0.0161, 2021: 0.0562, 2022: 0.1312, 2023: 0.0928, 2024: 0.0520, 2025: 0.0510}


def _norm(txt):
    txt = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", txt).strip()


def _campo_de(etiqueta):
    """Devuelve el campo al que corresponde el nombre de una cuenta, o None."""
    e = _norm(etiqueta)
    if not e or "patrimonio y pasivo" in e or "pasivo y patrimonio" in e or "pasivos y patrimonio" in e:
        return None
    for campo, lista in SINONIMOS.items():
        for s in lista:
            if e == s or e.startswith(s) or (len(s) > 8 and s in e):
                return campo
    return None


def _numero(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    if isinstance(v, (int, float, np.number)):
        return float(v)
    t = str(v).strip().replace("$", "").replace(" ", "")
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    if not t or t in ("-", "n.d.", "nd", "N/A"):
        return np.nan
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "," in t:
        t = t.replace(",", ".") if len(t.split(",")[-1]) <= 2 else t.replace(",", "")
    elif t.count(".") > 1:
        t = t.replace(".", "")
    try:
        x = float(t)
    except ValueError:
        return np.nan
    return -x if neg else x


def _anio(v):
    m = re.search(r"(19|20)\d{2}", str(v))
    return int(m.group(0)) if m else None


# ---------------------------------------------------------------------------
# 2. LECTURA DE ARCHIVOS
# ---------------------------------------------------------------------------
def leer_formato_plantilla(df):
    """Formato largo de la plantilla: una fila por empresa y año."""
    cols = {c: _norm(c) for c in df.columns}
    c_emp = next((c for c, n in cols.items() if n in ("empresa", "operador", "company", "razon social")), None)
    c_anio = next((c for c, n in cols.items() if n in ("ano", "anio", "year", "periodo")), None)
    if c_emp is None or c_anio is None:
        return None
    mapa = {}
    for c, n in cols.items():
        for campo, nombre in CAMPOS.items():
            if n in (campo.replace("_", " "), _norm(nombre), campo) or _campo_de(n) == campo:
                mapa.setdefault(campo, c)
    out = pd.DataFrame({"empresa": df[c_emp].astype(str).str.strip(), "anio": df[c_anio].map(_anio)})
    for campo, c in mapa.items():
        out[campo] = df[c].map(_numero)
    return out.dropna(subset=["anio"])


def leer_formato_emis(df, empresa):
    """Formato de EMIS / Supersociedades: cuentas en filas y años en columnas."""
    df = df.copy()
    # Busca la fila de encabezado que tenga años
    fila_enc = None
    for i in range(min(len(df), 30)):
        if sum(_anio(v) is not None for v in df.iloc[i].values) >= 2:
            fila_enc = i
            break
    if fila_enc is not None:
        df.columns = [str(v) for v in df.iloc[fila_enc].values]
        df = df.iloc[fila_enc + 1:]
    cols_anio = {c: _anio(c) for c in df.columns if _anio(c)}
    if len(cols_anio) < 2:
        return None
    col_etq = next(c for c in df.columns if c not in cols_anio)
    registros = {}
    for _, fila in df.iterrows():
        campo = _campo_de(fila[col_etq])
        if campo is None:
            continue
        for c, a in cols_anio.items():
            x = _numero(fila[c])
            if not np.isnan(x):
                registros.setdefault(a, {}).setdefault(campo, x)  # se queda con la primera coincidencia
    if not registros:
        return None
    out = pd.DataFrame([{"empresa": empresa, "anio": a, **v} for a, v in registros.items()])
    return out


def leer_archivo(nombre, contenido):
    """Lee un Excel o CSV y devuelve (datos, mensajes)."""
    mensajes = []
    base = re.sub(r"\.(xlsx|xls|csv)$", "", nombre, flags=re.I)
    if nombre.lower().endswith(".csv"):
        hojas = {base: pd.read_csv(io.BytesIO(contenido), header=None, sep=None, engine="python")}
    else:
        hojas = pd.read_excel(io.BytesIO(contenido), sheet_name=None, header=None)
    partes = []
    for hoja, crudo in hojas.items():
        if _norm(hoja).startswith(("ejemplo", "instruc")):
            continue  # hojas de ayuda de la plantilla
        crudo = crudo.dropna(how="all").dropna(axis=1, how="all")
        if len(crudo) <= 1:
            continue
        # ¿Formato plantilla? (primera fila con "Empresa" y "Año")
        con_enc = crudo.copy()
        con_enc.columns = [str(v) for v in crudo.iloc[0].values]
        largo = leer_formato_plantilla(con_enc.iloc[1:])
        if largo is not None and not largo.empty:
            partes.append(largo)
            continue
        empresa = base if len(hojas) == 1 else (hoja if hoja.lower() not in ("sheet1", "hoja1") else base)
        ancho = leer_formato_emis(crudo, empresa)
        if ancho is not None:
            partes.append(ancho)
        else:
            mensajes.append(f"La hoja «{hoja}» no tiene cuentas reconocibles; se omitió.")
    if not partes:
        return None, mensajes + ["No se encontraron estados financieros en el archivo."]
    datos = pd.concat(partes, ignore_index=True)
    return datos, mensajes


NOMBRES_CORTOS = {"promoambiental": "Promoambiental", "ciudad limpia": "Ciudad Limpia",
                  "limpieza metropolitana": "LIME", "lime": "LIME", "bogota limpia": "Bogotá Limpia",
                  "area limpia": "Área Limpia"}


def nombre_corto(nombre):
    n = _norm(str(nombre).replace("_", " "))
    for clave, corto in NOMBRES_CORTOS.items():
        if n.startswith(clave) or f" {clave}" in f" {n}":
            return corto
    return str(nombre).replace("_", " ").strip()


def consolidar(datos, anios=5):
    """Une archivos, se queda con los últimos `anios` años de cada empresa y calcula indicadores."""
    datos = datos.groupby(["empresa", "anio"], as_index=False).first()
    datos = datos.sort_values(["empresa", "anio"])
    datos = datos.groupby("empresa").tail(anios)
    for c in CAMPOS:
        if c not in datos:
            datos[c] = np.nan
    # En EMIS los costos a veces vienen negativos: se usan en valor absoluto
    for c in ["costo_ventas", "gastos_admin", "depreciacion", "gastos_financieros"]:
        datos[c] = datos[c].abs()
    # EMIS no separa los gastos de administración: se obtienen como ingresos − costo − utilidad operacional
    falta = datos["gastos_admin"].isna() & datos["utilidad_operacional"].notna()
    datos.loc[falta, "gastos_admin"] = (datos["ingresos"] - datos["costo_ventas"]
                                        - datos["utilidad_operacional"])[falta]
    datos["empresa"] = datos["empresa"].map(nombre_corto)
    return indicadores(datos.reset_index(drop=True))


# ---------------------------------------------------------------------------
# 3. INDICADORES POR EMPRESA Y AÑO
# ---------------------------------------------------------------------------
def indicadores(d):
    d = d.copy()
    uo = d["utilidad_operacional"].fillna(d["ingresos"] - d["costo_ventas"] - d["gastos_admin"].fillna(0))
    d["utilidad_operacional"] = uo
    d["ebitda"] = uo + d["depreciacion"].fillna(0)
    d["margen_ebitda"] = d["ebitda"] / d["ingresos"]
    sin_dep = d.groupby("empresa")["depreciacion"].transform(lambda x: x.isna().all())
    d.loc[sin_dep, ["ebitda", "margen_ebitda"]] = np.nan  # sin depreciación no se puede calcular el EBITDA
    d["margen_operacional"] = uo / d["ingresos"]
    d["margen_neto"] = d["utilidad_neta"] / d["ingresos"]
    d["crecimiento"] = d.groupby("empresa")["ingresos"].pct_change()
    d["dias_cartera"] = d["deudores"] / d["ingresos"] * 365
    d["dias_proveedores"] = d["proveedores"] / d["costo_ventas"] * 365
    d["ktno"] = d["deudores"].fillna(0) + d["inventarios"].fillna(0) - d["proveedores"].fillna(0)
    sin_cartera = d.groupby("empresa")["deudores"].transform(lambda x: x.isna().all())
    d.loc[sin_cartera, "ktno"] = d["activo_corriente"] - d["pasivo_corriente"]  # aproximación contable
    d["pkt"] = d["ktno"] / d["ingresos"]
    margen_caja = d["margen_ebitda"].fillna(d["margen_operacional"])
    d["palanca"] = np.where(d["pkt"] > 0, margen_caja / d["pkt"], np.nan)
    d["deuda_ebitda"] = np.where(d["ebitda"] > 0, d["deuda_financiera"] / d["ebitda"], np.nan)
    d["cobertura_intereses"] = np.where(d["gastos_financieros"] > 0, d["ebitda"] / d["gastos_financieros"], np.nan)
    pasivos = d["pasivos_totales"].fillna(d["activo_total"] - d["patrimonio"])
    d["endeudamiento"] = pasivos / d["activo_total"]
    d["liquidez"] = d["activo_corriente"] / d["pasivo_corriente"]
    return d


INDICADORES = {
    "margen_operacional": ("Margen operacional (EBIT)", "pct", "De cada $100 que factura, cuánto le queda después de costos y gastos de operación."),
    "margen_ebitda": ("Margen EBITDA", "pct", "De cada $100 que factura, cuánto le queda después de pagar la operación."),
    "crecimiento": ("Crecimiento de ingresos", "pct", "Cuánto crecieron los ingresos frente al año anterior."),
    "dias_cartera": ("Días de cartera", "dias", "Cuántos días tarda en cobrar lo que factura."),
    "pkt": ("Productividad del capital de trabajo (PKT)", "pct", "Cuánto capital de trabajo necesita por cada $100 de ingresos."),
    "deuda_ebitda": ("Deuda / EBITDA", "veces", "Cuántos años de EBITDA necesita para pagar la deuda."),
    "margen_neto": ("Margen neto", "pct", "Utilidad final por cada $100 de ingresos."),
    "liquidez": ("Razón de liquidez", "veces", "Cuántos pesos de activo corriente tiene por cada peso que debe a corto plazo."),
    "endeudamiento": ("Endeudamiento", "pct", "Qué parte de los activos está financiada con deudas."),
}


def disponibles(d):
    """Indicadores que se pueden calcular con los datos cargados."""
    return [k for k in INDICADORES if k in d and d[k].notna().any()]


def resumen_sector(d):
    """Promedio de los años disponibles por empresa y promedio del sector."""
    cols = list(INDICADORES)
    por_empresa = d.groupby("empresa")[cols + ["ingresos"]].mean(numeric_only=True)
    sector = por_empresa[cols].median()
    return por_empresa, sector


def semaforo(indicador, v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "neutro"
    reglas = {
        "margen_ebitda": lambda x: "ok" if x >= 0.12 else ("alerta" if x >= 0.06 else "riesgo"),
        "crecimiento": lambda x: "ok" if x >= 0.05 else ("alerta" if x >= 0 else "riesgo"),
        "dias_cartera": lambda x: "ok" if x <= 45 else ("alerta" if x <= 75 else "riesgo"),
        "pkt": lambda x: "ok" if x <= 0.12 else ("alerta" if x <= 0.20 else "riesgo"),
        "palanca": lambda x: "ok" if x >= 1 else "riesgo",
        "deuda_ebitda": lambda x: "ok" if x <= 2.5 else ("alerta" if x <= 3.5 else "riesgo"),
        "margen_neto": lambda x: "ok" if x >= 0.05 else ("alerta" if x >= 0 else "riesgo"),
        "margen_operacional": lambda x: "ok" if x >= 0.10 else ("alerta" if x >= 0.04 else "riesgo"),
        "liquidez": lambda x: "ok" if x >= 1.2 else ("alerta" if x >= 1.0 else "riesgo"),
        "endeudamiento": lambda x: "ok" if x <= 0.6 else ("alerta" if x <= 0.75 else "riesgo"),
    }
    return reglas[indicador](v)


# ---------------------------------------------------------------------------
# 4. VALIDACIÓN: ¿EL MODELO PRONOSTICA MEJOR QUE LA HOJA DE CÁLCULO?
# ---------------------------------------------------------------------------
def validar(d, ipc=IPC, minimo_previos=2):
    """Validación año por año (origen móvil): para cada operador y cada año t, el modelo solo ve
    los años anteriores a t, pronostica t sin mirarlo y se compara con lo que la empresa reportó.
    Ejemplo con 2021-2025: 2021-2022 -> pronostica 2023; 2021-2023 -> 2024; 2021-2024 -> 2025.
    - Modelo (por drivers): ingresos con el crecimiento promedio observado y utilidad con el margen
      promedio observado.
    - Método tradicional (hoja de cálculo): el año anterior más la inflación (IPC)."""
    filas = []
    for emp, g in d.groupby("empresa"):
        g = g.sort_values("anio").reset_index(drop=True)
        con_ebitda = g["ebitda"].notna().all()
        col, nom = ("ebitda", "EBITDA") if con_ebitda else ("utilidad_operacional", "Utilidad operacional")
        for t in range(minimo_previos, len(g)):
            previos, real = g.iloc[:t], g.iloc[t]
            ultimo = previos.iloc[-1]
            crec = previos["ingresos"].pct_change().dropna().mean()
            margen = (previos[col] / previos["ingresos"]).mean()
            inf = ipc.get(int(ultimo["anio"]), 0.05)
            ing_mod = ultimo["ingresos"] * (1 + crec)
            ing_hoja = ultimo["ingresos"] * (1 + inf)
            for var, mod, hoja, r in [("Ingresos", ing_mod, ing_hoja, real["ingresos"]),
                                       (nom, ing_mod * margen, ultimo[col] * (1 + inf), real[col])]:
                if pd.isna(r) or r == 0 or pd.isna(mod):
                    continue
                filas.append({"empresa": emp, "anio": int(real["anio"]), "con_datos_hasta": int(ultimo["anio"]),
                              "variable": var, "real": r, "modelo": mod, "hoja": hoja,
                              "error_modelo": abs(mod - r) / abs(r), "error_hoja": abs(hoja - r) / abs(r)})
    res = pd.DataFrame(filas)
    if res.empty:
        return res, {}
    resumen = {
        "por_anio": res.groupby("anio")[["error_modelo", "error_hoja"]].mean(),
        "por_variable": res.groupby("variable")[["error_modelo", "error_hoja"]].mean(),
        "empresas": int(res["empresa"].nunique()),
        "mape_modelo": res["error_modelo"].mean(),
        "mape_hoja": res["error_hoja"].mean(),
        "gana_modelo": (res["error_modelo"] < res["error_hoja"]).mean(),
        "n": len(res),
        "p_valor": np.nan,
    }
    if len(res) >= 6 and (res["error_modelo"] != res["error_hoja"]).any():
        resumen["p_valor"] = stats.wilcoxon(res["error_modelo"], res["error_hoja"], alternative="less").pvalue
    return res, resumen


# ---------------------------------------------------------------------------
# 5. CALIBRACIÓN DEL MODELO CON LA MEDIANA DEL SECTOR
# ---------------------------------------------------------------------------
MONETARIOS = ["nomina_operativa", "combustible", "mantenimiento_flota", "gastos_administrativos", "otros_pagos",
              "poliza_semestral", "servicio_deuda", "inversion_flota", "impuesto_renta_anual", "caja_inicial",
              "caja_minima", "inventarios", "saldo_deuda", "costo_disposicion_ton"]
OPERATIVOS = ["nomina_operativa", "combustible", "mantenimiento_flota", "gastos_administrativos", "otros_pagos",
              "poliza_semestral", "costo_disposicion_ton"]


def objetivos_sector(d):
    """Ingreso anual y margen operativo de una empresa típica de Bogotá (mediana de los operadores)."""
    ultimo = d.sort_values("anio").groupby("empresa").tail(1)
    por_emp = d.groupby("empresa")
    margen = por_emp["margen_ebitda"].mean().median()
    fuente = "EBITDA"
    if np.isnan(margen):
        margen, fuente = por_emp["margen_operacional"].mean().median(), "operacional (EBIT)"
    return {"ingreso_anual": float(ultimo["ingresos"].median()), "anio": int(ultimo["anio"].max()),
            "margen": float(margen), "fuente_margen": fuente,
            "empresas": int(d["empresa"].nunique())}


# Mediana de los 5 operadores de aseo de Bogotá (EMIS, estados financieros 2021-2025).
# Solo se guardan estos dos agregados; los estados financieros de cada empresa no se publican.
OBJETIVO_BOGOTA = {"ingreso_anual": 221_289.946, "anio": 2025, "margen": 0.1756,
                   "fuente_margen": "operacional (EBIT)", "empresas": 5}


def calibrar_modelo(s, d, modelo, obj=None):
    """Ajusta los supuestos del modelo para que la empresa tipo tenga el tamaño y el margen
    de la mediana de los operadores reales. Devuelve (supuestos_nuevos, tabla_de_cambios, resumen).
    Si no se pasan datos (d=None), usa la mediana guardada en OBJETIVO_BOGOTA."""
    from dataclasses import replace, asdict
    obj = obj or (objetivos_sector(d) if d is not None else OBJETIVO_BOGOTA)
    ind0 = modelo.indicadores(modelo.proyectar(s), s)
    escala = obj["ingreso_anual"] / ind0["ingresos_anuales"]
    s1 = replace(s, tarifa_promedio=s.tarifa_promedio * escala,
                 **{c: getattr(s, c) * escala for c in MONETARIOS})
    proy = modelo.proyectar(s1)
    ingresos = proy["facturado"].sum()
    costos = proy[modelo.COSTOS_OPERATIVOS].sum().sum()
    k = (1 - obj["margen"]) * ingresos / costos       # factor para llegar al margen del sector
    s2 = replace(s1, **{c: getattr(s1, c) * k for c in OPERATIVOS})
    ind2 = modelo.indicadores(modelo.proyectar(s2), s2)
    a, b = asdict(s), asdict(s2)
    cambios = pd.DataFrame([{"supuesto": c, "antes": a[c], "calibrado": b[c]} for c in a if abs(a[c] - b[c]) > 1e-9])
    resumen = {**obj, "escala": escala, "ajuste_costos": k,
               "ingreso_antes": ind0["ingresos_anuales"], "ingreso_despues": ind2["ingresos_anuales"],
               "margen_antes": ind0["margen_ebitda_pct"] / 100, "margen_despues": ind2["margen_ebitda_pct"] / 100}
    return s2, cambios, resumen


# ---------------------------------------------------------------------------
# 6. PLANTILLA Y DATOS DE EJEMPLO
# ---------------------------------------------------------------------------
def ejemplo():
    """Cinco operadores FICTICIOS (A a E) con cuatro años, solo para probar el aplicativo.
    No son cifras reales de ninguna empresa."""
    rng = np.random.default_rng(7)
    filas = []
    for i, emp in enumerate(["Operador A", "Operador B", "Operador C", "Operador D", "Operador E"]):
        ing = 180_000 + 40_000 * i
        margen = 0.11 + 0.025 * i
        dias_c = 40 + 8 * i
        for j, anio in enumerate(range(2021, 2025)):
            if j:
                ing *= 1 + IPC[anio - 1] + rng.normal(0.02, 0.025)
            m = margen + rng.normal(0, 0.012)
            dep = ing * 0.04
            costo = ing * (1 - m) * 0.86
            gadm = ing * (1 - m) * 0.14
            uo = ing - costo - gadm - dep
            ebitda = uo + dep
            deuda = ebitda * (1.2 + 0.5 * i + rng.normal(0, 0.2))
            filas.append({
                "Empresa": emp, "Año": anio, "Ingresos operacionales": round(ing),
                "Costo de ventas": round(costo + dep * 0.0), "Gastos de administración": round(gadm),
                "Depreciación y amortización": round(dep), "Utilidad operacional": round(uo),
                "Gastos financieros": round(deuda * 0.12), "Utilidad neta": round((uo - deuda * 0.12) * 0.65),
                "Efectivo": round(ing * 0.05), "Cuentas por cobrar": round(ing * dias_c / 365),
                "Inventarios": round(ing * 0.01), "Proveedores": round(costo * 30 / 365),
                "Obligaciones financieras": round(deuda), "Activo total": round(ing * 0.9),
                "Patrimonio": round(ing * 0.35),
            })
    return pd.DataFrame(filas)


def plantilla_excel():
    buf = io.BytesIO()
    vacia = pd.DataFrame(columns=["Empresa", "Año"] + [CAMPOS[c] for c in CAMPOS])
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        vacia.to_excel(w, sheet_name="Datos EMIS", index=False)
        ejemplo().to_excel(w, sheet_name="Ejemplo ficticio", index=False)
        pd.DataFrame({
            "Instrucción": [
                "Una fila por empresa y por año (los últimos 4 años).",
                "Cifras en millones de pesos, tal como aparecen en EMIS.",
                "Obligatorios: Ingresos operacionales y Costo de ventas. Los demás mejoran el análisis.",
                "También puede subir directamente el Excel que descarga EMIS (cuentas en filas y años en columnas).",
                "La hoja 'Ejemplo ficticio' tiene operadores inventados solo para probar.",
            ]}).to_excel(w, sheet_name="Instrucciones", index=False)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 7. SUPUESTOS DEL MODELO A PARTIR DE DATOS REALES (EMIS + FUENTES PÚBLICAS)
# ---------------------------------------------------------------------------
# Mediana 2025 de los 5 operadores de Bogotá (EMIS), como proporción de los ingresos.
# Solo se guardan agregados; los estados financieros de cada empresa no se publican.
REFERENCIA_BOGOTA = {
    "nombre": "Mediana de los 5 operadores de Bogotá", "anio": 2025, "ingresos": 221_289.9,
    "costo_r": 0.6697, "admin_r": 0.1131, "uai_r": 0.1121, "plp_r": 0.0413,
    "crec_real": 0.0446, "toneladas": None,
}
IPC_2025 = 0.0510                     # DANE: inflación anual a diciembre de 2025
TON_DIA_BOGOTA = 5_682                # UAESP: toneladas recolectadas al día en Bogotá, 2025
TON_MES_LIME = 54_892                 # Superservicios: disposición mensual promedio del ASE 2 (LIME)
TASA_RENTA = 0.35                     # Ley 2277 de 2022: tarifa general del impuesto de renta
# Distribución de referencia del costo de ventas entre rubros (el TOTAL sí es real, de EMIS).
REPARTO_COSTOS = {"disposicion": 0.287, "nomina_operativa": 0.417, "combustible": 0.157,
                  "mantenimiento_flota": 0.081, "otros_pagos": 0.035, "poliza": 0.023}


def base_empresa(d=None, empresa=None):
    """Datos base del último año de una empresa (o de la mediana del sector) para el modelo."""
    if d is None:
        return dict(REFERENCIA_BOGOTA)
    if empresa is None:
        u = d.sort_values("anio").groupby("empresa").tail(1).copy()
        u["costo_r"] = u["costo_ventas"] / u["ingresos"]
        u["admin_r"] = u["gastos_admin"] / u["ingresos"]
        u["uai_r"] = u["utilidad_neta"] / u["ingresos"]
        u["plp_r"] = (u["pasivos_totales"] - u["pasivo_corriente"]) / u["ingresos"]
        crec = [crecimiento_real(g) for _, g in d.groupby("empresa")]
        return {"nombre": f"Mediana de los {len(u)} operadores", "anio": int(u["anio"].max()),
                "ingresos": float(u["ingresos"].median()), "costo_r": float(u["costo_r"].median()),
                "admin_r": float(u["admin_r"].median()), "uai_r": float(u["uai_r"].median()),
                "plp_r": float(u["plp_r"].median()), "crec_real": float(np.nanmedian(crec)), "toneladas": None}
    g = d[d["empresa"] == empresa].sort_values("anio")
    u = g.iloc[-1]
    ing = float(u["ingresos"])
    return {"nombre": empresa, "anio": int(u["anio"]), "ingresos": ing,
            "costo_r": float(u["costo_ventas"]) / ing, "admin_r": float(np.nan_to_num(u["gastos_admin"])) / ing,
            "uai_r": float(u["utilidad_neta"]) / ing,
            "plp_r": float(np.nan_to_num(u["pasivos_totales"] - u["pasivo_corriente"])) / ing,
            "crec_real": crecimiento_real(g), "toneladas": TON_MES_LIME if empresa == "LIME" else None}


def crecimiento_real(g):
    """Crecimiento anual promedio de los ingresos descontando la inflación (IPC del DANE)."""
    g = g.sort_values("anio")
    tasas = [(b["ingresos"] / a["ingresos"]) / (1 + IPC.get(int(b["anio"]), 0.05)) - 1
             for (_, a), (_, b) in zip(g.iloc[:-1].iterrows(), g.iloc[1:].iterrows())]
    return float(np.mean(tasas)) if tasas else 0.0


def _mil(x):
    return f"{x:,.0f}".replace(",", ".")


def _pc(x, dec=1):
    return f"{x * 100:.{dec}f}%".replace(".", ",")


def supuestos_reales(b, modelo):
    """Construye los supuestos del modelo a partir de datos reales. Devuelve (Supuestos, tabla de fuentes)."""
    crec = max(min(b["crec_real"], 0.15), -0.05)
    ingreso_anual_2026 = b["ingresos"] * (1 + crec) * (1 + IPC_2025)
    fact_mes = ingreso_anual_2026 / 12
    costo_mes = fact_mes * b["costo_r"]
    admin_mes = fact_mes * b["admin_r"]
    toneladas = b["toneladas"] or TON_DIA_BOGOTA * 365 / 12 / 5
    disp = costo_mes * REPARTO_COSTOS["disposicion"]
    saldo_deuda = b["ingresos"] * b["plp_r"]
    uai = b["ingresos"] * b["uai_r"]
    s = modelo.Supuestos(
        usuarios=1, tarifa_promedio=fact_mes, crecimiento_usuarios_anual=crec,
        tasa_recaudo=0.92, porcion_mes_siguiente=0.50,
        toneladas_mes=toneladas, costo_disposicion_ton=disp / toneladas,
        nomina_operativa=costo_mes * REPARTO_COSTOS["nomina_operativa"],
        combustible=costo_mes * REPARTO_COSTOS["combustible"],
        mantenimiento_flota=costo_mes * REPARTO_COSTOS["mantenimiento_flota"],
        gastos_administrativos=admin_mes,
        otros_pagos=costo_mes * REPARTO_COSTOS["otros_pagos"],
        poliza_semestral=costo_mes * REPARTO_COSTOS["poliza"] * 6,
        servicio_deuda=saldo_deuda / 60, inversion_flota=fact_mes * 0.02,
        impuesto_renta_anual=max(uai, 0) * TASA_RENTA,
        inflacion_anual=IPC_2025, caja_inicial=fact_mes * 0.5,
        caja_minima=(costo_mes + admin_mes) * 0.5,
        inventarios=fact_mes * 0.05, dias_proveedores=30, saldo_deuda=saldo_deuda,
    )
    E, P, V, G = "✅ EMIS", "✅ Fuente pública", "⚠️ Por validar con expertos", "Decisión de la gerencia"
    a = b["anio"]
    filas = [
        ["Facturación mensual base", f"{_mil(fact_mes)} M$", E,
         f"Ingresos {a} ({_mil(b['ingresos'])} M$) × (1 + crecimiento real) × (1 + IPC 2025) ÷ 12"],
        ["Crecimiento real anual", _pc(crec), E, f"Promedio {a - 4}–{a}, descontando la inflación del DANE"],
        ["Inflación (ajuste de tarifas y costos)", _pc(IPC_2025, 2), P, "DANE: IPC 2025"],
        ["Costo de ventas", f"{_pc(b['costo_r'])} de los ingresos", E, f"Estado de resultados {a}"],
        ["Gastos de administración", f"{_pc(b['admin_r'])} de los ingresos", E, f"Estado de resultados {a}"],
        ["Toneladas al mes", f"{_mil(toneladas)} t", P,
         "Superservicios: promedio mensual del ASE 2" if b["toneladas"] else
         f"UAESP: {_mil(TON_DIA_BOGOTA)} t/día en Bogotá (2025) ÷ 5 áreas de servicio"],
        ["Rezago del recaudo", "50% al mes siguiente y 50% a los dos meses", P,
         "Alcaldía de Bogotá: la factura conjunta con el Acueducto se emite cada 58 a 62 días"],
        ["Impuesto de renta", f"{_mil(max(uai, 0) * TASA_RENTA)} M$ al año, en 3 cuotas", P,
         f"Tarifa del 35% (Ley 2277 de 2022) sobre la utilidad antes de impuestos {a} (EMIS)"],
        ["Saldo de la deuda de largo plazo", f"{_mil(saldo_deuda)} M$", E, f"Pasivo total − pasivo corriente {a}"],
        ["Tasa de recaudo", "92%", V, "No es público; se valida con expertos del sector"],
        ["Reparto del costo entre rubros", "nómina 42%, disposición 29%, combustible 16%…", V,
         "El total es real (EMIS); el reparto entre rubros se valida con expertos"],
        ["Cuota mensual de la deuda", f"{_mil(saldo_deuda / 60)} M$", V, "Saldo de la deuda ÷ 60 meses (plazo de 5 años)"],
        ["Reposición de flota", "2% de la facturación", V, "No es público; se valida con expertos"],
        ["Caja inicial", "medio mes de facturación", V, "EMIS no separa el efectivo"],
        ["Caja mínima operativa", "15 días de costos y gastos", G, "Política de liquidez definida por la gerencia"],
    ]
    tabla = pd.DataFrame(filas, columns=["Supuesto", "Valor", "Origen", "Cómo se obtiene"])
    return s, tabla


# ---------------------------------------------------------------------------
# 8. CONTROL PRESUPUESTAL CON DATOS REALES
# ---------------------------------------------------------------------------
def presupuesto_vs_real(d, empresa, tolerancia=0.05):
    """Presupuesto del último año hecho con el método del modelo (solo con los años anteriores)
    frente a lo que la empresa realmente reportó. Devuelve (tabla, año)."""
    g = d[d["empresa"] == empresa].sort_values("anio")
    if len(g) < 3:
        return None, None
    prev, real = g.iloc[:-1], g.iloc[-1]
    ult = prev.iloc[-1]
    crec = prev["ingresos"].pct_change().dropna().mean()
    ing_p = ult["ingresos"] * (1 + crec)
    costo_p = ing_p * (prev["costo_ventas"] / prev["ingresos"]).mean()
    admin_p = ing_p * (prev["gastos_admin"] / prev["ingresos"]).mean()
    uo_p = ing_p * (prev["utilidad_operacional"] / prev["ingresos"]).mean()
    un_p = ing_p * (prev["utilidad_neta"] / prev["ingresos"]).mean()
    filas = []
    for rubro, p, r, es_ingreso in [("Ingresos operacionales", ing_p, real["ingresos"], True),
                                    ("Costo de ventas", costo_p, real["costo_ventas"], False),
                                    ("Gastos de administración", admin_p, real["gastos_admin"], False),
                                    ("Utilidad operacional", uo_p, real["utilidad_operacional"], True),
                                    ("Utilidad neta", un_p, real["utilidad_neta"], True)]:
        if pd.isna(r) or pd.isna(p) or p == 0:
            continue
        desv = (r - p) / abs(p)
        malo = desv < -tolerancia if es_ingreso else desv > tolerancia
        filas.append({"Rubro": rubro, "Presupuestado": p, "Ejecutado": r, "Desviación %": desv * 100,
                      "Estado": "Desfavorable" if malo else ("Favorable" if abs(desv) > tolerancia else "Dentro del rango")})
    return pd.DataFrame(filas), int(real["anio"])
