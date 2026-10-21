"""
Asistente financiero con inteligencia artificial generativa (Claude).

Gobierno de datos: el asistente NUNCA recibe la base de datos completa.
Solo recibe un resumen de indicadores agregados calculados por el modelo
financiero (modelo.py). Así se protege la información confidencial de la
empresa y se evita que la IA invente cifras: todas salen del modelo.
"""

import json
import os

MODELO_CLAUDE = "claude-sonnet-5-5"   # registrar la versión exacta usada en la tesis

INSTRUCCIONES_SISTEMA = """Eres un analista financiero senior de una empresa prestadora del servicio \
de aseo en Colombia. Recibes un resumen de indicadores calculados por un modelo financiero \
(cifras en millones de pesos colombianos). Responde en español, de forma clara y breve, para la \
gerencia.

Reglas:
1. Usa SOLO las cifras del resumen. Nunca inventes datos. Si algo no está en el resumen, dilo.
2. Cita las cifras que sustentan cada afirmación.
3. Cuando detectes riesgos de liquidez, genera una alerta y una recomendación concreta \
(por ejemplo, activar crédito de tesorería, aplazar pagos, gestionar el recaudo).
4. Ten en cuenta el contexto del sector: ingresos regulados, recaudo con rezago a través de \
terceros y costos operativos de pago inmediato.
5. Máximo 200 palabras."""


def construir_contexto(escenario, supuestos, proyeccion, indicadores, desviaciones, mes_desviaciones):
    """Arma el resumen AGREGADO que se envía a la IA."""
    return {
        "escenario": escenario,
        "caja_minima_operativa": supuestos.caja_minima,
        "indicadores_proyeccion_12_meses": {k: (round(v, 1) if isinstance(v, float) else v)
                                            for k, v in indicadores.items()},
        "saldo_caja_por_mes": {r["mes"]: round(r["saldo_caja"]) for _, r in proyeccion.iterrows()},
        "flujo_neto_por_mes": {r["mes"]: round(r["flujo_neto"]) for _, r in proyeccion.iterrows()},
        "pagos_grandes": {r["mes"]: round(r["poliza"] + r["impuestos"]) for _, r in proyeccion.iterrows()
                          if r["poliza"] + r["impuestos"] > 0},
        f"desviaciones_presupuestales_{mes_desviaciones}": [
            {"rubro": d["Rubro"], "desviacion_pct": round(d["Desviación %"], 1), "estado": d["Estado"]}
            for _, d in desviaciones.iterrows()
        ],
    }


def construir_mensaje(contexto, pregunta):
    return ("Resumen de indicadores del modelo financiero:\n"
            + json.dumps(contexto, ensure_ascii=False, indent=2)
            + f"\n\nPregunta de la gerencia: {pregunta}")


def obtener_api_key(secretos=None):
    if secretos is not None:
        try:
            if "ANTHROPIC_API_KEY" in secretos:
                return secretos["ANTHROPIC_API_KEY"]
        except Exception:
            pass
    return os.environ.get("ANTHROPIC_API_KEY")


def consultar_claude(contexto, pregunta, api_key):
    """Envía el resumen agregado y la pregunta a Claude. Devuelve (respuesta, modelo_usado)."""
    import anthropic
    cliente = anthropic.Anthropic(api_key=api_key)
    respuesta = cliente.messages.create(
        model=MODELO_CLAUDE,
        max_tokens=600,
        temperature=0,   # respuestas lo más estables posible, para la evaluación
        system=INSTRUCCIONES_SISTEMA,
        messages=[{"role": "user", "content": construir_mensaje(contexto, pregunta)}],
    )
    texto = "".join(b.text for b in respuesta.content if getattr(b, "type", "") == "text")
    return texto, respuesta.model


def _m(v):
    return f"${v:,.0f} M".replace(",", ".")


def alertas_por_reglas(contexto):
    """Modo demostración sin IA: alertas calculadas con reglas fijas.
    También sirve como línea base para comparar con las respuestas de la IA."""
    ind = contexto["indicadores_proyeccion_12_meses"]
    minimo = contexto["caja_minima_operativa"]
    alertas = []
    if ind["caja_minima_proyectada"] < 0:
        alertas.append(f"ALERTA CRÍTICA: la caja proyectada llega a {_m(ind['caja_minima_proyectada'])} "
                       f"en {ind['mes_critico']}. Se requiere financiación antes de esa fecha.")
    elif ind["caja_minima_proyectada"] < minimo:
        alertas.append(f"ALERTA: la caja baja a {_m(ind['caja_minima_proyectada'])} en {ind['mes_critico']}, "
                       f"por debajo del mínimo operativo de {_m(minimo)}.")
    else:
        alertas.append(f"La caja se mantiene sobre el mínimo operativo. El punto más bajo es "
                       f"{_m(ind['caja_minima_proyectada'])} en {ind['mes_critico']}.")
    if ind["meses_bajo_minimo"] > 0:
        alertas.append(f"Hay {ind['meses_bajo_minimo']} meses con caja por debajo del mínimo.")
    if contexto["pagos_grandes"]:
        meses = ", ".join(f"{m} ({_m(v)})" for m, v in contexto["pagos_grandes"].items())
        alertas.append(f"Pagos grandes previstos: {meses}.")
    for d in next(v for k, v in contexto.items() if k.startswith("desviaciones")):
        if d["estado"] == "Desfavorable":
            alertas.append(f"Desviación desfavorable en {d['rubro']}: {d['desviacion_pct']:+.1f}%.")
    return alertas
