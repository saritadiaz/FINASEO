# FinAseo: aplicativo financiero con inteligencia artificial

Prototipo del trabajo escrito *"Modelo financiero con inteligencia artificial para el presupuesto y el flujo de caja de una empresa de aseo en Colombia"*.

Maestría en Finanzas, Universidad Libre de Colombia.
Autoras: Sandra Nope - Sara Cuta Díaz.

> Todas las cifras son **sintéticas** (inventadas pero realistas). No corresponden a ninguna empresa.

---

## Qué hay en esta carpeta

| Archivo | Qué es |
|---|---|
| `modelo.py` | **El modelo financiero** (el motor). Aquí se hacen todas las cuentas: proyección de caja, presupuesto, indicadores y backtesting. |
| `estilo.py` | **El diseño.** Colores, tarjetas con ícono y ayuda, y las cajas de "Lectura del resultado". |
| `informe.py` | **El informe automático.** Gráficos de barras que explican las cifras mes a mes, con descarga en Excel. |
| `logo.svg` | Logo del aplicativo. |
| `.streamlit/config.toml` | Colores generales y tipo de letra. |
| `datos.py` | **La carga de datos reales.** Lee y valida el Excel, calibra los drivers y hace el backtesting con datos cargados. |
| `asistente.py` | **El asistente de IA** (el intérprete). Arma el resumen agregado que recibe Claude y las instrucciones que sigue. |
| `app.py` | **El aplicativo** (el medio). Las pantallas que ve el usuario. |
| `requirements.txt` | La lista de programas que necesita Python. |

## Los seis módulos

1. **Supuestos y drivers:** usuarios, tarifa, recaudo, toneladas, costos, deuda, impuestos y caja mínima. Se pueden cambiar.
2. **Presupuesto:** presupuestado frente a ejecutado 2026, con las desviaciones marcadas.
3. **Flujo de caja:** proyección de 12 meses en tres escenarios y tabla de sensibilidad.
4. **Indicadores:** caja mínima, mes crítico, margen EBITDA, días de cartera y cobertura de caja.
5. **Backtesting (H1):** compara el error (MAPE) del modelo contra el método tradicional en hoja de cálculo, con prueba estadística de Wilcoxon.
6. **Asistente IA:** alertas automáticas y preguntas en lenguaje natural a Claude.
7. **Carga de datos (Excel):** reemplaza los datos sintéticos por datos reales de una empresa, resumidos por mes en una plantilla (por ejemplo, desde reportes de SAP).

## Usar datos reales (módulo 7)

1. En el módulo 7, descarguen la **plantilla de Excel**. Trae instrucciones, la fuente habitual de cada dato en SAP y 36 meses de ejemplo.
2. Reemplacen los datos de ejemplo por los de la empresa: una fila por mes, cifras en **millones de pesos** y con **criterio de caja** (lo cobrado y pagado, no lo causado). Mínimo 12 meses; con 24 o más se activa el backtesting con datos reales.
3. Carguen el archivo, ingresen usuarios y toneladas, revisen los supuestos calibrados y hagan clic en **Usar estos datos en el aplicativo**.

**Confidencialidad:** usen datos reales solo con autorización escrita de la empresa, y ejecuten el aplicativo en un computador de la empresa (opción B), no en la versión publicada. Nunca suban datos reales a GitHub: el repositorio es público. Los datos cargados no se guardan; se borran al recargar la página.

---

## Opción A: usarlo en internet, sin instalar nada (recomendada)

1. Creen una cuenta gratuita en **GitHub** (github.com).
2. Creen un repositorio nuevo, por ejemplo `finaseo`, y suban los cuatro archivos de esta carpeta (botón *Add file → Upload files*).
3. Entren a **Streamlit Community Cloud** (share.streamlit.io) con la misma cuenta de GitHub.
4. Pulsen *Create app*, elijan el repositorio `finaseo` y el archivo `app.py`, y pulsen *Deploy*.
5. En pocos minutos tendrán un enlace para abrir el aplicativo desde cualquier navegador.

Así también cumplen lo que dice la propuesta: el código queda versionado en GitHub.

## Opción B: usarlo en su computador

1. Instalen **Python** desde python.org (versión 3.10 o superior). En Windows, marquen la casilla *Add Python to PATH* al instalar.
2. Abran la carpeta del aplicativo, hagan clic en la barra de direcciones, escriban `cmd` y pulsen Enter. Se abre una ventana negra.
3. Escriban esto y pulsen Enter (solo la primera vez):
   ```
   pip install -r requirements.txt
   ```
4. Para abrir el aplicativo, escriban:
   ```
   streamlit run app.py
   ```
5. Se abre en el navegador. Para cerrarlo, cierren la ventana negra.

---

## Activar el asistente de IA (Claude)

Sin configurar nada, el asistente funciona en **modo demostración**: muestra las alertas automáticas y exactamente lo que se le enviaría a la IA, pero no responde preguntas.

Para activarlo necesitan una clave de la API de Anthropic, que se obtiene en console.anthropic.com. El uso tiene costo según el consumo; para un prototipo es bajo, pero revisen las tarifas vigentes antes de empezar.

- **En Streamlit Community Cloud:** en la configuración de la app, sección *Secrets*, escriban:
  ```
  ANTHROPIC_API_KEY = "su-clave-aquí"
  ```
- **En su computador:** creen una carpeta `.streamlit` dentro de la carpeta del aplicativo y, dentro, un archivo `secrets.toml` con la misma línea.

**Nunca suban la clave a GitHub ni la escriban dentro del código.**

---

## Gobierno de datos

- El asistente **nunca recibe la base de datos completa**: solo un resumen de indicadores agregados (saldo por mes, indicadores y desviaciones).
- La IA **no calcula cifras**: todas salen de `modelo.py`. Se le ordena no inventar datos.
- Se usa temperatura 0 para que las respuestas sean lo más estables posible, y se registra la versión exacta del modelo en cada respuesta, para la evaluación.
- En el módulo 6, la sección *"Ver lo que se envía a la IA"* muestra el mensaje completo, para que cualquier evaluador lo revise.

## Cómo usarlo para la evaluación del trabajo

- **Hipótesis H1 (precisión):** módulo 5, botón *Ejecutar prueba repetida*. Descarguen el CSV con los resultados para el capítulo de resultados.
- **Hipótesis H3 (calidad de la IA):** módulo 6. Hagan las preguntas de la evaluación, descarguen el CSV de respuestas y entréguenselas a los expertos junto con las respuestas de los analistas humanos, sin indicar cuál es cuál.

## Nota sobre el desarrollo

Este prototipo se construyó con asistencia de inteligencia artificial. Para la tesis, documenten ese proceso en la metodología y asegúrense de entender qué hace cada parte del código, porque los jurados pueden preguntar.
