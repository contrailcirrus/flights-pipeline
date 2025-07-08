import plotly.graph_objects as go
from pathlib import Path


def generate_figs(output_path: Path, debug: bool = False):
    """
    Generate the ensemble of figs needed for the pdf.
    """
    print("\n📊 Generating figures... ")
    figs_dir = output_path / "figs"
    figs_dir.mkdir(parents=True, exist_ok=True)

    # --- Generate page 1 Chart ---
    p1_gwp_bar_chart = "page1_gwp_bar_chart.png"
    if debug:
        print(f"  📈 Generating page 1 bar chart: {figs_dir / p1_gwp_bar_chart}...")
    fig1 = create_interleaved_chart()
    fig1.write_image(figs_dir / p1_gwp_bar_chart, width=360, height=180, scale=12)
    if debug:
        print("  ✅ Generated page 1 gwp bar chart.")

    # --- Generate page 2 Charts ---
    p2_stacked_gwp_chart = "page2_stacked_gwp_chart.png"
    if debug:
        print(
            f"  📈 Generating page 2 stacked chart: {figs_dir / p2_stacked_gwp_chart}..."
        )
    fig2 = create_p2_stacked_gwp_chart()
    fig2.write_image(figs_dir / p2_stacked_gwp_chart, width=800, height=250, scale=10)
    if debug:
        print("  ✅ Generated page 2 stacked chart.")

    p2_day_night_chart = "page2_day_night_chart.png"
    if debug:
        print(
            f"  📈 Generating page 2 day night chart: {figs_dir / p2_day_night_chart}..."
        )
    fig3 = create_p2_night_day_bar_chart()
    fig3.write_image(figs_dir / p2_day_night_chart, width=800, height=150, scale=10)
    if debug:
        print("  ✅ Generated page 2 day night chart.")

    if debug:
        print("✅ All figures generated.")


def create_interleaved_chart() -> go.Figure:
    """Generates a Plotly figure with a custom layout of text labels and single-bar charts."""
    chart_data = [
        {"top": "GWP 100 ", "val": "20", "unit": " kg CO2e/km"},
        {"top": "GWP 50 ", "val": "40", "unit": " kg CO2e/km"},
        {"top": "GWP 20 ", "val": "60", "unit": " kg CO2e/km"},
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
            font=dict(size=6, color="#808080", family="Roboto Light"),  # Gray color
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
            font=dict(size=24, color="#000000"),
        )

        # Annotation 3: Unit
        value_char_length = len(str(data_item["val"]))
        unit_x_pos = value_char_length * 0.032
        fig.add_annotation(
            xref="paper",
            yref="y",
            x=unit_x_pos,
            y=row_center_y + value_y_offset - label_gap - 20,
            text=f" {data_item['unit']}",
            showarrow=False,
            align="left",
            xanchor="left",
            yanchor="bottom",
            font=dict(size=8, color="#000000"),
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
        height=300,
        showlegend=False,
        font=dict(family="Roboto Light"),
    )
    return fig

def create_p2_stacked_gwp_chart() -> go.Figure:
    """
    Generates a Plotly figure with text and percentages stacked correctly.
    """
    # TODO: Add real data
    chart_data = [
        {"label": "GWP 100", "co2_pct": 81, "co2e_pct": 19},
        {"label": "GWP 50", "co2_pct": 76, "co2e_pct": 24},
        {"label": "GWP 20", "co2_pct": 65, "co2e_pct": 35},
    ]

    row_height = 90
    label_y_in_row = 85
    bar_y_in_row = 50
    bar_height = 65  # The visual height of the bar.
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
            font=dict(size=12, color="#252525", family="Roboto Light"),
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
            y=bar_center_y + (bar_height * 0.2),
            text="Fuel Emissions (tonnes CO2)",
            showarrow=False,
            xanchor="left",
            yanchor="top",
            font=dict(size=12, color="white", family="Roboto Light"),
        )
        # CO2 Percentage - Positioned in the bottom part of the left bar
        fig.add_annotation(
            xref="x",
            yref="y",
            x=1,
            y=bar_center_y - bar_height * 0.1,
            text=f"{data_item['co2_pct']}%",
            showarrow=False,
            xanchor="left",
            yanchor="top",
            font=dict(size=24, color="white", family="Roboto Light"),
        )

        # "Contrails" text - Positioned in the top part of the right bar
        fig.add_annotation(
            xref="x",
            yref="y",
            x=data_item["co2_pct"] + 2,
            y=bar_center_y + bar_height * 0.25,
            text="Contrails (CO2e)",
            showarrow=False,
            xanchor="left",
            yanchor="top",
            font=dict(size=12, color="white", family="Roboto Light"),
        )
        # CO2e Percentage - Positioned in the bottom part of the right bar
        fig.add_annotation(
            xref="x",
            yref="y",
            x=data_item["co2_pct"] + 2,
            y=bar_center_y - bar_height * 0.1,
            text=f"{data_item['co2e_pct']}%",
            showarrow=False,
            xanchor="left",
            yanchor="top",
            font=dict(size=24, color="white", family="Roboto Light"),
        )

    fig.update_layout(
        xaxis=dict(visible=False, range=[-1, 101]),
        yaxis=dict(visible=False, range=[0, total_y_range]),
        margin=dict(l=0, r=0, t=5, b=5),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=280,
        showlegend=False,
        font=dict(family="Roboto Light"),
    )
    return fig


def create_p2_night_day_bar_chart() -> go.Figure:
    """
    Generates a Plotly figure showing a single stacked bar for
    Nighttime vs. Daytime CO2e emissions.
    """
    # TODO: Add the actual data to this chart
    night_val = 260082
    day_val = 10650
    total_val = night_val + day_val

    # Calculate the percentage split for the bar's width
    night_pct = (night_val / total_val) * 100
    bar_height = 30  # The visual height of the bar
    bar_center_y = bar_height / 2  # Vertical center of the bar in the plot

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

    # "Nighttime" label
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
    # Nighttime value
    fig.add_annotation(
        xref="x",
        yref="y",
        x=2,
        y=bar_center_y + (bar_height * 0.1),
        text=f"{night_val:,} t CO2e",
        showarrow=False,
        xanchor="left",
        yanchor="middle",
        font=dict(size=28, color="white", family="Roboto Light"),
    )

    # "Daytime" label
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
    # Daytime value
    fig.add_annotation(
        xref="x",
        yref="y",
        x=night_pct + 2,
        y=bar_center_y + (bar_height * 0.1),
        text=f"{day_val:,} t CO2e",
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
