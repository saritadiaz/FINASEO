"""
FinAseo: aplicativo financiero con inteligencia artificial generativa para una
empresa prestadora del servicio de aseo en Colombia.

Trabajo escrito - Maestría en Finanzas, Universidad Libre de Colombia.
Autoras: Sandra Viviana Nope y Sara Cuta Díaz.

Para ejecutarlo:  streamlit run app.py
"""

from dataclasses import fields
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import modelo as m
import asistente as ia

st.set_page_config(page_title="FinAseo", page_icon="💼", layout="wide")

AZUL, ROJO, GRIS, VERDE = "#2563EB", "#DC2626", "#6B7280", "#16A34A"


def pesos(v):
    return f"${v:,.0f} M".replace(",", ".")


# ---------------------------------------------------------------------------
# Supuestos guardados en la sesión
# ---------------------------------------------------------------------------
if "supuestos" not in st.session_state:
    st.session_state.supuestos = m.Supuestos()
if "historial_ia" not in st.session_state:
    st.session_state.historial_ia = []

s: m.Supuestos = st.session_state.supuestos

# ---------------------------------------------------------------------------
# Menú lateral
# ---------------------------------------------------------------------------
st.sidebar.title("FinAseo")
st.sidebar.caption("Empresa tipo de aseo · datos sintéticos")
pagina = st.sidebar.radio("Módulo", [
    "Inicio", "1. Supuestos y drivers", "2. Presupuesto", "3. Flujo de caja",
    "4. Indicadores", "5. Backtesting (H1)", "6. Asistente IA",
])
escenario = st.sidebar.selectbox("Escenario", list(m.ESCENARIOS), index=0)
st.sidebar.caption(m.DESCRIPCION_ESCENARIOS[escenario])
st.sidebar.divider()
st.sidebar.caption("Cifras en millones de pesos. Ninguna corresponde a una empresa real.")

# Cálculos comunes (el motor financiero)
proy = m.proyectar(s, escenario)
ind = m.indicadores(proy, s)
presupuesto = m.proyectar(s, "Base", anio_inicio=2026)
ejecutado = m.ejecutado_sintetico(presupuesto)


# ---------------------------------------------------------------------------
# INICIO
# ---------------------------------------------------------------------------
if pagina == "Inicio":
    st.title("Aplicativo financiero con inteligencia artificial")
    st.subheader("Presupuesto, flujo de caja y analítica para una empresa de aseo")
    st.write(
        "Este prototipo integra un **modelo financiero** (que hace todas las cuentas), un "
        "**aplicativo** (que facilita su uso) y un **asistente de inteligencia artificial** "
        "(que interpreta los resultados para la gerencia)."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Caja mínima proyectada", pesos(ind["caja_minima_proyectada"]))
    c2.metric("Mes crítico", ind["mes_critico"])
    c3.metric("Meses bajo el mínimo", ind["meses_bajo_minimo"])
    c4.metric("Margen EBITDA", f"{ind['margen_ebitda_pct']:.1f}%")
    st.info(
        "Cómo se relaciona con el trabajo escrito:\n\n"
        "- **Módulos 1 a 4** responden la pregunta específica 1 (arquitectura y drivers).\n"
        "- **Módulo 5** prueba la hipótesis H1 (precisión de las proyecciones, MAPE).\n"
        "- **Módulo 6** genera los análisis que se comparan con los de analistas humanos (H3)."
    )

# ---------------------------------------------------------------------------
# 1. SUPUESTOS
# ---------------------------------------------------------------------------
elif pagina == "1. Supuestos y drivers":
    st.title("Supuestos y drivers financieros")
    st.write("Cambie cualquier valor; todo el aplicativo se recalcula de inmediato.")
    etiquetas = {
        "usuarios": "Usuarios facturados", "tarifa_promedio": "Tarifa promedio por usuario (M$)",
        "crecimiento_usuarios_anual": "Crecimiento anual de usuarios", "tasa_recaudo": "Tasa de recaudo",
        "porcion_mes_siguiente": "Porción del recaudo que llega al mes siguiente",
        "toneladas_mes": "Toneladas recolectadas al mes", "costo_disposicion_ton": "Costo de disposición por tonelada (M$)",
        "nomina_operativa": "Nómina operativa mensual", "combustible": "Combustible mensual",
        "mantenimiento_flota": "Mantenimiento de flota mensual", "gastos_administrativos": "Gastos administrativos mensuales",
        "otros_pagos": "Otros pagos mensuales", "poliza_semestral": "Póliza de flota (abril y octubre)",
        "servicio_deuda": "Servicio de la deuda mensual", "inversion_flota": "Reposición de flota mensual",
        "impuesto_renta_anual": "Impuesto de renta anual (3 cuotas)", "inflacion_anual": "Inflación anual",
        "caja_inicial": "Caja inicial", "caja_minima": "Caja mínima operativa",
    }
    grupos = {
        "Ingresos y recaudo": ["usuarios", "tarifa_promedio", "crecimiento_usuarios_anual", "tasa_recaudo", "porcion_mes_siguiente"],
        "Costos de operación": ["toneladas_mes", "costo_disposicion_ton", "nomina_operativa", "combustible",
                                "mantenimiento_flota", "gastos_administrativos", "otros_pagos", "poliza_semestral"],
        "Financiación, impuestos y tesorería": ["servicio_deuda", "inversion_flota", "impuesto_renta_anual",
                                                 "inflacion_anual", "caja_inicial", "caja_minima"],
    }
    nuevos = {}
    cols = st.columns(3)
    for col, (grupo, campos) in zip(cols, grupos.items()):
        col.markdown(f"**{grupo}**")
        for c in campos:
            v = getattr(s, c)
            if isinstance(v, int):
                nuevos[c] = col.number_input(etiquetas[c], value=v, step=1000, key=f"in_{c}")
            elif v < 1:
                nuevos[c] = col.number_input(etiquetas[c], value=float(v), step=0.005, format="%.3f", key=f"in_{c}")
            else:
                nuevos[c] = col.number_input(etiquetas[c], value=float(v), step=50.0, key=f"in_{c}")
    b1, b2 = st.columns([1, 5])
    if b1.button("Aplicar cambios", type="primary"):
        st.session_state.supuestos = m.Supuestos(**nuevos)
        st.rerun()
    if b2.button("Restablecer valores iniciales"):
        st.session_state.supuestos = m.Supuestos()
        for f in fields(m.Supuestos):
            st.session_state.pop(f"in_{f.name}", None)
        st.rerun()

# ---------------------------------------------------------------------------
# 2. PRESUPUESTO
# ---------------------------------------------------------------------------
elif pagina == "2. Presupuesto":
    st.title("Presupuesto frente a ejecutado 2026")
    mes = st.select_slider("Mes cerrado", options=list(ejecutado["mes"]), value=ejecutado["mes"].iloc[2])
    idx = int(ejecutado.index[ejecutado["mes"] == mes][0])
    tabla = m.tabla_desviaciones(presupuesto, ejecutado, idx)

    def color(fila):
        c = "color: #DC2626; font-weight: 600" if fila["Estado"] == "Desfavorable" else ""
        return [c] * len(fila)

    st.dataframe(
        tabla.style.apply(color, axis=1).format({"Presupuestado": pesos, "Ejecutado": pesos, "Desviación %": "{:+.1f}%"}),
        hide_index=True, width="stretch",
    )
    st.caption("Se marca desfavorable un ingreso 3% por debajo o un egreso 3% por encima de lo presupuestado.")

    fig = go.Figure()
    fig.add_bar(x=presupuesto["mes"].head(9), y=presupuesto["flujo_neto"].head(9), name="Presupuestado", marker_color=GRIS)
    fig.add_bar(x=ejecutado["mes"], y=ejecutado["flujo_neto"], name="Ejecutado", marker_color=AZUL)
    fig.update_layout(title="Flujo neto mensual: presupuestado frente a ejecutado", barmode="group",
                      yaxis_title="Millones de pesos", height=380, margin=dict(t=50, b=30))
    st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------------------
# 3. FLUJO DE CAJA
# ---------------------------------------------------------------------------
elif pagina == "3. Flujo de caja":
    st.title(f"Flujo de caja proyectado 2027 · escenario {escenario.lower()}")
    fig = go.Figure()
    for esc, color in [("Pesimista", ROJO), ("Base", AZUL), ("Optimista", VERDE)]:
        d = m.proyectar(s, esc)
        fig.add_scatter(x=d["mes"], y=d["saldo_caja"], name=esc, mode="lines+markers",
                        line=dict(color=color, width=3 if esc == escenario else 1.5),
                        opacity=1 if esc == escenario else 0.45)
    fig.add_hline(y=s.caja_minima, line_dash="dash", line_color=ROJO,
                  annotation_text=f"Caja mínima {pesos(s.caja_minima)}", annotation_position="top left")
    fig.update_layout(yaxis_title="Saldo de caja (millones de pesos)", height=420, margin=dict(t=30, b=30))
    st.plotly_chart(fig, width="stretch")

    tabla = proy[["mes", "facturado", "recaudo", "egresos", "flujo_neto", "saldo_caja"]].rename(columns={
        "mes": "Mes", "facturado": "Facturado", "recaudo": "Recaudo", "egresos": "Egresos",
        "flujo_neto": "Flujo neto", "saldo_caja": "Saldo de caja"})
    st.dataframe(tabla.style.format({c: pesos for c in tabla.columns if c != "Mes"}),
                 hide_index=True, width="stretch")
    st.download_button("Descargar proyección (CSV)", proy.to_csv(index=False).encode("utf-8"),
                       file_name=f"proyeccion_{escenario.lower()}.csv", mime="text/csv")

    st.subheader("Sensibilidad: caja mínima según recaudo y combustible")
    recaudos = [0.88, 0.90, 0.92, 0.94, 0.96]
    combustibles = [0.9, 1.0, 1.1, 1.2]
    matriz = pd.DataFrame(index=[f"Combustible {int(c * 100)}%" for c in combustibles],
                          columns=[f"Recaudo {int(r * 100)}%" for r in recaudos], dtype=float)
    for c in combustibles:
        for r in recaudos:
            from dataclasses import replace
            d = m.proyectar(replace(s, tasa_recaudo=r, combustible=s.combustible * c), "Base")
            matriz.loc[f"Combustible {int(c * 100)}%", f"Recaudo {int(r * 100)}%"] = d["saldo_caja"].min()
    st.dataframe(matriz.style.format(pesos).background_gradient(cmap="RdYlGn", axis=None),
                 width="stretch")
    st.caption("Cada celda muestra el saldo de caja más bajo del año. Combustible en % del valor del supuesto.")

# ---------------------------------------------------------------------------
# 4. INDICADORES
# ---------------------------------------------------------------------------
elif pagina == "4. Indicadores":
    st.title(f"Tablero de indicadores · escenario {escenario.lower()}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Caja mínima proyectada", pesos(ind["caja_minima_proyectada"]))
    c2.metric("Mes crítico", ind["mes_critico"])
    c3.metric("Meses bajo el mínimo", ind["meses_bajo_minimo"])
    c4.metric("Saldo final del año", pesos(ind["saldo_final"]))
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Margen EBITDA", f"{ind['margen_ebitda_pct']:.1f}%")
    c6.metric("Recaudo sobre facturado", f"{ind['recaudo_sobre_facturado_pct']:.1f}%")
    c7.metric("Días de cartera", f"{ind['dias_cartera']:.0f} días")
    c8.metric("Cobertura de caja", f"{ind['cobertura_caja_meses']:.1f} meses")

    rubros = ["disposicion_final", "nomina", "combustible", "mantenimiento", "administrativos",
              "otros", "poliza", "servicio_deuda", "inversion_flota", "impuestos"]
    nombres = ["Disposición final", "Nómina", "Combustible", "Mantenimiento", "Administrativos",
               "Otros", "Póliza", "Deuda", "Flota", "Impuestos"]
    total = proy[rubros].sum().values
    orden = total.argsort()[::-1]
    fig = go.Figure(go.Bar(x=[total[i] for i in orden], y=[nombres[i] for i in orden], orientation="h", marker_color=AZUL))
    fig.update_layout(title="Egresos del año por rubro", xaxis_title="Millones de pesos",
                      height=400, margin=dict(t=50, b=30), yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------------------
# 5. BACKTESTING
# ---------------------------------------------------------------------------
elif pagina == "5. Backtesting (H1)":
    st.title("Backtesting: ¿el modelo proyecta mejor que la hoja de cálculo?")
    st.write(
        "Se simula la historia 'real' de 2023 a 2025. Con la información hasta diciembre de 2024 se "
        "pronostica 2025 de dos formas, y se compara contra lo que realmente ocurrió:\n\n"
        "- **Modelo por drivers:** proyecta con tarifas, usuarios, recaudo con rezago y costos, y aprende "
        "la estacionalidad del recaudo de los años anteriores.\n"
        "- **Método tradicional:** toma el flujo del mismo mes del año anterior y le suma la inflación."
    )
    semilla = st.number_input("Número de simulación", min_value=0, max_value=999, value=42, step=1)
    comp, res = m.backtesting(s, int(semilla))
    c1, c2 = st.columns(2)
    c1.metric("MAPE modelo por drivers", f"{res['mape_modelo']:.1f}%")
    c2.metric("MAPE método tradicional", f"{res['mape_tradicional']:.1f}%")
    fig = go.Figure()
    fig.add_scatter(x=comp["mes"], y=comp["Real"], name="Real", line=dict(color="#111827", width=3))
    fig.add_scatter(x=comp["mes"], y=comp["Modelo por drivers"], name="Modelo por drivers", line=dict(color=AZUL, dash="dot"))
    fig.add_scatter(x=comp["mes"], y=comp["Método tradicional"], name="Método tradicional", line=dict(color=GRIS, dash="dash"))
    fig.update_layout(yaxis_title="Saldo de caja (millones de pesos)", height=400, margin=dict(t=30, b=30))
    st.plotly_chart(fig, width="stretch")

    st.subheader("Prueba repetida para la hipótesis H1")
    n = st.slider("Número de simulaciones", 20, 200, 50, step=10)
    if st.button("Ejecutar prueba repetida"):
        rep = m.backtesting_repetido(s, n)
        a, b, c = st.columns(3)
        a.metric("MAPE promedio del modelo", f"{rep['mape_modelo'].mean():.1f}%")
        b.metric("MAPE promedio tradicional", f"{rep['mape_tradicional'].mean():.1f}%")
        c.metric("Simulaciones en que gana el modelo", f"{rep['gana_modelo'].mean() * 100:.0f}%")
        try:
            from scipy.stats import wilcoxon
            p = wilcoxon(rep["mape_modelo"], rep["mape_tradicional"], alternative="less").pvalue
            st.write(f"Prueba de Wilcoxon (H1: el MAPE del modelo es menor): p = {p:.4f}. "
                     + ("Se acepta H1 al 5% de significancia." if p < 0.05 else "No hay evidencia suficiente para aceptar H1."))
        except ImportError:
            st.caption("Instale scipy para ver la prueba estadística de Wilcoxon.")
        st.download_button("Descargar resultados (CSV)", rep.to_csv(index=False).encode("utf-8"),
                           file_name="backtesting_repetido.csv", mime="text/csv")
    st.caption("Datos sintéticos: los resultados ilustran el método de evaluación, no el desempeño de una empresa real.")

# ---------------------------------------------------------------------------
# 6. ASISTENTE IA
# ---------------------------------------------------------------------------
elif pagina == "6. Asistente IA":
    st.title("Asistente financiero con inteligencia artificial")
    st.write("El asistente recibe **solo indicadores agregados** del modelo, nunca la base de datos completa, "
             "y no calcula cifras: interpreta las que produce el modelo financiero.")
    mes_idx = 2
    tabla = m.tabla_desviaciones(presupuesto, ejecutado, mes_idx)
    contexto = ia.construir_contexto(escenario, s, proy, ind, tabla, presupuesto.loc[mes_idx, "mes"])

    st.subheader("Alertas automáticas (reglas, sin IA)")
    for a in ia.alertas_por_reglas(contexto):
        (st.error if "ALERTA" in a else st.warning if "Desviación" in a else st.info)(a)

    st.subheader("Pregunte al asistente")
    sugeridas = ["¿Por qué baja la caja en abril y junio?", "¿Necesitamos un crédito de tesorería este año?",
                 "Explique las desviaciones presupuestales de marzo", "¿Qué escenario debería preocupar a la gerencia?"]
    elegida = st.selectbox("Preguntas sugeridas", ["(escriba la suya)"] + sugeridas)
    pregunta = st.text_area("Pregunta", value="" if elegida == "(escriba la suya)" else elegida, height=80)

    try:
        secretos = st.secrets
    except Exception:
        secretos = None
    api_key = ia.obtener_api_key(secretos)
    if not api_key:
        st.caption("Modo demostración: no hay clave de la API de Claude configurada. "
                   "Vea la guía de instalación para activarla.")

    if st.button("Consultar", type="primary"):
        if not pregunta.strip():
            st.error("Escriba una pregunta primero.")
        elif not api_key:
            st.warning("Sin clave de API no se puede consultar a Claude. Abajo puede ver exactamente "
                       "lo que se le enviaría.")
        else:
            with st.spinner("El asistente está analizando…"):
                try:
                    texto, modelo_usado = ia.consultar_claude(contexto, pregunta, api_key)
                    st.session_state.historial_ia.insert(0, {"pregunta": pregunta, "respuesta": texto,
                                                             "modelo": modelo_usado, "escenario": escenario})
                except Exception as e:
                    st.error(f"No se pudo consultar a Claude: {e}")

    for h in st.session_state.historial_ia:
        with st.chat_message("user"):
            st.write(h["pregunta"])
        with st.chat_message("assistant"):
            st.write(h["respuesta"])
            st.caption(f"Modelo: {h['modelo']} · escenario {h['escenario'].lower()}")
    if st.session_state.historial_ia:
        st.download_button("Descargar respuestas para la evaluación (CSV)",
                           pd.DataFrame(st.session_state.historial_ia).to_csv(index=False).encode("utf-8"),
                           file_name="respuestas_asistente.csv", mime="text/csv")

    with st.expander("Ver lo que se envía a la IA (gobierno de datos)"):
        st.code(ia.INSTRUCCIONES_SISTEMA, language=None)
        st.code(ia.construir_mensaje(contexto, pregunta or "(pregunta)"), language="json")
