"""
Módulo de licitación: estados financieros anuales de los operadores de aseo (EMIS),
validación del modelo con datos reales y simulador de la oferta para la licitación.

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
}
OBLIGATORIOS = ["ingresos", "costo_ventas"]

# Palabras con que EMIS y Supersociedades suelen nombrar cada cuenta (en español e inglés).
SINONIMOS = {
    "ingresos": ["ingresos de actividades ordinarias", "ingresos operacionales", "ingresos operativos",
                 "ventas netas", "ingresos", "revenue", "net sales", "total revenue", "operating revenue"],
    "costo_ventas": ["costo de ventas", "costos de ventas", "costo de prestacion", "costo de la prestacion",
                     "cost of sales", "cost of goods sold", "cost of revenue"],
    "gastos_admin": ["gastos de administracion", "gastos administrativos", "gastos de ventas",
                     "administrative expenses", "selling general", "operating expenses"],
    "depreciacion": ["depreciacion", "amortizacion", "depreciation", "amortization"],
    "utilidad_operacional": ["utilidad operacional", "ganancia operacional", "resultado operacional",
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
    "activo_total": ["total activos", "activo total", "total de activos", "total assets"],
    "patrimonio": ["total patrimonio", "patrimonio total", "patrimonio", "total equity", "equity"],
}

# IPC de Colombia (variación anual a diciembre, DANE). Se usa para la proyección tradicional.
IPC = {2019: 0.0380, 2020: 0.0161, 2021: 0.0562, 2022: 0.1312, 2023: 0.0928, 2024: 0.0520, 2025: 0.0510}


def _norm(txt):
    txt = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", txt).strip()


def _campo_de(etiqueta):
    """Devuelve el campo al que corresponde el nombre de una cuenta, o None."""
    e = _norm(etiqueta)
    if not e:
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


def consolidar(datos, anios=4):
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
    d["margen_neto"] = d["utilidad_neta"] / d["ingresos"]
    d["crecimiento"] = d.groupby("empresa")["ingresos"].pct_change()
    d["dias_cartera"] = d["deudores"] / d["ingresos"] * 365
    d["dias_proveedores"] = d["proveedores"] / d["costo_ventas"] * 365
    d["ktno"] = d["deudores"].fillna(0) + d["inventarios"].fillna(0) - d["proveedores"].fillna(0)
    d["pkt"] = d["ktno"] / d["ingresos"]
    d["palanca"] = np.where(d["pkt"] > 0, d["margen_ebitda"] / d["pkt"], np.nan)
    d["deuda_ebitda"] = np.where(d["ebitda"] > 0, d["deuda_financiera"] / d["ebitda"], np.nan)
    d["cobertura_intereses"] = np.where(d["gastos_financieros"] > 0, d["ebitda"] / d["gastos_financieros"], np.nan)
    d["endeudamiento"] = (d["activo_total"] - d["patrimonio"]) / d["activo_total"]
    return d


INDICADORES = {
    "margen_ebitda": ("Margen EBITDA", "pct", "De cada $100 que factura, cuánto le queda después de pagar la operación."),
    "crecimiento": ("Crecimiento de ingresos", "pct", "Cuánto crecieron los ingresos frente al año anterior."),
    "dias_cartera": ("Días de cartera", "dias", "Cuántos días tarda en cobrar lo que factura."),
    "pkt": ("Productividad del capital de trabajo (PKT)", "pct", "Cuánto capital de trabajo necesita por cada $100 de ingresos."),
    "palanca": ("Palanca de crecimiento", "veces", "Mayor a 1: crecer le genera caja. Menor a 1: crecer le consume caja."),
    "deuda_ebitda": ("Deuda / EBITDA", "veces", "Cuántos años de EBITDA necesita para pagar la deuda."),
    "margen_neto": ("Margen neto", "pct", "Utilidad final por cada $100 de ingresos."),
}


def resumen_sector(d):
    """Promedio de los años disponibles por empresa y promedio del sector."""
    cols = list(INDICADORES)
    por_empresa = d.groupby("empresa")[cols + ["ingresos", "ebitda"]].mean(numeric_only=True)
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
    }
    return reglas[indicador](v)


# ---------------------------------------------------------------------------
# 4. VALIDACIÓN: ¿EL MODELO PRONOSTICA MEJOR QUE LA HOJA DE CÁLCULO?
# ---------------------------------------------------------------------------
def validar(d, ipc=IPC):
    """Con los años anteriores se pronostica el último año de cada empresa, sin mirarlo,
    y se compara con lo que realmente reportó.
    - Modelo (por drivers): ingresos con el crecimiento promedio de la empresa y
      EBITDA con su margen promedio.
    - Hoja tradicional: el año anterior más la inflación (IPC)."""
    filas = []
    for emp, g in d.groupby("empresa"):
        g = g.sort_values("anio")
        if len(g) < 3:
            continue
        previos, real = g.iloc[:-1], g.iloc[-1]
        ultimo = previos.iloc[-1]
        crec = previos["crecimiento"].dropna().mean()
        margen = previos["margen_ebitda"].mean()
        inf = ipc.get(int(ultimo["anio"]), 0.05)
        ing_mod = ultimo["ingresos"] * (1 + crec)
        ing_hoja = ultimo["ingresos"] * (1 + inf)
        ebitda_mod = ing_mod * margen
        ebitda_hoja = ultimo["ebitda"] * (1 + inf)
        for var, mod, hoja, r in [("Ingresos", ing_mod, ing_hoja, real["ingresos"]),
                                   ("EBITDA", ebitda_mod, ebitda_hoja, real["ebitda"])]:
            if pd.isna(r) or r == 0:
                continue
            filas.append({"empresa": emp, "anio": int(real["anio"]), "variable": var, "real": r,
                          "modelo": mod, "hoja": hoja,
                          "error_modelo": abs(mod - r) / abs(r), "error_hoja": abs(hoja - r) / abs(r)})
    res = pd.DataFrame(filas)
    if res.empty:
        return res, {}
    resumen = {
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
# 5. SIMULADOR DE LA OFERTA PARA LA LICITACIÓN
# ---------------------------------------------------------------------------
def evaluar_oferta(p, descuento, choque_costos=0.0):
    """Proyecta el contrato año por año para un descuento sobre la tarifa techo.
    p: diccionario de parámetros (ver PARAMETROS_OFERTA). Devuelve (tabla, resultado)."""
    años = int(p["plazo"])
    costo_pct = (1 - p["margen_ebitda"]) * (1 + choque_costos)  # los costos no bajan con el descuento
    inversion = p["inversion_inicial"]
    deuda0 = inversion * p["porc_deuda"]
    cuota_capital = deuda0 / p["plazo_credito"]
    saldo = deuda0
    ktno_ant = 0.0
    filas = [{"anio": 0, "ingresos": 0, "costos": 0, "ebitda": 0, "impuestos": 0, "inversion": inversion,
              "var_ktno": 0, "flujo_libre": -inversion, "deuda": saldo}]
    for t in range(1, años + 1):
        base = p["ingreso_techo"] * (1 + p["crecimiento"]) ** (t - 1) * (1 + p["inflacion"]) ** (t - 1)
        ingresos = base * (1 - descuento)
        costos = base * costo_pct
        ebitda = ingresos - costos
        depreciacion = inversion / p["vida_flota"] if t <= p["vida_flota"] else 0
        intereses = saldo * p["tasa_credito"]
        impuestos = max(0.0, (ebitda - depreciacion - intereses) * p["tasa_impuesto"])
        ktno = ingresos * p["pkt"]
        var_ktno = ktno - ktno_ant
        ktno_ant = ktno
        reposicion = ingresos * p["reposicion"]
        flujo = ebitda - impuestos - var_ktno - reposicion
        if t <= p["plazo_credito"]:
            saldo = max(0.0, saldo - cuota_capital)
        filas.append({"anio": t, "ingresos": ingresos, "costos": costos, "ebitda": ebitda,
                      "impuestos": impuestos, "inversion": reposicion, "var_ktno": var_ktno,
                      "flujo_libre": flujo, "deuda": saldo})
    tabla = pd.DataFrame(filas)
    # Al final del contrato se recupera el capital de trabajo
    tabla.loc[tabla.index[-1], "flujo_libre"] += ktno_ant
    tasa = p["tasa_descuento"]
    vpn = float(sum(f / (1 + tasa) ** t for t, f in zip(tabla["anio"], tabla["flujo_libre"])))
    try:
        tir = float(_tir(tabla["flujo_libre"].values))
    except Exception:
        tir = np.nan
    a1 = tabla.iloc[1]
    resultado = {
        "vpn": vpn, "tir": tir,
        "margen_ebitda_1": a1["ebitda"] / a1["ingresos"] if a1["ingresos"] else np.nan,
        "deuda_ebitda_1": deuda0 / a1["ebitda"] if a1["ebitda"] > 0 else np.inf,
        "ingreso_anual_1": a1["ingresos"],
        "ebitda_1": a1["ebitda"],
    }
    return tabla, resultado


def _tir(flujos):
    lo, hi = -0.99, 5.0
    f = lambda r: sum(c / (1 + r) ** i for i, c in enumerate(flujos))
    if f(lo) * f(hi) > 0:
        return np.nan
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def descuento_maximo(p, choque_costos=0.0):
    """Mayor descuento sobre la tarifa techo con el que el contrato todavía no destruye valor (VPN ≥ 0)."""
    if evaluar_oferta(p, 0.0, choque_costos)[1]["vpn"] < 0:
        return None
    lo, hi = 0.0, 0.9
    for _ in range(60):
        mid = (lo + hi) / 2
        if evaluar_oferta(p, mid, choque_costos)[1]["vpn"] >= 0:
            lo = mid
        else:
            hi = mid
    return lo


def curva_descuentos(p, hasta=0.30, paso=0.005):
    filas = []
    for dto in np.arange(0, hasta + 1e-9, paso):
        _, r = evaluar_oferta(p, dto)
        _, rp = evaluar_oferta(p, dto, p["choque_pesimista"])
        filas.append({"descuento": dto, "vpn": r["vpn"], "vpn_pesimista": rp["vpn"],
                      "margen": r["margen_ebitda_1"], "deuda_ebitda": r["deuda_ebitda_1"]})
    return pd.DataFrame(filas)


def parametros_desde_sector(por_empresa, sector, empresa=None):
    ref = por_empresa.loc[empresa] if empresa else por_empresa.median(numeric_only=True)
    margen = float(ref["margen_ebitda"]) if not np.isnan(ref["margen_ebitda"]) else 0.15
    pkt = float(ref["pkt"]) if not np.isnan(ref["pkt"]) else 0.10
    crec_hist = float(ref["crecimiento"]) if not np.isnan(ref["crecimiento"]) else 0.06
    return {
        "ingreso_techo": float(ref["ingresos"]),
        "margen_ebitda": margen,
        "pkt": max(pkt, 0.0),
        "crecimiento": max(min(crec_hist - 0.05, 0.05), 0.0),  # crecimiento real (sin inflación), acotado
        "inflacion": 0.05,
        "plazo": 8,
        "inversion_inicial": float(ref["ingresos"]) * 0.30,
        "porc_deuda": 0.60,
        "tasa_credito": 0.13,
        "plazo_credito": 5,
        "vida_flota": 8,
        "reposicion": 0.02,
        "tasa_impuesto": 0.35,
        "tasa_descuento": 0.14,
        "choque_pesimista": 0.05,
    }


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
