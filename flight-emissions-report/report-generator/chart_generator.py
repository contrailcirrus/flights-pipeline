import plotly.graph_objects as go
from pathlib import Path


def generate_figs(output_path: Path, debug: bool = False):
    """
    Generate the ensemble of figs needed for the pdf.
    """
    print("\n📊 Generating figures... ")

    # Page one

    # GWP 20,50,100 Bar chart
    p1_gwp_bar_chart_name = "p1_gwp_bar_chart.png"
    if debug:
        print(f"  📈 Generating page 1 bar chart: out/figs/{p1_gwp_bar_chart_name}...")
    fig1 = create_interleaved_chart()
    fig1.write_image(output_path / "figs" / p1_gwp_bar_chart_name)
    if debug:
        print(f"  ✅ Generated page 1 bar chart: out/figs/{p1_gwp_bar_chart_name}")


def create_interleaved_chart() -> go.Figure:
    """Generates a Plotly figure with a custom layout of text labels and single-bar charts."""
    chart_data = [
        {"top": "GWP 100 ", "val": "20", "unit": "kg CO2e/km"},
        {"top": "GWP 50 ", "val": "40", "unit": "kg CO2e/km"},
        {"top": "GWP 20 ", "val": "60", "unit": "kg CO2e/km"},
    ]

    # Configuration
    row_height = 100  # Total vertical space for one complete row (label + bar).
    text_y_offset = 25  # Y position for the top label within the row.
    value_y_offset = -5  # Y position for the main value and unit.
    bar_y_offset = -40  # Y position for the bar.
    bar_thickness = 7  # Half the visual height of the bar.
    label_gap = 6  # Gap between the labels and the bars.

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
            font=dict(size=6, color="#808080", family="Roboto-Light"),  # Gray color
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
            y=row_center_y + value_y_offset - label_gap - 18,
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
        font=dict(family="Roboto-Light"),
    )
    return fig
