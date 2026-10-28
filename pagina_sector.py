"""Pantalla 9: comparación con el sector (EMIS): diagnóstico, validación y calibración del modelo."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import modelo as m
import sector_emis as lic
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
def _leer_emis(archivos):
    partes, avisos = [], []
    for a in archivos:
        datos, msj = lic.leer_archivo(a.name, a.getvalue())
        avisos += [f"{a.name}: {x}" for x in msj]
        if datos is not None:
            partes.append(datos)
    for x in avisos:
        st.warning(x)
    if not partes:
        return None
    d = lic.consolidar(pd.concat(partes, ignore_index=True))
    falta = [lic.CAMPOS[c] for c in lic.OBLIGATORIOS if d[c].isna().all()]
    if falta:
        st.error("No se encontró: " + ", ".join(falta) + ". Revise el archivo o use la plantilla.")
        return None
    return d


def _aplicar(d, origen):
    """Guarda los datos y calibra el modelo con ellos (una sola vez por carga)."""
    s_nuevo, _, r = lic.calibrar_modelo(m.Supuestos(), d, m)
    st.session_state.update({"emis": d, "emis_origen": origen, "supuestos": s_nuevo, "supuestos_base": s_nuevo,
                             "calibrado_emis": True, "emis_resumen": r})


def _tabla_datos(d):
    cuentas = [c for c in lic.CAMPOS if d[c].notna().any()]
    cuenta = st.selectbox("Cuenta", cuentas, format_func=lambda c: lic.CAMPOS[c], key="emis_cuenta")
    tabla = d.pivot_table(index="anio", columns="empresa", values=cuenta, aggfunc="first").sort_index()
    tabla.index = tabla.index.astype(int).astype(str)
    tabla.index.name = "Año"
    tabla.columns.name = None
    st.table(tabla.map(lambda v: "—" if pd.isna(v) else f"{v:,.0f}".replace(",", ".")))
    st.caption("Millones de pesos. Cada columna es un operador y cada fila un año. "
               "Fuente: EMIS, con datos de la Cámara de Comercio de Bogotá.")


def fuente_de_supuestos(modelo_mod, sup_bogota, cargar_empresa):
    """Parte superior de '1. Supuestos': de dónde sale la información que alimenta el modelo."""
    st.subheader("¿De dónde sale la información?")
    d = st.session_state.get("emis")
    r = st.session_state.get("emis_resumen") or lic.OBJETIVO_BOGOTA
    if st.session_state.get("hist_real") is not None:
        st.info(f"El modelo está usando los datos mensuales de **{st.session_state.archivo}**.", icon=":material/info:")
    elif st.session_state.get("calibrado_emis"):
        st.success(f"Los supuestos están calibrados con los **{r['empresas']} operadores de aseo de Bogotá** (EMIS): "
                   f"ingresos de {pesos(r['ingreso_anual'])} al año (mediana {r['anio']}) y margen operacional de "
                   f"{pct(r['margen'] * 100)}. A partir de ellos se generan el presupuesto, el flujo de caja y los "
                   "indicadores.", icon=":material/check_circle:")
    t1, t2 = st.tabs(["Estados financieros de los operadores (EMIS)", "Datos mensuales de una empresa (opcional)"])
    with t1:
        st.caption("Suba el Excel con los estados financieros de los operadores. Los supuestos se recalculan solos "
                   "con la mediana del sector. Si no sube nada, el modelo usa la mediana ya guardada (2021–2025).")
        archivos = st.file_uploader("Archivos de EMIS (Excel o CSV)", type=["xlsx", "xls", "csv"],
                                    accept_multiple_files=True, key="emis_archivos")
        firma = tuple((a.name, a.size) for a in archivos) if archivos else None
        if firma and firma != st.session_state.get("emis_firma"):
            nuevos = _leer_emis(archivos)
            if nuevos is not None:
                _aplicar(nuevos, "real")
                st.session_state.emis_firma = firma
                st.toast("Supuestos recalculados con los datos de EMIS.")
                st.rerun()
        c1, c3 = st.columns(2)
        c1.download_button("Descargar plantilla", lic.plantilla_excel(), "plantilla_emis.xlsx",
                           icon=":material/download:", width="stretch")
        if c3.button("Volver a la mediana guardada", icon=":material/restart_alt:", width="stretch"):
            st.session_state.update({"supuestos": sup_bogota, "supuestos_base": sup_bogota, "calibrado_emis": True,
                                     "emis_resumen": None})
            st.rerun()
        if d is not None:
            origen = st.session_state.get("emis_origen")
            st.markdown(f"**Datos cargados:** {d['empresa'].nunique()} empresas, años {int(d['anio'].min())} a "
                        f"{int(d['anio'].max())}" + (" · *operadores ficticios de prueba*" if origen == "ejemplo" else ""))
            with st.expander("Ver los datos leídos"):
                _tabla_datos(d)
    with t2:
        st.caption("Solo si una empresa autoriza usar sus datos mensuales (ventas, recaudo, pagos y saldo de bancos). "
                   "Con ellos el modelo proyecta la caja de esa empresa en particular.")
        cargar_empresa()


# ---------------------------------------------------------------------------
def _diagnostico(d):
    por_emp, sector = lic.resumen_sector(d)
    st.markdown("#### ¿Cómo están financieramente los operadores?")
    st.caption("Promedio de los años cargados. El semáforo usa los mismos umbrales del tablero de indicadores.")
    disp = lic.disponibles(d)
    preferidos = [k for k in ["margen_ebitda", "margen_operacional", "dias_cartera", "liquidez",
                              "endeudamiento", "deuda_ebitda"] if k in disp][:4]
    cols = st.columns(4)
    for i, ind in enumerate(preferidos):
        nombre, tipo, ayuda = lic.INDICADORES[ind]
        tarjeta(cols[i], f"{nombre} · sector", _fmt(sector[ind], tipo), lic.semaforo(ind, sector[ind]),
                "mediana de los operadores", "porcentaje" if tipo == "pct" else "objetivo", ayuda)
    leyenda_estados()

    ind = st.segmented_control("Indicador", disp, default=disp[0],
                               format_func=lambda k: lic.INDICADORES[k][0], key="lic_ind")
    ind = ind if ind in disp else disp[0]
    nombre, tipo, ayuda = lic.INDICADORES[ind]
    fig = go.Figure()
    paleta = [VERDE, PETROLEO, NARANJA, GRIS, "#4ADE80", "#7C3AED", "#B45309"]
    for k, (emp, g) in enumerate(d.groupby("empresa")):
        y = g[ind] * (100 if tipo == "pct" else 1)
        fig.add_bar(x=g["anio"].astype(str), y=y, name=emp, marker_color=paleta[k % len(paleta)])
    fig.update_layout(barmode="group", yaxis_ticksuffix="%" if tipo == "pct" else "")
    st.plotly_chart(estilo_grafico(fig, 380, f"{nombre} por operador y año"), width="stretch")

    mejor = por_emp[ind].idxmax() if ind not in ("dias_cartera", "pkt", "deuda_ebitda", "endeudamiento") else por_emp[ind].idxmin()
    peor = por_emp[ind].idxmin() if ind not in ("dias_cartera", "pkt", "deuda_ebitda", "endeudamiento") else por_emp[ind].idxmax()
    lectura(f"<b>{nombre}:</b> {ayuda} El mejor operador en este indicador es <b>{mejor}</b> "
            f"({_fmt(por_emp.loc[mejor, ind], tipo)}) y el más débil es <b>{peor}</b> "
            f"({_fmt(por_emp.loc[peor, ind], tipo)}). La mediana del sector es {_fmt(sector[ind], tipo)}.")

    st.markdown("#### Tabla resumen por operador")
    res = por_emp[disp].copy()
    vista = pd.DataFrame({lic.INDICADORES[c][0]: [_fmt(v, lic.INDICADORES[c][1]) for v in res[c]]
                          for c in res.columns}, index=res.index)
    vista.index.name = "Operador"
    vista.loc["Mediana del sector"] = [_fmt(sector[c], lic.INDICADORES[c][1]) for c in res.columns]
    st.table(vista)


# ---------------------------------------------------------------------------
def _validacion(d):
    st.markdown("#### ¿El modelo proyecta mejor que la hoja de cálculo tradicional?")
    st.caption("Validación año por año con datos reales: el modelo solo ve los años anteriores, proyecta el "
               "siguiente sin mirarlo y se compara con lo que la empresa reportó a EMIS. Se repite para cada "
               "operador y cada año. Es la prueba de la hipótesis H1.")
    res, r = lic.validar(d)
    if res.empty:
        st.info("Se necesitan al menos 3 años por empresa para validar.")
        return
    anios = sorted(res["anio"].unique())
    pasos = " · ".join(f"datos hasta {a - 1} → proyecta {a}" for a in anios)
    st.markdown(f'<p class="leyenda">{pasos}</p>', unsafe_allow_html=True)

    c = st.columns(4)
    gana = r["mape_modelo"] < r["mape_hoja"]
    tarjeta(c[0], "Error del modelo (MAPE)", pct(r["mape_modelo"] * 100), "ok" if gana else "alerta",
            f"{r['n']} proyecciones", "objetivo",
            "Error porcentual promedio de las proyecciones del modelo frente al dato real.")
    tarjeta(c[1], "Error de la hoja (MAPE)", pct(r["mape_hoja"] * 100), "neutro", "año anterior + IPC", "recibo",
            "Error del método tradicional: el año anterior más la inflación.")
    tarjeta(c[2], "Veces que gana el modelo", pct(r["gana_modelo"] * 100, 0),
            "ok" if r["gana_modelo"] >= 0.5 else "alerta", f"de {r['n']} proyecciones", "escudo")
    p = r["p_valor"]
    tarjeta(c[3], "Prueba de Wilcoxon", "s. d." if np.isnan(p) else f"p = {p:.3f}".replace(".", ","),
            "neutro" if np.isnan(p) else ("ok" if p < 0.05 else "alerta"),
            "significativo si p < 0,05", "porcentaje",
            "Prueba estadística que dice si la diferencia de errores es real o puede ser casualidad.")

    g1, g2 = st.columns(2)
    pa = r["por_anio"]
    fig = go.Figure()
    fig.add_bar(x=[str(a) for a in pa.index], y=pa["error_modelo"] * 100, name="Modelo", marker_color=VERDE,
                text=[pct(v * 100) for v in pa["error_modelo"]], textposition="outside")
    fig.add_bar(x=[str(a) for a in pa.index], y=pa["error_hoja"] * 100, name="Hoja tradicional", marker_color=GRIS,
                text=[pct(v * 100) for v in pa["error_hoja"]], textposition="outside")
    fig.update_layout(barmode="group", yaxis_ticksuffix="%", xaxis_title="Año proyectado")
    g1.plotly_chart(estilo_grafico(fig, 380, "Error promedio por año (más bajo es mejor)"), width="stretch")
    pv = r["por_variable"]
    fig2 = go.Figure()
    fig2.add_bar(x=list(pv.index), y=pv["error_modelo"] * 100, name="Modelo", marker_color=VERDE,
                 text=[pct(v * 100) for v in pv["error_modelo"]], textposition="outside")
    fig2.add_bar(x=list(pv.index), y=pv["error_hoja"] * 100, name="Hoja tradicional", marker_color=GRIS,
                 text=[pct(v * 100) for v in pv["error_hoja"]], textposition="outside")
    fig2.update_layout(barmode="group", yaxis_ticksuffix="%")
    g2.plotly_chart(estilo_grafico(fig2, 380, "Error promedio por variable"), width="stretch")

    tabla = pd.DataFrame({
        "Año proyectado": [str(a) for a in pa.index] + ["Total"],
        "Error del modelo": [pct(v * 100) for v in pa["error_modelo"]] + [pct(r["mape_modelo"] * 100)],
        "Error de la hoja": [pct(v * 100) for v in pa["error_hoja"]] + [pct(r["mape_hoja"] * 100)],
        "Gana": ["Modelo" if a < b else "Hoja" for a, b in zip(pa["error_modelo"], pa["error_hoja"])]
                + ["Modelo" if gana else "Hoja"],
    }).set_index("Año proyectado")
    st.table(tabla)

    años_gana = [str(a) for a, (m_, h_) in pa.iterrows() if m_ < h_]
    mejor_var = [v for v, (m_, h_) in pv.iterrows() if m_ < h_]
    peor_var = [v for v, (m_, h_) in pv.iterrows() if m_ >= h_]
    texto = (f"Con {r['empresas']} operadores y {len(anios)} años proyectados ({r['n']} proyecciones), el modelo "
             f"se equivocó en promedio <b>{pct(r['mape_modelo'] * 100)}</b> y la hoja tradicional "
             f"<b>{pct(r['mape_hoja'] * 100)}</b>. ")
    texto += ("En promedio, <b>el modelo proyecta mejor</b>" if gana else "En promedio, <b>la hoja tradicional proyecta mejor</b>")
    if años_gana:
        lista = años_gana[0] if len(años_gana) == 1 else ", ".join(años_gana[:-1]) + " y " + años_gana[-1]
        texto += f"; el modelo gana en {lista}"
    texto += ". "
    if mejor_var:
        texto += f"Su ventaja está en <b>{', '.join(v.lower() for v in mejor_var)}</b>"
        texto += (f", mientras que en {', '.join(v.lower() for v in peor_var)} el método tradicional es más preciso. "
                  if peor_var else ". ")
    if np.isnan(p):
        texto += "Con tan pocos datos la prueba estadística no se puede calcular; el resultado es exploratorio."
    elif p < 0.05:
        texto += f"La diferencia es estadísticamente significativa (p = {p:.3f}), por lo que H1 se acepta.".replace("0.", "0,", 1)
    else:
        texto += (f"Sin embargo, la diferencia no es estadísticamente significativa (p = {p:.3f}): con cinco operadores "
                  "el resultado es exploratorio y H1 no se puede confirmar con este nivel de evidencia.").replace("0.", "0,", 1)
    lectura(texto, "Lectura para la hipótesis H1")

    with st.expander("Ver cada proyección (millones de pesos)"):
        det = res.rename(columns={"empresa": "Empresa", "anio": "Año proyectado", "con_datos_hasta": "Con datos hasta",
                                  "variable": "Variable", "real": "Real", "modelo": "Modelo",
                                  "hoja": "Hoja tradicional", "error_modelo": "Error modelo", "error_hoja": "Error hoja"})
        st.dataframe(det, hide_index=True, width="stretch", column_config={
            "Año proyectado": st.column_config.NumberColumn(format="%d"),
            "Con datos hasta": st.column_config.NumberColumn(format="%d"),
            **{k: st.column_config.NumberColumn(format="%,.0f") for k in ("Real", "Modelo", "Hoja tradicional")},
            **{k: st.column_config.NumberColumn(format="percent") for k in ("Error modelo", "Error hoja")}})


# ---------------------------------------------------------------------------
def pagina_sector(simulacion=None, pag_supuestos=None):
    encabezado("Validación", "6. Validación con datos reales",
               "Aquí se prueba la hipótesis H1: si el modelo proyecta mejor que la hoja de cálculo tradicional, "
               "usando los estados financieros reales de los operadores de aseo de Bogotá.",
               "1) Diagnóstico: cómo está cada operador frente a la mediana. 2) Validación año por año: con los años "
               "anteriores el modelo proyecta el siguiente y se compara con lo real. 3) Simulación mensual: la misma "
               "prueba, mes a mes, con datos simulados.")
    tabs = st.tabs(["1. Diagnóstico de los operadores", "2. Validación año por año"]
                   + (["3. Simulación mensual"] if simulacion else []))
    d = st.session_state.get("emis")
    for t, fn in [(tabs[0], _diagnostico), (tabs[1], _validacion)]:
        with t:
            if d is None:
                st.info("Primero cargue los estados financieros de EMIS en la parte superior de '1. Supuestos'.",
                        icon=":material/info:")
                if pag_supuestos is not None:
                    st.page_link(pag_supuestos, label="Ir a 1. Supuestos", icon=":material/arrow_forward:")
            else:
                fn(d)
    if simulacion:
        with tabs[2]:
            st.caption("Complemento: como EMIS no trae datos mensuales, esta prueba usa meses simulados con "
                       "resultado conocido para medir qué tan bien anticipa el modelo la caja mes a mes.")
            simulacion()
