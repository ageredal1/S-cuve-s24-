"""
app.py — Interfaz Streamlit para visualización de Curva S
Proyecto: Control de Avance de Obras con EVM
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib
matplotlib.use("Agg")   # backend no interactivo para Streamlit

import logic  # módulo de cálculos y gráficos

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE PÁGINA
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Curva S — Control de Avance",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS PERSONALIZADO (dark premium theme)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Fondo principal */
[data-testid="stAppViewContainer"] { background: #0F1923; }
[data-testid="stSidebar"]          { background: #111D2B; border-right: 1px solid #1E3050; }

/* Tipografía base */
html, body, [class*="css"] { font-family: 'Segoe UI', sans-serif; color: #E0E8F0; }

/* Encabezado de página */
.hero-title {
    font-size: 2.2rem; font-weight: 700;
    background: linear-gradient(135deg, #4C9BE8 0%, #C77DFF 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 0;
}
.hero-sub { font-size: 0.95rem; color: #8899AA; margin-top: 2px; }

/* Tarjetas KPI */
.kpi-card {
    background: #162030;
    border: 1px solid #1E3050;
    border-radius: 14px;
    padding: 18px 20px;
    text-align: center;
    transition: transform 0.2s, box-shadow 0.2s;
}
.kpi-card:hover { transform: translateY(-3px); box-shadow: 0 8px 24px #00000066; }
.kpi-value { font-size: 1.8rem; font-weight: 700; }
.kpi-label { font-size: 0.78rem; color: #8899AA; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.08em; }
.kpi-good  { color: #6BCB77; }
.kpi-bad   { color: #F06449; }
.kpi-neutral { color: #FFD166; }
.kpi-blue    { color: #4C9BE8; }

/* Divisor */
hr { border-color: #1E3050; }

/* Sección de gráficos */
.section-title {
    font-size: 1.05rem; font-weight: 600; color: #8899AA;
    letter-spacing: 0.05em; text-transform: uppercase;
    margin: 24px 0 12px;
}

/* Botón de descarga */
.stDownloadButton button {
    background: linear-gradient(135deg, #1B3A5C, #2A1B4A);
    color: #E0E8F0; border: 1px solid #2E4A6A;
    border-radius: 8px; font-size: 0.85rem;
}
.stDownloadButton button:hover { border-color: #4C9BE8; color: #4C9BE8; }

/* Sidebar labels */
.stSlider label, .stSelectbox label, .stFileUploader label,
.stCheckbox label, .stNumberInput label {
    color: #A0B4C8 !important; font-size: 0.88rem;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_CSV = Path(__file__).parent / "data" / "avance_sintetico.csv"


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR — CONTROLES
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuración")
    st.markdown("---")

    # Fuente de datos
    st.markdown("### 📂 Fuente de Datos")
    fuente = st.radio(
        "Seleccionar origen",
        ["Usar datos sintéticos", "Cargar CSV propio"],
        index=0,
        label_visibility="collapsed",
    )

    uploaded_file = None
    if fuente == "Cargar CSV propio":
        uploaded_file = st.file_uploader(
            "Archivo CSV de avance",
            type=["csv"],
            help="Columnas requeridas: semana, avance_planificado_pct, avance_real_pct\n"
                 "Opcionales: costo_planificado_acum, costo_real_acum",
        )

    st.markdown("---")

    # Parámetros del proyecto
    st.markdown("### 🏗️ Parámetros del Proyecto")
    presupuesto = st.number_input(
        "Presupuesto Total ($)",
        min_value=10_000,
        max_value=100_000_000,
        value=1_000_000,
        step=50_000,
        format="%d",
    )

    st.markdown("---")

    # Rango de semanas (se actualiza tras cargar datos)
    st.markdown("### 📅 Rango de Semanas")
    rango_placeholder = st.empty()   # se rellena dinámicamente

    st.markdown("---")

    # Opciones de visualización
    st.markdown("### 🎨 Visualización")
    mostrar_area = st.checkbox("Mostrar área entre curvas", value=True)
    mostrar_costos = st.checkbox("Gráfico de Costos", value=True)
    mostrar_indices = st.checkbox("Gráfico SPI/CPI", value=True)
    mostrar_varianza = st.checkbox("Gráfico de Varianzas", value=False)
    dpi_export = st.select_slider(
        "Resolución de exportación (DPI)",
        options=[72, 96, 150, 200, 300],
        value=150,
    )

    st.markdown("---")
    st.markdown(
        "<div style='color:#445566;font-size:0.75rem;text-align:center'>"
        "Curva S · EVM Dashboard · v1.0<br>Powered by Streamlit + Matplotlib"
        "</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CARGA DE DATOS
# ─────────────────────────────────────────────────────────────────────────────
source = uploaded_file if uploaded_file is not None else DEFAULT_CSV
df_raw, errors = logic.load_data(source)

if errors:
    for e in errors:
        st.error(e)
    st.stop()

# Slider dinámico de semanas
sem_min = int(df_raw["semana"].min())
sem_max = int(df_raw["semana"].max())
with rango_placeholder:
    sem_ini, sem_fin = st.slider(
        "Rango de semanas a visualizar",
        min_value=sem_min,
        max_value=sem_max,
        value=(sem_min, sem_max),
    )

df_filt = logic.filtrar_por_semanas(df_raw, sem_ini, sem_fin)
df_evm  = logic.calcular_indicadores(df_filt, presupuesto)
resumen = logic.calcular_resumen(df_evm, presupuesto)


# ─────────────────────────────────────────────────────────────────────────────
# ENCABEZADO
# ─────────────────────────────────────────────────────────────────────────────
col_logo, col_title = st.columns([0.08, 0.92])
with col_title:
    st.markdown('<div class="hero-title">📈 Curva S — Control de Avance de Proyecto</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="hero-sub">Earned Value Management (EVM) · '
        f'Semanas {sem_ini}–{sem_fin} · '
        f'Presupuesto: ${presupuesto:,.0f}</div>',
        unsafe_allow_html=True,
    )

st.markdown("<hr>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# TARJETAS KPI
# ─────────────────────────────────────────────────────────────────────────────
def fmt_pct(v):
    return f"{v:.1f}%" if v == v else "N/D"

def fmt_idx(v):
    return f"{v:.3f}" if v == v else "N/D"

def fmt_currency(v):
    return f"${v:,.0f}" if v == v else "N/D"

def color_class(v, threshold=1.0, invert=False):
    if v != v:
        return "kpi-neutral"
    good = v >= threshold if not invert else v <= threshold
    return "kpi-good" if good else "kpi-bad"

if resumen:
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    kpis = [
        (c1, "Avance Planif.",  fmt_pct(resumen["avance_plan_pct"]),  "kpi-blue"),
        (c2, "Avance Real",     fmt_pct(resumen["avance_real_pct"]),   color_class(resumen["avance_real_pct"] - resumen["avance_plan_pct"], 0)),
        (c3, "SPI",             fmt_idx(resumen["spi"]),               color_class(resumen.get("spi", np.nan))),
        (c4, "CPI",             fmt_idx(resumen.get("cpi", np.nan)),   color_class(resumen.get("cpi", np.nan))),
        (c5, "EAC",             fmt_currency(resumen.get("eac", np.nan)), "kpi-neutral"),
        (c6, "VAC",             fmt_currency(resumen.get("vac", np.nan)), color_class(resumen.get("vac", np.nan), 0)),
    ]
    for col, label, value, cls in kpis:
        with col:
            st.markdown(
                f'<div class="kpi-card">'
                f'<div class="kpi-value {cls}">{value}</div>'
                f'<div class="kpi-label">{label}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

st.markdown("<br>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# GRÁFICOS
# ─────────────────────────────────────────────────────────────────────────────

def render_figure(fig, filename: str, caption: str = ""):
    """Renderiza figura matplotlib y agrega botón de descarga."""
    col_fig, col_dl = st.columns([0.85, 0.15])
    with col_fig:
        st.pyplot(fig, use_container_width=True)
    with col_dl:
        img_bytes = logic.fig_to_bytes(fig, dpi=dpi_export)
        st.download_button(
            label="⬇️ Exportar",
            data=img_bytes,
            file_name=filename,
            mime="image/png",
            key=filename,
        )
    if caption:
        st.caption(caption)


# 1. Curva S — Avance %
st.markdown('<div class="section-title">Curva S de Avance (%)</div>', unsafe_allow_html=True)
fig_s_pct = logic.grafico_curva_s_pct(df_evm, mostrar_area=mostrar_area)
render_figure(fig_s_pct, "curva_s_avance.png",
              "Área sombreada: desvío entre avance planificado y real por semana.")

# 2. Curva S — Costos
if mostrar_costos:
    fig_costos = logic.grafico_curva_s_costos(df_evm, mostrar_area=mostrar_area)
    if fig_costos:
        st.markdown("---")
        st.markdown('<div class="section-title">Curva S de Costos Acumulados</div>', unsafe_allow_html=True)
        render_figure(fig_costos, "curva_s_costos.png",
                      "Costo planificado (verde) vs costo real acumulado (dorado) en miles de dólares.")
    else:
        st.info("ℹ️ El CSV no contiene columnas de costo. Agregue `costo_planificado_acum` y `costo_real_acum` para habilitar este gráfico.")

# 3. SPI & CPI
if mostrar_indices:
    fig_idx = logic.grafico_indices(df_evm)
    if fig_idx:
        st.markdown("---")
        st.markdown('<div class="section-title">Índices de Desempeño (SPI & CPI)</div>', unsafe_allow_html=True)
        render_figure(fig_idx, "indices_evm.png",
                      "SPI < 1 → retraso en cronograma. CPI < 1 → sobrecosto. Zona roja = bajo rendimiento.")

# 4. Varianzas
if mostrar_varianza:
    fig_var = logic.grafico_varianza(df_evm)
    if fig_var:
        st.markdown("---")
        st.markdown('<div class="section-title">Varianzas de Cronograma y Costo</div>', unsafe_allow_html=True)
        render_figure(fig_var, "varianzas_evm.png",
                      "Barras rojas = desviación negativa (retraso/sobrecosto). Barras azules/verdes = desempeño positivo.")

st.markdown("<hr>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# TABLA DE DATOS
# ─────────────────────────────────────────────────────────────────────────────
with st.expander("📋 Ver tabla de datos (EVM)", expanded=False):
    cols_mostrar = ["semana", "avance_planificado_pct", "avance_real_pct",
                    "PV", "EV", "AC", "SV", "CV", "SPI", "CPI", "EAC"]
    cols_disp = [c for c in cols_mostrar if c in df_evm.columns]

    df_display = df_evm[cols_disp].copy()

    # Formateo para la tabla
    rename_map = {
        "semana": "Semana",
        "avance_planificado_pct": "Plan (%)",
        "avance_real_pct": "Real (%)",
        "PV": "PV ($)", "EV": "EV ($)", "AC": "AC ($)",
        "SV": "SV ($)", "CV": "CV ($)",
        "SPI": "SPI", "CPI": "CPI", "EAC": "EAC ($)",
    }
    df_display = df_display.rename(columns=rename_map)

    st.dataframe(
        df_display.style
            .format({
                "Plan (%)": "{:.1f}%",
                "Real (%)": "{:.1f}%",
                "PV ($)": "${:,.0f}",
                "EV ($)": "${:,.0f}",
                "AC ($)": "${:,.0f}",
                "SV ($)": "${:,.0f}",
                "CV ($)": "${:,.0f}",
                "SPI": "{:.3f}",
                "CPI": "{:.3f}",
                "EAC ($)": "${:,.0f}",
            }, na_rep="—")
            .map(lambda v: "color: #F06449" if isinstance(v, (int, float)) and v < 0 else "",
                      subset=["SV ($)", "CV ($)"] if "SV ($)" in df_display.columns else []),
        use_container_width=True,
        height=340,
    )

    # Descarga de datos procesados
    csv_export = df_display.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Descargar tabla EVM como CSV",
        data=csv_export,
        file_name="evm_calculado.csv",
        mime="text/csv",
    )
