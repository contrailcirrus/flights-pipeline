#!/usr/bin/env python3

"""
Generate a PDF report to match the google designed flight report template.
"""

import argparse
import os

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import matplotlib.lines as lines
import matplotlib.patches as patches
from matplotlib.ticker import MultipleLocator
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
import json
from typing import Optional, Dict, Any
import cartopy.crs as ccrs
import cartopy.feature as cfeature

from services import FlightsReportFetchSvc

from log import logger

# A4 size in points (595.27 x 841.89)
# 1 point = 1/72 inch
# A4 is 210mm × 297mm (8.27 × 11.69 inches)
page_width = 595.27
page_height = 841.89
title_color = "#111111"  # dark dark gray
text_color = "#444444"  # dark gray
container_color = "#C4C7C5"
background_text_color = "#1F1F1F"
hyperlink_text_color = "#0000EE"
left_margin = 30
horizontal_spacing = 13
vertical_spacing = 10
header_offset = 10
container_width = page_width - left_margin * 2 + 5
container_text_font_size = 8.5
container_title_font_size = 14
scaling_factor = 15 / 18
paragraph_spacing = 10
line_spacing = 10
text_width = 520

fig_legend_text_size = 16


def _gen_pie_fig(summary_json_fp: str, out_path: str):
    with open(summary_json_fp, "r") as fp:
        summary_json = json.load(fp)

    fig = plt.figure(figsize=(5, 5))
    ax = fig.add_subplot(1, 1, 1)
    percent_with_warming = round(
        summary_json["percentages"]["flight_distance_with_warming_contrails"], 1
    )
    percent_without_warming = 100 - percent_with_warming

    colors = ["#4285F4", "#D3E3FD"]

    ax.pie(
        [percent_with_warming, percent_without_warming],
        labels=["", ""],
        startangle=90,
        counterclock=False,
        colors=colors,
        wedgeprops={"width": 0.15},
    )

    ax.set_aspect("equal")  # Ensures the pie chart is circular

    legend_colors = [
        plt.Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor=color,
            markersize=15,
        )
        for color in colors
    ]
    legend_labels = [
        "Distance with warming contrails",
        "Distance without warming contrails",
    ]

    plt.legend(
        handles=legend_colors,
        labels=legend_labels,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.15),
        ncol=1,
        frameon=False,
        labelspacing=1.0,
        fontsize=16,
    )
    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_visible(False)

    plt.subplots_adjust(left=0.01, right=1.04, top=0.99)
    plt.savefig(
        f"{out_path}/fig_contrail_warming_percentage.png",
        bbox_inches="tight",
    )


def _gen_daytime_nighttime_detailed_bar_fig(summary_json_fp: str, out_path: str):
    with open(summary_json_fp, "r") as fp:
        summary_json = json.load(fp)

        # Common settings for both plots
        bar_height = 0.3
        y_position = 0.5
        colors = ["#2C2857", "#F7CA45"]

        plot_settings = {
            "left": 0.01,
            "right": 0.95,
            "top": 0.99,
            "bottom": 0.2,
        }

        # -----------------
        # TOP PLOT
        # -----------------
        fig, ax = plt.subplots(figsize=(4, 1))
        total_flight_distance = summary_json["flight_distance_km"]["total"]
        night_percent = round(
            (summary_json["flight_distance_km"]["nighttime"] / total_flight_distance)
            * 100
        )
        day_percent = round(
            (summary_json["flight_distance_km"]["daytime"] / total_flight_distance)
            * 100
        )

        # determine text placement/coords
        inlay_nighttime_text_margin = total_flight_distance * 0.05
        inlay_daytime_text_margin = total_flight_distance * 0.85
        y_margin = y_position * 0.96

        # nighttime
        # ------
        ax.barh(
            y_position,
            summary_json["flight_distance_km"]["nighttime"],
            height=bar_height,
            color=colors[0],
            left=0,
        )
        ax.text(
            inlay_nighttime_text_margin,
            y_margin,
            f"{night_percent}%",
            color="white",
            ha="left",
            va="center",
            fontsize=11,
        )

        # daytime
        # ------
        ax.barh(
            y_position,
            summary_json["flight_distance_km"]["daytime"],
            height=bar_height,
            color=colors[1],
            left=summary_json["flight_distance_km"]["nighttime"],
        )
        ax.text(
            inlay_daytime_text_margin,
            y_margin,
            f"{day_percent}%",
            color="black",
            ha="left",
            va="center",
            fontsize=11,
        )

        ax.set_ylim(0, 1)

        ax.xaxis.set_visible(False)
        ax.yaxis.set_visible(False)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_visible(False)

        plt.subplots_adjust(**plot_settings)
        plt.savefig(
            f"{out_path}/fig_distance_daytime_nighttime.png",
            bbox_inches="tight",
        )

        # -----------------
        # BOTTOM FIG
        # -----------------
        fig, ax = plt.subplots(figsize=(4, 1))

        total_warming_flight_distance = summary_json["flight_distance_km"][
            "with_contrails"
        ]["is_warming"]["total"]
        night_percent = round(
            (
                summary_json["flight_distance_km"]["with_contrails"]["is_warming"][
                    "nighttime"
                ]
                / total_warming_flight_distance
            )
            * 100
        )
        day_percent = round(
            (
                summary_json["flight_distance_km"]["with_contrails"]["is_warming"][
                    "daytime"
                ]
                / total_warming_flight_distance
            )
            * 100
        )

        # determine text placement/coords
        inlay_nighttime_text_margin = total_warming_flight_distance * 0.05
        inlay_daytime_text_margin = total_warming_flight_distance * 0.85
        y_margin = y_position * 0.96

        # nighttime
        # ------
        ax.barh(
            y_position,
            summary_json["flight_distance_km"]["with_contrails"]["is_warming"][
                "nighttime"
            ],
            height=bar_height,
            color=colors[0],
            left=0,
        )

        ax.text(
            inlay_nighttime_text_margin,
            y_margin,
            f"{night_percent}%",
            color="white",
            ha="left",
            va="center",
            fontsize=11,
        )

        # daytime
        # ------
        ax.barh(
            y_position,
            summary_json["flight_distance_km"]["with_contrails"]["is_warming"][
                "daytime"
            ],
            height=bar_height,
            color=colors[1],
            left=summary_json["flight_distance_km"]["with_contrails"]["is_warming"][
                "nighttime"
            ],
        )
        ax.text(
            inlay_daytime_text_margin,
            y_margin,
            f"{day_percent}%",
            color="black",
            ha="left",
            va="center",
            fontsize=11,
        )

        ax.set_ylim(0, 1)

        legend_colors = [
            plt.Line2D(
                [0], [0], marker="o", color="w", markerfacecolor=color, markersize=10
            )
            for color in colors
        ]
        legend_labels = ["Nighttime", "Daytime"]
        plt.legend(
            handles=legend_colors,
            labels=legend_labels,
            loc="lower left",
            bbox_to_anchor=(0, -0.2),
            ncol=2,
            frameon=False,
            fontsize=11,
        )
        ax.xaxis.set_visible(False)
        ax.yaxis.set_visible(False)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_visible(False)
        plt.subplots_adjust(**plot_settings)
        plt.savefig(
            f"{out_path}/fig_contrail_distance_warming_daytime_nighttime.png",
            bbox_inches="tight",
        )


def _gen_map_fig(data_all_internal_fp: str, out_path: str):
    summary_df = pd.read_csv(data_all_internal_fp)
    projection = ccrs.Mercator(
        central_longitude=12, min_latitude=-56.9, max_latitude=84.0
    )
    fig = plt.figure(
        figsize=(10, 10)
    )  # Increased height slightly to accommodate legend
    ax = fig.add_subplot(1, 1, 1, projection=projection)
    ax.set_global()
    ax.add_feature(cfeature.LAND, color="#C4C7C5")
    ax.fill(
        [c[0] for c in FlightsReportFetchSvc.CONUS_COORDS],
        [c[1] for c in FlightsReportFetchSvc.CONUS_COORDS],
        facecolor="#F7CA45",
        edgecolor="#F7CA45",
        linewidth=1.0,
        alpha=0.5,
        transform=ccrs.Geodetic(),
    )
    for ix, row in summary_df.iterrows():
        # downsample number of flights plotted if the dataset is big
        if len(summary_df) > 300:
            frac = int(len(summary_df) / 300)
            if (ix % frac) != 0:
                continue
        plt.plot(
            [row.lon_start, row.lon_end],
            [row.lat_start, row.lat_end],
            color="black",
            alpha=0.3,
            linewidth=0.3,
            transform=ccrs.Geodetic(),
        )

    legend_elements = [
        patches.Rectangle(
            (0, 0),
            1,
            1,
            facecolor="#F7CA45",
            alpha=0.5,
            label="Satellite verified region",
        ),
        patches.Rectangle(
            (0, 0),
            1,
            1,
            facecolor="#C4C7C5",
            label="Algorithm predictions only",
        ),
        #  lines.Line2D([0], [0], color="black", linewidth=1, label="Flight paths"),
    ]

    # Add legend
    ax.legend(
        handles=legend_elements,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.3),
        ncol=1,
        frameon=False,
        fontsize=21.5,
    )

    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    plt.savefig(
        f"{out_path}/map.png",
        bbox_inches="tight",  # This ensures the legend is not cut off
    )


def _gen_fuel_vs_contrail_co2_bar_fig(summary_json_fp: str, out_path: str):
    with open(summary_json_fp, "r") as fp:
        summary_json = json.load(fp)

    fig = plt.figure(figsize=(8, 3))
    ax = fig.add_subplot(1, 1, 1)

    total = (
        summary_json["co2_metric_tons"]["total"]
        + summary_json["co2e_metric_tons"]["gwp50"]["total"]
    )
    normalized_values = [
        v / total
        for v in [
            summary_json["co2_metric_tons"]["total"],
            summary_json["co2e_metric_tons"]["gwp50"]["total"],
        ]
    ]
    colors = ["#1967D2", "#4285F4"]

    left = 0
    for value, color in zip(normalized_values, colors):
        ax.barh("Tons warming", value, color=color, left=left)
        left += value

    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_visible(False)

    plt.subplots_adjust(left=0.01, right=1.04, top=0.99, bottom=0.01)
    plt.savefig(f"{out_path}/fuel_vs_contrail_co2.png")


def _gen_daytime_nighttime_bar_fig(summary_json_fp: str, out_path: str):
    """Generate horizontal bar with daytime warming vs. nighttime warming."""
    with open(summary_json_fp, "r") as fp:
        summary_json = json.load(fp)

    fig = plt.figure(figsize=(8, 3))
    ax = fig.add_subplot(1, 1, 1)

    # Calculate total and normalize values
    total = (
        summary_json["co2e_metric_tons"]["gwp50"]["nighttime"]["total"]
        + summary_json["co2e_metric_tons"]["gwp50"]["daytime"]["total"]
    )
    normalized_values = [
        v / total
        for v in [
            summary_json["co2e_metric_tons"]["gwp50"]["nighttime"]["total"],
            summary_json["co2e_metric_tons"]["gwp50"]["daytime"]["total"],
        ]
    ]
    colors = ["#2C2857", "#F7CA45"]

    left = 0
    for value, color in zip(normalized_values, colors):
        ax.barh("Tons warming", value, color=color, left=left)
        left += value

    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_visible(False)

    plt.subplots_adjust(left=0.01, right=1.04, top=0.99, bottom=0.01)
    plt.savefig(f"{out_path}/fig_contrail_warming_daytime_vs_nighttime.png")


def _gen_od_bar_figs(summary_json_fp: str, out_path: str):
    with open(summary_json_fp, "r") as fp:
        summary_json = json.load(fp)

    # remove None-None OD-pair from consideration
    # (case where origin/destination airport code not reported in Spire)
    od_pruned = []
    for itm in summary_json["od_pairs"]:
        od = itm["airport_iata_od"]
        o = od.split("_")[0]
        d = od.split("_")[0]
        if o == "None" or d == "None":
            continue
        od_pruned.append(itm)

    # ----------------------------------
    # BY NET CO2e
    # ----------------------------------
    od_pruned.sort(key=lambda itm: itm["co2e50_metric_tons"], reverse=True)

    top_ods_by_net_co2e = od_pruned[:10]

    fig_w = 9  # inch
    fig_h = 4  # inch
    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)

    night_co2e_grp = [
        int(
            itm["co2e50_metric_tons"] * min(itm["percentage_nighttime_co2e"], 100) / 100
        )
        for itm in top_ods_by_net_co2e
    ]
    day_co2e_grp = [
        int(
            itm["co2e50_metric_tons"]
            * (100 - min(itm["percentage_nighttime_co2e"], 100))
            / 100
        )
        for itm in top_ods_by_net_co2e
    ]
    flight_count = [itm["flight_count"] for itm in top_ods_by_net_co2e]
    flight_dist_km = [round(int(itm["tot_dist_km"]), -2) for itm in top_ods_by_net_co2e]
    grp_names = [
        itm["airport_iata_od"].replace("_", " - ") for itm in top_ods_by_net_co2e
    ]

    night_co2e_grp.reverse()
    day_co2e_grp.reverse()
    flight_count.reverse()
    grp_names.reverse()

    # Plot the stacked bars
    night_bar = ax.barh(grp_names, night_co2e_grp, color="#2C2857", zorder=2)
    day_bar = ax.barh(
        grp_names, day_co2e_grp, left=night_co2e_grp, color="#F7CA45", zorder=2
    )

    max_co2e = max([int(itm["co2e50_metric_tons"]) for itm in top_ods_by_net_co2e])
    x_range = list(np.arange(0, max_co2e + 5000, 5000))
    x_range_labels = [f"{i:,}t CO2e" for i in x_range]
    ax.set_xticks(x_range, labels=x_range_labels)

    ax.xaxis.set_minor_locator(MultipleLocator(1000))
    ax.grid(
        axis="x",
        which="minor",
        linewidth=1.5,
        linestyle="dotted",
        color="#C4C7C5",
        zorder=0,
    )
    ax.grid(
        axis="x",
        which="major",
        linewidth=1.5,
        linestyle="dotted",
        color="#C4C7C5",
        zorder=0,
    )

    # set margins
    min_bar_width = night_bar[0].get_width() + day_bar[0].get_width()
    inline_flights_margin = min_bar_width * 0.05
    inline_km_margin = min_bar_width * 0.5
    inline_co2e_padding = min_bar_width * 0.01

    # set flight count inline text
    for ix, bar in enumerate(night_bar):
        label_text = f"{flight_count[ix]} Flights"
        ax.text(
            inline_flights_margin,
            bar.get_y() + bar.get_height() / 2,
            label_text,
            ha="left",
            va="center",
            color="white",
        )

    # set flight distance km inline text
    for ix, bar in enumerate(night_bar):
        label_text = f"{round(flight_dist_km[ix]/1000.):,}K km"
        ax.text(
            inline_km_margin,
            bar.get_y() + bar.get_height() / 2,
            label_text,
            ha="left",
            va="center",
            color="white",
        )

    # set total co2e inline text
    for ix, bars in enumerate(zip(night_bar, day_bar)):
        total_co2e = int(night_co2e_grp[ix] + day_co2e_grp[ix])
        label_text = f"{total_co2e/1000:.0f}kt CO2e"
        ax.text(
            bars[0].get_width() + bars[1].get_width() + inline_co2e_padding,
            bars[0].get_y() + bars[0].get_height() / 2,
            label_text,
            ha="left",
            va="center",
            color="black",
        )

    # set impact density on RHS of axes
    # ax_offset = 4030
    # cmap = plt.get_cmap("hot")
    # c_min = min(impact_kgco2e_per_km)
    # c_max = max(impact_kgco2e_per_km)
    # c_offset = (c_max - c_min) / 2
    # norm = plt.Normalize(c_min, c_max + 3 * c_offset)
    # colors = cmap(norm(impact_kgco2e_per_km))
    # for ix, bar in enumerate(night_bar):
    #    label_text = f"{impact_kgco2e_per_km[ix]}kg CO2e/km"
    #    ax.text(
    #        ax_offset,
    #        bar.get_y() + bar.get_height() / 2,
    #        label_text,
    #        ha="left",
    #        va="center",
    #        color=colors[ix],
    #    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color("#C4C7C5")
    ax.spines["bottom"].set_linewidth(5)

    ax = plt.gca()
    lf = ax.figure.subplotpars.left
    r = ax.figure.subplotpars.right
    t = ax.figure.subplotpars.top
    b = ax.figure.subplotpars.bottom
    figw = float(fig_w) / (r - lf)
    figh = float(fig_h) / (t - b)
    ax.figure.set_size_inches(figw, figh)
    plt.savefig(f"{out_path}/fig_od_by_net_co2e.png")

    # ----------------------------------
    # BY IMPACT DENSITY
    # ----------------------------------
    od_pruned.sort(
        key=lambda i: i["impact_density_co2e_metric_tons_per_dist_km"],
        reverse=True,
    )
    top_ods_by_impact_density = od_pruned[:10]

    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)

    impact_kgco2e_per_km = [
        int(itm["impact_density_co2e_metric_tons_per_dist_km"] * 1000)
        for itm in top_ods_by_impact_density
    ]
    flight_count = [itm["flight_count"] for itm in top_ods_by_impact_density]
    flight_dist_km = [
        round(int(itm["tot_dist_km"]), -2) for itm in top_ods_by_impact_density
    ]
    grp_names = [
        itm["airport_iata_od"].replace("_", " - ") for itm in top_ods_by_impact_density
    ]

    impact_kgco2e_per_km.reverse()
    flight_count.reverse()
    flight_dist_km.reverse()
    grp_names.reverse()
    # Plot the stacked bars
    bars = ax.barh(grp_names, impact_kgco2e_per_km, color="#2C2857", zorder=2)

    max_x = max([int(itm) for itm in impact_kgco2e_per_km])
    x_range = list(np.arange(0, max_x + 20, 10))
    x_range_labels = [f"{i:,}kg CO2e/km" for i in x_range]
    ax.set_xticks(x_range, labels=x_range_labels)

    ax.xaxis.set_minor_locator(MultipleLocator(2))
    ax.grid(
        axis="x",
        which="minor",
        linewidth=1.5,
        linestyle="dotted",
        color="#C4C7C5",
        zorder=0,
    )
    ax.grid(
        axis="x",
        which="major",
        linewidth=1.5,
        linestyle="dotted",
        color="#C4C7C5",
        zorder=0,
    )

    # set margins
    min_bar_width = bars[0].get_width()
    inline_flights_margin = min_bar_width * 0.05
    inline_km_margin = min_bar_width * 0.3
    inline_co2e_per_kg_padding = min_bar_width * 0.01

    # set flight count inline text
    for ix, bar in enumerate(bars):
        label_text = f"{flight_count[ix]} Flights"
        ax.text(
            inline_flights_margin,
            bar.get_y() + bar.get_height() / 2,
            label_text,
            ha="left",
            va="center",
            color="white",
        )

    # set flight distance km inline text
    for ix, bar in enumerate(bars):
        label_text = f"{round(flight_dist_km[ix] / 1000.):,}K km"
        ax.text(
            inline_km_margin,
            bar.get_y() + bar.get_height() / 2,
            label_text,
            ha="left",
            va="center",
            color="white",
        )

    # set co2e per kg inline text
    for ix, bar in enumerate(bars):
        label_text = f"{impact_kgco2e_per_km[ix]}kg CO2e/km"
        ax.text(
            bar.get_width() + inline_co2e_per_kg_padding,
            bar.get_y() + bar.get_height() / 2,
            label_text,
            ha="left",
            va="center",
            color="black",
        )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color("#C4C7C5")
    ax.spines["bottom"].set_linewidth(5)

    # title_str = "OD Pairs"
    # ax.set_title(title_str, x=-0.05)
    ax = plt.gca()
    lf = ax.figure.subplotpars.left
    r = ax.figure.subplotpars.right
    t = ax.figure.subplotpars.top
    b = ax.figure.subplotpars.bottom
    fig_w = 9  # inch
    fig_h = 4  # inch
    figw = float(fig_w) / (r - lf)
    figh = float(fig_h) / (t - b)
    ax.figure.set_size_inches(figw, figh)

    plt.savefig(f"{out_path}/fig_od_by_impact_density.png")


def _gen_case_study_fig(data_case_study_fp: str, out_path: str):
    """
    Generate case study plots.

    Parameters
    ----------
    data_case_study_fp
        Fully qualified path to a csv file containing a single flights per-segment data.
    out_path
        Directory path for exporting the rendered fig.
    """

    seg_df = pd.read_csv(data_case_study_fp)

    # -----------------
    # export case study plots
    # -----------------
    seg_df.sort_values(["time_start"], inplace=True)
    seg_df.reset_index(inplace=True, drop=True)
    seg_df.loc[:, "dist_cum_km"] = seg_df["chunk_len_km"].cumsum()

    fig = plt.figure(figsize=(7, 2))
    ax = fig.add_subplot(1, 1, 1)

    x_v = seg_df["dist_cum_km"]
    y_v = seg_df["median_altitude_ft"] / 100.0

    min_x = -100
    max_x = seg_df["dist_cum_km"].max() + 100
    min_y = y_v.min() - 10
    max_y = y_v.max() + 45

    x_contrails_pred = x_v[seg_df["sum_ef_mj"] != 0]
    y_contrails_pred = y_v[seg_df["sum_ef_mj"] != 0]

    x_contrails_attr = x_v[seg_df["goog_is_attributed"] != 0]
    y_contrails_attr = y_v[seg_df["goog_is_attributed"] != 0]

    x_conus_min = seg_df[seg_df["in_conus"]]["dist_cum_km"].min()
    x_conus_max = seg_df[seg_df["in_conus"]]["dist_cum_km"].max()

    conus_patch = plt.Rectangle(
        (x_conus_min, min_y),
        x_conus_max - x_conus_min,
        max_y - min_y,
        alpha=0.4,
        facecolor="#F7CA45",
    )
    ax.add_patch(conus_patch)

    ax.scatter(
        x_contrails_pred,
        y_contrails_pred,
        color="#D3E3FD",
        s=1000,
    )
    ax.scatter(
        x_contrails_attr,
        y_contrails_attr,
        color="#F7CA45",
        s=400,
    )
    ax.plot(
        x_v,
        y_v,
        color="black",
        linewidth=2.5,
    )

    ax.grid(axis="y", linewidth=1.5, linestyle="dotted", color="#C4C7C5")

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color("#C4C7C5")
    ax.spines["bottom"].set_linewidth(5)

    x_range = list(np.arange(0, 20000, 1000))
    x_range_labels = [f"{i/1000:.0f}k km" for i in x_range]
    ax.set_xticks(x_range, labels=x_range_labels, rotation=90)

    y_range = list(np.arange(100, 500, 50))
    y_range_labels = [f"FL{i}" for i in y_range]
    ax.set_yticks(y_range, labels=y_range_labels)

    ax.set_xlim([min_x, max_x])
    ax.set_ylim([min_y, max_y])

    legend_elements = [
        lines.Line2D(
            [0],
            [0],
            color="black",
            linewidth=2.5,
            label="Flight path",
        ),
        lines.Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#D3E3FD",
            markersize=10,
            label="Predicted contrails",
        ),
        lines.Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#F7CA45",
            markersize=10,
            label="Confirmed contrails",
        ),
        patches.Rectangle(
            (0, 0),
            1,
            1,
            facecolor="#F7CA45",
            alpha=0.4,
            label="Observation region",
        ),
    ]

    ax.legend(
        handles=legend_elements,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.5),
        ncol=4,
        frameon=False,
        fontsize=9.3,
    )

    plt.savefig(
        f"{out_path}/fig_case_study.png",
        bbox_inches="tight",
    )


def load_data(json_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        data["data_path"] = os.path.dirname(json_path)

        # Validate the data structure:
        if not isinstance(data, dict):
            raise ValueError("Invalid data structure: expected a dictionary")
        return data
    except Exception as e:
        print("Error loading data:", e)
        return None


def register_fonts() -> None:
    FONT_PATH = "fonts/"
    pdfmetrics.registerFont(TTFont("Roboto", FONT_PATH + "Roboto/Roboto-Regular.ttf"))
    pdfmetrics.registerFont(
        TTFont("Roboto-Light", FONT_PATH + "Roboto/Roboto-Light.ttf")
    )
    pdfmetrics.registerFont(
        TTFont("Roboto-Medium", FONT_PATH + "Roboto/Roboto-Medium.ttf")
    )


def format_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:,.1f}M"
    elif n >= 1000:
        return f"{n/1000:,.0f}k"
    return f"{n:,}"


def draw_grid(c: Any, page_width: float, page_height: float) -> None:
    """Draw a grid with lines every 1/4 inch (18 points), with inch lines bolded"""
    c.saveState()
    # Set stroke color with transparency (alpha value)
    c.setStrokeColorRGB(
        0.5, 0.5, 0.5, alpha=0.3
    )  # RGB values for gray with 30% opacity

    # Grid spacing (1/4 inch = 18 points since 72 points = 1 inch),
    # but the example pdf looks to have 15 points (10 big segments across?)
    small_grid_spacing = int(18 * scaling_factor)
    inch_grid_spacing = int(72 * scaling_factor)

    c.setLineWidth(0.1)
    for x in range(0, int(page_width), small_grid_spacing):
        c.line(x, 0, x, page_height)

    for y in range(0, int(page_height), small_grid_spacing):
        c.line(0, y, page_width, y)

    c.setLineWidth(1)
    for x in range(0, int(page_width), inch_grid_spacing):
        c.line(x, 0, x, page_height)

    for y in range(0, int(page_height), inch_grid_spacing):
        c.line(0, y, page_width, y)

    c.restoreState()


def draw_text_block(
    c,
    text,
    x,
    y,
    font_name="Roboto",
    font_size=container_text_font_size,
    width=520,
    height=None,
    align="left",
    color=text_color,
) -> float:
    """Draw a block of text"""
    from reportlab.lib.utils import simpleSplit

    c.setFont(font_name, font_size)
    c.setFillColor(color)  # Set the text color

    # Split text into paragraphs
    paragraphs = text.split("\n\n")
    current_y = y

    for paragraph in paragraphs:
        lines = simpleSplit(paragraph.strip(), font_name, font_size, width)
        for line in lines:
            if align == "center":
                line_width = c.stringWidth(line, font_name, font_size)
                line_x = x + (width - line_width) / 2
            elif align == "right":
                line_width = c.stringWidth(line, font_name, font_size)
                line_x = x + width - line_width
            else:  # left align (default)
                line_x = x

            c.drawString(line_x, current_y, line)
            current_y -= font_size * 1.2
        # Add extra space between paragraphs
        current_y -= font_size * 0.8

    return current_y


def draw_container(
    c: Any, x: float, y: float, width: float, height: float, radius: float = 10
) -> float:
    """Helper function to draw rounded rectangle containers"""
    c.setStrokeColor(container_color)
    c.roundRect(x, y, width, height, radius, fill=0, stroke=1)
    c.setFillColor(text_color)
    return y - vertical_spacing


def draw_stat_with_info_symbol(
    c,
    key,
    number,
    unit,
    x,
    y,
    font_size=8,
    number_font_size=24,
) -> float:
    """Draw a statistic with an info symbol next to it."""
    # draw stat label (e.g. # of flights)
    c.setFont("Roboto-Medium", font_size)
    c.setFillColor("#868686")
    c.drawString(x, y, key)

    # draw number value
    c.setFont("Roboto", number_font_size)
    c.setFillColor(text_color)
    number_width = c.stringWidth(number, "Roboto", number_font_size)
    c.drawString(x, y - (number_font_size - font_size) - 10, number)

    # draw units
    c.setFont("Roboto-Medium", font_size)
    c.setFillColor(text_color)
    c.drawString(
        x + number_width + 5,
        y - 26,
        unit,
    )

    current_y = y - (number_font_size - font_size) - 20
    return current_y


def draw_stat_for_plots(
    c,
    key,
    number,
    unit,
    x,
    y,
    font_name="Roboto",
    font_size=8,
    number_font_size=22,
    text_color=background_text_color,
) -> float:
    """Draw a statistic with the unit next to it, and the description smaller and just above it.."""
    c.setFont(font_name, font_size)
    c.setFillColor(text_color)
    c.drawString(x, y, key)

    c.setFont(font_name, number_font_size)
    c.setFillColor(text_color)
    c.drawString(x, y - (number_font_size - font_size) - 10, number + " " + unit)

    current_y = y - (number_font_size - font_size) - 20
    return current_y


def create_page_one(c: Any, data: Dict[str, Any], airline_name: str) -> Any:
    """Generate the first page of the report"""
    c.drawImage(
        f"static/logos/{airline_name}_logo.png",
        left_margin,
        750,
        width=60,
        height=60,
    )

    c.setFillColor(background_text_color)
    c.setFont("Roboto", 10)
    c.drawString(525, 812, "Page 1 of 5")

    c.setFillColor(title_color)
    c.setFont("Roboto", 26)
    c.drawString(30, 750 - 28, "Airline Contrail Impact Report 2024")

    # What are Contrails? section
    draw_container(
        c=c,
        x=left_margin,
        y=510,
        width=page_width - left_margin * 2 + 5,
        height=195,
    )

    c.setFont("Roboto", container_title_font_size)
    current_y = draw_text_block(
        c=c,
        text="What are Contrails?",
        x=left_margin + horizontal_spacing,
        y=710 - 28,
        font_name="Roboto",
        font_size=container_title_font_size,
    )

    contrails_text = """Contrails — the thin, white lines you sometimes see behind airplanes — have a surprisingly large impact on our climate. Contrails warm the planet because contrail clouds act like a blanket on Earth and have a net heating effect. The 2022 IPCC report noted that clouds created by contrails account for roughly 35% of aviation's global warming impact — over half the impact of the world's jet fuel. Find more info about contrails and the climate on our website"""
    current_y = draw_text_block(
        c=c,
        text=contrails_text,
        x=left_margin + horizontal_spacing,
        y=current_y + header_offset,
        font_name="Roboto",
        font_size=container_text_font_size,
    )

    link_text = "contrails.org."
    c.setFont("Roboto", container_text_font_size)
    after_text_width = 187
    c.setFillColor(text_color)

    c.drawString(
        x=left_margin + after_text_width + 2,
        y=current_y + 17,
        text=link_text,
    )

    link_width = c.stringWidth(link_text, "Roboto", container_text_font_size)

    c.line(
        left_margin + after_text_width + 2,
        current_y + 15,
        left_margin + after_text_width + link_width + 2,
        current_y + 15,
    )

    c.linkURL(
        "https://www.contrails.org",
        (
            left_margin + after_text_width + 2,
            current_y + (9 * 2) - 1,
            left_margin + after_text_width + link_width + 2,
            current_y + (9 * 2) + 8,
        ),
        color=colors.HexColor(hyperlink_text_color),
    )
    c.setFillColor(text_color)

    current_y = draw_text_block(
        c=c,
        text="What is Global Warming Potential (GWP)?",
        x=left_margin + horizontal_spacing,
        y=current_y - vertical_spacing,
        font_name="Roboto",
        font_size=container_title_font_size,
    )
    gwp_text = """GWP measures how much warming contrails cause over a number of years compared to CO2. Contrails heat the Earth quickly but for a short time, and GWP helps compare their short-term impact to the longer-lasting greenhouse gas, CO2.

    In this report we initially show the contrail impact in CO2e over 20, 50 and 100 years to align with the guidelines from the EU Non-CO2 MRV reporting that is mandatory from 2025. Wherever we only show one value for CO2e we use the middle value, GWP50, as default.  If you want to convert a GWP50 value to GWP100, multiply by 0.57. If you want to convert a GWP50 value to GWP20, multiply by 2.10."""
    current_y = draw_text_block(
        c=c,
        text=gwp_text,
        x=left_margin + horizontal_spacing,
        y=current_y + header_offset,
        font_name="Roboto",
        font_size=container_text_font_size,
    )

    draw_container(
        c=c,
        x=left_margin,
        y=120,
        width=container_width,
        height=6.25 * 72 * scaling_factor,
    )
    c.setFont("Roboto", 16)
    current_y = draw_text_block(
        c=c,
        text="Impact Data",
        x=left_margin + horizontal_spacing,
        y=472,
        font_name="Roboto",
        font_size=container_title_font_size,
    )
    stats_text = f"""Based on our prediction model, {round(data['flight_distance_km']['with_contrails']['is_warming']['total'], -3):,} km or {data['percentages']['flight_distance_with_warming_contrails']}% of all {airline_name} flights generated warming contrails in 2024."""
    current_y = draw_text_block(
        c=c,
        text=stats_text,
        x=left_margin + horizontal_spacing,
        y=current_y + header_offset,
        font_name="Roboto",
        font_size=container_text_font_size,
    )

    stats_data = {
        "# of Flights": {
            "value": f"{data['count_flights']['total']:,}",
            "unit": "flights",
        },
        "Flight hours": {
            "value": f"{data['flight_hours']['total']:,}",
            "unit": "hours",
        },
        "Contrails (GWP 50)": {
            "value": f"{format_number(data['co2e_metric_tons']['gwp50']['total'])}",
            "unit": "tonnes CO2e",
        },
        "Fuel Burn": {
            "value": f"{format_number(data['co2_metric_tons']['total'])}",
            "unit": "tonnes CO2",
        },
    }

    y = current_y - 20
    x = left_margin + horizontal_spacing
    spacing_between_stats = 140

    for key, stat in stats_data.items():
        number = stat["value"]
        unit = stat["unit"]

        draw_stat_with_info_symbol(
            c=c,
            key=key,
            number=number,
            unit=unit,
            x=x,
            y=y,
            font_size=8,
            number_font_size=24,
        )

        x += spacing_between_stats

    c.setStrokeColor(container_color)
    c.setLineWidth(0.5)
    c.line(left_margin, y - 55, page_width - left_margin + 5, y - 55)

    container_bottom = y - (467 + 18) * scaling_factor
    midpoint_x = (left_margin + (page_width - left_margin + 5)) / 2
    midpoint_y = (y - 118 + container_bottom) / 2

    c.line(midpoint_x, y - 55, midpoint_x, y - 297)

    # Pie chart
    # TODO: Comment from Joachim: Also, the lower bar should be 10.4% of the upper bar - corresponding to the value in the circle to the left, correct?
    # The image is currently a bit confusing because the title and plot are in reference to percent of flights, whereas the stat in the middle is about percent of flight *distance*
    c.drawImage(
        data["data_path"] + "/figs/fig_contrail_warming_percentage.png",
        x=60,
        y=121,
        width=495 * 0.42,
        height=514 * 0.42,
    )

    draw_text_block(
        c=c,
        text="Flight distance where warming contrails were created",
        x=left_margin + horizontal_spacing,
        y=midpoint_y + 180,
        font_name="Roboto",
        font_size=container_title_font_size - 2,
        width=midpoint_x - left_margin - horizontal_spacing,
    )

    draw_text_block(
        c=c,
        text=f"{data['percentages']['flight_distance_with_warming_contrails']}%",
        x=midpoint_x / 3 + 40,
        y=237,
        font_name="Roboto",
        font_size=24,
        width=midpoint_x - left_margin - horizontal_spacing,
    )
    draw_text_block(
        c=c,
        text=f"of {data['airline_name']} flight distance generated warming contrails",
        x=midpoint_x / 3 + 15,
        y=220,
        font_name="Roboto",
        font_size=container_text_font_size,
        width=100,
        color=background_text_color,
        align="center",
    )

    current_y = draw_text_block(
        c=c,
        text="How many flight kilometers created warming contrails?",
        x=midpoint_x + horizontal_spacing,
        y=midpoint_y + 180,
        font_name="Roboto",
        font_size=container_title_font_size - 2,
        width=midpoint_x - left_margin - horizontal_spacing,
    )
    c.drawImage(
        data["data_path"] + "/figs/fig_distance_daytime_nighttime.png",
        x=midpoint_x + horizontal_spacing - 3,
        y=215,
        width=396 * 0.61,
        height=99 * 0.61,
    )
    current_y = draw_stat_with_info_symbol(
        c,
        key="Total flight kilometers",
        number=format_number(data["flight_distance_km"]["total"]),
        unit="km",
        x=midpoint_x + horizontal_spacing,
        y=current_y,
    )

    c.drawImage(
        data["data_path"] + "/figs/fig_contrail_distance_warming_daytime_nighttime.png",
        x=midpoint_x + horizontal_spacing - 3,
        y=123,
        width=396 * 0.61,
        height=107 * 0.61,
    )
    draw_stat_with_info_symbol(
        c,
        key="Flight kilometers creating warming contrails",
        number=format_number(
            data["flight_distance_km"]["with_contrails"]["is_warming"]["total"]
        ),
        unit="km",
        x=midpoint_x + horizontal_spacing,
        y=current_y - 50,
    )

    return c


def create_page_two(c: Any, data: Dict[str, Any]) -> None:
    """Generate the second page of the report"""
    c.setFont("Roboto", 10)
    c.setFillColor(background_text_color)
    c.drawString(525, 812, "Page 2 of 5")

    # Euro section

    current_y = draw_text_block(
        c=c,
        text="Impact Data: intra-European flights only",
        x=left_margin + horizontal_spacing,
        y=770,
        font_size=16,
    )
    c.drawImage(
        "static/Europe Map_trimmed.png",
        x=page_width / 2 + 90,
        y=555,
        width=72 * 2.55 * scaling_factor,
        height=72 * 2.7 * scaling_factor,
    )

    draw_container(
        c=c,
        x=left_margin,
        y=555,
        width=page_width - left_margin * 2 + 5,
        height=72 * 4 * scaling_factor,
    )

    description = """Based on our prediction model, this is the impact from the DHL flights that are included in the EU's non-CO2 reporting requirements. The EU ETS area covers flights within and between countries in the European Economic Area (EEA), which consists of EU member states and Iceland, Norway, and Liechtenstein, and from the EEA to the UK and Switzerland. It also covers the EU's nine, so-called outermost regions: French Guiana, Guadeloupe, Martinique, Mayotte, Réunion Island, Saint-Martin, Azores, Madeira, and The Canary Islands."""
    current_y = draw_text_block(
        c=c,
        text=description,
        x=left_margin + horizontal_spacing,
        y=current_y + header_offset,
    )

    stats_data = {
        "# of Flights": {
            "value": f"{data['count_flights']['in_eu']:,}",
            "unit": "flights",
        },
        "Flight distance": {
            "value": f"{data['flight_distance_km']['in_eu']:,}",
            "unit": "km",
        },
        "Contrails (GWP 50)": {
            "value": f"{format_number(data['co2e_metric_tons']['gwp50']['in_eu'])}",
            "unit": "tonnes CO2e",
        },
        "Fuel burn": {
            "value": f"{format_number(data['co2_metric_tons']['total'])}",
            "unit": "tonnes CO2",
        },
    }
    y = current_y - 20
    x = left_margin + horizontal_spacing
    spacing_between_stats = 140

    counter = 0
    for key, stat in stats_data.items():
        number = stat["value"]
        unit = stat["unit"]
        if counter > 1:
            x = left_margin + horizontal_spacing
            y -= 70
            counter = 0
        draw_stat_with_info_symbol(
            c=c,
            key=key,
            number=number,
            unit=unit,
            x=x,
            y=y,
            font_size=8,
            number_font_size=24,
        )
        counter += 1
        x += spacing_between_stats

    # Observation coverage area & verification section
    draw_container(
        c=c,
        x=left_margin,
        y=2.25 * 72 * scaling_factor,
        width=page_width / 2 - left_margin,
        height=72 * 6.75 * scaling_factor,
    )

    current_y = draw_text_block(
        c=c,
        text="Observation coverage area & verification",
        x=left_margin + horizontal_spacing,
        y=517,
        width=page_width / 2 - 65,
        font_size=container_title_font_size,
    )
    c.drawImage(
        data["data_path"] + "/figs/map.png",
        x=left_margin + horizontal_spacing,
        y=4.25 * 72 * scaling_factor,
        width=794 * 0.3,
        height=667 * 0.3,
    )

    current_y = draw_text_block(
        c=c,
        text="""The yellow area shows the coverage region where our satellite image based verification has been validated. For the rest of the world, we use our algorithm predictions.""",
        x=left_margin + horizontal_spacing,
        y=current_y + header_offset,
        width=page_width / 2 - 65,
        font_size=container_text_font_size,
    )

    current_y = draw_stat_with_info_symbol(
        c=c,
        x=left_margin + horizontal_spacing,
        y=230,
        key="Predicted contrail warming in observation area",
        number=format_number(data["co2e_metric_tons"]["gwp50"]["in_conus"]),
        unit="tonnes CO2e",
    )
    current_y = draw_stat_with_info_symbol(
        c=c,
        x=left_margin + horizontal_spacing,
        y=current_y - vertical_spacing * 2.2,
        key="Verified contrails warming in observation area",
        number=format_number(data["co2e_metric_tons"]["gwp50"]["goog_sat_verified"]),
        unit="tonnes CO2e",
    )

    # Contrail warming section
    draw_container(
        c=c,
        x=left_margin / 2 + page_width / 2 + 3,
        y=2.25 * 72 * scaling_factor,
        width=page_width / 2 - left_margin - horizontal_spacing - 3,
        height=72 * 6.75 * scaling_factor,
    )

    current_y = draw_text_block(
        c=c,
        x=left_margin / 2 + horizontal_spacing + page_width / 2 + 3,
        y=515,
        text="Contrail warming using different time horizons: GWP20, GWP50, and GWP100.",
        width=page_width / 2 - 65,
        font_size=container_title_font_size,
    )

    current_y = draw_text_block(
        c=c,
        x=left_margin / 2 + horizontal_spacing + page_width / 2 + 3,
        y=current_y + header_offset,
        text="""There is no single “correct” way to convert contrail warming to CO2e. This is partly because the lifetime of a single contrail (hours) is much shorter than the lifetime of CO2 in the atmosphere (hundreds to thousands of years). So when using the Global Warming Potential (GWP) metric and comparing contrail warming to the warming from CO2 over 20 years, the contrail warming will be about four times higher than if comparing to CO2 over 100 years. We show GWP20, GWP50, and GWP100 to align with the EU MRV guidelines. The middle value, GWP50, is used as the default in the report.""",
        width=page_width / 2 - 65,
        font_size=container_text_font_size,
    )

    current_y = draw_stat_with_info_symbol(
        c=c,
        x=left_margin / 2 + horizontal_spacing + page_width / 2 + 3,
        y=current_y - vertical_spacing,
        key="GWP 100",
        number=format_number(data["co2e_metric_tons"]["gwp100"]["total"]),
        unit="tonnes CO2e",
    )
    denom = data["co2e_metric_tons"]["gwp20"]["total"]
    bar_widths_fractions = [
        data["co2e_metric_tons"]["gwp100"]["total"] / denom,
        data["co2e_metric_tons"]["gwp50"]["total"] / denom,
        1,
    ]

    c.drawImage(
        "static/horizontal_bar_gwp_warming.png",
        x=left_margin / 2 + horizontal_spacing + page_width / 2,
        y=current_y - vertical_spacing * 1.2,
        width=bar_widths_fractions[0] * page_width / 2.45,
        height=72 * 0.25 * scaling_factor,
    )
    current_y = draw_stat_with_info_symbol(
        c=c,
        x=left_margin / 2 + horizontal_spacing + page_width / 2 + 3,
        y=current_y - vertical_spacing * 3,
        key="GWP 50",
        number=format_number(data["co2e_metric_tons"]["gwp50"]["total"]),
        unit="tonnes CO2e",
    )
    c.drawImage(
        "static/horizontal_bar_gwp_warming.png",
        x=left_margin / 2 + horizontal_spacing + page_width / 2 - 0.5,
        y=current_y - vertical_spacing * 1.2,
        width=bar_widths_fractions[1] * page_width / 2.45,
        height=72 * 0.25 * scaling_factor,
    )
    current_y = draw_stat_with_info_symbol(
        c=c,
        x=left_margin / 2 + horizontal_spacing + page_width / 2 + 3,
        y=current_y - vertical_spacing * 3,
        key="GWP 20",
        number=format_number(data["co2e_metric_tons"]["gwp20"]["total"]),
        unit="tonnes CO2e",
    )
    c.drawImage(
        "static/horizontal_bar_gwp_warming.png",
        x=left_margin / 2 + horizontal_spacing + page_width / 2 - 2.25,
        y=current_y - vertical_spacing * 1.2,
        width=page_width / 2.45,
        height=72 * 0.25 * scaling_factor,
    )


def create_page_three(c: Any, data: Dict[str, Any]) -> Any:
    """Generate the third page of the report"""

    c.setFillColor(background_text_color)
    c.setFont("Roboto", 10)
    c.drawString(525, 812, "Page 3 of 5")

    # Fuel emissions (CO2) vs contrail warming (CO2e) GWP50
    draw_container(
        c=c,
        x=left_margin,
        y=615,
        width=page_width - left_margin * 2 + 5,
        height=72 * 3 * scaling_factor,
    )

    current_y = draw_text_block(
        c=c,
        text="Fuel emissions (CO2) vs contrail warming (CO2e) (GWP50)",
        x=left_margin + horizontal_spacing,
        y=771,
        font_size=container_title_font_size,
    )
    c.drawImage(
        data["data_path"] + "/figs/fuel_vs_contrail_co2.png",
        x=39,
        y=627,
        width=page_width - left_margin * 3 + 14,
        height=72 * 1.75 * scaling_factor,
    )
    fuel_percent_of_total = 100 * (
        data["co2_metric_tons"]["total"]
        / (
            data["co2_metric_tons"]["total"]
            + data["co2e_metric_tons"]["gwp50"]["total"]
        )
    )
    contrail_percent_of_total = 100 * (
        data["co2e_metric_tons"]["gwp50"]["total"]
        / (
            data["co2_metric_tons"]["total"]
            + data["co2e_metric_tons"]["gwp50"]["total"]
        )
    )

    total_width = 504
    left_margin_plot = 55

    fuel_x = left_margin_plot
    contrail_x = left_margin_plot * 1.83 + (total_width - left_margin_plot) * (
        fuel_percent_of_total / 100
    )

    draw_stat_for_plots(
        c,
        key="Fuel emissions (tonnes CO2)",
        number=format_number(data["co2_metric_tons"]["total"]),
        unit=f"({fuel_percent_of_total:.0f}%)",
        x=fuel_x,
        y=700,
        text_color="white",
    )

    draw_stat_for_plots(
        c,
        key="Contrails (tonnes CO2e)",
        number=format_number(data["co2e_metric_tons"]["gwp50"]["total"]),
        unit=f"({contrail_percent_of_total:.0f}%)",
        x=contrail_x,
        y=700,
        text_color="white",
    )

    description = (
        "The impact of contrail warming measured in CO2e (GWP 50) in relation to the impact of the CO2 emissions from fuel burn can vary from day to day, "
        "season to season, and even from year to year -- just like the weather on Earth varies across seasons and years."
    )
    _ = draw_text_block(
        c=c,
        text=description,
        x=left_margin + horizontal_spacing,
        y=current_y + header_offset,
    )

    draw_container(
        c=c,
        x=left_margin,
        y=410,
        width=page_width - left_margin * 2 + 5,
        height=3.25 * 72 * scaling_factor - 5,
    )
    current_y = draw_text_block(
        c=c,
        text="Contrail warming - daytime vs nighttime (GWP50)",
        x=left_margin + horizontal_spacing,
        y=576,
        font_size=container_title_font_size,
    )

    current_y = draw_text_block(
        c=c,
        text="""In the daytime, contrails sometimes have a cooling effect when reflecting some of the sun's heat back into space. But at all times, contrails have a warming effect by acting like a blanket on Earth. This is evident at night when there is no sunlight to reflect, and all contrails are warming.""",
        x=left_margin + horizontal_spacing,
        y=current_y + header_offset,
        font_size=container_text_font_size,
    )

    image_width = page_width - left_margin * 5.6
    c.drawImage(
        data["data_path"] + "/figs/fig_contrail_warming_daytime_vs_nighttime.png",
        x=38,
        y=current_y - vertical_spacing * 10,
        width=image_width,
        height=72 * 1.75 * scaling_factor,
    )

    nighttime_percent_of_total = 100 * (
        data["co2e_metric_tons"]["gwp50"]["nighttime"]["total"]
        / (
            data["co2e_metric_tons"]["gwp50"]["daytime"]["total"]
            + data["co2e_metric_tons"]["gwp50"]["nighttime"]["total"]
        )
    )
    daytime_percent_of_total = 100 * (
        data["co2e_metric_tons"]["gwp50"]["daytime"]["total"]
        / (
            data["co2e_metric_tons"]["gwp50"]["daytime"]["total"]
            + data["co2e_metric_tons"]["gwp50"]["nighttime"]["total"]
        )
    )

    nighttime_x = left_margin_plot
    daytime_x = left_margin_plot - 12 + image_width * (nighttime_percent_of_total / 100)

    draw_stat_for_plots(
        c,
        key="Nighttime (tonnes CO2e)",
        number=format_number(data["co2e_metric_tons"]["gwp50"]["nighttime"]["total"]),
        unit=f"({nighttime_percent_of_total:.0f}%)",
        x=nighttime_x - 2,
        y=current_y - vertical_spacing * 2.4,
        text_color="white",
    )

    draw_stat_for_plots(
        c,
        key="Daytime (tonnes CO2e)",
        number=format_number(data["co2e_metric_tons"]["gwp50"]["daytime"]["total"]),
        unit=f"({daytime_percent_of_total:.0f}%)",
        x=daytime_x,
        y=current_y - vertical_spacing * 2.4,
        text_color=background_text_color,
    )

    # Origin-Destination pairs with the highest average total contrail warming (GWP50 CO2e)
    c.drawImage(
        data["data_path"] + "/figs/fig_od_by_net_co2e.png",
        x=10,
        y=85,
        width=580,
        height=259,
    )
    current_y = draw_text_block(
        c=c,
        text="Origin-Destination pairs with the highest net contrail warming (GWP 50)",
        x=left_margin + horizontal_spacing,
        y=370,
        font_size=container_title_font_size,
    )
    current_y = draw_text_block(
        c=c,
        text=f"These ten OD pairs are responsible for 63% of {data['airline_name']}'s "
        f"total contrail warming. The most warming OD pairs are often very long flights "
        f"where the majority of the journey takes place in the dark, when contrails are most warming.",
        x=left_margin + horizontal_spacing,
        y=current_y + header_offset,
        font_size=container_text_font_size,
    )

    draw_container(
        c=c,
        x=left_margin,
        y=85,
        width=page_width - left_margin * 2 + 5,
        height=5 * 72 * scaling_factor + 10,
    )
    return c


def create_page_four(c: Any, data: Dict[str, Any]) -> Any:
    """Generate the fourth page of the report"""

    c.setFillColor(background_text_color)
    c.setFont("Roboto", 10)
    c.drawString(525, 812, "Page 4 of 5")

    # Fuel emissions (CO2) vs contrail warming (CO2e) GWP50

    current_y = draw_text_block(
        c=c,
        text="Origin-Destination pairs with the highest contrail warming per flown kilometer (GWP50)",
        x=left_margin + horizontal_spacing,
        y=772,
        font_size=container_title_font_size,
    )

    c.drawImage(
        data["data_path"] + "/figs/fig_od_by_impact_density.png",
        x=10,
        y=473,
        width=1161 * 0.5,
        height=519 * 0.5,
    )
    description = """The most warming OD pairs per flown kilometer are often flights that fly through contrail-prone zones (for example, the North Atlantic) at night when contrails are most warming.  The average carbon dioxide emissions for all flights were 21 kg CO2 / km.  For the OD pair with the highest contrail warming per kilometer, the CO2 emissions were 49 kg CO2e/km - or 2.3 times the average warming from the CO2 alone."""
    current_y = draw_text_block(
        c=c,
        text=description,
        x=left_margin + horizontal_spacing,
        y=current_y + header_offset,
        width=515,
    )
    draw_container(
        c=c,
        x=left_margin,
        y=480,
        width=page_width - left_margin * 2 + 5,
        height=72 * 5.25 * scaling_factor,
    )
    # Case study: predicted vs. verified contrails.
    c.drawImage(
        data["data_path"] + "/figs/fig_case_study.png",
        x=40,
        y=210,
        width=693 * 0.66,
        height=281 * 0.66,
    )
    draw_container(
        c=c,
        x=left_margin,
        y=210,
        width=page_width - left_margin * 2 + 5,
        height=4.25 * 72 * scaling_factor,
    )

    current_y = draw_text_block(
        c=c,
        text="Case study: predicted vs verified contrails",
        x=left_margin + horizontal_spacing,
        y=440,
        font_size=container_title_font_size,
    )

    # Flight trajectory case study
    data_case_study_fp = f"{data['data_path']}/data_case_study_0.csv"
    seg_df = pd.read_csv(data_case_study_fp)
    case_study_title_str = "{origin}-{dest} {date}".format(
        origin=seg_df.iloc[0]["departure_airport_iata"],
        dest=seg_df.iloc[0]["arrival_airport_iata"],
        date=pd.to_datetime(seg_df.iloc[0]["time_start_local_date"]).strftime(
            "%B %d, %Y"
        ),
    )

    draw_text_block(
        c=c,
        text=f"The light yellow color shows the observation area, and dark yellow indicates "
        f"verified contrail formation from satellite imagery within the observation area. "
        f"The light blue areas indicate where contrails are predicted to appear. "
        f"This is from flight {case_study_title_str}.",
        x=left_margin + horizontal_spacing,
        y=current_y + header_offset,
        font_size=container_text_font_size,
    )

    # Did You Know?
    # ------------
    draw_container(
        c=c,
        x=left_margin,
        y=10,
        width=page_width - left_margin * 2 + 5,
        height=3.1 * 72 * scaling_factor,
    )

    current_y = draw_text_block(
        c=c,
        text="""Did you know?""",
        x=left_margin + horizontal_spacing,
        y=170,
        font_size=container_title_font_size,
    )

    # current_x = left_margin + horizontal_spacing
    # y = current_y

    # First paragraph
    first_text = (
        "Some flight planning software providers, like Flightkeys and CAE, "
        "have implemented contrail avoidance in their flight planning tools "
        "(or are about to). \n\n\n\n In 2023, American Airlines, Google Research, "
        "and Breakthrough Energy conducted a trial (https://pub.contrails.org/guardian2023) "
        "in which they avoided 54% of contrail "
        "kilometers by flying under the contrail prone areas. \n\n\n\n In 2024, an extensive "
        "study (https://pub.contrails.org/frias032024rg) of over 84,000 flights showed that, "
        "theoretically, it was possible to "
        "eliminate 73% of the contrail warming from these flights by spending "
        "0.11% more jet fuel to adjust some of the flight paths. \n\n\n\n "
        "See where contrails are forming right now on the world map of contrails (https://map.contrails.org). "
        "The warming impact is often lower in the summer time and higher in the darker months. "
        "This is because contrail clouds that persist in the dark are the most warming. "
        "\n\n\n\n Explore the map and read more about contrails at https://contrails.org and https://sites.research.google/contrails/"
    )

    current_y = draw_text_block(
        c=c,
        text=first_text,
        x=left_margin + horizontal_spacing,
        y=current_y + header_offset,
        width=515,
    )

    """
    
    # contrails.org
    # https://sites.research.google/contrails/
    
    width = add_plain_text(
        c, first_text, current_x, y + header_offset, font_size=container_text_font_size
    )
    current_x += width
    width = add_text_with_link(
        c, "Flight Keys", "https://www.flightkeys.com", current_x, y + header_offset
    )
    current_x += width

    width = add_plain_text(c, " and ", current_x, y + header_offset)
    current_x += width

    width = add_text_with_link(
        c,
        "CAE",
        "https://www.cae.com/civil-aviation/aviation-software/flight-operations-solutions/flight-management/",
        current_x,
        y + header_offset,
    )
    current_x += width

    remaining_text = ", have implemented contrail avoidance in their flight planning tools (or are about to)."
    lines = wrap_text(
        c, remaining_text, text_width - (current_x - (left_margin + horizontal_spacing))
    )
    for i, line in enumerate(lines):
        if i == 0:
            add_plain_text(c, line, current_x, y + header_offset)
        else:
            y -= line_spacing - header_offset
            add_plain_text(c, line, left_margin + horizontal_spacing, y)

    # Move to next paragraph with extra spacing to prevent overlap
    y -= paragraph_spacing + line_spacing - header_offset

    # Second paragraph
    current_x = left_margin + horizontal_spacing
    intro_text = "In 2023, American Airlines, Google Research, and Breakthrough Energy conducted a "
    width = add_plain_text(c, intro_text, current_x, y)
    current_x += width

    width = add_text_with_link(
        c,
        "trial ",
        "https://www.theguardian.com/environment/2023/aug/09/ai-helps-airline-pilots-avoid-areas-that-create-polluting-contrails",
        current_x,
        y,
    )
    current_x += width

    remaining_text = " in which they avoided 54% of contrail kilometers by flying under contrail-prone areas."
    lines = wrap_text(
        c, remaining_text, text_width - (current_x - (left_margin + horizontal_spacing))
    )
    for i, line in enumerate(lines):
        if i == 0:
            add_plain_text(c, line, current_x, y)
        else:
            y -= line_spacing
            add_plain_text(c, line, left_margin + horizontal_spacing, y)

    y -= paragraph_spacing + line_spacing

    # Third paragraph
    current_x = left_margin + horizontal_spacing
    intro_text = "In 2024, an "
    width = add_plain_text(c, intro_text, current_x, y)
    current_x += width

    width = add_text_with_link(
        c,
        "extensive study ",
        "https://www.researchgate.net/publication/378811848_Feasibility_of_contrail_avoidance_in_a_commercial_flight_planning_system_an_operational_analysis",
        current_x,
        y,
    )
    current_x += width

    remaining_text = " of over 84,000 flights showed that, theoretically, it was possible to eliminate 73% of the contrail warming from these flights by spending 0.11% more jet fuel to adjust some of the flight paths."
    lines = wrap_text(
        c, remaining_text, text_width - (current_x - (left_margin + horizontal_spacing))
    )
    for i, line in enumerate(lines):
        if i == 0:
            add_plain_text(c, line, current_x, y)
        else:
            y -= line_spacing
            add_plain_text(c, line, left_margin + horizontal_spacing, y)

    y -= paragraph_spacing + line_spacing

    # Fourth paragraph
    current_x = left_margin + horizontal_spacing
    intro_text = "See where contrails are forming right now on this "
    width = add_plain_text(c, intro_text, current_x, y)
    current_x += width

    width = add_text_with_link(
        c, "world map of contrails", "https://map.contrails.org", current_x, y
    )
    current_x += width

    add_plain_text(
        c,
        ".  The contrail warming impact is often lower in the summer time ",
        current_x,
        y,
    )
    current_x = left_margin + horizontal_spacing
    y -= line_spacing
    add_plain_text(
        c,
        "and higher in the darker months. This is because contrail clouds that persist in the dark are the most warming.",
        current_x,
        y,
    )

    # Sixth paragraph
    y -= paragraph_spacing + line_spacing
    current_x = left_margin + horizontal_spacing
    intro_text = "Read more about contrails on "
    width = add_plain_text(c, intro_text, current_x, y)
    current_x += width

    width = add_text_with_link(
        c, "contrails.org", "https://contrails.org", current_x, y
    )
    current_x += width

    width = add_plain_text(c, ", and ", current_x, y)
    current_x += width

    width = add_text_with_link(
        c,
        "sites.research.google/contrails/",
        "https://sites.research.google/contrails/",
        current_x,
        y,
    )
    current_x += width

    add_plain_text(c, ".", current_x, y)
"""
    return c


def create_page_five(c: Any, data: Dict[str, Any]) -> Any:
    """Generate the fourth page of the report"""

    c.setFillColor(background_text_color)
    c.setFont("Roboto", 10)
    c.drawString(525, 812, "Page 5 of 5")

    # Fuel emissions (CO2) vs contrail warming (CO2e) GWP50

    current_y = draw_text_block(
        c=c,
        text="How do we validate our results?",
        x=left_margin + horizontal_spacing,
        y=772,
        font_size=container_title_font_size,
    )

    c.drawImage(
        "static/google_goes_frame.png",
        x=left_margin + horizontal_spacing,
        y=310,
        width=490,
        height=345,
    )
    description = (
        "Satellite observations of contrails can validate our results. "
        "We use machine learning to identify contrails in satellite images "
        "(https://pub.contrails.org/ng2024ieee) and match them to flight tracks "
        "(https://pub.contrails.org/geraedts012024er). Once we know how many kilometers "
        "of contrails have formed we multiply this by a warming per kilometer obtained "
        "by averaging many pycontrails simulations (https://pub.contrails.org/platt092024er). "
        "In the image below the blue lines represent detected contrails and the orange "
        "line is where we expect contrails to form for a target flight. \n\n\n\n "
        "In 2024 our reporting is based on the GOES satellites which cover the Americas, "
        "but starting in 2025 the Meteosat Third Generation satellite will "
        "enable European coverage."
    )
    _ = draw_text_block(
        c=c,
        text=description,
        x=left_margin + horizontal_spacing,
        y=current_y + header_offset,
        width=515,
    )

    draw_container(
        c=c,
        x=left_margin,
        y=290,
        width=page_width - left_margin * 2 + 5,
        height=8.4 * 72 * scaling_factor,
    )

    return c


def wrap_text(c, text, width, font="Roboto", font_size=container_text_font_size):
    """Split text into lines that fit within given width"""
    words = text.split()
    lines = []
    current_line = []
    current_width = 0

    for word in words:
        word_width = c.stringWidth(word + " ", font, font_size)
        if current_width + word_width <= width:
            current_line.append(word)
            current_width += word_width
        else:
            lines.append(" ".join(current_line))
            current_line = [word]
            current_width = word_width

    if current_line:
        lines.append(" ".join(current_line))
    return lines


def add_text_with_link(
    c, text, link_url, x, y, font="Roboto", font_size=container_text_font_size
):
    """Helper function to add text with a clickable link"""
    c.setFont(font, font_size)
    c.drawString(x=x, y=y, text=text)
    text_width = c.stringWidth(text, font, font_size)
    c.linkURL(
        link_url,
        (x, y - 2, x + text_width, y + 9),
        color=colors.HexColor(hyperlink_text_color),
    )
    return text_width


def add_plain_text(c, text, x, y, font="Roboto", font_size=container_text_font_size):
    """Helper function to add plain text and return its width"""
    c.setFont(font, font_size)
    c.drawString(x=x, y=y, text=text)
    return c.stringWidth(text, font, font_size)


def generate_figs(data_path: str):
    """
    Generate the ensemble of figs needed for the pdf.

    Parameters
    ----------
    data_path
        fully qualified path to data files for a given airline.
    """
    fig_output_path = f"{data_path}/figs"
    summary_json_fp = f"{data_path}/data_summary.json"
    data_all_internal_fp = f"{data_path}/data_all_internal.csv"
    data_case_study_fp = f"{data_path}/data_case_study_0.csv"

    if not os.path.exists(fig_output_path):
        os.mkdir(fig_output_path)

    # pg1
    logger.info("pg1. generating pie chart.")
    _gen_pie_fig(summary_json_fp, fig_output_path)
    logger.info("pg1. generating daytime/nighttime bar charts.")
    _gen_daytime_nighttime_detailed_bar_fig(summary_json_fp, fig_output_path)

    # pg2
    logger.info("pg2. generating flights map.")
    _gen_map_fig(data_all_internal_fp, fig_output_path)

    # pg3/4
    logger.info("pg3/4. generating CO2 contrail vs. fuel bar.")
    _gen_fuel_vs_contrail_co2_bar_fig(summary_json_fp, fig_output_path)
    logger.info("pg3/4. generating CO2e nighttime/daytime bar.")
    _gen_daytime_nighttime_bar_fig(summary_json_fp, fig_output_path)
    logger.info("pg3/4. generating OD figs.")
    _gen_od_bar_figs(summary_json_fp, fig_output_path)
    logger.info("pg3/4. generating case study fig.")
    _gen_case_study_fig(data_case_study_fp, fig_output_path)


def generate_pdf(output_path: str, data: Dict[str, Any], is_gridded: False) -> None:
    register_fonts()

    c = canvas.Canvas(output_path, pagesize=(page_width, page_height))

    logger.info("generating pg1")
    if is_gridded:
        draw_grid(c, page_width, page_height)
    create_page_one(c, data, airline_name=data["airline_name"])
    c.showPage()

    logger.info("generating pg2")
    if is_gridded:
        draw_grid(c, page_width, page_height)
    create_page_two(c, data)
    c.showPage()

    logger.info("generating pg3")
    if is_gridded:
        draw_grid(c, page_width, page_height)
    create_page_three(c, data)
    c.showPage()

    logger.info("generating pg4")
    if is_gridded:
        draw_grid(c, page_width, page_height)
    create_page_four(c, data)
    c.showPage()

    logger.info("generating pg5")
    if is_gridded:
        draw_grid(c, page_width, page_height)
    create_page_five(c, data)
    c.showPage()

    c.save()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a PDF report.")
    parser.add_argument(
        "--data_path",
        type=str,
        help="path to data directory. e.g. out/D0",
    )

    parser.add_argument(
        "--airline_name",
        type=str,
        help="airline friendly name",
    )

    parser.add_argument(
        "--grid", type=bool, default=False, help="add grid to pdf overlay (True/False)"
    )
    args = parser.parse_args()

    # generate figures
    generate_figs(args.data_path)

    # generate pdf
    data = load_data(json_path=args.data_path + "/data_summary.json")
    data["airline_name"] = args.airline_name
    generate_pdf(
        output_path=args.data_path + "/flights_report.pdf",
        data=data,
        is_gridded=args.grid,
    )


if __name__ == "__main__":
    main()
