"""
FinAseo: aplicativo financiero con inteligencia artificial generativa para una
empresa prestadora del servicio de aseo en Colombia.

Trabajo escrito - Maestría en Finanzas, Universidad Libre de Colombia.
Autoras: Sandra Nope - Sara Cuta Díaz.

Para ejecutarlo:  streamlit run app.py
"""

from dataclasses import fields
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import modelo as m
import asistente as ia

st.set_page_config(page_title="FinAseo", page_icon="💼", layout="wide")

# ---------------------------------------------------------------------------
# Diseño: verde sostenible (los colores generales están en .streamlit/config.toml)
# ---------------------------------------------------------------------------
# Paleta verde sostenible: verde oscuro y verde principal, azul petróleo y naranja como acentos
VERDE_OSCURO, VERDE, PETROLEO, NARANJA, GRIS = "#14432A", "#15803D", "#0F5E6E", "#D9822B", "#8A9A8F"
ROJO = "#B42318"
FUENTE = "Inter, sans-serif"

ESTILOS = """
<style>
.portada {background: #14432A; color: #F3F4F6; border-radius: 14px; padding: 2.2rem 2.4rem;
          border-bottom: 5px solid #D9822B; margin-bottom: 1.4rem;}
.portada .inst {font-size: .78rem; letter-spacing: .14em; text-transform: uppercase; color: #A7D7B5;
                font-weight: 600; margin: 0;}
.portada .fac {font-size: .9rem; color: #CFE3D6; margin: .25rem 0 1.2rem 0;}
.portada h1 {font-family: 'Playfair Display', serif; color: #FFFFFF; font-size: 1.95rem;
             line-height: 1.25; margin: 0 0 1.2rem 0; padding: 0;}
.portada .linea {height: 1px; background: #2F6B47; margin: 1rem 0;}
.portada .autoras {display: flex; gap: 2.5rem; flex-wrap: wrap;}
.portada .autoras div {font-size: 1.02rem; color: #FFFFFF; font-weight: 600;}
.portada .autoras span {display: block; font-size: .75rem; color: #CFE3D6; font-weight: 400;
                        letter-spacing: .08em; text-transform: uppercase;}
.portada .meta {font-size: .85rem; color: #CFE3D6; margin-top: 1rem;}
.kpi {background: #FFFFFF; border: 1px solid #D3E2D7; border-left: 6px solid #8A9A8F; border-radius: 10px;
      padding: .9rem 1.1rem; min-height: 128px; margin-bottom: .9rem;}
.kpi.ok {border-left-color: #15803D;}
.kpi.alerta {border-left-color: #D9822B;}
.kpi.riesgo {border-left-color: #B42318;}
.kpi .lbl {font-size: .78rem; color: #3F5A4A; text-transform: uppercase; letter-spacing: .06em;
           font-weight: 600; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.kpi .val {font-size: 1.65rem; font-weight: 700; color: #14432A; margin: .35rem 0 .3rem 0;
           font-variant-numeric: tabular-nums;}
.kpi .est {display: inline-block; font-size: .72rem; font-weight: 600; padding: .12rem .55rem;
           border-radius: 999px; margin-right: .4rem;}
.kpi.ok .est {background: #DCFCE7; color: #14532D;}
.kpi.alerta .est {background: #FDEBD3; color: #7A3E0B;}
.kpi.riesgo .est {background: #FEE4E2; color: #7A1A12;}
.kpi.neutro .est {background: #E8F1EA; color: #0F5E6E;}
.kpi .nota {font-size: .78rem; color: #557062; white-space: nowrap;}
.capa {background: #FFFFFF; border: 1px solid #D3E2D7; border-top: 4px solid #D9822B; border-radius: 10px;
       padding: 1rem 1.1rem; height: 100%;}
.capa h4 {font-family: 'Playfair Display', serif; color: #14432A; margin: 0 0 .3rem 0; font-size: 1.1rem;}
.capa .rol {font-size: .72rem; text-transform: uppercase; letter-spacing: .1em; color: #D9822B;
            font-weight: 700; margin: 0;}
.capa p {font-size: .88rem; color: #2E4A3B; margin: .3rem 0 0 0;}
.leyenda {font-size: .8rem; color: #3F5A4A; margin: .4rem 0 1rem 0;}
.leyenda b {display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin: 0 .3rem 0 .9rem;}
</style>
"""
st.markdown(ESTILOS, unsafe_allow_html=True)


def pesos(v):
    signo = "-" if v < 0 else ""
    return f"{signo}${abs(v):,.0f} M".replace(",", ".")


ESTADOS = {"ok": "Saludable", "alerta": "Vigilar", "riesgo": "En riesgo", "neutro": "Referencia"}


def tarjeta(columna, etiqueta, valor, estado="neutro", nota=""):
    """Tarjeta de indicador con borde de color según su estado."""
    columna.markdown(
        f'<div class="kpi {estado}"><p class="lbl">{etiqueta}</p><div class="val">{valor}</div>'
        f'<span class="est">{ESTADOS[estado]}</span><span class="nota">{nota}</span></div>',
        unsafe_allow_html=True,
    )


def leyenda_estados():
    st.markdown(
        '<div class="leyenda">Estado del indicador:'
        '<b style="background:#15803D"></b>Saludable<b style="background:#D9822B"></b>Vigilar'
        '<b style="background:#B42318"></b>En riesgo<b style="background:#8A9A8F"></b>Referencia</div>',
        unsafe_allow_html=True,
    )


def estilo_grafico(fig, alto=400, titulo=None):
    fig.update_layout(
        template="plotly_white", height=alto, title=titulo,
        font=dict(family=FUENTE, color=VERDE_OSCURO, size=13),
        title_font=dict(family="'Playfair Display', serif", size=18, color=VERDE_OSCURO),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFFFF",
        margin=dict(t=60 if titulo else 30, b=30, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hoverlabel=dict(font_family=FUENTE),
        separators=",.",   # formato colombiano: punto de miles y coma decimal
    )
    fig.update_xaxes(showgrid=False, linecolor="#D3E2D7")
    fig.update_yaxes(gridcolor="#E8F1EA", zerolinecolor="#D3E2D7", separatethousands=True)
    return fig


def estado_indicadores(ind, s):
    """Reglas de semáforo para cada indicador (umbrales de referencia del prototipo)."""
    caja = ind["caja_minima_proyectada"]
    meses = ind["meses_bajo_minimo"]
    ebitda = ind["margen_ebitda_pct"]
    recaudo = ind["recaudo_sobre_facturado_pct"]
    cartera = ind["dias_cartera"]
    cobertura = ind["cobertura_caja_meses"]
    return {
        "caja": "riesgo" if caja < 0 else "alerta" if caja < s.caja_minima * 1.25 else "ok",
        "meses": "ok" if meses == 0 else "alerta" if meses <= 2 else "riesgo",
        "ebitda": "ok" if ebitda >= 15 else "alerta" if ebitda >= 10 else "riesgo",
        "recaudo": "ok" if recaudo >= 90 else "alerta" if recaudo >= 85 else "riesgo",
        "cartera": "ok" if cartera <= 45 else "alerta" if cartera <= 60 else "riesgo",
        "cobertura": "ok" if cobertura >= 1 else "alerta" if cobertura >= 0.2 else "riesgo",
        "final": "ok" if ind["saldo_final"] >= s.caja_minima else "riesgo",
    }


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
st.sidebar.caption("Sandra Nope - Sara Cuta Díaz  \nMaestría en Finanzas · Universidad Libre")

# Cálculos comunes (el motor financiero)
proy = m.proyectar(s, escenario)
ind = m.indicadores(proy, s)
presupuesto = m.proyectar(s, "Base", anio_inicio=2026)
ejecutado = m.ejecutado_sintetico(presupuesto)


# ---------------------------------------------------------------------------
# INICIO
# ---------------------------------------------------------------------------
if pagina == "Inicio":
    st.markdown(
        '<div class="portada">'
        '<p class="inst">Universidad Libre de Colombia</p>'
        '<p class="fac">Facultad de Ciencias Económicas, Administrativas y Contables · Maestría en Finanzas</p>'
        '<h1>Desarrollo y evaluación de un aplicativo financiero con inteligencia artificial generativa '
        'para la integración del presupuesto, el flujo de caja y la analítica en una empresa prestadora '
        'del servicio de aseo en Colombia</h1>'
        '<div class="linea"></div>'
        '<div class="autoras"><div><span>Autora</span>Sandra Nope</div>'
        '<div><span>Autora</span>Sara Cuta Díaz</div></div>'
        '<p class="meta">Trabajo escrito · Investigación I · Prototipo con datos sintéticos · 2026</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.subheader(f"Resumen del año 2027 · escenario {escenario.lower()}")
    est = estado_indicadores(ind, s)
    c1, c2, c3, c4 = st.columns(4)
    tarjeta(c1, "Caja mínima proyectada", pesos(ind["caja_minima_proyectada"]), est["caja"],
            f"mínimo {pesos(s.caja_minima)}")
    tarjeta(c2, "Mes crítico", ind["mes_critico"], "neutro", "saldo más bajo")
    tarjeta(c3, "Meses bajo el mínimo", str(ind["meses_bajo_minimo"]), est["meses"], "de 12 meses")
    tarjeta(c4, "Margen EBITDA", f"{ind['margen_ebitda_pct']:.1f}%".replace(".", ","), est["ebitda"],
            "sobre lo facturado")
    leyenda_estados()

    st.subheader("Cómo funciona la solución")
    k1, k2, k3 = st.columns(3)
    k1.markdown('<div class="capa"><p class="rol">El motor</p><h4>Modelo financiero</h4>'
                '<p>Proyecta el flujo de caja por drivers, controla la ejecución presupuestal y '
                'calcula los indicadores. Hace todas las cuentas.</p></div>', unsafe_allow_html=True)
    k2.markdown('<div class="capa"><p class="rol">El medio</p><h4>Aplicativo</h4>'
                '<p>Pone el modelo al alcance de la gerencia, con escenarios, gráficos y tablas, '
                'sin manejar hojas de cálculo complejas.</p></div>', unsafe_allow_html=True)
    k3.markdown('<div class="capa"><p class="rol">El intérprete</p><h4>Asistente de IA</h4>'
                '<p>Explica en lenguaje natural lo que muestran las cifras y genera alertas. '
                'Nunca inventa cifras.</p></div>', unsafe_allow_html=True)

    st.subheader("Relación con el trabajo escrito")
    st.markdown(
        "- **Módulos 1 a 4:** responden la pregunta específica 1 (arquitectura y drivers).\n"
        "- **Módulo 5:** prueba la hipótesis H1 (precisión de las proyecciones, MAPE).\n"
        "- **Módulo 6:** genera los análisis que se comparan con los de analistas humanos (H3)."
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
        c = "color: #B42318; font-weight: 600" if fila["Estado"] == "Desfavorable" else ""
        return [c] * len(fila)

    st.dataframe(
        tabla.style.apply(color, axis=1).format({"Presupuestado": pesos, "Ejecutado": pesos, "Desviación %": "{:+.1f}%"}),
        hide_index=True, width="stretch",
    )
    st.caption("Se marca desfavorable un ingreso 3% por debajo o un egreso 3% por encima de lo presupuestado.")

    fig = go.Figure()
    fig.add_bar(x=presupuesto["mes"].head(9), y=presupuesto["flujo_neto"].head(9), name="Presupuestado", marker_color=GRIS)
    fig.add_bar(x=ejecutado["mes"], y=ejecutado["flujo_neto"], name="Ejecutado", marker_color=VERDE_OSCURO)
    estilo_grafico(fig, 400, "Flujo neto mensual: presupuestado frente a ejecutado")
    fig.update_layout(barmode="group", yaxis_title="Millones de pesos", bargap=0.25)
    st.plotly_chart(fig, width="stretch")

# ---------------------------------------------------------------------------
# 3. FLUJO DE CAJA
# ---------------------------------------------------------------------------
elif pagina == "3. Flujo de caja":
    st.title(f"Flujo de caja proyectado 2027 · escenario {escenario.lower()}")
    fig = go.Figure()
    for esc, color in [("Pesimista", NARANJA), ("Optimista", PETROLEO), ("Base", VERDE)]:
        d = m.proyectar(s, esc)
        activo = esc == escenario
        fig.add_scatter(x=d["mes"], y=d["saldo_caja"], name=esc, mode="lines+markers",
                        line=dict(color=color, width=3.5 if activo else 1.5, dash="solid" if activo else "dot"),
                        marker=dict(size=7 if activo else 4), opacity=1 if activo else 0.6)
    fig.add_hline(y=s.caja_minima, line_dash="dash", line_color=ROJO, line_width=1.5,
                  annotation_text=f"Caja mínima {pesos(s.caja_minima)}", annotation_position="top left",
                  annotation_font_color=ROJO)
    estilo_grafico(fig, 440)
    fig.update_layout(yaxis_title="Saldo de caja (millones de pesos)")
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
    from matplotlib.colors import LinearSegmentedColormap
    mapa = LinearSegmentedColormap.from_list("riesgo", ["#F4C7C3", "#FCEFD9", "#D8EDDC", "#8CC79B"])
    st.dataframe(matriz.style.format(pesos).background_gradient(cmap=mapa, axis=None),
                 width="stretch")
    st.caption("Cada celda muestra el saldo de caja más bajo del año. Combustible en % del valor del supuesto.")

# ---------------------------------------------------------------------------
# 4. INDICADORES
# ---------------------------------------------------------------------------
elif pagina == "4. Indicadores":
    st.title(f"Tablero de indicadores · escenario {escenario.lower()}")
    est = estado_indicadores(ind, s)
    st.markdown("##### Liquidez")
    c1, c2, c3, c4 = st.columns(4)
    tarjeta(c1, "Caja mínima proyectada", pesos(ind["caja_minima_proyectada"]), est["caja"],
            f"mínimo {pesos(s.caja_minima)}")
    tarjeta(c2, "Mes crítico", ind["mes_critico"], "neutro", "saldo más bajo")
    tarjeta(c3, "Meses bajo el mínimo", str(ind["meses_bajo_minimo"]), est["meses"], "de 12 meses")
    tarjeta(c4, "Saldo final del año", pesos(ind["saldo_final"]), est["final"], "diciembre")
    st.markdown("##### Rentabilidad y recaudo")
    c5, c6, c7, c8 = st.columns(4)
    tarjeta(c5, "Margen EBITDA", f"{ind['margen_ebitda_pct']:.1f}%".replace(".", ","), est["ebitda"], "meta ≥ 15%")
    tarjeta(c6, "Recaudo / facturado", f"{ind['recaudo_sobre_facturado_pct']:.1f}%".replace(".", ","),
            est["recaudo"], "meta ≥ 90%")
    tarjeta(c7, "Días de cartera", f"{ind['dias_cartera']:.0f} días", est["cartera"], "meta ≤ 45 días")
    tarjeta(c8, "Cobertura de caja", f"{ind['cobertura_caja_meses']:.1f} meses".replace(".", ","),
            est["cobertura"], "meta ≥ 1 mes")
    leyenda_estados()
    st.caption("Umbrales de referencia del prototipo; se validarán con los expertos durante la investigación.")

    rubros = ["disposicion_final", "nomina", "combustible", "mantenimiento", "administrativos",
              "otros", "poliza", "servicio_deuda", "inversion_flota", "impuestos"]
    nombres = ["Disposición final", "Nómina", "Combustible", "Mantenimiento", "Administrativos",
               "Otros", "Póliza", "Deuda", "Flota", "Impuestos"]
    total = proy[rubros].sum().values
    orden = total.argsort()[::-1]
    colores = [NARANJA if k == 0 else VERDE for k in range(len(orden))]
    fig = go.Figure(go.Bar(x=[total[i] for i in orden], y=[nombres[i] for i in orden], orientation="h",
                           marker_color=colores, text=[pesos(total[i]) for i in orden], textposition="outside",
                           cliponaxis=False))
    estilo_grafico(fig, 430, "Egresos del año por rubro")
    fig.update_layout(xaxis_title="Millones de pesos", yaxis=dict(autorange="reversed"), showlegend=False)
    fig.update_xaxes(showticklabels=False, range=[0, max(total) * 1.18])
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
    gana = res["mape_modelo"] < res["mape_tradicional"]
    c1, c2 = st.columns(2)
    tarjeta(c1, "MAPE modelo por drivers", f"{res['mape_modelo']:.1f}%".replace(".", ","),
            "ok" if gana else "alerta", "error promedio del pronóstico")
    tarjeta(c2, "MAPE método tradicional", f"{res['mape_tradicional']:.1f}%".replace(".", ","),
            "neutro", "año anterior + inflación")
    st.write("")
    fig = go.Figure()
    fig.add_scatter(x=comp["mes"], y=comp["Real"], name="Real", line=dict(color=VERDE_OSCURO, width=3.5))
    fig.add_scatter(x=comp["mes"], y=comp["Modelo por drivers"], name="Modelo por drivers",
                    line=dict(color=NARANJA, width=2.5, dash="dot"))
    fig.add_scatter(x=comp["mes"], y=comp["Método tradicional"], name="Método tradicional",
                    line=dict(color=GRIS, width=2, dash="dash"))
    estilo_grafico(fig, 420)
    fig.update_layout(yaxis_title="Saldo de caja (millones de pesos)")
    st.plotly_chart(fig, width="stretch")

    st.subheader("Prueba repetida para la hipótesis H1")
    n = st.slider("Número de simulaciones", 20, 200, 50, step=10)
    if st.button("Ejecutar prueba repetida"):
        rep = m.backtesting_repetido(s, n)
        a, b, c = st.columns(3)
        tarjeta(a, "MAPE promedio del modelo", f"{rep['mape_modelo'].mean():.1f}%".replace(".", ","), "ok",
                f"{n} simulaciones")
        tarjeta(b, "MAPE promedio tradicional", f"{rep['mape_tradicional'].mean():.1f}%".replace(".", ","),
                "neutro", f"{n} simulaciones")
        pct = rep["gana_modelo"].mean() * 100
        tarjeta(c, "Gana el modelo", f"{pct:.0f}%", "ok" if pct >= 70 else "alerta", "de las simulaciones")
        st.write("")
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
