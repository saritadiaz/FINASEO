"""
FinAseo: aplicativo financiero con inteligencia artificial generativa para una
empresa prestadora del servicio de aseo en Bogotá.

Trabajo escrito - Maestría en Finanzas, Universidad Libre de Colombia.
Autoras: Sandra Nope - Sara Cuta Díaz.

Para ejecutarlo:  streamlit run app.py

Estructura del código:
  modelo.py     el motor financiero (todas las cuentas)
  datos.py      la carga de datos reales desde Excel
  informe.py    el informe automático con gráficos de barras
  asistente.py  el asistente de inteligencia artificial
  estilo.py     colores, tarjetas y ayudas didácticas
  app.py        este archivo: las pantallas y la navegación
"""

import io
from dataclasses import fields, replace

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import asistente as ia
import datos
import informe
import modelo as m
from pagina_sector import fuente_de_supuestos, pagina_sector
from estilo import (GRIS, NARANJA, NEGRO, PETROLEO, ROJO, VERDE, aplicar_estilos, dona, encabezado,
                    estilo_grafico, lectura, leyenda_estados, pct, pesos, tarjeta)

st.set_page_config(page_title="FinAseo", page_icon=":material/eco:", layout="wide")
aplicar_estilos()

# ---------------------------------------------------------------------------
# Estado de la sesión (lo que se recuerda mientras la página está abierta)
# ---------------------------------------------------------------------------
import sector_emis

SUP_BOGOTA = sector_emis.calibrar_modelo(m.Supuestos(), None, m)[0]   # empresa tipo de Bogotá (mediana EMIS)

for clave, valor in {"supuestos": SUP_BOGOTA, "supuestos_base": SUP_BOGOTA, "historial_ia": [],
                     "calibrado_emis": True,
                     "hist_real": None, "pres_real": None, "inicio": (2027, 1), "archivo": None,
                     "usuarios_real": 450_000, "toneladas_real": 55_000.0, "esc": "Base"}.items():
    st.session_state.setdefault(clave, valor)

REALES = st.session_state.hist_real is not None
ANIO_P, MES_P = st.session_state.inicio


@st.cache_data(show_spinner=False)
def historico_ejemplo():
    """Histórico sintético de 36 meses (el mismo de la plantilla), para el informe de ejemplo."""
    return datos.leer_excel(io.BytesIO(datos.plantilla_excel()))[0]


def proyectar_app(sup, esc):
    """Proyección de 12 meses que empieza después del último dato real (o en enero de 2027)."""
    previo = st.session_state.hist_real["facturado"].tail(2).tolist() if REALES else None
    return m.proyectar(sup, esc, anio_inicio=ANIO_P, mes_inicio=MES_P, facturado_previo=previo)


def presupuesto_y_ejecutado():
    """Devuelve (presupuesto, ejecutado) alineados por mes, o (None, None) si no hay presupuesto."""
    if REALES:
        pres_r, hist_r = st.session_state.pres_real, st.session_state.hist_real
        if pres_r is None:
            return None, None
        pres = pres_r[pres_r["fecha"].isin(hist_r["fecha"])].reset_index(drop=True)
        ejec = hist_r[hist_r["fecha"].isin(pres["fecha"])].reset_index(drop=True)
        return pres, ejec
    pres = m.proyectar(st.session_state.supuestos, "Base", anio_inicio=2026)
    return pres, m.ejecutado_sintetico(pres)


def estado_indicadores(ind, s):
    """Reglas del semáforo (umbrales de referencia del prototipo, a validar con expertos)."""
    caja, meses = ind["caja_minima_proyectada"], ind["meses_bajo_minimo"]
    return {
        "caja": "riesgo" if caja < 0 else "alerta" if caja < s.caja_minima * 1.25 else "ok",
        "meses": "ok" if meses == 0 else "alerta" if meses <= 2 else "riesgo",
        "ebitda": "ok" if ind["margen_ebitda_pct"] >= 15 else "alerta" if ind["margen_ebitda_pct"] >= 10 else "riesgo",
        "recaudo": "ok" if ind["recaudo_sobre_facturado_pct"] >= 90 else "alerta" if ind["recaudo_sobre_facturado_pct"] >= 85 else "riesgo",
        "cartera": "ok" if ind["dias_cartera"] <= 45 else "alerta" if ind["dias_cartera"] <= 60 else "riesgo",
        "cobertura": "ok" if ind["cobertura_caja_meses"] >= 1 else "alerta" if ind["cobertura_caja_meses"] >= 0.2 else "riesgo",
        "final": "ok" if ind["saldo_final"] >= s.caja_minima else "riesgo",
        "pkt": "ok" if ind["pkt_pct"] <= 15 else "alerta" if ind["pkt_pct"] <= 25 else "riesgo",
        "deuda": "ok" if ind["deuda_ebitda"] <= 2.5 else "alerta" if ind["deuda_ebitda"] <= 3.5 else "riesgo",
    }


def barra_filtros():
    """Barra superior con el escenario, el periodo y la fuente de los datos. Devuelve los cálculos."""
    with st.container(border=True):
        c1, c2, c3 = st.columns([2.2, 2, 2], vertical_alignment="center")
        esc = c1.segmented_control("Escenario", list(m.ESCENARIOS), key="esc",
                                   help="Base: supuestos tal como se definieron. Pesimista y optimista: "
                                        "cambian el recaudo, la velocidad de cobro y el combustible.")
        esc = esc or "Base"
        s = st.session_state.supuestos
        proy = proyectar_app(s, esc)
        periodo = f"{proy['mes'].iloc[0]} a {proy['mes'].iloc[-1]}"
        c2.markdown(f"**Periodo proyectado**  \n{periodo}")
        fuente = (f'<span class="chip real">Datos cargados: {st.session_state.archivo}</span>' if REALES
                  else '<span class="chip">Empresa tipo de Bogotá · mediana de 5 operadores (EMIS)</span>' if st.session_state.get("calibrado_emis")
                  else '<span class="chip">Datos sintéticos · empresa tipo</span>')
        c3.markdown(f"**Fuente de datos**  \n{fuente}", unsafe_allow_html=True)
        st.caption(m.DESCRIPCION_ESCENARIOS[esc])
    return esc, s, proy, m.indicadores(proy, m.aplicar_escenario(s, esc)), periodo


def meses_pagos_grandes(proy):
    grandes = proy[(proy["poliza"] + proy["impuestos"]) > 0]
    return ", ".join(grandes["mes"].str.split().str[0].str.lower().tolist())


# ---------------------------------------------------------------------------
# PÁGINAS
# ---------------------------------------------------------------------------
def pagina_inicio():
    st.markdown(
        '<div class="portada"><div class="cubierta">'
        '<p class="inst">Universidad Libre de Colombia</p>'
        '<p class="fac">Facultad de Ciencias Económicas, Administrativas y Contables · Maestría en Finanzas</p>'
        '<h1>Modelo financiero con inteligencia artificial para el presupuesto y el flujo de caja de las empresas de aseo de Bogotá</h1></div>'
        '<div class="autoras"><div><span>Autora</span>Sandra Nope</div><div><span>Autora</span>Sara Cuta Díaz</div>'
        '<div><span>Trabajo escrito</span>Investigación I · 2026</div></div></div>', unsafe_allow_html=True)

    st.subheader("¿Para qué sirve este modelo?")
    st.markdown(
        "Las empresas de aseo de Bogotá facturan cada mes, pero cobran semanas después, mientras la nómina, el "
        "combustible y la disposición final se pagan de inmediato. Por eso una empresa rentable puede quedarse sin "
        "caja. **Este modelo proyecta el presupuesto y el flujo de caja de los próximos 12 meses y le avisa al "
        "gerente financiero, con anticipación, en qué mes le faltaría plata y por qué**, para que decida a tiempo "
        "(financiarse, cobrar antes o aplazar pagos). La inteligencia artificial explica los resultados en palabras.")
    r1, r2, r3 = st.columns(3)
    r1.markdown('<div class="capa"><p class="rol">1 · Proyecta</p><h4>El modelo</h4><p>Con los supuestos (usuarios, '
                'tarifa, recaudo y costos) calcula presupuesto, caja mes a mes e indicadores.</p></div>',
                unsafe_allow_html=True)
    r2.markdown('<div class="capa"><p class="rol">2 · Se valida</p><h4>Con datos reales</h4><p>Sus supuestos se '
                'calibran con los 5 operadores de aseo de Bogotá (EMIS) y sus proyecciones se comparan año por año '
                'con lo que realmente pasó.</p></div>', unsafe_allow_html=True)
    r3.markdown('<div class="capa"><p class="rol">3 · Explica</p><h4>Asistente de IA</h4><p>Traduce las cifras a '
                'lenguaje sencillo y genera alertas. Nunca inventa cifras: solo interpreta las del modelo.</p></div>',
                unsafe_allow_html=True)

    st.subheader("Resultados de la empresa tipo")
    st.caption("¿De qué empresa son estas cifras? De una **empresa tipo de aseo de Bogotá**: tiene el tamaño "
               "(ingresos de $221.290 M al año) y el margen operacional (17,6%) de la mediana de los cinco "
               "operadores reales de la ciudad, según sus estados financieros en EMIS. No es ninguna empresa en "
               "particular. ¿Para qué sirven? Para ver, mes a mes, si la caja alcanza y cuándo habría que actuar.")
    esc, s, proy, ind, periodo = barra_filtros()
    est = estado_indicadores(ind, s)
    c1, c2, c3, c4 = st.columns(4)
    tarjeta(c1, "Caja mínima proyectada", pesos(ind["caja_minima_proyectada"]), est["caja"],
            f"mínimo {pesos(s.caja_minima)}", "caja", "Saldo más bajo que tendrá la caja en los 12 meses proyectados.")
    tarjeta(c2, "Mes crítico", ind["mes_critico"], "neutro", "saldo más bajo", "calendario",
            "Mes en que la caja llega a su punto más bajo: es cuando la gerencia debe estar preparada.")
    tarjeta(c3, "Meses bajo el mínimo", str(ind["meses_bajo_minimo"]), est["meses"], "de 12 meses", "alerta",
            "Cantidad de meses en que la caja queda por debajo del mínimo operativo.")
    tarjeta(c4, "Margen EBITDA", pct(ind["margen_ebitda_pct"]), est["ebitda"], "sobre lo facturado", "porcentaje",
            "(Facturado − costos operativos) ÷ facturado. Mide cuánto queda de cada peso facturado después de operar.")
    leyenda_estados()
    if ind["meses_bajo_minimo"] > 0:
        lectura(f"En el escenario {esc.lower()}, la caja estará por debajo del mínimo operativo durante "
                f"{ind['meses_bajo_minimo']} meses y llegará a {pesos(ind['caja_minima_proyectada'])} en "
                f"{ind['mes_critico']}. Revise el módulo de flujo de caja para ver desde cuándo conviene gestionar financiación.")
    else:
        holgura = ind["caja_minima_proyectada"] - s.caja_minima
        lectura(f"En el escenario {esc.lower()}, la caja se mantiene sobre el mínimo operativo todo el periodo. "
                f"El momento más ajustado es {ind['mes_critico']}, con una holgura de {pesos(holgura)} sobre el mínimo. "
                "Pruebe el escenario pesimista para ver qué pasaría si el recaudo se demora.")

    with st.expander("Glosario de términos"):
        glosario()


def glosario():
    st.dataframe(pd.DataFrame([
        ["Driver", "Variable que mueve los resultados: usuarios, tarifa, tasa de recaudo, costos."],
        ["Flujo de caja", "Dinero que efectivamente entra y sale cada mes (criterio de caja, no de causación)."],
        ["Caja mínima operativa", "Saldo que la empresa necesita para operar sin riesgo. Por debajo, hay que financiarse."],
        ["Recaudo con rezago", "Lo facturado en un mes se cobra en los meses siguientes, no en el mismo mes."],
        ["Escenario", "Conjunto de supuestos: base, pesimista u optimista."],
        ["Margen EBITDA", "(Facturado − costos operativos) ÷ facturado."],
        ["Días de cartera", "Días que tarda en promedio la empresa en recaudar lo facturado."],
        ["Backtesting", "Pronosticar un periodo que ya ocurrió para medir cuánto se equivoca el modelo."],
        ["MAPE", "Error porcentual absoluto medio: promedio de |real − pronóstico| ÷ real."],
        ["Datos sintéticos", "Datos inventados pero realistas, calibrados con fuentes públicas, para proteger la confidencialidad."],
        ["Asimetría de información", "La gerencia sabe menos que el área financiera sobre su propia empresa."],
    ], columns=["Término", "Significado"]), hide_index=True, width="stretch")


def pagina_supuestos():
    encabezado("El modelo financiero", "1. Supuestos y drivers",
               "Los drivers son las variables que mueven la caja. Todo el aplicativo se recalcula a partir de ellos.",
               ["Cada pestaña agrupa un tipo de driver.", "Pase el cursor sobre el signo ? de cada casilla para ver qué significa.",
                "Cambie los valores y haga clic en 'Aplicar cambios'.", "Vaya al flujo de caja para ver el efecto."])
    fuente_de_supuestos(m, SUP_BOGOTA, lambda: pagina_carga(embebido=True))
    st.subheader("Supuestos del modelo")
    s = st.session_state.supuestos
    ayudas = {
        "usuarios": ("Usuarios facturados", "Suscriptores a los que se les factura el servicio cada mes."),
        "tarifa_promedio": ("Tarifa promedio por usuario (M$)", "Valor promedio facturado por usuario al mes, en millones de pesos (0,025 = $25.000)."),
        "crecimiento_usuarios_anual": ("Crecimiento anual de usuarios", "Proporción en que crecen los usuarios cada año (0,015 = 1,5%)."),
        "tasa_recaudo": ("Tasa de recaudo", "Parte de lo facturado que finalmente se recauda (0,92 = 92%)."),
        "porcion_mes_siguiente": ("Porción del recaudo que llega al mes siguiente", "Del dinero recaudado, cuánto llega un mes después de facturar; el resto llega a los dos meses."),
        "toneladas_mes": ("Toneladas recolectadas al mes", "Volumen de residuos que se recolectan y se llevan a disposición final."),
        "costo_disposicion_ton": ("Costo de disposición por tonelada (M$)", "Lo que cuesta disponer una tonelada en el relleno (0,045 = $45.000)."),
        "nomina_operativa": ("Nómina operativa mensual", "Pagos mensuales al personal operativo, en millones."),
        "combustible": ("Combustible mensual", "Pagos mensuales de combustible de la flota, en millones."),
        "mantenimiento_flota": ("Mantenimiento de flota mensual", "Pagos mensuales de mantenimiento de vehículos, en millones."),
        "gastos_administrativos": ("Gastos administrativos mensuales", "Pagos mensuales de administración, en millones."),
        "otros_pagos": ("Otros pagos mensuales", "Otros pagos operativos, en millones."),
        "poliza_semestral": ("Póliza de flota (abril y octubre)", "Pago de la póliza de vehículos, dos veces al año."),
        "servicio_deuda": ("Servicio de la deuda mensual", "Cuotas de créditos: capital e intereses."),
        "inversion_flota": ("Reposición de flota mensual", "Compra o reposición de vehículos y contenedores."),
        "impuesto_renta_anual": ("Impuesto de renta anual (3 cuotas)", "Se paga en febrero, abril y junio."),
        "inflacion_anual": ("Inflación anual", "Ajusta tarifas y costos cada mes (0,05 = 5%)."),
        "caja_inicial": ("Caja inicial", "Saldo de caja con el que empieza la proyección."),
        "caja_minima": ("Caja mínima operativa", "Saldo por debajo del cual la empresa debe buscar financiación."),
        "inventarios": ("Inventarios (M$)", "Repuestos, llantas e insumos en bodega. En servicios suelen ser bajos."),
        "dias_proveedores": ("Días de pago a proveedores", "Días que la empresa tarda en pagar a sus proveedores. Más días = menos capital de trabajo."),
        "saldo_deuda": ("Saldo de la deuda financiera (M$)", "Saldo total de los créditos con bancos. Se usa para el indicador deuda / EBITDA."),
    }
    grupos = {
        "Ingresos y recaudo": ["usuarios", "tarifa_promedio", "crecimiento_usuarios_anual", "tasa_recaudo", "porcion_mes_siguiente"],
        "Costos de operación": ["toneladas_mes", "costo_disposicion_ton", "nomina_operativa", "combustible",
                                "mantenimiento_flota", "gastos_administrativos", "otros_pagos", "poliza_semestral"],
        "Financiación, impuestos y tesorería": ["servicio_deuda", "inversion_flota", "impuesto_renta_anual",
                                                 "inflacion_anual", "caja_inicial", "caja_minima"],
        "Capital de trabajo y deuda": ["inventarios", "dias_proveedores", "saldo_deuda"],
    }
    pasos = {"dias_proveedores": 5.0, "inventarios": 50.0, "saldo_deuda": 500.0}
    nuevos = {}
    for tab, (grupo, campos) in zip(st.tabs(list(grupos)), grupos.items()):
        with tab:
            cols = st.columns(2)
            for i, c in enumerate(campos):
                etiqueta, ayuda = ayudas[c]
                v = getattr(s, c)
                col = cols[i % 2]
                if isinstance(v, int):
                    nuevos[c] = col.number_input(etiqueta, value=v, step=1000, key=f"in_{c}", help=ayuda)
                elif v < 1:
                    nuevos[c] = col.number_input(etiqueta, value=float(v), step=0.005, format="%.3f", key=f"in_{c}", help=ayuda)
                else:
                    nuevos[c] = col.number_input(etiqueta, value=float(v), step=pasos.get(c, 50.0), key=f"in_{c}", help=ayuda)
    for f in fields(m.Supuestos):
        nuevos.setdefault(f.name, getattr(s, f.name))
    b1, b2, _ = st.columns([1.2, 1.6, 3])
    if b1.button("Aplicar cambios", type="primary", icon=":material/check:"):
        st.session_state.supuestos = m.Supuestos(**nuevos)
        st.toast("Supuestos actualizados. Todo el aplicativo se recalculó.")
        st.rerun()
    if b2.button("Restablecer valores iniciales", icon=":material/restart_alt:"):
        st.session_state.supuestos = st.session_state.supuestos_base
        for f in fields(m.Supuestos):
            st.session_state.pop(f"in_{f.name}", None)
        st.rerun()
    lectura(f"Con estos supuestos, la empresa factura cerca de {pesos(s.usuarios * s.tarifa_promedio)} al mes y "
            f"recauda el {pct(s.tasa_recaudo * 100)} de lo facturado, con un rezago: el "
            f"{pct(s.porcion_mes_siguiente * 100, 0)} llega al mes siguiente y el resto, a los dos meses. "
            "Ese rezago es la razón principal por la que la caja se aprieta aunque la empresa sea rentable.",
            "Qué dicen estos supuestos")


def cargar_presupuesto(abierto=False):
    """Permite cargar el presupuesto de la empresa directamente en esta ventana."""
    with st.expander("Cargar el presupuesto de la empresa (Excel o CSV)", expanded=abierto, icon=":material/upload_file:"):
        if not REALES:
            st.info("Para comparar, el aplicativo necesita también lo **ejecutado** (lo que realmente pasó). "
                    "Cárguelo primero en '1. Supuestos' y vuelva aquí.", icon=":material/info:")
            st.page_link(PAG_SUPUESTOS, label="Ir a 1. Supuestos para cargar los datos", icon=":material/arrow_forward:")
            return
        st.caption("Un archivo con el presupuesto mes a mes: fecha, recaudo o facturación presupuestada y los rubros de "
                   "egresos. Las columnas se reconocen solas por su nombre.")
        archivo = st.file_uploader("Archivo del presupuesto", type=["xlsx", "xls", "csv"], key="archivo_presupuesto")
        if archivo is None:
            return
        try:
            hojas = datos.leer_hojas(archivo)
        except Exception as e:
            st.error(f"No se pudo abrir el archivo: {e}", icon=":material/error:")
            return
        nombres = list(hojas)
        sugerida = next((n for n in nombres if "presupuesto" in n.lower()), datos.hoja_sugerida(hojas))
        hoja = st.selectbox("¿Qué hoja tiene el presupuesto?", nombres, index=nombres.index(sugerida)) if len(nombres) > 1 else sugerida
        mapeo = revisar_columnas(hojas[hoja], f"pres_{archivo.name}_{hoja}", quitar=("saldo_caja",))
        pres, errores, avisos = datos.procesar(hojas[hoja], mapeo, 0.0, hoja)
        for e in errores:
            st.error(e, icon=":material/error:")
        if pres is None:
            return
        comunes = pres["fecha"].isin(st.session_state.hist_real["fecha"])
        if not comunes.any():
            st.error("Los meses del presupuesto no coinciden con los de los datos ejecutados que cargó.", icon=":material/error:")
            return
        st.success(f"Presupuesto leído: {len(pres)} meses, {int(comunes.sum())} de ellos con datos ejecutados para comparar.",
                   icon=":material/check_circle:")
        if st.button("Usar este presupuesto", type="primary", icon=":material/check:"):
            st.session_state.pres_real = pres
            st.rerun()


def pagina_presupuesto():
    pres, ejec = presupuesto_y_ejecutado()
    encabezado("El modelo financiero", "2. Presupuesto",
               "Compara lo presupuestado con lo ejecutado para detectar a tiempo las desviaciones.",
               ["Elija el mes cerrado que quiere revisar.", "La pestaña 'Resumen del mes' muestra lo esencial.",
                "En 'Detalle por rubro', las filas en rojo son desviaciones desfavorables.",
                "'Mes a mes' compara el flujo neto presupuestado y el ejecutado."])
    cargar_presupuesto(abierto=pres is None)
    if pres is None:
        st.info("Cargue el presupuesto de la empresa arriba para compararlo con lo ejecutado.", icon=":material/info:")
        return
    with st.container(border=True):
        inicial = ejec["mes"].iloc[-1] if REALES else ejec["mes"].iloc[2]
        mes = st.select_slider("Mes cerrado", options=list(ejec["mes"]), value=inicial)
    idx = int(ejec.index[ejec["mes"] == mes][0])
    tabla = m.tabla_desviaciones(pres, ejec, idx)
    desfav = tabla[tabla["Estado"] == "Desfavorable"]

    t1, t2, t3 = st.tabs(["Resumen del mes", "Detalle por rubro", "Mes a mes"])
    with t1:
        rec_p, rec_e = pres.loc[idx, "recaudo"], ejec.loc[idx, "recaudo"]
        eg_p, eg_e = pres.loc[idx, "egresos"], ejec.loc[idx, "egresos"]
        fl_p, fl_e = pres.loc[idx, "flujo_neto"], ejec.loc[idx, "flujo_neto"]
        c1, c2, c3, c4 = st.columns(4)
        d_rec = (rec_e - rec_p) / rec_p * 100
        tarjeta(c1, "Recaudo ejecutado", pesos(rec_e), "ok" if d_rec >= -3 else "riesgo",
                f"{pct(d_rec)} vs. presupuesto" if d_rec < 0 else f"+{pct(d_rec)} vs. presupuesto", "recibo", "Dinero recaudado en el mes frente al presupuestado.")
        d_eg = (eg_e - eg_p) / eg_p * 100
        tarjeta(c2, "Egresos ejecutados", pesos(eg_e), "ok" if d_eg <= 3 else "riesgo",
                f"{pct(d_eg)} vs. presupuesto" if d_eg < 0 else f"+{pct(d_eg)} vs. presupuesto", "camion", "Total de pagos del mes frente a lo presupuestado.")
        tarjeta(c3, "Flujo neto del mes", pesos(fl_e), "ok" if fl_e >= fl_p else "alerta",
                f"presupuestado {pesos(fl_p)}", "tendencia", "Recaudo menos egresos del mes.")
        tarjeta(c4, "Rubros desfavorables", str(len(desfav)), "ok" if desfav.empty else "alerta",
                f"de {len(tabla)} rubros", "alerta", "Ingresos 3% por debajo o egresos 3% por encima del presupuesto.")
        # Barras de desviación por rubro
        orden = tabla.reindex(tabla["Desviación %"].abs().sort_values(ascending=True).index)
        colores = [ROJO if e == "Desfavorable" else VERDE for e in orden["Estado"]]
        fig = go.Figure(go.Bar(x=orden["Desviación %"], y=orden["Rubro"], orientation="h", marker_color=colores,
                               text=[f"{v:+.1f}%".replace(".", ",") for v in orden["Desviación %"]], textposition="outside",
                               cliponaxis=False))
        estilo_grafico(fig, max(300, 110 + 38 * len(orden)), f"Desviación frente al presupuesto · {mes}")
        lim = max(5, orden["Desviación %"].abs().max() * 1.3)
        fig.update_xaxes(range=[-lim, lim], ticksuffix="%")
        fig.add_vline(x=0, line_color=GRIS, line_width=1)
        st.plotly_chart(fig, width="stretch")
        if desfav.empty:
            lectura(f"En {mes} todos los rubros estuvieron dentro del rango de tolerancia (±3%).")
        else:
            peor = desfav.reindex(desfav["Desviación %"].abs().sort_values(ascending=False).index).iloc[0]
            signo = "+" if peor["Desviación %"] >= 0 else ""
            texto = (f"En {mes} hubo {len(desfav)} rubro(s) con desviación desfavorable (barras rojas). La más importante fue "
                     f"{peor['Rubro'].lower()}, con {signo}{pct(peor['Desviación %'])} frente a lo presupuestado "
                     f"({pesos(peor['Ejecutado'] - peor['Presupuestado'])}). ")
            if peor["Rubro"] == "Recaudo de tarifa":
                texto += "Un recaudo menor al esperado suele deberse a rezagos en el giro del recaudo por parte de terceros."
            elif peor["Rubro"] == "Combustible":
                texto += "Un mayor costo de combustible conviene revisarlo frente al precio del diésel y los recorridos."
            lectura(texto)
    with t2:
        def color(fila):
            c = "color: #B42318; font-weight: 600" if fila["Estado"] == "Desfavorable" else ""
            return [c] * len(fila)
        st.dataframe(tabla.style.apply(color, axis=1).format(
            {"Presupuestado": pesos, "Ejecutado": pesos, "Desviación %": "{:+.1f}%"}), hide_index=True, width="stretch")
        st.caption("Se marca desfavorable un ingreso 3% por debajo o un egreso 3% por encima de lo presupuestado.")
    with t3:
        n = len(ejec)
        fig = go.Figure()
        fig.add_bar(x=pres["mes"].head(n), y=pres["flujo_neto"].head(n), name="Presupuestado", marker_color=GRIS)
        fig.add_bar(x=ejec["mes"], y=ejec["flujo_neto"], name="Ejecutado", marker_color=VERDE)
        estilo_grafico(fig, 400, "Flujo neto mensual: presupuestado frente a ejecutado")
        fig.update_layout(barmode="group", yaxis_title="Millones de pesos", bargap=0.25)
        st.plotly_chart(fig, width="stretch")
        dif = (ejec["flujo_neto"] - pres["flujo_neto"].head(n)).sum()
        lectura(f"En los {n} meses cerrados, el flujo neto ejecutado fue {pesos(abs(dif))} "
                + ("mayor" if dif >= 0 else "menor") + " que el presupuestado en total.")


def pagina_flujo():
    encabezado("El modelo financiero", "3. Flujo de caja",
               "Proyecta mes a mes cuánto dinero tendrá la empresa, para anticipar faltantes de liquidez.",
               ["Elija el escenario en la barra superior.", "La línea roja punteada es la caja mínima operativa.",
                "Si la línea del escenario cruza la línea roja, la empresa necesitará financiación ese mes.",
                "La pestaña 'Entradas y salidas' muestra en barras de dónde viene el resultado de cada mes."])
    esc, s, proy, ind, periodo = barra_filtros()
    est = estado_indicadores(ind, s)
    c1, c2, c3, c4 = st.columns(4)
    tarjeta(c1, "Caja inicial", pesos(s.caja_inicial), "neutro", "inicio del periodo", "caja", "Saldo de caja con el que empieza la proyección.")
    tarjeta(c2, "Caja mínima proyectada", pesos(ind["caja_minima_proyectada"]), est["caja"], f"en {ind['mes_critico']}",
            "alerta", "Saldo más bajo del periodo proyectado.")
    tarjeta(c3, "Meses bajo el mínimo", str(ind["meses_bajo_minimo"]), est["meses"], f"mínimo {pesos(s.caja_minima)}",
            "calendario", "Meses en que la caja queda por debajo de la caja mínima operativa.")
    tarjeta(c4, "Saldo final", pesos(ind["saldo_final"]), est["final"], proy["mes"].iloc[-1], "tendencia",
            "Saldo de caja al cierre del periodo proyectado.")

    t1, t2, t3, t4 = st.tabs(["Proyección", "Entradas y salidas", "Detalle mensual", "Sensibilidad"])
    with t1:
        fig = go.Figure()
        for e, color in [("Pesimista", NARANJA), ("Optimista", PETROLEO), ("Base", VERDE)]:
            d = proyectar_app(s, e)
            activo = e == esc
            fig.add_scatter(x=d["mes"], y=d["saldo_caja"], name=e, mode="lines+markers",
                            line=dict(color=color, width=3.5 if activo else 1.5, dash="solid" if activo else "dot"),
                            marker=dict(size=7 if activo else 4), opacity=1 if activo else 0.6)
        fig.add_hline(y=s.caja_minima, line_dash="dash", line_color=ROJO, line_width=1.5,
                      annotation_text=f"Caja mínima {pesos(s.caja_minima)}", annotation_position="top left",
                      annotation_font_color=ROJO)
        estilo_grafico(fig, 430)
        fig.update_layout(yaxis_title="Saldo de caja (millones de pesos)")
        st.plotly_chart(fig, width="stretch")
        bajo = proy[proy["saldo_caja"] < s.caja_minima]
        grandes = meses_pagos_grandes(proy)
        if bajo.empty:
            lectura(f"En el escenario {esc.lower()}, la caja no baja del mínimo operativo. El punto más ajustado es "
                    f"{ind['mes_critico']} ({pesos(ind['caja_minima_proyectada'])}). Las caídas de la línea coinciden con "
                    f"los meses de pagos grandes ({grandes}): pólizas e impuesto de renta.")
        else:
            lectura(f"En el escenario {esc.lower()}, la caja cae por debajo del mínimo desde {bajo['mes'].iloc[0]} y llega a "
                    f"{pesos(ind['caja_minima_proyectada'])} en {ind['mes_critico']}. Conviene gestionar desde antes un "
                    f"crédito de tesorería por al menos {pesos(s.caja_minima - ind['caja_minima_proyectada'])}, o acelerar el recaudo.")
    with t2:
        fig = go.Figure()
        fig.add_bar(x=proy["mes"], y=proy["recaudo"], name="Entradas: recaudo", marker_color=VERDE)
        fig.add_bar(x=proy["mes"], y=-proy["egresos"], name="Salidas: egresos", marker_color=NARANJA)
        fig.add_scatter(x=proy["mes"], y=proy["flujo_neto"], name="Flujo neto", mode="lines+markers",
                        line=dict(color=NEGRO, width=2))
        estilo_grafico(fig, 420, "Entradas y salidas de caja por mes")
        fig.update_layout(barmode="relative", yaxis_title="Millones de pesos")
        st.plotly_chart(fig, width="stretch")
        peor = proy.loc[proy["flujo_neto"].idxmin()]
        lectura(f"Las barras verdes son el dinero que entra y las naranja el que sale; la línea negra es la diferencia. "
                f"El peor mes es {peor['mes']}, con un flujo neto de {pesos(peor['flujo_neto'])}, porque coinciden pagos "
                f"grandes ({pesos(peor['poliza'] + peor['impuestos'])} en pólizas e impuestos) con un recaudo que no cambia.")
    with t3:
        tabla = proy[["mes", "facturado", "recaudo", "egresos", "flujo_neto", "saldo_caja"]].rename(columns={
            "mes": "Mes", "facturado": "Facturado", "recaudo": "Recaudo", "egresos": "Egresos",
            "flujo_neto": "Flujo neto", "saldo_caja": "Saldo de caja"})
        st.dataframe(tabla.style.format({c: pesos for c in tabla.columns if c != "Mes"}), hide_index=True, width="stretch")
        st.download_button("Descargar proyección (CSV)", proy.to_csv(index=False).encode("utf-8"),
                           file_name=f"proyeccion_{esc.lower()}.csv", mime="text/csv", icon=":material/download:")
        st.caption("Recaudo = tasa de recaudo × (porción × facturado del mes anterior + resto × facturado de hace dos meses). "
                   "Saldo = saldo anterior + recaudo − egresos.")
    with t4:
        recaudos, combustibles = [0.88, 0.90, 0.92, 0.94, 0.96], [0.9, 1.0, 1.1, 1.2]
        matriz = pd.DataFrame(index=[f"Combustible {int(c * 100)}%" for c in combustibles],
                              columns=[f"Recaudo {int(r * 100)}%" for r in recaudos], dtype=float)
        for c in combustibles:
            for r in recaudos:
                d = proyectar_app(replace(s, tasa_recaudo=r, combustible=s.combustible * c), "Base")
                matriz.loc[f"Combustible {int(c * 100)}%", f"Recaudo {int(r * 100)}%"] = d["saldo_caja"].min()
        from matplotlib.colors import LinearSegmentedColormap
        mapa = LinearSegmentedColormap.from_list("riesgo", ["#F4C7C3", "#FCEFD9", "#DCF3E1", "#86EFAC"])
        st.dataframe(matriz.style.format(pesos).background_gradient(cmap=mapa, axis=None), width="stretch")
        peor = matriz.min().min()
        lectura("Cada celda muestra el saldo de caja más bajo del año si el recaudo y el combustible fueran los de esa "
                f"fila y columna. En la combinación más difícil (recaudo 88% y combustible 120%) la caja llega a {pesos(peor)}. "
                "Las celdas rojas indican combinaciones en las que la empresa necesitaría financiación.",
                "Cómo leer la tabla")


def num(v, dec=1):
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def capital_de_trabajo(ind, est, s):
    """Pestaña de capital de trabajo y deuda / EBITDA."""
    c1, c2, c4 = st.columns(3)
    tarjeta(c1, "KTNO", pesos(ind["ktno"]), "neutro", "cartera + inventarios − proveedores", "caja",
            "Capital de trabajo neto operativo: la plata que la operación tiene 'atrapada' en cartera e inventarios, "
            "menos lo que todavía se debe a proveedores.")
    tarjeta(c2, "Productividad del KT", pct(ind["pkt_pct"]), est["pkt"], "KTNO ÷ ingresos anuales", "porcentaje",
            "Cuántos centavos de capital de trabajo necesita cada peso de ingresos. Entre más bajo, mejor.")
    tarjeta(c4, "Deuda / EBITDA", f"{num(ind['deuda_ebitda'], 2)} veces", est["deuda"], "meta ≤ 2,5 veces", "escudo",
            "Saldo de la deuda ÷ EBITDA anual: cuántos años de EBITDA se necesitan para pagar la deuda.")
    leyenda_estados()

    fig = go.Figure(go.Waterfall(
        x=["Cartera", "Inventarios", "Proveedores", "KTNO"], measure=["relative", "relative", "relative", "total"],
        y=[ind["cartera"], s.inventarios, -ind["proveedores"], 0],
        text=[pesos(ind["cartera"]), pesos(s.inventarios), pesos(-ind["proveedores"]), pesos(ind["ktno"])],
        textposition="outside", cliponaxis=False,
        increasing=dict(marker=dict(color=VERDE)), decreasing=dict(marker=dict(color=NARANJA)),
        totals=dict(marker=dict(color=PETROLEO)), connector=dict(line=dict(color=GRIS, width=1, dash="dot"))))
    estilo_grafico(fig, 380, "Cómo se forma el capital de trabajo (KTNO)")
    fig.update_layout(showlegend=False, yaxis_title="Millones de pesos")
    fig.update_yaxes(range=[0, (ind["cartera"] + s.inventarios) * 1.15])
    st.plotly_chart(fig, width="stretch")

    lectura(f"La operación tiene {pesos(ind['ktno'])} invertidos en capital de trabajo, sobre todo en cartera: por "
            f"cada $100 de ingresos se necesitan ${num(ind['pkt_pct'], 1)} de capital de trabajo. Si el recaudo se "
            "demora, esa cifra crece y la caja se aprieta; cobrar más rápido o negociar plazos con proveedores la reduce."
            + f" La deuda equivale a {num(ind['deuda_ebitda'], 2)} años de EBITDA, "
            + ("un nivel manejable." if ind["deuda_ebitda"] <= 2.5 else "un nivel alto: limita la capacidad de pedir nuevos créditos."),
            "Qué significa para la gerencia")


def verificar_indicadores(proy, ind, s, esc):
    """Muestra cada indicador con su fórmula y la cuenta hecha con las cifras, para poder comprobarlo."""
    fac = proy["facturado"].sum()
    rec = proy["recaudo"].sum()
    costos = proy[m.COSTOS_OPERATIVOS].sum().sum()
    cartera = ind["cartera"]
    fac_mes = fac / len(proy)
    egr_mes = proy["egresos"].mean()
    filas = [
        ["Caja mínima proyectada", "Saldo de caja más bajo de los 12 meses",
         f"mínimo de los saldos mensuales = {pesos(ind['caja_minima_proyectada'])} ({ind['mes_critico']})",
         pesos(ind["caja_minima_proyectada"]), f"Saludable si ≥ {pesos(s.caja_minima * 1.25)} (mínimo + 25%); en riesgo si < 0"],
        ["Meses bajo el mínimo", "Meses con saldo menor que la caja mínima",
         f"meses con saldo < {pesos(s.caja_minima)}", str(ind["meses_bajo_minimo"]), "Saludable si 0; vigilar si 1 o 2"],
        ["Margen EBITDA", "(Facturado − costos operativos) ÷ facturado",
         f"({pesos(fac)} − {pesos(costos)}) ÷ {pesos(fac)}", pct(ind["margen_ebitda_pct"]), "Saludable si ≥ 15%; vigilar si ≥ 10%"],
        ["Recaudo sobre facturado", "Recaudo ÷ facturado",
         f"{pesos(rec)} ÷ {pesos(fac)}", pct(ind["recaudo_sobre_facturado_pct"]), "Saludable si ≥ 90%; vigilar si ≥ 85%"],
        ["Días de cartera", "Cartera pendiente ÷ facturación mensual promedio × 30",
         f"{pesos(cartera)} ÷ {pesos(fac_mes)} × 30", f"{ind['dias_cartera']:.0f} días", "Saludable si ≤ 45 días; vigilar si ≤ 60"],
        ["Cobertura de caja", "Saldo final ÷ egresos mensuales promedio",
         f"{pesos(ind['saldo_final'])} ÷ {pesos(egr_mes)}", f"{ind['cobertura_caja_meses']:.1f} meses".replace(".", ","),
         "Saludable si ≥ 1 mes; vigilar si ≥ 0,2"],
        ["Saldo final", "Saldo de caja del último mes proyectado",
         f"saldo de {proy['mes'].iloc[-1]}", pesos(ind["saldo_final"]), "Saludable si ≥ caja mínima"],
        ["KTNO", "Cartera + inventarios − proveedores",
         f"{pesos(ind['cartera'])} + {pesos(s.inventarios)} − {pesos(ind['proveedores'])}", pesos(ind["ktno"]),
         "Referencia (se interpreta con la productividad del KT)"],
        ["Productividad del KT", "KTNO ÷ ingresos anuales",
         f"{pesos(ind['ktno'])} ÷ {pesos(ind['ingresos_anuales'])}", pct(ind["pkt_pct"]), "Saludable si ≤ 15%; vigilar si ≤ 25%"],
        ["Deuda / EBITDA", "Saldo de la deuda ÷ EBITDA anual",
         f"{pesos(s.saldo_deuda)} ÷ {pesos(ind['ebitda_anual'])}", f"{num(ind['deuda_ebitda'], 2)} veces",
         "Saludable si ≤ 2,5; vigilar si ≤ 3,5"],
    ]
    tabla = pd.DataFrame(filas, columns=["Indicador", "Fórmula", "Cálculo con las cifras", "Resultado", "Criterio del semáforo"])
    # En las tablas el signo $ se escapa para que no se interprete como fórmula matemática
    st.table(tabla.set_index("Indicador").map(lambda x: str(x).replace("$", "\\$")))
    st.download_button("Descargar verificación (CSV)", tabla.to_csv(index=False).encode("utf-8"),
                       file_name=f"verificacion_indicadores_{esc.lower()}.csv", mime="text/csv", icon=":material/download:")
    lectura("Cada indicador muestra su fórmula y la cuenta hecha con las cifras del periodo, para que pueda comprobarse con "
            "una calculadora o en Excel, usando la proyección que se descarga en '3. Flujo de caja' → 'Detalle mensual'. "
            "Los criterios del semáforo son umbrales de referencia del prototipo: en la investigación se validarán con el "
            "juicio de expertos.", "Cómo se validan los indicadores")


def pagina_indicadores():
    encabezado("El modelo financiero", "4. Indicadores",
               "Tablero con los indicadores de liquidez, rentabilidad y recaudo, con semáforo y fórmula de cada uno.",
               ["El color del borde inferior es el semáforo del indicador.", "Pase el cursor sobre el signo ? para ver la fórmula.",
                "Los umbrales son de referencia y se validarán con expertos."])
    esc, s, proy, ind, periodo = barra_filtros()
    est = estado_indicadores(ind, s)
    t1, t2, t5, t3, t4 = st.tabs(["Liquidez", "Rentabilidad y recaudo", "Capital de trabajo y deuda", "Egresos",
                                  "Verificación de cálculos"])
    with t5:
        capital_de_trabajo(ind, est, s)
    with t4:
        verificar_indicadores(proy, ind, s, esc)
    with t1:
        c1, c2, c3, c4 = st.columns(4)
        tarjeta(c1, "Caja mínima proyectada", pesos(ind["caja_minima_proyectada"]), est["caja"], f"mínimo {pesos(s.caja_minima)}",
                "caja", "Saldo más bajo del periodo. Vigilar si está a menos del 25% por encima del mínimo.")
        tarjeta(c2, "Mes crítico", ind["mes_critico"], "neutro", "saldo más bajo", "calendario", "Mes con el saldo de caja más bajo.")
        tarjeta(c3, "Meses bajo el mínimo", str(ind["meses_bajo_minimo"]), est["meses"], "de 12 meses", "alerta",
                "Meses con caja por debajo del mínimo operativo.")
        tarjeta(c4, "Cobertura de caja", f"{ind['cobertura_caja_meses']:.1f} meses".replace(".", ","), est["cobertura"],
                "meta ≥ 1 mes", "escudo", "Saldo final ÷ egresos mensuales promedio. Cuántos meses podría pagar sin recaudar.")
        leyenda_estados()
        colores = [ROJO if v < s.caja_minima else VERDE for v in proy["saldo_caja"]]
        fig = go.Figure(go.Bar(x=proy["mes"], y=proy["saldo_caja"], marker_color=colores))
        fig.add_hline(y=s.caja_minima, line_dash="dash", line_color=ROJO, annotation_text="Caja mínima",
                      annotation_position="top left", annotation_font_color=ROJO)
        estilo_grafico(fig, 340, "Saldo de caja al cierre de cada mes")
        fig.update_layout(showlegend=False, yaxis_title="Millones de pesos")
        st.plotly_chart(fig, width="stretch")
        lectura(f"Con un saldo final de {pesos(ind['saldo_final'])}, la empresa podría cubrir "
                f"{ind['cobertura_caja_meses']:.1f}".replace(".", ",") + " meses de egresos sin recaudar nada. "
                + ("Es una cobertura baja: un retraso del recaudo afectaría rápidamente los pagos."
                   if ind["cobertura_caja_meses"] < 1 else "Es una cobertura adecuada frente a retrasos del recaudo."))
    with t2:
        c1, c2, c3, c4 = st.columns(4)
        tarjeta(c1, "Margen EBITDA", pct(ind["margen_ebitda_pct"]), est["ebitda"], "meta ≥ 15%", "porcentaje",
                "(Facturado − costos operativos) ÷ facturado.")
        tarjeta(c2, "Recaudo / facturado", pct(ind["recaudo_sobre_facturado_pct"]), est["recaudo"], "meta ≥ 90%", "recibo",
                "Recaudo del periodo ÷ facturación del periodo.")
        tarjeta(c3, "Días de cartera", f"{ind['dias_cartera']:.0f} días", est["cartera"], "meta ≤ 45 días", "reloj",
                "Cartera pendiente ÷ facturación mensual promedio × 30.")
        tarjeta(c4, "Saldo final del periodo", pesos(ind["saldo_final"]), est["final"], proy["mes"].iloc[-1], "tendencia",
                "Saldo de caja al cierre del periodo proyectado.")
        leyenda_estados()
        fig = go.Figure()
        fig.add_bar(x=proy["mes"], y=proy["facturado"], name="Facturado", marker_color="#86EFAC")
        fig.add_bar(x=proy["mes"], y=proy["recaudo"], name="Recaudado", marker_color=VERDE)
        estilo_grafico(fig, 340, "Facturado frente a recaudado")
        fig.update_layout(barmode="group", yaxis_title="Millones de pesos", bargap=0.2)
        st.plotly_chart(fig, width="stretch")
        lectura(f"La empresa es rentable (margen EBITDA de {pct(ind['margen_ebitda_pct'])}), pero recauda el "
                f"{pct(ind['recaudo_sobre_facturado_pct'])} de lo que factura y tarda unos {ind['dias_cartera']:.0f} días en cobrar. "
                "Por eso la rentabilidad no garantiza liquidez: la diferencia está en cuándo entra el dinero.")
    with t3:
        rubros = ["disposicion_final", "nomina", "combustible", "mantenimiento", "administrativos",
                  "otros", "poliza", "servicio_deuda", "inversion_flota", "impuestos"]
        nombres = ["Disposición final", "Nómina", "Combustible", "Mantenimiento", "Administrativos",
                   "Otros", "Póliza", "Deuda", "Flota", "Impuestos"]
        total = proy[rubros].sum().values
        orden = total.argsort()[::-1]
        suma = total.sum()
        fig = go.Figure(go.Bar(x=[total[i] for i in orden], y=[nombres[i] for i in orden], orientation="h",
                               marker_color=[NARANJA if k == 0 else VERDE for k in range(len(orden))],
                               text=[f"{pesos(total[i])} · {pct(total[i] / suma * 100)}" for i in orden],
                               textposition="outside", cliponaxis=False))
        estilo_grafico(fig, 430, "Egresos del periodo por rubro")
        fig.update_layout(yaxis=dict(autorange="reversed"), showlegend=False)
        fig.update_xaxes(showticklabels=False, range=[0, max(total) * 1.45])
        g1, g2 = st.columns([1.25, 1])
        g1.plotly_chart(fig, width="stretch")
        g2.plotly_chart(dona(pd.Series(total, index=nombres), "Composición de los egresos", 430), width="stretch")
        lectura(f"El rubro más grande es {nombres[orden[0]].lower()}, con el {pct(total[orden[0]] / suma * 100)} de los egresos. "
                "Es donde una mejora de eficiencia tendría más efecto sobre la caja.")


def pagina_backtesting(embebido=False):
    if not embebido:
        encabezado("Investigación", "5. Backtesting (hipótesis H1)",
                   "Comprueba si el modelo proyecta la caja con menos error que el método tradicional en hoja de cálculo.",
                   ["Empiece por la pestaña '¿Qué es?'.", "En 'Una simulación' verá un caso; cambie el número para ver otro.",
                    "En 'Prueba repetida' está la evidencia estadística de la hipótesis H1.",
                    "Si cargó 24 meses o más de datos reales, aparece la pestaña 'Datos cargados'."])
    s = st.session_state.supuestos
    nombres = ["¿Qué es?", "Una simulación", "Prueba repetida (H1)"]
    con_real = REALES and len(st.session_state.hist_real) >= datos.MESES_BACKTESTING
    if con_real:
        nombres.append("Datos cargados")
    tabs = st.tabs(nombres)

    def grafico(comp):
        fig = go.Figure()
        fig.add_scatter(x=comp["mes"], y=comp["Real"], name="Real", line=dict(color=NEGRO, width=3.5))
        fig.add_scatter(x=comp["mes"], y=comp["Modelo por drivers"], name="Modelo por drivers",
                        line=dict(color=VERDE, width=2.5, dash="dot"))
        fig.add_scatter(x=comp["mes"], y=comp["Método tradicional"], name="Método tradicional",
                        line=dict(color=NARANJA, width=2, dash="dash"))
        estilo_grafico(fig, 400)
        fig.update_layout(yaxis_title="Saldo de caja (millones de pesos)")
        st.plotly_chart(fig, width="stretch")
        err = pd.DataFrame({
            "mes": comp["mes"],
            "Modelo por drivers": (comp["Real"] - comp["Modelo por drivers"]).abs() / comp["Real"].abs() * 100,
            "Método tradicional": (comp["Real"] - comp["Método tradicional"]).abs() / comp["Real"].abs() * 100,
        })
        fig = go.Figure()
        fig.add_bar(x=err["mes"], y=err["Modelo por drivers"], name="Modelo por drivers", marker_color=VERDE)
        fig.add_bar(x=err["mes"], y=err["Método tradicional"], name="Método tradicional", marker_color=NARANJA)
        estilo_grafico(fig, 320, "Error de cada mes (%): barras más bajas = pronóstico más preciso")
        fig.update_layout(barmode="group", bargap=0.2)
        fig.update_yaxes(ticksuffix="%")
        st.plotly_chart(fig, width="stretch")

    def tarjetas(res):
        gana = res["mape_modelo"] < res["mape_tradicional"]
        c1, c2, c3 = st.columns(3)
        tarjeta(c1, "MAPE modelo por drivers", pct(res["mape_modelo"]), "ok" if gana else "alerta",
                "error promedio", "objetivo", "Promedio de |real − pronóstico| ÷ real, mes a mes.")
        tarjeta(c2, "MAPE método tradicional", pct(res["mape_tradicional"]), "neutro", "año anterior + inflación",
                "recibo", "Flujo del mismo mes del año anterior más inflación.")
        veces = res["mape_tradicional"] / res["mape_modelo"] if res["mape_modelo"] > 0 else float("nan")
        tarjeta(c3, "Mejora del modelo", f"{veces:.1f} veces".replace(".", ","), "ok" if gana else "alerta",
                "más preciso" if gana else "menos preciso", "tendencia", "MAPE tradicional ÷ MAPE del modelo.")
        return gana

    with tabs[0]:
        st.markdown(
            "**El backtesting** consiste en pronosticar un periodo que ya ocurrió, para comparar el pronóstico con lo que "
            "realmente pasó. Es como probar un pronóstico del clima con los días de la semana pasada.\n\n"
            "1. Se toma la historia hasta diciembre de 2024.\n"
            "2. Con ella se pronostica 2025 de dos formas: con el **modelo por drivers** y con el **método tradicional** "
            "(el flujo del mismo mes del año anterior más la inflación).\n"
            "3. Se compara cada pronóstico con lo que realmente ocurrió en 2025 y se calcula el error con el **MAPE**.")
        st.latex(r"MAPE = \frac{1}{n}\sum_{t=1}^{n}\left|\frac{Real_t - Pron\acute{o}stico_t}{Real_t}\right| \times 100")
        lectura("Ejemplo: si el saldo real de un mes fue $4.854 M y el modelo pronosticó $4.788 M, el error de ese mes es "
                "|4.854 − 4.788| ÷ 4.854 = 1,4%. El MAPE es el promedio de los errores de los 12 meses. "
                "Un MAPE menor significa un pronóstico más preciso.", "Ejemplo con números")
    with tabs[1]:
        semilla = st.number_input("Número de simulación", min_value=0, max_value=999, value=42, step=1,
                                  help="Cada número genera una historia distinta con variaciones aleatorias.")
        comp, res = m.backtesting(s, int(semilla))
        gana = tarjetas(res)
        grafico(comp)
        lectura(f"En esta simulación, el modelo por drivers se equivocó en promedio {pct(res['mape_modelo'])} y el "
                f"método tradicional {pct(res['mape_tradicional'])}. "
                + ("En las barras se ve que el modelo se equivoca menos casi todos los meses, porque proyecta con el "
                   "recaudo y no con lo que pasó el año anterior." if gana
                   else "En este caso el método tradicional fue mejor; por eso se necesita la prueba repetida."))
    with tabs[2]:
        n = st.slider("Número de simulaciones", 20, 200, 50, step=10)
        if st.button("Ejecutar prueba repetida", type="primary", icon=":material/play_arrow:"):
            rep = m.backtesting_repetido(s, n)
            a, b, c = st.columns(3)
            tarjeta(a, "MAPE promedio del modelo", pct(rep["mape_modelo"].mean()), "ok", f"{n} simulaciones", "objetivo")
            tarjeta(b, "MAPE promedio tradicional", pct(rep["mape_tradicional"].mean()), "neutro", f"{n} simulaciones", "recibo")
            gana_pct = rep["gana_modelo"].mean() * 100
            tarjeta(c, "Gana el modelo", pct(gana_pct, 0), "ok" if gana_pct >= 70 else "alerta", "de las simulaciones", "tendencia")
            fig = go.Figure()
            fig.add_bar(x=["Modelo por drivers", "Método tradicional"],
                        y=[rep["mape_modelo"].mean(), rep["mape_tradicional"].mean()],
                        marker_color=[VERDE, NARANJA], width=0.45,
                        text=[pct(rep["mape_modelo"].mean()), pct(rep["mape_tradicional"].mean())], textposition="outside")
            estilo_grafico(fig, 320, f"Error promedio (MAPE) en {n} simulaciones")
            fig.update_yaxes(ticksuffix="%", range=[0, rep["mape_tradicional"].mean() * 1.3])
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, width="stretch")
            try:
                from scipy.stats import wilcoxon
                p = wilcoxon(rep["mape_modelo"], rep["mape_tradicional"], alternative="less").pvalue
                lectura(f"El modelo se equivocó menos en el {pct(gana_pct, 0)} de las {n} simulaciones. La prueba de Wilcoxon "
                        f"da p = {p:.4f}".replace(".", ",") + ". "
                        + ("Como p es menor que 0,05, se acepta la hipótesis H1: el modelo proyecta con menos error que el "
                           "método tradicional." if p < 0.05 else "No hay evidencia suficiente para aceptar H1."),
                        "Conclusión para la hipótesis H1")
            except ImportError:
                st.caption("Instale scipy para ver la prueba estadística de Wilcoxon.")
            st.download_button("Descargar resultados (CSV)", rep.to_csv(index=False).encode("utf-8"),
                               file_name="backtesting_repetido.csv", mime="text/csv", icon=":material/download:")
        st.caption("Datos sintéticos: los resultados ilustran el método de evaluación, no el desempeño de una empresa real.")
    if con_real:
        with tabs[3]:
            hist_r = st.session_state.hist_real
            st.markdown(f"Se calibra con **{hist_r['mes'].iloc[0]}** a **{hist_r['mes'].iloc[-13]}** y se pronostican "
                        f"**{hist_r['mes'].iloc[-12]}** a **{hist_r['mes'].iloc[-1]}**.")
            comp, res = datos.backtesting_real(hist_r, s, st.session_state.usuarios_real, st.session_state.toneladas_real)
            if pd.isna(res["mape_modelo"]):
                st.warning("Algún saldo de caja real es cero, por lo que el MAPE no se puede calcular.")
            else:
                tarjetas(res)
                grafico(comp)
            st.download_button("Descargar comparación (CSV)", comp.to_csv(index=False).encode("utf-8"),
                               file_name="backtesting_datos_cargados.csv", mime="text/csv", icon=":material/download:")
            lectura("Con datos reales hay una sola historia, así que el resultado es un caso y debe interpretarse junto "
                    "con la prueba repetida.")


def pagina_asistente():
    encabezado("El modelo financiero", "5. Asistente de inteligencia artificial",
               "La IA interpreta en palabras las cifras del modelo. Recibe solo indicadores agregados y nunca inventa cifras.",
               ["Primero revise las alertas automáticas, calculadas con reglas.", "Elija una pregunta sugerida o escriba la suya.",
                "En la última pestaña puede ver exactamente qué se le envía a la IA."])
    esc, s, proy, ind, periodo = barra_filtros()
    pres, ejec = presupuesto_y_ejecutado()
    if pres is None:
        tabla, mes_desv = pd.DataFrame(columns=["Rubro", "Desviación %", "Estado"]), "sin_presupuesto"
    else:
        mes_idx = len(ejec) - 1 if REALES else 2
        tabla, mes_desv = m.tabla_desviaciones(pres, ejec, mes_idx), pres.loc[mes_idx, "mes"]
    contexto = ia.construir_contexto(esc, s, proy, ind, tabla, mes_desv)

    t1, t2, t3 = st.tabs(["Alertas automáticas", "Pregunte al asistente", "Qué se envía a la IA"])
    with t1:
        for a in ia.alertas_por_reglas(contexto):
            if "ALERTA" in a:
                st.error(a, icon=":material/warning:")
            elif "Desviación" in a:
                st.warning(a, icon=":material/trending_down:")
            else:
                st.info(a, icon=":material/info:")
        st.caption("Estas alertas no usan IA: se calculan con reglas fijas y sirven como línea base para comparar.")
    with t2:
        sugeridas = ["¿Por qué baja la caja en los meses críticos?", "¿Necesitamos un crédito de tesorería este año?",
                     "Explique las desviaciones presupuestales", "¿Qué escenario debería preocupar a la gerencia?"]
        elegida = st.pills("Preguntas sugeridas", sugeridas, selection_mode="single")
        pregunta = st.text_area("Su pregunta", value=elegida or "", height=80,
                                placeholder="Por ejemplo: ¿qué pasa con la caja si el recaudo se demora un mes?")
        try:
            secretos = st.secrets
        except Exception:
            secretos = None
        api_key = ia.obtener_api_key(secretos)
        if not api_key:
            st.caption("Modo demostración: no hay clave de la API de Claude configurada. Vea la guía README para activarla.")
        if st.button("Consultar", type="primary", icon=":material/send:"):
            if not pregunta.strip():
                st.error("Escriba una pregunta primero.")
            elif not api_key:
                st.warning("Sin clave de API no se puede consultar a Claude. En la pestaña 'Qué se envía a la IA' "
                           "puede ver exactamente lo que se le enviaría.")
            else:
                with st.spinner("El asistente está analizando…"):
                    try:
                        texto, modelo_usado = ia.consultar_claude(contexto, pregunta, api_key)
                        st.session_state.historial_ia.insert(0, {"pregunta": pregunta, "respuesta": texto,
                                                                 "modelo": modelo_usado, "escenario": esc})
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
                               file_name="respuestas_asistente.csv", mime="text/csv", icon=":material/download:")
    with t3:
        lectura("La IA recibe solo este resumen agregado, nunca la base de datos completa. Así se protege la "
                "confidencialidad y se evita que invente cifras: todas salen del modelo financiero.", "Gobierno de datos")
        st.markdown("**Instrucciones que sigue la IA**")
        st.code(ia.INSTRUCCIONES_SISTEMA, language=None)
        st.markdown("**Resumen que recibe**")
        st.code(ia.construir_mensaje(contexto, "(pregunta)"), language="json")


NO_ESTA = "— No está en el archivo —"


def ayuda_plantilla():
    with st.expander("¿No tiene un archivo? Descargue un ejemplo"):
        st.write("Un Excel de ejemplo con 36 meses de datos ficticios, para ver cómo debe ser el archivo.")
        st.download_button("Descargar ejemplo de Excel", datos.plantilla_excel(), file_name="plantilla_finaseo.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           icon=":material/download:")


def revisar_columnas(df, clave, quitar=(), abierto=False):
    """Muestra cómo se reconocieron las columnas y permite corregirlas. Devuelve el mapeo final."""
    auto = datos.detectar_columnas(df)
    columnas = {str(c): c for c in df.columns}
    opciones = [NO_ESTA] + list(columnas)
    campos = {k: v for k, v in datos.NOMBRES_CAMPOS.items() if k not in quitar}
    faltan = not auto.get("mes") or not (auto.get("facturado") or auto.get("recaudo"))
    reconocidas = sum(1 for k in campos if auto.get(k) is not None)
    with st.expander(f"Revise cómo se leyó su archivo · {reconocidas} de {len(campos)} datos reconocidos",
                     expanded=abierto or faltan, icon=":material/fact_check:"):
        st.caption("El aplicativo reconoció las columnas por su nombre. Si alguna no corresponde, elija la correcta. "
                   "Lo que no esté en su archivo se toma como 0.")
        cols, mapeo = st.columns(3), {}
        for i, (campo, nombre) in enumerate(campos.items()):
            actual = auto.get(campo)
            idx = opciones.index(str(actual)) if actual is not None else 0
            sel = cols[i % 3].selectbox(nombre, opciones, index=idx, key=f"map_{clave}_{campo}")
            mapeo[campo] = None if sel == NO_ESTA else columnas[sel]
    return mapeo


def pagina_carga(embebido=False):
    if not embebido:
        encabezado("Datos y validación", "7. Datos de una empresa",
                   "Cargue el archivo de la empresa, en Excel o CSV, y el aplicativo le muestra de inmediato el informe con "
                   "gráficos. Después puede usar esos datos en todo el aplicativo.",
                   ["Cargue su archivo: el aplicativo reconoce solo las columnas por su nombre.",
                    "Revise que cada dato se haya leído de la columna correcta.",
                    "Lea el informe que aparece abajo.",
                    "Si quiere, use los datos en el presupuesto, el flujo de caja y los indicadores."])
    st.warning("**Confidencialidad:** use datos reales solo con autorización de la empresa, y preferiblemente en un "
               "computador de la empresa. Los datos no se guardan: se borran al recargar la página.", icon=":material/lock:")

    archivo = st.file_uploader("Cargue su archivo de Excel o CSV", type=["xlsx", "xls", "csv"],
                               help="Una fila por mes (o por día: el aplicativo suma por mes). Por ejemplo, columnas como "
                                    "Fecha, Ventas, Recaudo, Nómina, Combustible y Saldo bancos.")
    if archivo is None:
        if REALES:
            st.success(f"El aplicativo está usando los datos de **{st.session_state.archivo}**.",
                       icon=":material/check_circle:")
            informe.mostrar_informe(st.session_state.hist_real, st.session_state.supuestos.caja_minima,
                                    f"datos cargados de {st.session_state.archivo}")
            if st.button("Volver a los datos sintéticos", icon=":material/undo:"):
                st.session_state.update({"hist_real": None, "pres_real": None, "inicio": (2027, 1), "archivo": None,
                                         "supuestos": SUP_BOGOTA, "supuestos_base": SUP_BOGOTA, "historial_ia": []})
                for f in fields(m.Supuestos):
                    st.session_state.pop(f"in_{f.name}", None)
                st.rerun()
        ayuda_plantilla()
        if not REALES:
            with st.expander("Ver un informe de ejemplo (36 meses de datos sintéticos)"):
                informe.mostrar_informe(historico_ejemplo(), st.session_state.supuestos.caja_minima,
                                        "datos sintéticos de ejemplo")
        return

    try:
        hojas = datos.leer_hojas(archivo)
    except Exception as e:
        st.error(f"No se pudo abrir el archivo: {e}", icon=":material/error:")
        return
    hoja = datos.hoja_sugerida(hojas)
    if len(hojas) > 1:
        nombres = list(hojas)
        hoja = st.selectbox("¿Qué hoja tiene los datos mes a mes?", nombres, index=nombres.index(hoja))
    df = hojas[hoja]
    mapeo = revisar_columnas(df, f"{archivo.name}_{hoja}")
    saldo_ini = None
    if not mapeo.get("saldo_caja"):
        saldo_ini = st.number_input("Su archivo no trae el saldo de caja. ¿Con cuánto saldo empezó el primer mes? "
                                    "(millones de pesos)", value=0.0, step=100.0)

    hist, errores, avisos = datos.procesar(df, mapeo, saldo_ini, hoja)
    for e in errores:
        st.error(e, icon=":material/error:")
    if hist is None:
        ayuda_plantilla()
        return
    pres, av_p = datos.presupuesto_de(hojas, hist)
    avisos += av_p
    st.success(f"Listo: se leyeron **{len(hist)} meses**, de {hist['mes'].iloc[0]} a {hist['mes'].iloc[-1]}"
               + (f", y un presupuesto de {len(pres)} meses." if pres is not None else "."), icon=":material/check_circle:")
    if avisos:
        with st.expander(f"Ajustes que hizo el aplicativo al leer el archivo ({len(avisos)})", icon=":material/info:"):
            for a in avisos:
                st.markdown(f"- {a}")

    st.subheader("Informe de su archivo")
    informe.mostrar_informe(hist, st.session_state.supuestos.caja_minima, f"archivo {archivo.name}")

    with st.container(border=True):
        st.markdown("#### Usar estos datos en todo el aplicativo")
        st.write("Con un clic, el presupuesto, el flujo de caja, los indicadores, el backtesting y el asistente pasan a usar "
                 "sus datos. La proyección empieza el mes siguiente al último dato.")
        c1, c2 = st.columns(2)
        usuarios = c1.number_input("Usuarios facturados (SUI o área comercial)", min_value=1,
                                   value=int(st.session_state.usuarios_real), step=1000,
                                   help="Se usa para calcular la tarifa promedio por usuario.")
        toneladas = c2.number_input("Toneladas recolectadas al mes (informes de operación)", min_value=1.0,
                                    value=float(st.session_state.toneladas_real), step=500.0,
                                    help="Se usa para calcular el costo de disposición por tonelada.")
        s_cal, explicacion = datos.calibrar(hist, m.Supuestos(), usuarios, toneladas)
        with st.expander("Ver cómo se calcularon los supuestos con sus datos"):
            st.dataframe(explicacion, hide_index=True, width="stretch")
        anio_i, mes_i = datos.inicio_proyeccion(hist)
        if st.button("Usar estos datos en el aplicativo", type="primary", icon=":material/check:"):
            st.session_state.update({"hist_real": hist, "pres_real": pres, "inicio": (anio_i, mes_i), "archivo": archivo.name,
                                     "supuestos": s_cal, "supuestos_base": s_cal, "usuarios_real": usuarios,
                                     "toneladas_real": toneladas, "historial_ia": []})
            for f in fields(m.Supuestos):
                st.session_state.pop(f"in_{f.name}", None)
            st.rerun()
    ayuda_plantilla()


# ---------------------------------------------------------------------------
# NAVEGACIÓN: menú lateral agrupado por secciones
# ---------------------------------------------------------------------------
PAG_INICIO = st.Page(pagina_inicio, title="Inicio", icon=":material/home:", default=True)
PAG_SUPUESTOS = st.Page(pagina_supuestos, title="1. Supuestos", icon=":material/tune:", url_path="supuestos")
PAG_PRESUPUESTO = st.Page(pagina_presupuesto, title="2. Presupuesto", icon=":material/request_quote:", url_path="presupuesto")
PAG_FLUJO = st.Page(pagina_flujo, title="3. Flujo de caja", icon=":material/payments:", url_path="flujo-de-caja")
PAG_INDICADORES = st.Page(pagina_indicadores, title="4. Indicadores", icon=":material/monitoring:", url_path="indicadores")
PAG_ASISTENTE = st.Page(pagina_asistente, title="5. Asistente IA", icon=":material/smart_toy:", url_path="asistente")


def pagina_validacion():
    pagina_sector(simulacion=lambda: pagina_backtesting(embebido=True), pag_supuestos=PAG_SUPUESTOS)


PAG_VALIDACION = st.Page(pagina_validacion, title="6. Validación con datos reales", icon=":material/fact_check:",
                         url_path="validacion")

navegacion = st.navigation({
    "": [PAG_INICIO],
    "El modelo financiero": [PAG_SUPUESTOS, PAG_PRESUPUESTO, PAG_FLUJO, PAG_INDICADORES, PAG_ASISTENTE],
    "Validación": [PAG_VALIDACION],
})

st.logo("logo.svg", size="large")
with st.sidebar:
    st.divider()
    if REALES:
        st.caption(f"Datos cargados: {st.session_state.archivo}. Manéjelos con confidencialidad.")
    else:
        st.caption("Empresa tipo calibrada con la mediana de los operadores de Bogotá (EMIS). "
                   "Cifras en millones de pesos; ninguna corresponde a una empresa real."
                   if st.session_state.get("calibrado_emis") else
                   "Datos sintéticos. Cifras en millones de pesos; ninguna corresponde a una empresa real.")
    st.caption("Sandra Nope - Sara Cuta Díaz  \nMaestría en Finanzas · Universidad Libre")

navegacion.run()
