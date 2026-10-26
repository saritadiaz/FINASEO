"""Pantalla 9: datos de EMIS, validación del modelo con datos reales y oferta para la licitación."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import licitacion as lic
from estilo import (GRIS, NARANJA, NEGRO, PETROLEO, ROJO, VERDE, encabezado, estilo_grafico,
                    lectura, leyenda_estados, pct, pesos, tarjeta)


def _fmt(v, tipo):
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return "s. d."
    if tipo == "pct":
        return pct(v * 100)
    if tipo == "dias":
        return f"{v:,.0f} días".replace(",", ".")
    return f"{v:,.2f} veces".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
def _cargar():
    st.markdown("#### Suba los estados financieros de los operadores")
    st.caption("Puede subir varios archivos a la vez: el Excel que descarga EMIS de cada empresa "
               "(cuentas en filas y años en columnas) o la plantilla con todas las empresas.")
    archivos = st.file_uploader("Archivos de EMIS (Excel o CSV)", type=["xlsx", "xls", "csv"],
                                accept_multiple_files=True, key="emis_archivos")
    c1, c2 = st.columns([1, 1])
    c1.download_button("Descargar plantilla", lic.plantilla_excel(), "plantilla_emis.xlsx",
                       icon=":material/download:", width="stretch")
    if c2.button("Probar con operadores ficticios", icon=":material/science:", width="stretch"):
        st.session_state.emis = lic.consolidar(
            lic.leer_formato_plantilla(lic.ejemplo().rename(columns=str)))
        st.session_state.emis_origen = "ejemplo"
        st.rerun()

    if archivos:
        partes, avisos = [], []
        for a in archivos:
            datos, msj = lic.leer_archivo(a.name, a.getvalue())
            avisos += [f"{a.name}: {m}" for m in msj]
            if datos is not None:
                partes.append(datos)
        for m in avisos:
            st.warning(m)
        if partes:
            d = lic.consolidar(pd.concat(partes, ignore_index=True))
            falta = [lic.CAMPOS[c] for c in lic.OBLIGATORIOS if d[c].isna().all()]
            if falta:
                st.error("No se encontró: " + ", ".join(falta) + ". Revise el archivo o use la plantilla.")
            else:
                st.session_state.emis = d
                st.session_state.emis_origen = "real"

    d = st.session_state.get("emis")
    if d is None:
        lectura("Aún no hay datos. Suba los archivos de EMIS o pruebe con los operadores ficticios "
                "para ver cómo funciona.", "Qué hacer")
        return
    origen = st.session_state.get("emis_origen")
    st.success(f"{d['empresa'].nunique()} empresas · años {int(d['anio'].min())} a {int(d['anio'].max())}"
               + (" · DATOS FICTICIOS de prueba" if origen == "ejemplo" else " · datos de EMIS"))
    tabla = d[["empresa", "anio"] + list(lic.CAMPOS)].rename(
        columns={"empresa": "Empresa", "anio": "Año", **lic.CAMPOS})
    with st.expander("Ver los datos leídos (millones de pesos)"):
        st.dataframe(tabla, hide_index=True, width="stretch",
                     column_config={"Año": st.column_config.NumberColumn(format="%d")})


# ---------------------------------------------------------------------------
def _diagnostico(d):
    por_emp, sector = lic.resumen_sector(d)
    st.markdown("#### ¿Cómo están financieramente los operadores?")
    st.caption("Promedio de los años cargados. El semáforo usa los mismos umbrales del tablero de indicadores.")
    cols = st.columns(4)
    for i, ind in enumerate(["margen_ebitda", "dias_cartera", "palanca", "deuda_ebitda"]):
        nombre, tipo, ayuda = lic.INDICADORES[ind]
        tarjeta(cols[i], f"{nombre} · sector", _fmt(sector[ind], tipo), lic.semaforo(ind, sector[ind]),
                "mediana de los operadores", "porcentaje" if tipo == "pct" else "objetivo", ayuda)
    leyenda_estados()

    ind = st.segmented_control("Indicador", list(lic.INDICADORES), default="margen_ebitda",
                               format_func=lambda k: lic.INDICADORES[k][0], key="lic_ind")
    ind = ind or "margen_ebitda"
    nombre, tipo, ayuda = lic.INDICADORES[ind]
    fig = go.Figure()
    paleta = [VERDE, PETROLEO, NARANJA, GRIS, "#4ADE80", "#7C3AED", "#B45309"]
    for k, (emp, g) in enumerate(d.groupby("empresa")):
        y = g[ind] * (100 if tipo == "pct" else 1)
        fig.add_bar(x=g["anio"].astype(str), y=y, name=emp, marker_color=paleta[k % len(paleta)])
    fig.update_layout(barmode="group", yaxis_ticksuffix="%" if tipo == "pct" else "")
    st.plotly_chart(estilo_grafico(fig, 380, f"{nombre} por operador y año"), width="stretch")

    mejor = por_emp[ind].idxmax() if ind not in ("dias_cartera", "pkt", "deuda_ebitda") else por_emp[ind].idxmin()
    peor = por_emp[ind].idxmin() if ind not in ("dias_cartera", "pkt", "deuda_ebitda") else por_emp[ind].idxmax()
    lectura(f"<b>{nombre}:</b> {ayuda} El mejor operador en este indicador es <b>{mejor}</b> "
            f"({_fmt(por_emp.loc[mejor, ind], tipo)}) y el más débil es <b>{peor}</b> "
            f"({_fmt(por_emp.loc[peor, ind], tipo)}). La mediana del sector es {_fmt(sector[ind], tipo)}.")

    st.markdown("#### Tabla resumen por operador")
    res = por_emp[list(lic.INDICADORES)].copy()
    vista = pd.DataFrame({lic.INDICADORES[c][0]: [_fmt(v, lic.INDICADORES[c][1]) for v in res[c]]
                          for c in res.columns}, index=res.index)
    vista.index.name = "Operador"
    vista.loc["Mediana del sector"] = [_fmt(sector[c], lic.INDICADORES[c][1]) for c in res.columns]
    st.table(vista)


# ---------------------------------------------------------------------------
def _validacion(d):
    st.markdown("#### ¿El modelo pronostica mejor que la hoja de cálculo tradicional?")
    st.caption("Para cada operador se toman los años anteriores, se pronostica el último año sin mirarlo "
               "y se compara con lo que realmente reportó a EMIS.")
    res, r = lic.validar(d)
    if res.empty:
        st.info("Se necesitan al menos 3 años por empresa para validar.")
        return
    c = st.columns(4)
    tarjeta(c[0], "Error del modelo (MAPE)", pct(r["mape_modelo"] * 100),
            "ok" if r["mape_modelo"] <= r["mape_hoja"] else "alerta", "promedio", "objetivo",
            "Error porcentual promedio del pronóstico del modelo frente al dato real.")
    tarjeta(c[1], "Error de la hoja (MAPE)", pct(r["mape_hoja"] * 100), "neutro", "año anterior + IPC", "recibo",
            "Error del método tradicional: el año anterior más la inflación.")
    tarjeta(c[2], "Veces que gana el modelo", pct(r["gana_modelo"] * 100, 0),
            "ok" if r["gana_modelo"] >= 0.5 else "alerta", f"de {r['n']} pronósticos", "escudo")
    p = r["p_valor"]
    tarjeta(c[3], "Prueba de Wilcoxon", "s. d." if np.isnan(p) else f"p = {p:.3f}".replace(".", ","),
            "neutro" if np.isnan(p) else ("ok" if p < 0.05 else "alerta"),
            "significativo si p < 0,05", "porcentaje",
            "Prueba estadística que dice si la diferencia de errores es real o puede ser casualidad.")

    graf = res.copy()
    graf["etq"] = graf["empresa"] + " · " + graf["variable"]
    fig = go.Figure()
    fig.add_bar(y=graf["etq"], x=graf["error_modelo"] * 100, name="Modelo", orientation="h", marker_color=VERDE)
    fig.add_bar(y=graf["etq"], x=graf["error_hoja"] * 100, name="Hoja tradicional", orientation="h",
                marker_color=GRIS)
    fig.update_layout(barmode="group", xaxis_ticksuffix="%", yaxis_autorange="reversed")
    st.plotly_chart(estilo_grafico(fig, 120 + 45 * len(graf), "Error del pronóstico (más corto es mejor)"),
                    width="stretch")

    gana = r["mape_modelo"] < r["mape_hoja"]
    texto = (f"El modelo se equivocó en promedio <b>{pct(r['mape_modelo'] * 100)}</b> y la hoja tradicional "
             f"<b>{pct(r['mape_hoja'] * 100)}</b>. ")
    texto += ("El modelo pronostica <b>mejor</b> que el método tradicional, " if gana else
              "En estos datos el modelo <b>no</b> superó al método tradicional, ")
    if np.isnan(p):
        texto += "pero con tan pocos datos la prueba estadística no se puede calcular; el resultado es exploratorio."
    elif p < 0.05:
        texto += f"y la diferencia es estadísticamente significativa (p = {p:.3f}).".replace(".", ",", 1)
    else:
        texto += (f"aunque la diferencia todavía no es estadísticamente significativa (p = {p:.3f}); "
                  "con más empresas o años la prueba gana fuerza.").replace("0.", "0,", 1)
    lectura(texto, "Lectura para la hipótesis H1")
    with st.expander("Ver el detalle de cada pronóstico (millones de pesos)"):
        det = res.rename(columns={"empresa": "Empresa", "anio": "Año pronosticado", "variable": "Variable",
                                  "real": "Real", "modelo": "Modelo", "hoja": "Hoja tradicional",
                                  "error_modelo": "Error modelo", "error_hoja": "Error hoja"})
        st.dataframe(det, hide_index=True, width="stretch", column_config={
            "Año pronosticado": st.column_config.NumberColumn(format="%d"),
            **{k: st.column_config.NumberColumn(format="%,.0f") for k in ("Real", "Modelo", "Hoja tradicional")},
            **{k: st.column_config.NumberColumn(format="percent") for k in ("Error modelo", "Error hoja")}})


# ---------------------------------------------------------------------------
def _oferta(d):
    por_emp, sector = lic.resumen_sector(d)
    st.markdown("#### ¿Con qué descuento puede ofertar una empresa sin perder plata?")
    st.caption("El simulador toma la estructura de costos de los últimos años y proyecta el contrato completo. "
               "Los costos no bajan con el descuento: por eso cada punto de descuento sale del margen.")
    opciones = ["Promedio del sector"] + list(por_emp.index)
    ref = st.selectbox("Empresa que oferta (sus costos y su capital de trabajo)", opciones, key="lic_ref")
    p = lic.parametros_desde_sector(por_emp, sector, None if ref == opciones[0] else ref)

    with st.expander("Supuestos del contrato (puede cambiarlos)", expanded=False):
        a, b, c = st.columns(3)
        p["ingreso_techo"] = a.number_input("Ingreso anual del área a tarifa techo (M$)", value=round(p["ingreso_techo"]),
                                            step=1000, help="Lo que facturaría al año cobrando la tarifa máxima de la CRA.")
        p["margen_ebitda"] = b.number_input("Margen EBITDA a tarifa techo", value=round(p["margen_ebitda"], 3),
                                            step=0.005, format="%.3f", help="Sale del histórico de EMIS.")
        p["plazo"] = c.number_input("Años del contrato", value=p["plazo"], min_value=3, max_value=15)
        p["inversion_inicial"] = a.number_input("Inversión inicial en flota (M$)", value=round(p["inversion_inicial"]),
                                                step=1000, help="Camiones compactadores, barredoras y contenedores.")
        p["porc_deuda"] = b.number_input("Porción financiada con crédito", value=p["porc_deuda"], step=0.05, format="%.2f")
        p["tasa_credito"] = c.number_input("Tasa del crédito (anual)", value=p["tasa_credito"], step=0.005, format="%.3f")
        p["tasa_descuento"] = a.number_input("Rentabilidad mínima exigida (tasa de descuento)", value=p["tasa_descuento"],
                                             step=0.005, format="%.3f",
                                             help="Lo mínimo que los socios esperan ganar al año. Con ella se calcula el VPN.")
        p["pkt"] = b.number_input("Capital de trabajo por cada $1 de ingreso (PKT)", value=round(p["pkt"], 3),
                                  step=0.01, format="%.3f", help="Sale del histórico de EMIS.")
        p["choque_pesimista"] = c.number_input("Escenario pesimista: costos más altos en", value=p["choque_pesimista"],
                                               step=0.01, format="%.2f")

    maximo = lic.descuento_maximo(p)
    seguro = lic.descuento_maximo(p, p["choque_pesimista"])
    if maximo is None:
        lectura("Con estos costos, el contrato <b>no es rentable ni siquiera cobrando la tarifa techo</b>. "
                "La empresa necesitaría reducir costos o pedir más ingreso antes de presentarse.", "Resultado")
        return

    oferta = st.slider("Descuento que ofertaría sobre la tarifa techo (%)", 0.0, 30.0,
                       float(round((seguro or 0) * 100, 1)), 0.5, format="%.1f%%", key="lic_dto") / 100
    tabla, r = lic.evaluar_oferta(p, oferta)
    _, rp = lic.evaluar_oferta(p, oferta, p["choque_pesimista"])

    c = st.columns(4)
    tarjeta(c[0], "Descuento recomendado", pct((seguro or 0) * 100), "ok", "aguanta el escenario pesimista", "escudo",
            "El mayor descuento que aún gana plata aunque los costos suban.")
    tarjeta(c[1], "Descuento máximo", pct(maximo * 100), "alerta", "a partir de aquí pierde plata", "alerta",
            "Con un descuento mayor, el VPN es negativo: el contrato destruye valor.")
    est = "ok" if rp["vpn"] >= 0 else ("alerta" if r["vpn"] >= 0 else "riesgo")
    tarjeta(c[2], "VPN de su oferta", pesos(r["vpn"]), est, "valor que crea el contrato", "tendencia",
            "Valor presente neto: lo que gana la empresa en pesos de hoy, después de exigir la rentabilidad mínima.")
    tarjeta(c[3], "TIR de su oferta", "s. d." if np.isnan(r["tir"]) else pct(r["tir"] * 100), est,
            f"exigida {pct(p['tasa_descuento'] * 100)}", "porcentaje",
            "Tasa interna de retorno: la rentabilidad anual del contrato.")

    tope = min(0.30, max(0.10, maximo * 1.8, oferta + 0.02))
    curva = lic.curva_descuentos(p, hasta=tope, paso=tope / 80)
    fig = go.Figure()
    x = curva["descuento"] * 100
    fig.add_vrect(x0=0, x1=(seguro or 0) * 100, fillcolor="#DCFCE7", opacity=0.6, line_width=0)
    fig.add_vrect(x0=(seguro or 0) * 100, x1=maximo * 100, fillcolor="#FDEBD3", opacity=0.6, line_width=0)
    fig.add_vrect(x0=maximo * 100, x1=tope * 100, fillcolor="#FEE4E2", opacity=0.5, line_width=0)
    fig.add_scatter(x=x, y=curva["vpn"], name="VPN escenario base", line=dict(color=VERDE, width=3))
    fig.add_scatter(x=x, y=curva["vpn_pesimista"], name="VPN escenario pesimista",
                    line=dict(color=NARANJA, width=2, dash="dash"))
    fig.add_hline(y=0, line_color=NEGRO, line_width=1)
    fig.add_vline(x=oferta * 100, line_color=PETROLEO, line_dash="dot",
                  annotation_text="Su oferta", annotation_position="bottom right")
    fig.update_layout(xaxis_title="Descuento sobre la tarifa techo", xaxis_ticksuffix="%",
                      yaxis_title="VPN (millones de pesos)")
    st.plotly_chart(estilo_grafico(fig, 420, "Valor que crea el contrato según el descuento ofertado"),
                    width="stretch")
    st.markdown('<p class="leyenda"><b style="background:#BBF7D0"></b>Zona segura: gana aunque suban los costos'
                '<b style="background:#FAD7A8"></b>Zona de riesgo: gana solo si los costos no suben'
                '<b style="background:#FCC8C2"></b>Pierde plata</p>', unsafe_allow_html=True)

    if rp["vpn"] >= 0:
        estado = "está en la <b>zona segura</b>: gana plata incluso si los costos suben"
    elif r["vpn"] >= 0:
        estado = "está en la <b>zona de riesgo</b>: gana plata solo si los costos se mantienen"
    else:
        estado = "<b>pierde plata</b>: el contrato destruiría valor"
    lectura(
        f"Con los costos de <b>{ref.lower() if ref == opciones[0] else ref}</b>, la empresa puede ofertar "
        f"hasta <b>{pct((seguro or 0) * 100)}</b> de descuento con tranquilidad, y nunca más de "
        f"<b>{pct(maximo * 100)}</b>. Con el {pct(oferta * 100)} que eligió, su oferta {estado}. "
        f"En el primer año facturaría {pesos(r['ingreso_anual_1'])}, con un margen EBITDA de "
        f"{pct(r['margen_ebitda_1'] * 100)} y una deuda equivalente a "
        f"{_fmt(r['deuda_ebitda_1'], 'veces')} su EBITDA.",
        "Recomendación para la licitación")
    st.caption("Si el pliego no permite ofertar descuento sobre la tarifa, lea el resultado como el ingreso "
               "mínimo que necesita el área: tarifa techo × (1 − descuento máximo).")

    with st.expander("Ver el flujo del contrato año por año (millones de pesos)"):
        vista = tabla.rename(columns={"anio": "Año", "ingresos": "Ingresos", "costos": "Costos",
                                      "ebitda": "EBITDA", "impuestos": "Impuestos",
                                      "inversion": "Inversión", "var_ktno": "Capital de trabajo",
                                      "flujo_libre": "Flujo libre", "deuda": "Saldo deuda"})
        st.dataframe(vista, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="%,.0f") for c in vista.columns if c != "Año"})


# ---------------------------------------------------------------------------
def pagina_licitacion():
    encabezado("Licitación", "9. Licitación con datos de EMIS",
               "Use los estados financieros reales de los operadores de aseo para validar el modelo y "
               "decidir con qué oferta presentarse a la licitación.",
               "1) Suba los Excel de EMIS de los últimos 4 años. 2) Revise el diagnóstico de cada operador. "
               "3) Vea si el modelo pronosticó mejor que la hoja tradicional. 4) Mueva el descuento y mire "
               "en qué zona queda su oferta: verde es segura, naranja es riesgosa y roja pierde plata.")
    t1, t2, t3, t4 = st.tabs(["1. Cargar datos", "2. Diagnóstico de los operadores",
                              "3. Validación del modelo", "4. Oferta para la licitación"])
    with t1:
        _cargar()
    d = st.session_state.get("emis")
    for t, fn in [(t2, _diagnostico), (t3, _validacion), (t4, _oferta)]:
        with t:
            if d is None:
                st.info("Primero cargue los datos en la pestaña 1.")
            else:
                fn(d)
