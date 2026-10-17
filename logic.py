"""
logic.py — Módulo de cálculos y generación de gráficos para Curva S
Separado de la interfaz Streamlit para mejor mantenibilidad.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from io import BytesIO


# ─────────────────────────────────────────────
# CONSTANTES DE ESTILO
# ─────────────────────────────────────────────
PALETTE = {
    "plan":       "#4C9BE8",   # azul claro
    "real":       "#F06449",   # naranja-rojizo
    "costo_plan": "#6BCB77",   # verde
    "costo_real": "#FFD166",   # amarillo dorado
    "spi_line":   "#C77DFF",   # violeta
    "grid":       "#2E3A4A",
    "bg":         "#0F1923",
    "panel":      "#162030",
    "text":       "#E0E8F0",
    "neutral":    "#8899AA",
}

FONT_FAMILY = "DejaVu Sans"
plt.rcParams.update({
    "figure.facecolor":  PALETTE["bg"],
    "axes.facecolor":    PALETTE["panel"],
    "axes.edgecolor":    PALETTE["grid"],
    "axes.labelcolor":   PALETTE["text"],
    "axes.titlecolor":   PALETTE["text"],
    "xtick.color":       PALETTE["neutral"],
    "ytick.color":       PALETTE["neutral"],
    "text.color":        PALETTE["text"],
    "grid.color":        PALETTE["grid"],
    "grid.linestyle":    "--",
    "grid.alpha":        0.5,
    "legend.facecolor":  PALETTE["panel"],
    "legend.edgecolor":  PALETTE["grid"],
    "legend.labelcolor": PALETTE["text"],
    "font.family":       FONT_FAMILY,
    "font.size":         10,
})


# ─────────────────────────────────────────────
# FUNCIONES DE CARGA Y VALIDACIÓN
# ─────────────────────────────────────────────

REQUIRED_COLS = {"semana", "avance_planificado_pct", "avance_real_pct"}

def load_data(source) -> tuple:
    """
    Carga el CSV desde un path o file-like object.
    Devuelve (dataframe, lista_de_errores).
    """
    errors = []
    try:
        df = pd.read_csv(source)
    except Exception as e:
        return pd.DataFrame(), [f"Error al leer el archivo: {e}"]

    df.columns = df.columns.str.strip().str.lower()

    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        errors.append(f"Columnas faltantes: {', '.join(missing)}")
        return df, errors

    df["semana"] = pd.to_numeric(df["semana"], errors="coerce")
    df["avance_planificado_pct"] = pd.to_numeric(df["avance_planificado_pct"], errors="coerce")
    df["avance_real_pct"]        = pd.to_numeric(df["avance_real_pct"],        errors="coerce")

    for col in ["costo_planificado_acum", "costo_real_acum"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("semana").reset_index(drop=True)
    return df, errors


# ─────────────────────────────────────────────
# CÁLCULO DE INDICADORES EVM
# ─────────────────────────────────────────────

def calcular_indicadores(df: pd.DataFrame, presupuesto_total: float) -> pd.DataFrame:
    """
    Calcula indicadores de Earned Value Management (EVM):
      PV  – Planned Value
      EV  – Earned Value
      AC  – Actual Cost
      SPI – Schedule Performance Index
      CPI – Cost Performance Index
      SV  – Schedule Variance
      CV  – Cost Variance
      EAC – Estimate at Completion
    """
    df = df.copy()
    df["PV"] = df["avance_planificado_pct"] / 100.0 * presupuesto_total
    df["EV"] = df["avance_real_pct"]        / 100.0 * presupuesto_total

    if "costo_real_acum" in df.columns:
        df["AC"] = df["costo_real_acum"]
    else:
        df["AC"] = np.nan

    df["SV"]  = df["EV"] - df["PV"]
    df["CV"]  = df["EV"] - df["AC"]
    df["SPI"] = (df["EV"] / df["PV"]).replace([np.inf, -np.inf], np.nan)
    df["CPI"] = (df["EV"] / df["AC"]).replace([np.inf, -np.inf], np.nan)
    df["EAC"] = presupuesto_total / df["CPI"].replace(0, np.nan)

    return df


def calcular_resumen(df: pd.DataFrame, presupuesto_total: float) -> dict:
    """
    Devuelve métricas resumen del período más reciente con datos reales.
    """
    real = df.dropna(subset=["avance_real_pct"])
    if real.empty:
        return {}

    last = real.iloc[-1]
    return {
        "semana_actual":      int(last["semana"]),
        "avance_plan_pct":    last.get("avance_planificado_pct", np.nan),
        "avance_real_pct":    last["avance_real_pct"],
        "spi":                last.get("SPI", np.nan),
        "cpi":                last.get("CPI", np.nan),
        "sv":                 last.get("SV",  np.nan),
        "cv":                 last.get("CV",  np.nan),
        "eac":                last.get("EAC", np.nan),
        "vac":                presupuesto_total - last.get("EAC", presupuesto_total),
        "presupuesto_total":  presupuesto_total,
    }


# ─────────────────────────────────────────────
# FILTRADO POR RANGO DE SEMANAS
# ─────────────────────────────────────────────

def filtrar_por_semanas(df: pd.DataFrame, sem_ini: int, sem_fin: int) -> pd.DataFrame:
    return df[(df["semana"] >= sem_ini) & (df["semana"] <= sem_fin)].copy()


# ─────────────────────────────────────────────
# HELPERS DE ESTILO
# ─────────────────────────────────────────────

def _shade_between(ax, x, y1, y2, color, alpha=0.12):
    """Rellena el área entre dos curvas."""
    ax.fill_between(x, y1, y2, color=color, alpha=alpha, interpolate=True)


def _apply_style(ax, grid_axis="both"):
    ax.set_facecolor(PALETTE["panel"])
    ax.grid(True, axis=grid_axis)
    for spine in ax.spines.values():
        spine.set_edgecolor(PALETTE["grid"])


# ─────────────────────────────────────────────
# GRÁFICO 1 — CURVA S (% AVANCE)
# ─────────────────────────────────────────────

def grafico_curva_s_pct(df: pd.DataFrame, mostrar_area: bool = True):
    """Curva S de porcentaje de avance planificado vs real."""
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(PALETTE["bg"])
    _apply_style(ax)

    x  = df["semana"]
    yp = df["avance_planificado_pct"]
    yr = df.dropna(subset=["avance_real_pct"])

    ax.plot(x, yp, color=PALETTE["plan"], linewidth=2.5,
            marker="o", markersize=4, label="Planificado (%)")
    ax.plot(yr["semana"], yr["avance_real_pct"],
            color=PALETTE["real"], linewidth=2.5,
            marker="s", markersize=4, label="Real (%)", linestyle="--")

    if mostrar_area and len(yr) > 0:
        common = df.dropna(subset=["avance_planificado_pct", "avance_real_pct"])
        _shade_between(ax, common["semana"],
                       common["avance_planificado_pct"],
                       common["avance_real_pct"],
                       PALETTE["real"])

    ax.set_xlim(x.min() - 0.3, x.max() + 0.3)
    ax.set_ylim(0, 110)
    ax.set_xlabel("Semana", fontsize=11)
    ax.set_ylabel("Avance (%)", fontsize=11)
    ax.set_title("📈  Curva S — Avance del Proyecto (%)", fontsize=13, fontweight="bold", pad=14)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.legend(loc="upper left", framealpha=0.8)

    ultima = df.dropna(subset=["avance_real_pct"])["semana"]
    if not ultima.empty:
        ax.axvline(ultima.max(), color=PALETTE["neutral"], linewidth=1, linestyle=":")

    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────
# GRÁFICO 2 — CURVA S (COSTOS ACUMULADOS)
# ─────────────────────────────────────────────

def grafico_curva_s_costos(df: pd.DataFrame, mostrar_area: bool = True):
    """Curva S de costo acumulado planificado vs real."""
    if "costo_planificado_acum" not in df.columns or "costo_real_acum" not in df.columns:
        return None

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(PALETTE["bg"])
    _apply_style(ax)

    df_cp = df.dropna(subset=["costo_planificado_acum"])
    df_cr = df.dropna(subset=["costo_real_acum"])

    ax.plot(df_cp["semana"], df_cp["costo_planificado_acum"] / 1e3,
            color=PALETTE["costo_plan"], linewidth=2.5,
            marker="o", markersize=4, label="Costo Planificado (k$)")
    ax.plot(df_cr["semana"], df_cr["costo_real_acum"] / 1e3,
            color=PALETTE["costo_real"], linewidth=2.5,
            marker="s", markersize=4, label="Costo Real (k$)", linestyle="--")

    if mostrar_area:
        common = df.dropna(subset=["costo_planificado_acum", "costo_real_acum"])
        if len(common) > 0:
            _shade_between(ax, common["semana"],
                           common["costo_planificado_acum"] / 1e3,
                           common["costo_real_acum"] / 1e3,
                           PALETTE["costo_real"])

    ax.set_xlabel("Semana", fontsize=11)
    ax.set_ylabel("Costo Acumulado (miles $)", fontsize=11)
    ax.set_title("💰  Curva S — Costo Acumulado del Proyecto", fontsize=13, fontweight="bold", pad=14)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}k"))
    ax.legend(loc="upper left", framealpha=0.8)

    ultima = df.dropna(subset=["costo_real_acum"])["semana"]
    if not ultima.empty:
        ax.axvline(ultima.max(), color=PALETTE["neutral"], linewidth=1, linestyle=":")

    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────
# GRÁFICO 3 — SPI & CPI
# ─────────────────────────────────────────────

def grafico_indices(df: pd.DataFrame):
    """Gráfico de líneas SPI y CPI a lo largo del tiempo."""
    if "SPI" not in df.columns:
        return None

    df_spi = df.dropna(subset=["SPI"])
    df_cpi = df.dropna(subset=["CPI"])

    if df_spi.empty:
        return None

    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor(PALETTE["bg"])
    _apply_style(ax)

    ax.plot(df_spi["semana"], df_spi["SPI"], color=PALETTE["spi_line"],
            linewidth=2.5, marker="o", markersize=4, label="SPI (Cronograma)")
    if not df_cpi.empty:
        ax.plot(df_cpi["semana"], df_cpi["CPI"], color=PALETTE["costo_real"],
                linewidth=2.5, marker="s", markersize=4,
                label="CPI (Costo)", linestyle="--")

    xmin, xmax = df["semana"].min(), df["semana"].max()
    ax.axhline(1.0, color="#FFFFFF", linewidth=1, linestyle="-", alpha=0.35, label="Referencia = 1.0")
    ax.fill_between([xmin, xmax], 1.0, 0.0, color=PALETTE["real"],       alpha=0.07)
    ax.fill_between([xmin, xmax], 1.0, 2.5, color=PALETTE["costo_plan"], alpha=0.05)

    ax.set_xlim(xmin - 0.3, xmax + 0.3)
    ax.set_ylim(0, 2.5)
    ax.set_xlabel("Semana", fontsize=11)
    ax.set_ylabel("Índice de Desempeño", fontsize=11)
    ax.set_title("📊  SPI & CPI — Índices de Desempeño EVM", fontsize=13, fontweight="bold", pad=14)
    ax.legend(loc="upper right", framealpha=0.8)

    ax.text(xmax + 0.1, 1.05, "Superior",        color=PALETTE["costo_plan"], fontsize=8, va="bottom")
    ax.text(xmax + 0.1, 0.92, "Bajo rendimiento", color=PALETTE["real"],       fontsize=8, va="top")

    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────
# GRÁFICO 4 — VARIANZAS POR SEMANA
# ─────────────────────────────────────────────

def grafico_varianza(df: pd.DataFrame):
    """Gráfico de barras de varianza de cronograma (SV) y costo (CV)."""
    if "SV" not in df.columns:
        return None

    df_v = df.dropna(subset=["SV"]).copy()
    if df_v.empty:
        return None

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    fig.patch.set_facecolor(PALETTE["bg"])

    for ax, col, label, color in [
        (axes[0], "SV", "Varianza de Cronograma (SV)", PALETTE["plan"]),
        (axes[1], "CV", "Varianza de Costo (CV)",       PALETTE["costo_plan"]),
    ]:
        _apply_style(ax, grid_axis="y")
        vals   = df_v[col].dropna() / 1e3
        idx    = vals.index
        semanas = df_v.loc[idx, "semana"]
        colors_bar = [PALETTE["real"] if v < 0 else color for v in vals]
        ax.bar(semanas, vals, color=colors_bar, alpha=0.85, width=0.7)
        ax.axhline(0, color=PALETTE["text"], linewidth=0.8, alpha=0.5)
        ax.set_xlabel("Semana", fontsize=10)
        ax.set_ylabel("Varianza (k$)", fontsize=10)
        ax.set_title(label, fontsize=11, fontweight="bold")
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}k"))

    fig.suptitle("📉  Varianzas de Cronograma y Costo por Semana", fontsize=13,
                 fontweight="bold", color=PALETTE["text"], y=1.02)
    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────
# EXPORTAR FIGURA A BYTES
# ─────────────────────────────────────────────

def fig_to_bytes(fig, dpi: int = 150) -> bytes:
    """Convierte una figura matplotlib a bytes PNG para descarga."""
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor=PALETTE["bg"])
    buf.seek(0)
    return buf.getvalue()
