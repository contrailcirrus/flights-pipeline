import matplotlib
import plotly.graph_objects as go
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.ticker import FuncFormatter, MaxNLocator
from concurrent.futures import ThreadPoolExecutor

from styles import DARK_GRAY, DARK_DARK_GRAY

matplotlib.use('Agg')

def generate_figs(data: dict, output_path: Path, debug: bool = False):
    """
    Generate all figures needed for the PDF report.
    """
    print("\n📊 Generating figures... ")
    figs_dir = output_path / "figs"
    figs_dir.mkdir(parents=True, exist_ok=True)

    def generate_page1_charts():
        if debug:
            print("  -> Generating: page1_gwp_bar_chart.png...")
        create_interleaved_chart(data).write_image(
            figs_dir / "page1_gwp_bar_chart.png", width=360, height=180, scale=12
        )

    def generate_page2_charts():
        if debug:
            print("  -> Generating: page2_stacked_gwp_chart.png...")
        create_p2_stacked_gwp_chart(data).write_image(
            figs_dir / "page2_stacked_gwp_chart.png", width=800, height=250, scale=10
        )

        if debug:
            print("  -> Generating: page2_day_night_chart.png...")
        create_p2_night_day_bar_chart(data).write_image(
            figs_dir / "page2_day_night_chart.png", width=800, height=150, scale=10
        )

    def generate_page4_charts():
        if debug:
            print("  -> Generating: page4_top_flights_chart.png...")
        create_top_flights_chart(data, str(figs_dir / "page4_top_flights_chart.png"))

    def generate_page5_charts():
        data_all_internal_fp = output_path / "data_all_internal.csv"
        if debug:
            print("  -> Generating: page5_flight_paths_map.png...")
        create_flight_paths_map(
            str(data_all_internal_fp), str(figs_dir / "page5_flight_paths_map.png")
        )
        csv_path = output_path / "data_case_study_0.csv"
        if csv_path.exists():
            if debug:
                print("  -> Generating: page5_case_study_chart.png...")
            create_case_study_chart(str(csv_path), str(figs_dir / "page5_case_study_chart.png"))
        else:
            if debug:
                print("  -> Skipping: page5_case_study_chart.png (case study CSV not found)")

    def generate_page6_charts():
        if debug:
            print("  -> Generating Page 6 charts...")
        create_warming_by_month_chart(str(figs_dir / "page6_warming_by_month.png"))
        create_warming_per_flight_chart(str(figs_dir / "page6_warming_per_flight.png"))
        create_warming_by_departure_time_chart(str(figs_dir / "page6_warming_by_departure.png"))

    try:
        # Run chart generation in parallel
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [
                executor.submit(generate_page1_charts),
                executor.submit(generate_page2_charts),
                executor.submit(generate_page4_charts),
                executor.submit(generate_page5_charts),
                executor.submit(generate_page6_charts)
            ]
            # Wait for all to complete
            for future in futures:
                future.result()

        print("✅ All figures generated.")
    except Exception as e:
        print(f"❌ Error generating figures: {str(e)}")
        raise


def create_interleaved_chart(data: dict) -> go.Figure:
    """Generates a Plotly figure with dynamic GWP data."""

    # 1. Calculate the kg/km values from the data dictionary
    total_km = data["flight_distance_km"]["total"]
    gwp20_tonnes = data["co2e_metric_tons"]["gwp20"]["total"]
    gwp50_tonnes = data["co2e_metric_tons"]["gwp50"]["total"]
    gwp100_tonnes = data["co2e_metric_tons"]["gwp100"]["total"]

    gwp20_per_km = (gwp20_tonnes * 1000) / total_km
    gwp50_per_km = (gwp50_tonnes * 1000) / total_km
    gwp100_per_km = (gwp100_tonnes * 1000) / total_km

    # 2. Build the chart_data list with the calculated values
    chart_data = [
        {"top": "GWP 100 ", "val": f"{gwp100_per_km:.1f}", "unit": "kg CO2e/km"},
        {"top": "GWP 50 ", "val": f"{gwp50_per_km:.1f}", "unit": "kg CO2e/km"},
        {"top": "GWP 20 ", "val": f"{gwp20_per_km:.1f}", "unit": "kg CO2e/km"},
    ]

    # Configuration
    row_height = 100  # Total vertical space for one complete row (label + bar).
    text_y_offset = 30  # Y position for the top label within the row.
    value_y_offset = 5  # Y position for the main value and unit.
    bar_y_offset = -30  # Y position for the bar.
    bar_thickness = 7  # Half the visual height of the bar.
    label_gap = 7  # Gap between the labels and the bars.

    total_y_range = len(chart_data) * row_height
    fig = go.Figure()

    # Main Loop: Draw each row using multiple annotations
    for i, data_item in enumerate(chart_data):
        row_center_y = total_y_range - (i * row_height) - (row_height / 2)

        # Annotation 1: Top Label
        fig.add_annotation(
            xref="paper",
            yref="y",
            x=0,
            y=row_center_y + text_y_offset,
            text=f"{data_item['top']} ⓘ",
            showarrow=False,
            align="left",
            xanchor="left",
            yanchor="middle",
            font=dict(size=7, color=DARK_GRAY, family="Roboto Light"),  # Gray color
        )

        # Annotation 2: Main Value
        fig.add_annotation(
            xref="paper",
            yref="y",
            x=0,
            y=row_center_y + value_y_offset - label_gap,
            text=data_item["val"],
            showarrow=False,
            align="left",
            xanchor="left",
            yanchor="middle",
            font=dict(size=24, color=DARK_DARK_GRAY, family="Roboto Light"),
        )

        # Annotation 3: Unit
        value_char_length = len(str(data_item["val"]))
        unit_x_pos = value_char_length * 0.032
        fig.add_annotation(
            xref="paper",
            yref="y",
            x=unit_x_pos,
            y=row_center_y + value_y_offset - label_gap - 20,
            text=f"{data_item['unit']}",
            showarrow=False,
            align="left",
            xanchor="left",
            yanchor="bottom",
            font=dict(size=7.5, color=DARK_DARK_GRAY, family="Roboto Light"),
        )

        # Add Bar Shape
        bar_center_y = row_center_y + bar_y_offset
        bar_value = float(data_item["val"])
        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=0,
            y0=bar_center_y - bar_thickness,
            x1=bar_value,
            y1=bar_center_y + bar_thickness,
            fillcolor="#4285F4",
            line_width=0,
            layer="below",
        )

    # Final Layout Configuration
    fig.update_layout(
        xaxis=dict(
            visible=False, range=[0, max(float(d["val"]) for d in chart_data) * 1.05]
        ),
        yaxis=dict(visible=False, range=[0, total_y_range]),
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=165,
        showlegend=False,
        font=dict(family="Roboto Light"),
    )
    return fig


def create_p2_stacked_gwp_chart(data: dict) -> go.Figure:
    """
    Generates a Plotly figure with dynamic GWP percentages.
    """
    # 1. Get the base values from the data dictionary
    total_co2 = data["co2_metric_tons"]["total"]
    gwp20_co2e = data["co2e_metric_tons"]["gwp20"]["total"]
    gwp50_co2e = data["co2e_metric_tons"]["gwp50"]["total"]
    gwp100_co2e = data["co2e_metric_tons"]["gwp100"]["total"]

    # 2. Helper function to calculate the percentage split for any GWP value
    def calculate_percentages(co2e_value):
        total_warming = total_co2 + co2e_value
        if total_warming == 0:  # Avoid division by zero
            return 100, 0
        co2_pct = round((total_co2 / total_warming) * 100)
        co2e_pct = 100 - co2_pct  # Ensure it always adds to 100
        return co2_pct, co2e_pct

    # 3. Calculate percentages for each GWP value
    gwp100_co2_pct, gwp100_co2e_pct = calculate_percentages(gwp100_co2e)
    gwp50_co2_pct, gwp50_co2e_pct = calculate_percentages(gwp50_co2e)
    gwp20_co2_pct, gwp20_co2e_pct = calculate_percentages(gwp20_co2e)

    # 4. Build the chart_data list dynamically
    chart_data = [
        {"label": "GWP 100", "co2_pct": gwp100_co2_pct, "co2e_pct": gwp100_co2e_pct},
        {"label": "GWP 50", "co2_pct": gwp50_co2_pct, "co2e_pct": gwp50_co2e_pct},
        {"label": "GWP 20", "co2_pct": gwp20_co2_pct, "co2e_pct": gwp20_co2e_pct},
    ]

    row_height = 118
    label_y_in_row = 113
    bar_y_in_row = 65
    bar_height = 80  # The visual height of the bar.
    num_rows = len(chart_data)
    total_y_range = num_rows * row_height
    fig = go.Figure()

    for i, data_item in enumerate(chart_data):
        row_bottom_y = i * row_height
        label_y_pos = row_bottom_y + label_y_in_row
        bar_center_y = row_bottom_y + bar_y_in_row

        # --- GWP Label ---
        fig.add_annotation(
            xref="x",
            yref="y",
            x=0,
            y=label_y_pos,
            text=f"{data_item['label']}",
            showarrow=False,
            xanchor="left",
            font=dict(size=14, color=DARK_DARK_GRAY, family="Roboto Light"),
        )

        # --- Bar Shapes ---
        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            layer="below",
            x0=0,
            y0=bar_center_y - (bar_height / 2) - 10,
            x1=data_item["co2_pct"],
            y1=bar_center_y + (bar_height / 2) - 10,
            fillcolor="#5c84d8",
            line_width=0,
        )
        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            layer="below",
            x0=data_item["co2_pct"],
            y0=bar_center_y - (bar_height / 2) - 10,
            x1=100,
            y1=bar_center_y + (bar_height / 2) - 10,
            fillcolor="#789cf4",
            line_width=0,
        )

        # "Fuel Emissions" text - Positioned in the top part of the left bar
        fig.add_annotation(
            xref="x",
            yref="y",
            x=1,
            y=bar_center_y + (bar_height * 0.25),
            text="Fuel Emissions (tonnes CO2)",
            showarrow=False,
            xanchor="left",
            yanchor="top",
            font=dict(size=11, color="white", family="Roboto"),
        )
        # CO2 Percentage - Positioned in the bottom part of the left bar
        fig.add_annotation(
            xref="x",
            yref="y",
            x=1,
            y=bar_center_y,
            text=f"{data_item['co2_pct']}%",
            showarrow=False,
            xanchor="left",
            yanchor="top",
            font=dict(size=20, color="white", family="Roboto"),
        )

        # "Contrails" text - Positioned in the top part of the right bar
        fig.add_annotation(
            xref="x",
            yref="y",
            x=data_item["co2_pct"] + 2,
            y=bar_center_y + (bar_height * 0.25),
            text="Contrails (CO2e)",
            showarrow=False,
            xanchor="left",
            yanchor="top",
            font=dict(size=11, color="white", family="Roboto Light"),
        )
        # CO2e Percentage - Positioned in the bottom part of the right bar
        fig.add_annotation(
            xref="x",
            yref="y",
            x=data_item["co2_pct"] + 2,
            y=bar_center_y,
            text=f"{data_item['co2e_pct']}%",
            showarrow=False,
            xanchor="left",
            yanchor="top",
            font=dict(size=20, color="white", family="Roboto Light"),
        )

    fig.update_layout(
        xaxis=dict(visible=False, range=[-1, 101]),
        yaxis=dict(visible=False, range=[0, total_y_range]),
        margin=dict(l=0, r=0, t=5, b=5),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=200,
        width=500,
        showlegend=False,
        font=dict(family="Roboto Light"),
    )
    return fig


def create_p2_night_day_bar_chart(data: dict) -> go.Figure:
    """
    Generates a Plotly figure showing a single stacked bar for
    Nighttime vs. Daytime CO2e emissions with dynamic unit formatting.
    """
    night_val = data["co2e_metric_tons"]["gwp50"]["nighttime"]["total"]
    day_val = data["co2e_metric_tons"]["gwp50"]["daytime"]["total"]

    # Format the nighttime value
    if night_val > 100000:
        night_text = f"{night_val / 1000:,.0f} kt CO2e"
    else:
        night_text = f"{night_val:,.0f} t CO2e"

    # Format the daytime value
    if day_val > 100000:
        day_text = f"{day_val / 1000:,.0f} kt CO2e"
    else:
        day_text = f"{day_val:,.0f} t CO2e"

    total_val = night_val + day_val
    if total_val == 0:
        night_pct = 100
    else:
        night_pct = (night_val / total_val) * 100

    bar_height = 30
    bar_center_y = bar_height / 2

    fig = go.Figure()

    # Add the "Nighttime" segment
    fig.add_shape(
        type="rect",
        xref="x",
        yref="y",
        layer="below",
        x0=0,
        y0=bar_center_y - (bar_height / 2),
        x1=night_pct,
        y1=bar_center_y + (bar_height / 2),
        fillcolor="#4a4266",
        line_width=0,
    )
    # Add the "Daytime" segment
    fig.add_shape(
        type="rect",
        xref="x",
        yref="y",
        layer="below",
        x0=night_pct,
        y0=bar_center_y - (bar_height / 2),
        x1=100,
        y1=bar_center_y + (bar_height / 2),
        fillcolor="#e6c86e",
        line_width=0,
    )

    # Annotations
    fig.add_annotation(
        xref="x",
        yref="y",
        x=2,
        y=bar_center_y + (bar_height * 0.3),
        text="Nighttime",
        showarrow=False,
        xanchor="left",
        yanchor="middle",
        font=dict(size=12, color="white", family="Roboto Light"),
    )
    fig.add_annotation(
        xref="x",
        yref="y",
        x=2,
        y=bar_center_y + (bar_height * 0.1),
        text=night_text,  # Use formatted text
        showarrow=False,
        xanchor="left",
        yanchor="middle",
        font=dict(size=28, color="white", family="Roboto Light"),
    )
    fig.add_annotation(
        xref="x",
        yref="y",
        x=night_pct + 2,
        y=bar_center_y + (bar_height * 0.3),
        text="Daytime",
        showarrow=False,
        xanchor="left",
        yanchor="middle",
        font=dict(size=12, color="#4A3F55", family="Roboto"),
    )
    fig.add_annotation(
        xref="x",
        yref="y",
        x=night_pct + 2,
        y=bar_center_y + (bar_height * 0.1),
        text=day_text,
        showarrow=False,
        xanchor="left",
        yanchor="middle",
        font=dict(size=24, color="#4A3F55", family="Roboto"),
    )

    fig.update_layout(
        xaxis=dict(visible=False, range=[0, 150]),
        yaxis=dict(visible=False, range=[0, bar_height]),
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        height=bar_height,
    )
    return fig


def create_flight_paths_map(data_csv_path: str, output_image_path: str):
    """
    Generates a map with flight paths
    """
    summary_df = pd.read_csv(data_csv_path)
    projection = ccrs.Mercator(
        central_longitude=12, min_latitude=-56.9, max_latitude=84.0
    )
    fig = plt.figure(figsize=(10, 10))
    ax = fig.add_subplot(1, 1, 1, projection=projection)
    ax.set_global()
    ax.add_feature(cfeature.LAND, color="#C4C7C5")

    # Coordinates below are taken from flight-emissions-report/services.py (CONUS region boundary)
    CONUS_COORDS = (
        (-40, 61),
        (-110, 61),
        (-128, 52.3),
        (-134, 50),
        (-120, 10),
        (-90, -5),
        (-90, -40),
        (-50, -40),
        (-30, 0),
        (-60, 15),
    )
    ax.fill(
        [c[0] for c in CONUS_COORDS],
        [c[1] for c in CONUS_COORDS],
        facecolor="#F7CA45",
        edgecolor=None,
        linewidth=1.0,
        alpha=0.5,
        transform=ccrs.Geodetic(),
    )
    
    # Downsample and draw flight paths
    num_flights_to_plot = 300
    if len(summary_df) > num_flights_to_plot:
        summary_df = summary_df.sample(n=num_flights_to_plot, random_state=1)

    for ix, row in summary_df.iterrows():
        plt.plot(
            [row.lon_start, row.lon_end],
            [row.lat_start, row.lat_end],
            color="black",
            alpha=0.3,
            linewidth=0.3,
            transform=ccrs.Geodetic(),
        )

    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    plt.savefig(
        output_image_path,
        bbox_inches="tight",
        transparent=True,
        dpi=300
    )
    plt.close(fig)


def create_case_study_chart(data_case_study_fp: str, output_image_path: str):
    """
    Generates the case study plot with the correct dimensions to fit in the PDF.
    """
    try:
        seg_df = pd.read_csv(data_case_study_fp)
    except FileNotFoundError:
        print(f"❌ ERROR: Case study CSV not found at {data_case_study_fp}")
        return

    # --- Prepare data ---
    seg_df.sort_values(["time_start"], inplace=True)
    seg_df["dist_cum_km"] = seg_df["chunk_len_km"].cumsum()

    fig, ax = plt.subplots(figsize=(14, 3))

    x_v = seg_df["dist_cum_km"]
    y_v = seg_df["median_altitude_ft"] / 100.0

    min_x, max_x = 0, seg_df["dist_cum_km"].max() * 1.05
    min_y, max_y = 50, 420

    # --- Plotting Layers ---
    if "in_conus" in seg_df.columns and seg_df["in_conus"].any():
        x_conus_min = seg_df.loc[seg_df["in_conus"], "dist_cum_km"].min()
        x_conus_max = seg_df.loc[seg_df["in_conus"], "dist_cum_km"].max()
        ax.add_patch(
            plt.Rectangle(
                (x_conus_min, min_y),
                x_conus_max - x_conus_min,
                max_y - min_y,
                alpha=0.2,
                facecolor="#F3CD5D",
                edgecolor=None,
                zorder=1,
            )
        )

    if "sum_ef_mj" in seg_df.columns:
        x_pred = x_v[seg_df["sum_ef_mj"] != 0]
        y_pred = y_v[seg_df["sum_ef_mj"] != 0]
        ax.scatter(x_pred, y_pred, color="#B1C6FD", s=1200, alpha=0.3, zorder=2)

    if "goog_is_attributed" in seg_df.columns:
        x_conf = x_v[seg_df["goog_is_attributed"] != 0]
        y_conf = y_v[seg_df["goog_is_attributed"] != 0]
        ax.scatter(x_conf, y_conf, color="#F9DF92", s=500, alpha=0.9, zorder=3)

    ax.plot(x_v, y_v, color="black", linewidth=1.5, zorder=4)

    # --- Styling and Formatting ---
    ax.grid(axis="y", linewidth=1, linestyle="dotted", color="#E0E0E0")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#BDBDBD")
    ax.tick_params(axis="both", which="major", labelsize=13, length=0)

    ax.set_yticks(np.arange(100, 451, 50))
    ax.set_yticklabels([f"FL{int(y)}" for y in ax.get_yticks()])

    ax.xaxis.set_major_locator(MaxNLocator(nbins=14, integer=True))

    def km_formatter(x, pos):
        return f"{x:,.0f}km"

    ax.xaxis.set_major_formatter(FuncFormatter(km_formatter))

    plt.xticks(rotation=90)

    ax.set_xlim([min_x, max_x])
    ax.set_ylim([min_y, max_y])

    # --- Save Figure ---
    fig.tight_layout()
    plt.savefig(output_image_path, transparent=True, dpi=600)
    plt.close(fig)


def create_warming_by_month_chart(output_image_path: str):
    """Generates the 'Contrail warming by month' bar chart."""
    months = [
        "JAN",
        "FEB",
        "MAR",
        "APR",
        "MAY",
        "JUN",
        "JUL",
        "AUG",
        "SEP",
        "OCT",
        "NOV",
        "DEC",
    ]
    co2_emissions = np.random.uniform(50000, 85000, 12)
    contrail_warming = np.random.uniform(70000, 120000, 12)

    df = pd.DataFrame(
        {
            "Month": months,
            "CO₂ Emissions (tCO₂e)": co2_emissions,
            "Contrail Warming (tCO₂e)": contrail_warming,
        }
    )

    fig, ax = plt.subplots(figsize=(10, 3))
    df.plot(x="Month", kind="bar", ax=ax, color=["red", "gray"], width=0.8, legend=None)

    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", color="lightgray")
    ax.set_ylabel("")
    ax.set_xlabel("")
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", rotation=0)

    fig.tight_layout()
    plt.savefig(output_image_path, transparent=True, dpi=300)
    plt.close(fig)


def create_warming_per_flight_chart(output_image_path: str):
    """Generates the 'Contrail Warming per Flight' dual-axis chart."""
    aircraft = ["A320", "A380", "737-800", "727", "CRI-900", "737 Max"]
    num_flights = [4000, 1000, 10000, 1500, 9000, 1000]
    warming_per_flight = [20, 5, 45, 15, 55, 10]

    fig, ax1 = plt.subplots(figsize=(10, 4))

    # Bar chart for Number of Flights (left y-axis)
    ax1.bar(aircraft, num_flights, color="gray", width=0.4, label="Number of Flights")
    ax1.set_ylabel("Number of Flights", color="gray")
    ax1.tick_params(axis="y", labelcolor="gray")
    ax1.spines[["top", "left", "right"]].set_visible(False)

    # Bar chart for Contrail Warming (right y-axis)
    ax2 = ax1.twinx()
    ax2.bar(
        np.arange(len(aircraft)) + 0.4,
        warming_per_flight,
        color="red",
        alpha=0.6,
        width=0.4,
        label="Contrail Warming per Flight",
    )
    ax2.set_ylabel("Contrail Warming per Flight", color="red")
    ax2.tick_params(axis="y", labelcolor="red")
    ax2.spines[["top", "left", "right"]].set_visible(False)

    fig.legend(loc="lower center", bbox_to_anchor=(0.5, -0.1), ncol=2, frameon=False)

    fig.tight_layout()
    plt.savefig(output_image_path, transparent=True, dpi=300)
    plt.close(fig)


def create_warming_by_departure_time_chart(output_image_path: str):
    """Generates the 'Contrail warming by local departure time' chart with vertical bar labels."""
    hours = np.arange(24)
    contrail_warming = np.random.uniform(10, 65, 24)
    number_of_flights = np.random.uniform(100, 2000, 24)

    width = 0.4
    fig, ax1 = plt.subplots(figsize=(10, 4))

    rects1 = ax1.bar(
        hours - width / 2,
        contrail_warming,
        width,
        color="gray",
        label="Contrail warming",
    )
    ax1.set_ylabel("Energy Forcing (kW)")
    ax1.set_xlabel("Departure Hour (Local)")
    ax1.spines[["top", "right"]].set_visible(False)

    ax2 = ax1.twinx()
    rects2 = ax2.bar(
        hours + width / 2,
        number_of_flights,
        width,
        color="red",
        alpha=0.6,
        label="Number of flights",
    )
    ax2.set_ylabel("Number of Flights (tCO2)")
    ax2.spines[["top", "right"]].set_visible(False)

    ax1.bar_label(
        rects1,
        padding=3,
        fmt="%.0f",
        fontsize=7,
        color="gray",
        label_type="edge",
        rotation=90,
    )
    ax2.bar_label(
        rects2,
        padding=3,
        fmt="%.0f",
        fontsize=7,
        color="red",
        label_type="edge",
        rotation=90,
    )

    ax1.set_xticks(hours)
    fig.legend(loc="lower center", bbox_to_anchor=(0.5, -0.15), ncol=2, frameon=False)

    fig.tight_layout()
    plt.savefig(output_image_path, transparent=True, dpi=300)
    plt.close(fig)


def create_top_flights_chart(
    data: dict, output_image_path: str, min_flight_count: int = 52
):
    """
    Generates a horizontal bar chart of the top 10 OD pairs by contrail warming intensity (kg CO2e/km).
    """
    CHART_WIDTH_PX = 2008
    CHART_HEIGHT_PX = 827
    FONT_SIZE = 28
    BAR_WIDTH = 0.8
    BAR_COLOR = "#4A3F55"
    BAR_OPACITY = 0.9

    od_pairs_data = data.get("od_pairs", [])
    valid_od_pairs = [
        item
        for item in od_pairs_data
        if (
            item.get("airport_iata_od", "")
            and "None" not in item.get("airport_iata_od", "")
            and item.get("flight_count", 0) >= min_flight_count
        )
    ]

    if not valid_od_pairs:
        return

    valid_od_pairs.sort(
        key=lambda item: item.get("impact_density_co2e_metric_tons_per_dist_km", 0),
        reverse=True,
    )
    top_10_pairs = valid_od_pairs[:10]

    od_pairs_labels = [
        pair["airport_iata_od"].replace("_", " - ") for pair in top_10_pairs
    ][::-1]
    warming_values = [
        pair.get("impact_density_co2e_metric_tons_per_dist_km", 0) * 1000
        for pair in top_10_pairs
    ][::-1]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=warming_values,
            y=od_pairs_labels,
            orientation="h",
            marker=dict(color=BAR_COLOR, opacity=BAR_OPACITY),
            width=BAR_WIDTH,
            text=[f"  {val:.0f} kg CO₂e/km" for val in warming_values],
            textposition="outside",
            insidetextanchor="start",
            hovertemplate="%{y}: %{x:.0f} kg CO2e/km<extra></extra>",
            showlegend=False,
            cliponaxis=False,
            textfont=dict(size=FONT_SIZE, family="Roboto Light", color=DARK_DARK_GRAY),
        )
    )

    fig.update_layout(
        xaxis=dict(
            title="",
            showgrid=True,
            gridcolor="lightgray",
            zeroline=False,
            color=DARK_GRAY,
            tickfont=dict(size=FONT_SIZE, family="Roboto Light", color=DARK_DARK_GRAY),
            showline=False,
            showticklabels=True,
            ticks="outside",
            showspikes=False,
            ticksuffix=" kg CO₂e/km",
            tickformat=".0f",
            tickmode="auto",
            nticks=8,
            tickangle=0,
        ),
        yaxis=dict(
            showgrid=False,
            showline=False,
            color=DARK_GRAY,
            tickfont=dict(size=FONT_SIZE, family="Roboto Light", color=DARK_DARK_GRAY),
            showticklabels=True,
            ticks="outside",
            ticksuffix=" ",
            showspikes=False,
            automargin=True,
        ),
        margin=dict(l=0, r=0, t=10, b=0, pad=0),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        font=dict(family="Roboto Light", color=DARK_DARK_GRAY, size=FONT_SIZE),
        height=CHART_HEIGHT_PX,
        width=CHART_WIDTH_PX,
    )

    fig.write_image(
        output_image_path, width=CHART_WIDTH_PX, height=CHART_HEIGHT_PX, scale=2
    )
