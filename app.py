from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


# =========================================================
# Config
# =========================================================
APP_TITLE = "CRAWS Load Shape Explorer"

#KWH_FILE = Path("Inputs/CRAWS_kWh_LoadShape_updated.csv")
#THERM_FILE = Path("Inputs/CRAWS_Therm_LoadShape_updated.csv")
#BLDG_MAP_FILE = Path("Inputs/BldgType_map.xlsx")

KWH_FILE = "https://storage.googleapis.com/craws_loadshape_inputs/CRAWS_kWh_LoadShape_updated.csv"
THERM_FILE = "https://storage.googleapis.com/craws_loadshape_inputs/CRAWS_Therm_LoadShape_updated.csv"
BLDG_MAP_FILE = "https://storage.googleapis.com/craws_loadshape_inputs/BldgType_map.xlsx"

HOUR_COL = "Hour"


# =========================================================
# Loaders
# =========================================================
@st.cache_data(show_spinner=False)
def load_bldg_map(path_or_url: str) -> dict[str, str]:
    df = pd.read_excel(path_or_url, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]

    if "Code" not in df.columns or "Building Type" not in df.columns:
        raise ValueError('BldgType_map.xlsx must contain columns "Code" and "Building Type".')

    df["Code"] = df["Code"].astype(str).str.strip()
    df["Building Type"] = df["Building Type"].astype(str).str.strip()

    return dict(zip(df["Code"], df["Building Type"]))


@st.cache_data(show_spinner=False)
def load_loadshape_csv(path_or_url: str) -> pd.DataFrame:
    df = pd.read_csv(path_or_url)
    df.columns = [str(c).strip() for c in df.columns]
    return df


# =========================================================
# Parsing metadata from column names
# =========================================================
def parse_column_metadata(col_name: str) -> dict:
    """
    Expected patterns like:
    Fin_CZ01_CSW_Facility_mtr_hourly.csv
    Htl_CZ05_CSW_Facility_mtr.csv
    """
    if col_name == HOUR_COL:
        return {}

    parts = str(col_name).split("_")

    code = parts[0].strip() if len(parts) > 0 else None
    cz_part = parts[1].strip() if len(parts) > 1 else None
    tech = parts[2].strip() if len(parts) > 2 else None

    cz_num = None
    if cz_part is not None:
        m = re.match(r"CZ(\d+)", cz_part, flags=re.IGNORECASE)
        if m:
            cz_num = int(m.group(1))

    return {
        "column_name": col_name,
        "code": code,
        "climate_zone": cz_num,
        "technology": tech,
    }


# =========================================================
# Summary and hourly long tables
# =========================================================
@st.cache_data(show_spinner=False)
def build_summary(df: pd.DataFrame, fuel_label: str, bldg_map: dict[str, str]) -> pd.DataFrame:
    """
    Builds one summary row per data column.
    Summary metrics are computed from all 8760 values.
    """
    data_cols = [c for c in df.columns if c != HOUR_COL]

    rows = []
    for col in data_cols:
        meta = parse_column_metadata(col)
        s = pd.to_numeric(df[col], errors="coerce")

        rows.append(
            {
                "column_name": col,
                "code": meta["code"],
                "building_type": bldg_map.get(meta["code"], meta["code"]),
                "climate_zone": meta["climate_zone"],
                "technology": meta["technology"],
                "fuel": fuel_label,
                "annual_total": float(np.nansum(s)),
                "average_hourly": float(np.nanmean(s)),
                "peak_hour": float(np.nanmax(s)),
            }
        )

    out = pd.DataFrame(rows)
    out = out[out["technology"].astype(str).str.upper() == "CSW"].copy()

    return out


@st.cache_data(show_spinner=False)
def build_long_hourly_df(df: pd.DataFrame, fuel_label: str, bldg_map: dict[str, str]) -> pd.DataFrame:
    """
    Converts the wide 8760 file into a long table:
    Hour, column_name, code, building_type, climate_zone, technology, fuel, value
    """
    data_cols = [c for c in df.columns if c != HOUR_COL]

    long_df = df.melt(
        id_vars=[HOUR_COL],
        value_vars=data_cols,
        var_name="column_name",
        value_name="value",
    ).copy()

    meta_rows = []
    for col in data_cols:
        meta = parse_column_metadata(col)
        meta_rows.append(
            {
                "column_name": col,
                "code": meta["code"],
                "building_type": bldg_map.get(meta["code"], meta["code"]),
                "climate_zone": meta["climate_zone"],
                "technology": meta["technology"],
                "fuel": fuel_label,
            }
        )

    meta_df = pd.DataFrame(meta_rows)

    long_df = long_df.merge(meta_df, on="column_name", how="left")
    long_df["value"] = pd.to_numeric(long_df["value"], errors="coerce")

    # keep only CSW
    long_df = long_df[long_df["technology"].astype(str).str.upper() == "CSW"].copy()

    return long_df


def metric_col_from_label(metric_label: str) -> str:
    mapping = {
        "Annual total": "annual_total",
        "Average hourly": "average_hourly",
        "Peak hour": "peak_hour",
    }
    return mapping[metric_label]


# =========================================================
# Plot functions
# =========================================================
def plot_hourly_single_line(plot_df: pd.DataFrame, title: str, y_label: str):
    fig = px.line(
        plot_df,
        x=HOUR_COL,
        y="value",
        title=title,
        labels={
            HOUR_COL: "Hour",
            "value": y_label,
        },
    )
    return fig


def plot_consumption_by_climate_zone(plot_df: pd.DataFrame, metric_label: str, fuel_label: str):
    plot_df = plot_df.copy()
    plot_df["climate_zone_label"] = plot_df["climate_zone"].apply(lambda x: f"CZ{x:02d}")

    fig = px.bar(
        plot_df,
        x="climate_zone_label",
        y="value",
        color="building_type",
        barmode="group",
        hover_data=["code", "climate_zone", "column_name"],
        labels={
            "climate_zone_label": "Climate Zone",
            "value": metric_label,
            "building_type": "Building Type",
        },
        title=f"{metric_label} - {fuel_label}",
    )

    cz_order = [f"CZ{i:02d}" for i in sorted(plot_df["climate_zone"].dropna().unique())]
    fig.update_xaxes(type="category", categoryorder="array", categoryarray=cz_order)

    return fig


def plot_consumption_by_building_type(plot_df: pd.DataFrame, metric_label: str, fuel_label: str):
    plot_df = plot_df.copy()
    plot_df["climate_zone_label"] = plot_df["climate_zone"].apply(lambda x: f"CZ{x:02d}")

    fig = px.bar(
        plot_df,
        x="building_type",
        y="value",
        color="climate_zone_label",
        barmode="group",
        hover_data=["code", "column_name"],
        labels={
            "building_type": "Building Type",
            "value": metric_label,
            "climate_zone_label": "Climate Zone",
        },
        title=f"{metric_label} - {fuel_label}",
    )

    fig.update_layout(xaxis_tickangle=-35)
    return fig


# =========================================================
# App
# =========================================================
st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)

#if not KWH_FILE.exists():
#    st.error(f"Missing file: {KWH_FILE}")
#    st.stop()

#if not THERM_FILE.exists():
#    st.error(f"Missing file: {THERM_FILE}")
#    st.stop()

#if not BLDG_MAP_FILE.exists():
#    st.error(f"Missing file: {BLDG_MAP_FILE}")
#    st.stop()

bldg_map = load_bldg_map(BLDG_MAP_FILE)
df_kwh = load_loadshape_csv(KWH_FILE)
df_therm = load_loadshape_csv(THERM_FILE)

summary_kwh = build_summary(df_kwh, "kWh", bldg_map)
summary_therm = build_summary(df_therm, "Therms", bldg_map)

hourly_kwh = build_long_hourly_df(df_kwh, "kWh", bldg_map)
hourly_therm = build_long_hourly_df(df_therm, "Therms", bldg_map)

with st.sidebar:
    st.header("Controls")

    fuel_choice = st.radio("Fuel", ["kWh", "Therms"])
    metric_label = st.selectbox(
        "Metric",
        ["Annual total", "Average hourly", "Peak hour"],
        index=0,
    )

summary_df = summary_kwh if fuel_choice == "kWh" else summary_therm
hourly_df = hourly_kwh if fuel_choice == "kWh" else hourly_therm
metric_col = metric_col_from_label(metric_label)

all_building_types = sorted(summary_df["building_type"].dropna().unique().tolist())
all_czs = sorted(summary_df["climate_zone"].dropna().unique().tolist())

tabs = st.tabs([
    "Hourly by Building Type",
    "Hourly by Climate Zone",
    "Consumption by Climate Zone",
    "Consumption by Building Type",
    "Data Preview",
])

# ---------------------------------------------------------
# Tab 1 - Hourly by Building Type
# ---------------------------------------------------------
with tabs[0]:
    bldg_choice = st.selectbox(
        "Building type",
        options=["Average across all building types"] + all_building_types,
        index=0,
        key="hourly_bldg_choice",
    )

    if bldg_choice == "Average across all building types":
        plot_df = hourly_df.groupby(HOUR_COL, as_index=False)["value"].mean()
        chart_title = f"Hourly Load Shape - Average Across All Building Types - {fuel_choice}"
    else:
        plot_df = (
            hourly_df[hourly_df["building_type"] == bldg_choice]
            .groupby(HOUR_COL, as_index=False)["value"]
            .mean()
        )
        chart_title = f"Hourly Load Shape - {bldg_choice} - {fuel_choice}"

    if plot_df.empty:
        st.info("No matching data for that selection.")
    else:
        fig = plot_hourly_single_line(plot_df, title=chart_title, y_label=fuel_choice)
        st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------
# Tab 2 - Hourly by Climate Zone
# ---------------------------------------------------------
with tabs[1]:
    cz_choice = st.selectbox(
        "Climate zone",
        options=["Average across all climate zones"] + [f"CZ{x:02d}" for x in all_czs],
        index=0,
        key="hourly_cz_choice",
    )

    if cz_choice == "Average across all climate zones":
        plot_df = hourly_df.groupby(HOUR_COL, as_index=False)["value"].mean()
        chart_title = f"Hourly Load Shape - Average Across All Climate Zones - {fuel_choice}"
    else:
        cz_num = int(cz_choice.replace("CZ", ""))
        plot_df = (
            hourly_df[hourly_df["climate_zone"] == cz_num]
            .groupby(HOUR_COL, as_index=False)["value"]
            .mean()
        )
        chart_title = f"Hourly Load Shape - {cz_choice} - {fuel_choice}"

    if plot_df.empty:
        st.info("No matching data for that selection.")
    else:
        fig = plot_hourly_single_line(plot_df, title=chart_title, y_label=fuel_choice)
        st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------
# Tab 3 - Consumption by Climate Zone
# ---------------------------------------------------------
with tabs[2]:
    bldg_options = ["All Building Types"] + all_building_types
    selected_bldgs = st.multiselect(
        "Building types",
        options=bldg_options,
        default=["All Building Types"],
        key="consumption_cz_bldgs",
    )

    cz_options = ["All Climate Zones"] + [f"CZ{x:02d}" for x in all_czs]
    selected_czs = st.multiselect(
        "Climate zones",
        options=cz_options,
        default=["All Climate Zones"],
        key="consumption_cz_czs",
    )

    if "All Building Types" in selected_bldgs or len(selected_bldgs) == 0:
        bldgs_to_use = all_building_types
    else:
        bldgs_to_use = selected_bldgs

    if "All Climate Zones" in selected_czs or len(selected_czs) == 0:
        czs_to_use = all_czs
    else:
        czs_to_use = [int(x.replace("CZ", "")) for x in selected_czs]

    plot_df = summary_df[
        summary_df["building_type"].isin(bldgs_to_use)
        & summary_df["climate_zone"].isin(czs_to_use)
    ].copy()

    plot_df["value"] = plot_df[metric_col]

    if plot_df.empty:
        st.info("No matching data for those selections.")
    else:
        fig = plot_consumption_by_climate_zone(plot_df, metric_label, fuel_choice)
        st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------
# Tab 4 - Consumption by Building Type
# ---------------------------------------------------------
with tabs[3]:
    bldg_options = ["All Building Types"] + all_building_types
    selected_bldgs = st.multiselect(
        "Building types",
        options=bldg_options,
        default=["All Building Types"],
        key="consumption_bldg_bldgs",
    )

    cz_options = ["All Climate Zones"] + [f"CZ{x:02d}" for x in all_czs]
    selected_czs = st.multiselect(
        "Climate zones",
        options=cz_options,
        default=["All Climate Zones"],
        key="consumption_bldg_czs",
    )

    if "All Building Types" in selected_bldgs or len(selected_bldgs) == 0:
        bldgs_to_use = all_building_types
    else:
        bldgs_to_use = selected_bldgs

    if "All Climate Zones" in selected_czs or len(selected_czs) == 0:
        czs_to_use = all_czs
    else:
        czs_to_use = [int(x.replace("CZ", "")) for x in selected_czs]

    plot_df = summary_df[
        summary_df["building_type"].isin(bldgs_to_use)
        & summary_df["climate_zone"].isin(czs_to_use)
    ].copy()

    plot_df["value"] = plot_df[metric_col]

    if plot_df.empty:
        st.info("No matching data for those selections.")
    else:
        fig = plot_consumption_by_building_type(plot_df, metric_label, fuel_choice)
        st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------
# Tab 5 - Data Preview
# ---------------------------------------------------------
with tabs[4]:
    st.write("Summary data behind the charts")

    preview_df = summary_df.copy()
    preview_df["Annual total"] = preview_df["annual_total"]
    preview_df["Average hourly"] = preview_df["average_hourly"]
    preview_df["Peak hour"] = preview_df["peak_hour"]

    preview_df = preview_df[
        [
            "building_type",
            "code",
            "climate_zone",
            "technology",
            "fuel",
            "Annual total",
            "Average hourly",
            "Peak hour",
            "column_name",
        ]
    ].sort_values(["building_type", "climate_zone"])

    st.dataframe(preview_df, use_container_width=True, height=500)