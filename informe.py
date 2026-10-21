"""
Informe automático de los datos (reales o sintéticos).

Genera gráficos de barras que explican las cifras mes a mes y, debajo de cada uno,
una lectura en palabras calculada con reglas (sin IA). También permite descargar el
informe en Excel.
"""

import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import datos
from estilo import GRIS, NARANJA, NEGRO, PETROLEO, ROJO, VERDE, VERDE_CLARO, dona, estilo_grafico, lectura, pct, pesos, tarjeta

NOMBRES_RUBROS = {
    "disposicion_final": "Disposición final", "nomina": "Nómina", "combustible": "Combustible",
    "mantenimiento": "Mantenimiento", "administrativos": "Administrativos", "otros": "Otros pagos",
    "poliza": "Pólizas", "servicio_deuda": "Deuda", "inversion_flota": "Reposición de flota", "impuestos": "Impuestos",
}


def _barras_texto(valores):
    return [pesos(v) for v in valores]


def calcular_resumen(hist: pd.DataFrame, caja_minima: float) -> dict:
    tasa = hist["recaudo"].sum() / hist["facturado"].sum() * 100
    brecha = hist["facturado"] - hist["recaudo"]
    rubros = hist[list(NOMBRES_RUBROS)].sum().sort_values(ascending=False)
    negativos = hist[hist["flujo_neto"] < 0]
    pagos_grandes = hist[(hist["poliza"] + hist["impuestos"]) > 0]["mes"].tolist()
    return {
        "meses": len(hist), "desde": hist["mes"].iloc[0], "hasta": hist["mes"].iloc[-1],
        "tasa": tasa, "mes_brecha": hist.loc[brecha.idxmax(), "mes"], "brecha_max": brecha.max(),
        "rubros": rubros, "negativos": negativos, "pagos_grandes": pagos_grandes,
        "flujo_total": hist["flujo_neto"].sum(),
        "saldo_min": hist["saldo_caja"].min(), "mes_saldo_min": hist.loc[hist["saldo_caja"].idxmin(), "mes"],
        "bajo_minimo": hist[hist["saldo_caja"] < caja_minima]["mes"].tolist(),
    }


def mostrar_informe(hist: pd.DataFrame, caja_minima: float, origen: str):
    """Muestra el informe completo en la pantalla."""
    r = calcular_resumen(hist, caja_minima)
    st.markdown(f"**Informe de {r['meses']} meses, de {r['desde']} a {r['hasta']}** · {origen}")

    c1, c2, c3, c4 = st.columns(4)
    tarjeta(c1, "Recaudo sobre facturado", pct(r["tasa"]), "ok" if r["tasa"] >= 90 else "alerta",
            "promedio del periodo", "recibo", "Recaudo total ÷ facturación total del periodo.")
    tarjeta(c2, "Flujo neto acumulado", pesos(r["flujo_total"]), "ok" if r["flujo_total"] >= 0 else "riesgo",
            "recaudo − egresos", "tendencia", "Suma del flujo neto de todos los meses.")
    tarjeta(c3, "Meses con flujo negativo", str(len(r["negativos"])), "ok" if len(r["negativos"]) <= r["meses"] / 4 else "alerta",
            f"de {r['meses']} meses", "alerta", "Meses en que salió más dinero del que entró.")
    tarjeta(c4, "Saldo de caja más bajo", pesos(r["saldo_min"]), "ok" if r["saldo_min"] >= caja_minima else "riesgo",
            r["mes_saldo_min"], "caja", "Menor saldo de caja al cierre de mes en el periodo.")

    # 1. Facturado frente a recaudo
    st.markdown("##### 1. ¿Cuánto se facturó y cuánto se recaudó?")
    fig = go.Figure()
    fig.add_bar(x=hist["mes"], y=hist["facturado"], name="Facturado", marker_color=VERDE_CLARO)
    fig.add_bar(x=hist["mes"], y=hist["recaudo"], name="Recaudado", marker_color=VERDE)
    estilo_grafico(fig, 360)
    fig.update_layout(barmode="group", bargap=0.2, yaxis_title="Millones de pesos")
    st.plotly_chart(fig, width="stretch")
    lectura(f"En promedio se recaudó el {pct(r['tasa'])} de lo facturado: de cada $100 facturados entraron "
            f"${r['tasa']:.0f} a la caja. La mayor diferencia entre lo facturado y lo recaudado fue en "
            f"{r['mes_brecha']} ({pesos(r['brecha_max'])}). Como el recaudo llega con rezago, una diferencia alta en un "
            "mes suele reflejar demoras en el giro del recaudo.")

    # 2. Egresos por rubro
    st.markdown("##### 2. ¿En qué se fue el dinero?")
    rub = r["rubros"][r["rubros"] > 0]
    total = rub.sum()
    nombres = [NOMBRES_RUBROS[k] for k in rub.index]
    fig = go.Figure(go.Bar(x=rub.values, y=nombres, orientation="h",
                           marker_color=[NARANJA if i == 0 else VERDE for i in range(len(rub))],
                           text=[f"{pesos(v)} · {pct(v / total * 100)}" for v in rub.values],
                           textposition="outside", cliponaxis=False))
    estilo_grafico(fig, max(320, 60 + 38 * len(rub)))
    fig.update_layout(yaxis=dict(autorange="reversed"), showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
    fig.update_xaxes(showticklabels=False, range=[0, rub.max() * 1.45])
    g1, g2 = st.columns([1.25, 1])
    g1.plotly_chart(fig, width="stretch")
    composicion = pd.Series(rub.values, index=nombres)
    g2.plotly_chart(dona(composicion, alto=max(320, 60 + 38 * len(rub))), width="stretch")
    top3 = rub.head(3)
    lectura(f"Los tres rubros más grandes ({', '.join(NOMBRES_RUBROS[k].lower() for k in top3.index)}) suman el "
            f"{pct(top3.sum() / total * 100)} de los egresos. El primero, {NOMBRES_RUBROS[rub.index[0]].lower()}, "
            f"representa el {pct(rub.iloc[0] / total * 100)}: es donde una mejora de eficiencia tendría más efecto.")

    # 3. Flujo neto mensual
    st.markdown("##### 3. ¿En qué meses entró más dinero del que salió?")
    colores = [VERDE if v >= 0 else NARANJA for v in hist["flujo_neto"]]
    fig = go.Figure(go.Bar(x=hist["mes"], y=hist["flujo_neto"], marker_color=colores, name="Flujo neto"))
    estilo_grafico(fig, 340)
    fig.update_layout(showlegend=False, yaxis_title="Millones de pesos")
    st.plotly_chart(fig, width="stretch")
    neg = r["negativos"]
    if neg.empty:
        lectura("Todos los meses tuvieron flujo neto positivo: siempre entró más dinero del que salió.")
    else:
        coinciden = [m for m in neg["mes"] if m in r["pagos_grandes"]]
        texto = (f"Hubo {len(neg)} meses con flujo negativo (barras naranja). El peor fue {neg.loc[neg['flujo_neto'].idxmin(), 'mes']} "
                 f"({pesos(neg['flujo_neto'].min())}). ")
        if coinciden:
            texto += (f"{len(coinciden)} de ellos coinciden con pagos de pólizas o impuesto de renta, lo que muestra que "
                      "estos pagos concentrados son los que más presionan la caja y deben planearse con anticipación.")
        else:
            texto += "No coinciden con pagos de pólizas o impuestos: conviene revisar el recaudo de esos meses."
        lectura(texto)

    # 4. Saldo de caja
    st.markdown("##### 4. ¿Cómo evolucionó el saldo de caja?")
    colores = [ROJO if v < caja_minima else PETROLEO for v in hist["saldo_caja"]]
    fig = go.Figure(go.Bar(x=hist["mes"], y=hist["saldo_caja"], marker_color=colores, name="Saldo de caja"))
    fig.add_hline(y=caja_minima, line_dash="dash", line_color=ROJO, line_width=1.5,
                  annotation_text=f"Caja mínima {pesos(caja_minima)}", annotation_position="top left",
                  annotation_font_color=ROJO)
    estilo_grafico(fig, 340)
    fig.update_layout(showlegend=False, yaxis_title="Millones de pesos")
    st.plotly_chart(fig, width="stretch")
    if r["bajo_minimo"]:
        lectura(f"La caja estuvo por debajo del mínimo operativo en {len(r['bajo_minimo'])} meses (barras rojas), "
                f"empezando en {r['bajo_minimo'][0]}. El punto más bajo fue {pesos(r['saldo_min'])} en {r['mes_saldo_min']}. "
                "En esos meses la empresa necesitó, o habría necesitado, financiación de corto plazo.")
    else:
        lectura(f"La caja se mantuvo siempre por encima del mínimo operativo. El momento más ajustado fue "
                f"{r['mes_saldo_min']}, con {pesos(r['saldo_min'])}.")

    # 5. Comparación anual
    anual = None
    if hist["fecha"].dt.year.nunique() >= 2:
        st.markdown("##### 5. ¿Cómo cambió de un año a otro?")
        anual = hist.groupby(hist["fecha"].dt.year)[["facturado", "recaudo", "egresos"]].sum()
        meses_por_anio = hist.groupby(hist["fecha"].dt.year).size()
        fig = go.Figure()
        for col, nombre, color in [("facturado", "Facturado", VERDE_CLARO), ("recaudo", "Recaudado", VERDE), ("egresos", "Egresos", NARANJA)]:
            fig.add_bar(x=[f"{a} ({meses_por_anio[a]} meses)" for a in anual.index], y=anual[col], name=nombre,
                        marker_color=color, text=_barras_texto(anual[col]), textposition="outside", cliponaxis=False)
        estilo_grafico(fig, 380)
        fig.update_layout(barmode="group", yaxis_title="Millones de pesos", bargap=0.25)
        fig.update_yaxes(range=[0, anual.values.max() * 1.15])
        st.plotly_chart(fig, width="stretch")
        completos = [a for a in anual.index if meses_por_anio[a] == 12]
        if len(completos) >= 2:
            a0, a1 = completos[-2], completos[-1]
            cf = (anual.loc[a1, "facturado"] / anual.loc[a0, "facturado"] - 1) * 100
            ce = (anual.loc[a1, "egresos"] / anual.loc[a0, "egresos"] - 1) * 100
            lectura(f"Entre {a0} y {a1} la facturación creció {pct(cf)} y los egresos {pct(ce)}. "
                    + ("Los egresos crecieron más rápido que la facturación: el margen se está estrechando."
                       if ce > cf else "La facturación creció más rápido que los egresos: el margen mejora."))
        else:
            lectura("Hay años incompletos; compare los totales con cuidado, porque no tienen el mismo número de meses.")

    st.download_button("Descargar este informe en Excel", informe_excel(hist, r, anual),
                       file_name="informe_finaseo.xlsx", icon=":material/download:",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def informe_excel(hist: pd.DataFrame, r: dict, anual) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame([
            ["Periodo", f"{r['desde']} a {r['hasta']} ({r['meses']} meses)"],
            ["Recaudo sobre facturado", pct(r["tasa"])],
            ["Mes con mayor brecha facturado - recaudo", f"{r['mes_brecha']} ({pesos(r['brecha_max'])})"],
            ["Flujo neto acumulado", pesos(r["flujo_total"])],
            ["Meses con flujo negativo", len(r["negativos"])],
            ["Saldo de caja más bajo", f"{pesos(r['saldo_min'])} en {r['mes_saldo_min']}"],
            ["Meses bajo la caja mínima", ", ".join(r["bajo_minimo"]) or "Ninguno"],
        ], columns=["Indicador", "Valor"]).to_excel(xw, sheet_name="Resumen", index=False)
        cols = ["mes", "facturado", "recaudo"] + datos.EGRESOS + ["egresos", "flujo_neto", "saldo_caja"]
        hist[cols].round(1).to_excel(xw, sheet_name="Mensual", index=False)
        rub = r["rubros"]
        pd.DataFrame({"Rubro": [NOMBRES_RUBROS[k] for k in rub.index], "Total (M$)": rub.round(1).values,
                      "Participación %": (rub / rub.sum() * 100).round(1).values}).to_excel(xw, sheet_name="Por rubro", index=False)
        if anual is not None:
            anual.round(1).rename_axis("Año").to_excel(xw, sheet_name="Anual")
        for hoja in xw.sheets.values():
            for col in hoja.columns:
                hoja.column_dimensions[col[0].column_letter].width = 22
    return buf.getvalue()
