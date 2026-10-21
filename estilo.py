"""
Estilo visual y componentes didácticos de FinAseo.

Aquí están los colores, las tarjetas de indicadores con ícono y ayuda, los encabezados
de cada pantalla y las cajas de "Lectura del resultado". Separarlo del aplicativo hace
que app.py se concentre en la lógica de cada módulo.
"""

import streamlit as st

# Paleta verde claro con letra negra
VERDE_OSCURO, VERDE, PETROLEO, NARANJA, GRIS = "#111111", "#16A34A", "#0F766E", "#EA8C2F", "#9CA3AF"
VERDE_CLARO = "#86EFAC"
NEGRO = "#111111"
ROJO = "#B42318"
FUENTE = "Inter, sans-serif"

# Íconos sencillos en SVG (líneas), para no depender de fuentes externas
_ICONOS = {
    "caja": '<rect x="3" y="6" width="18" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M6 9v.01M18 15v.01"/>',
    "calendario": '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4M16 3v4M4 10h16"/>',
    "alerta": '<path d="M12 4 2.8 19h18.4z"/><path d="M12 10v4M12 17v.01"/>',
    "porcentaje": '<path d="M5 19 19 5"/><circle cx="7" cy="7" r="2"/><circle cx="17" cy="17" r="2"/>',
    "tendencia": '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "reloj": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "recibo": '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/>',
    "escudo": '<path d="M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6z"/>',
    "camion": '<path d="M3 7h11v9H3zM14 10h4l3 3v3h-7"/><circle cx="7" cy="17.5" r="1.8"/><circle cx="17" cy="17.5" r="1.8"/>',
    "objetivo": '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1"/>',
    "bombilla": '<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0 0 12 3z"/>',
}


def icono(nombre, color="#15803D", tam=22):
    return (f'<svg width="{tam}" height="{tam}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'{_ICONOS[nombre]}</svg>')


CSS = """
<style>
.block-container {padding-top: 3.6rem;}
.migas {font-size: .74rem; letter-spacing: .12em; text-transform: uppercase; color: #EA8C2F;
        font-weight: 700; margin: 0 0 .15rem 0;}
.proposito {font-size: .98rem; color: #333333; margin: -.4rem 0 .6rem 0;}
.portada {background: #FFFFFF; color: #111111; border: 1px solid #CFE5D4; border-radius: 14px; padding: 0;
          border-bottom: 5px solid #EA8C2F; margin-bottom: 1.2rem; overflow: hidden;}
.portada .cubierta {background: #A7E9B9; padding: 1.4rem 2rem 1.3rem 2rem; border-bottom: 1px solid #86D99C;}
.portada .etiqueta {display: inline-block; background: #FFFFFF; color: #111111; font-size: .72rem; font-weight: 700;
                    letter-spacing: .1em; text-transform: uppercase; padding: .28rem .75rem; border-radius: 999px;
                    border: 1px solid #6CCB86; margin: 0 0 .9rem 0;}
.portada .inst {font-size: .78rem; letter-spacing: .14em; text-transform: uppercase; color: #111111;
                font-weight: 700; margin: 0;}
.portada .fac {font-size: .88rem; color: #1F2937; margin: .2rem 0 .8rem 0;}
.portada h1 {font-family: 'Playfair Display', serif; color: #111111; font-size: 1.6rem;
             line-height: 1.3; margin: 0; padding: 0;}
.portada .autoras {display: flex; gap: 2.2rem; flex-wrap: wrap; padding: .9rem 2rem 1rem 2rem; background: #F3FAF4;}
.portada .autoras div {font-size: .98rem; color: #111111; font-weight: 600;}
.portada .autoras span {display: block; font-size: .7rem; color: #4B5563; font-weight: 400;
                        letter-spacing: .08em; text-transform: uppercase;}
.kpi {background: #FFFFFF; border: 1px solid #CFE5D4; border-radius: 12px; padding: .95rem 1.05rem;
      min-height: 138px; margin-bottom: .9rem; position: relative;}
.kpi .top {display: flex; align-items: center; gap: .6rem; margin-bottom: .45rem;}
.kpi .burbuja {width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center;
               justify-content: center; background: #EAF5EC; flex: none;}
.kpi.alerta .burbuja {background: #FDEBD3;} .kpi.riesgo .burbuja {background: #FEE4E2;}
.kpi .lbl {font-size: .76rem; color: #333333; text-transform: uppercase; letter-spacing: .05em;
           font-weight: 600; margin: 0; line-height: 1.25; padding-right: 22px;}
.kpi .ayuda {position: absolute; top: .7rem; right: .8rem; width: 19px; height: 19px; border-radius: 50%;
             border: 1px solid #A9C2B1; color: #4B5563; font-size: .72rem; font-weight: 700;
             display: flex; align-items: center; justify-content: center; cursor: help;}
.kpi .val {font-size: 1.6rem; font-weight: 700; color: #111111; margin: .1rem 0 .35rem 0;
           font-variant-numeric: tabular-nums; white-space: nowrap;}
.kpi .est {display: inline-block; font-size: .7rem; font-weight: 600; padding: .1rem .5rem;
           border-radius: 999px; margin-right: .35rem;}
.kpi.ok .est {background: #DCFCE7; color: #14532D;}
.kpi.alerta .est {background: #FDEBD3; color: #7A3E0B;}
.kpi.riesgo .est {background: #FEE4E2; color: #7A1A12;}
.kpi.neutro .est {background: #EAF5EC; color: #0F5E6E;}
.kpi .nota {font-size: .76rem; color: #4B5563;}
.kpi.ok {border-bottom: 4px solid #16A34A;} .kpi.alerta {border-bottom: 4px solid #EA8C2F;}
.kpi.riesgo {border-bottom: 4px solid #B42318;} .kpi.neutro {border-bottom: 4px solid #8A9A8F;}
.lectura {background: #FFFFFF; border: 1px solid #CFE5D4; border-left: 5px solid #EA8C2F; border-radius: 0;
          padding: .85rem 1.1rem; margin: .6rem 0 1rem 0; display: flex; gap: .8rem; align-items: flex-start;}
.lectura .tit {font-weight: 700; color: #111111; font-size: .85rem; text-transform: uppercase;
               letter-spacing: .05em; margin: 0 0 .25rem 0;}
.lectura p {margin: 0; color: #222222; font-size: .94rem; line-height: 1.55;}
.paso {background: #FFFFFF; border: 1px solid #CFE5D4; border-radius: 12px; padding: 1rem 1.1rem; min-height: 150px;}
.paso .num {width: 30px; height: 30px; border-radius: 50%; background: #16A34A; color: #FFFFFF; font-weight: 700;
            display: flex; align-items: center; justify-content: center; margin-bottom: .5rem;}
.paso h4 {margin: 0 0 .3rem 0; color: #111111; font-size: 1.02rem;}
.paso p {margin: 0; color: #333333; font-size: .88rem;}
.capa {background: #FFFFFF; border: 1px solid #CFE5D4; border-top: 4px solid #EA8C2F; border-radius: 10px;
       padding: .95rem 1.05rem; min-height: 150px;}
.capa h4 {font-family: 'Playfair Display', serif; color: #111111; margin: 0 0 .3rem 0; font-size: 1.08rem;}
.capa .rol {font-size: .7rem; text-transform: uppercase; letter-spacing: .1em; color: #EA8C2F; font-weight: 700; margin: 0;}
.capa p {font-size: .87rem; color: #222222; margin: .3rem 0 0 0;}
.chip {display: inline-block; font-size: .78rem; font-weight: 600; padding: .25rem .7rem; border-radius: 999px;
       background: #EAF5EC; color: #111111; margin: .15rem .3rem .15rem 0;}
.chip.real {background: #FDEBD3; color: #7A3E0B;}
.leyenda {font-size: .78rem; color: #333333; margin: -.3rem 0 .8rem 0;}
.leyenda b {display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin: 0 .3rem 0 .9rem;}
</style>
"""

ESTADOS = {"ok": "Saludable", "alerta": "Vigilar", "riesgo": "En riesgo", "neutro": "Referencia"}


def aplicar_estilos():
    st.markdown(CSS, unsafe_allow_html=True)


def pesos(v):
    signo = "-" if v < 0 else ""
    return f"{signo}${abs(v):,.0f} M".replace(",", ".")


def pct(v, dec=1):
    return f"{v:.{dec}f}%".replace(".", ",")


def encabezado(seccion, titulo, proposito, como_leer=None):
    """Encabezado didáctico: sección, título, para qué sirve y cómo leer la pantalla."""
    st.markdown(f'<p class="migas">{seccion}</p>', unsafe_allow_html=True)
    c1, c2 = st.columns([5, 1.3], vertical_alignment="bottom")
    c1.title(titulo)
    if como_leer:
        with c2.popover("¿Cómo se lee?", icon=":material/help:", use_container_width=True):
            for i, paso in enumerate(como_leer, start=1):
                st.markdown(f"**{i}.** {paso}")
    st.markdown(f'<p class="proposito">{proposito}</p>', unsafe_allow_html=True)


def tarjeta(columna, etiqueta, valor, estado="neutro", nota="", icono_nombre="caja", ayuda=""):
    """Tarjeta de indicador con ícono, semáforo y ayuda (pase el cursor sobre el signo ?)."""
    color = {"ok": "#15803D", "alerta": "#EA8C2F", "riesgo": "#B42318"}.get(estado, "#0F5E6E")
    ayuda_html = f'<div class="ayuda" title="{ayuda}">?</div>' if ayuda else ""
    columna.markdown(
        f'<div class="kpi {estado}">{ayuda_html}<div class="top"><div class="burbuja">{icono(icono_nombre, color)}</div>'
        f'<p class="lbl">{etiqueta}</p></div><div class="val">{valor}</div>'
        f'<span class="est">{ESTADOS[estado]}</span><span class="nota">{nota}</span></div>',
        unsafe_allow_html=True,
    )


def lectura(texto, titulo="Lectura del resultado"):
    """Caja que explica en palabras lo que muestran las cifras (calculada con reglas, sin IA)."""
    st.markdown(f'<div class="lectura">{icono("bombilla", "#EA8C2F", 26)}<div><p class="tit">{titulo}</p>'
                f'<p>{texto}</p></div></div>', unsafe_allow_html=True)


def leyenda_estados():
    st.markdown('<div class="leyenda">Semáforo:<b style="background:#15803D"></b>Saludable'
                '<b style="background:#EA8C2F"></b>Vigilar<b style="background:#B42318"></b>En riesgo'
                '<b style="background:#8A9A8F"></b>Referencia · Pase el cursor sobre <b style="background:none;'
                'width:auto;margin:0 .2rem">?</b> para ver la fórmula de cada indicador.</div>',
                unsafe_allow_html=True)


def estilo_grafico(fig, alto=400, titulo=None):
    fig.update_layout(
        template="plotly_white", height=alto,
        title=dict(text=titulo, y=0.98, yanchor="top") if titulo else None,
        font=dict(family=FUENTE, color=VERDE_OSCURO, size=13),
        title_font=dict(family="'Playfair Display', serif", size=17, color=VERDE_OSCURO),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#FFFFFF",
        margin=dict(t=90 if titulo else 30, b=30, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
        hoverlabel=dict(font_family=FUENTE), separators=",.",
    )
    fig.update_xaxes(showgrid=False, linecolor="#CFE5D4")
    fig.update_yaxes(gridcolor="#EAF5EC", zerolinecolor="#CFE5D4", separatethousands=True, tickformat=",.0f")
    return fig


def dona(valores, titulo=None, alto=360, max_partes=5):
    """Gráfica de dona para la composición de un total (por ejemplo, los egresos).
    Muestra las partes más grandes y agrupa el resto en 'Otros'."""
    import plotly.graph_objects as go
    serie = valores[valores > 0].sort_values(ascending=False)
    if len(serie) > max_partes + 1:
        principales = serie.head(max_partes)
        import pandas as pd
        serie = pd.concat([principales, pd.Series({"Otros": serie.iloc[max_partes:].sum()})])
    colores = ["#16A34A", "#EA8C2F", "#0F766E", "#86EFAC", "#4B5563", "#D1D5DB"]
    total = serie.sum()
    fig = go.Figure(go.Pie(
        labels=list(serie.index), values=list(serie.values), hole=0.62, sort=False, direction="clockwise",
        marker=dict(colors=colores[:len(serie)], line=dict(color="#FFFFFF", width=2)),
        texttemplate="%{percent:.0%}", textposition="outside", textfont=dict(color=NEGRO, size=13),
        hovertemplate="%{label}<br>%{value:,.0f} millones<br>%{percent:.1%}<extra></extra>",
    ))
    fig.update_layout(
        height=alto, title=dict(text=titulo, y=0.98, yanchor="top") if titulo else None,
        font=dict(family=FUENTE, color=NEGRO, size=13),
        title_font=dict(family="'Playfair Display', serif", size=17, color=NEGRO),
        paper_bgcolor="rgba(0,0,0,0)", separators=",.",
        margin=dict(t=70 if titulo else 30, b=30, l=50, r=50),
        legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.08, yanchor="top", font=dict(size=12)),
        annotations=[dict(text=f"<b>{pesos(total)}</b><br><span style='font-size:12px'>total egresos</span>",
                          x=0.5, y=0.5, showarrow=False, font=dict(size=16, color=NEGRO))],
    )
    return fig
