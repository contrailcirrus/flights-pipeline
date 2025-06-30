from reportlab.platypus import (
    Paragraph,
    Spacer,
    Table,
    Image,
)
import plotly.graph_objects as go

from styles import (
    report_title_style,
    section_title_style,
    body_style,
    bullet_style,
    label_style,
    container_table_style,
    page_num_style,
    four_column_table_style,
    t_shaped_table_style,
    GRID_UNIT,
)
from setup import LOGO_PATH
from chart_generator import PlotlyChartFlowable

TOTAL_PAGES = 5
GRID_SPACER = Spacer(1, GRID_UNIT)
HALF_GRID_SPACER = Spacer(1, GRID_UNIT / 2)
QUARTER_GRID_SPACER = Spacer(1, GRID_UNIT / 4)


def build_first_page(airline_name: str):
    """
    Assembles the entire 1st page for the report.
    """
    story = []

    # --- Page Number ---
    story.append(Table([[Paragraph(f"Page 1 of {TOTAL_PAGES}", page_num_style)]]))

    # --- Add Logo ---
    story.append(
        Table(
            [[Image(str(LOGO_PATH), width=GRID_UNIT * 2, height=GRID_UNIT)]],
            hAlign="LEFT",
        )
    )

    # --- Report Tilte ---
    story.append(Paragraph("Airline Contrail Impact Report 2024", report_title_style))

    # --- Contrails CONTAINER ---
    story.append(create_contrails_container())
    story.append(GRID_SPACER)

    # --- Impact Data CONTAINER ---
    story.append(build_impact_data_table(airline_name))

    return story


def create_contrails_container():
    """
    Assembles the contrails container that will be used on page 1.
    """
    container_content = [
        [HALF_GRID_SPACER],
        [Paragraph("What are Contrails?", section_title_style)],
        [GRID_SPACER],
    ]

    # Section - What are Contrails?
    container_content.append(
        [
            Paragraph(
                "Contrails warm the planet because contrail clouds act like a blanket on Earth and have a net heating effect. The 2022 IPCC report noted that clouds created by contrails account for roughly 35% of aviation's global warming impact.",
                body_style,
            )
        ]
    )

    # Section - What is Global Warming Potential (GWP)?
    container_content.extend(
        [
            [GRID_SPACER],
            [Paragraph("What is Global Warming Potential (GWP)?", section_title_style)],
            [GRID_SPACER],
        ]
    )
    container_content.append(
        [
            Paragraph(
                "GWP measures how much warming contrails cause over a number of years compared to CO2. Contrails heat the Earth quickly but for a short time. To align with the guidelines from the EU Non-CO2 MRV report the contrail impact is shown in CO2e over 20, 50 and 100 years. The middle value, GWP50, is used as default.",
                body_style,
            )
        ]
    )

    # Section - Methodology, Data Sources & Assumptions
    container_content.extend(
        [
            [GRID_SPACER],
            [Paragraph("Methodology, data sources & assumptions", section_title_style)],
            [GRID_SPACER],
        ]
    )

    # IATA Codes Section
    container_content.append(
        [
            Paragraph(
                "<b>IATA Codes:</b> This report covers [____] IATA code.", body_style
            )
        ]
    )

    # Modeling Process Section and bullets
    container_content.append([Paragraph("<b>Modeling Process:</b>", body_style)])
    modeling_bullets = [
        "Flight trajectories are built from ADS-B data and undergo quality control, removing bad trajectories (this reduces the number of analyzed flights).",
        "The CoCiP physics-based model predicts contrails and CO2e impact.",
        "Aircraft type (e.g., B777) is used to select a default engine type for modeling, unless the airline provides specific aircraft-engine pairings.",
    ]
    container_content.extend(
        [
            [Paragraph(text, style=bullet_style, bulletText="•")]
            for text in modeling_bullets
        ]
    )

    # Fuel Consumption Estimates Section
    container_content.append(
        [Paragraph("<b>Fuel Consumption Estimates:</b>", body_style)]
    )
    fuel_points = [
        "Fuel burn is based on the physics model, sensitive to engine type and assumed constant load factors (per aircraft type).",
        "It primarily reflects fuel consumption “during flight” or “at cruise,” generally excluding taxi, and sometimes take-off/landing.",
    ]
    container_content.extend(
        [
            [
                Paragraph(
                    text,
                    style=bullet_style,
                    bulletText="•",
                )
            ]
            for text in fuel_points
        ]
    )

    # Data Discrepancies Section
    container_content.append([Paragraph("<b>Data Discrepancies:</b>", body_style)])
    discrepancy_points = [
        "The report uses modeled estimates. An airline’s internal data regarding fuel use, load factor, exact trajectory, engine configuration, etc., is more precise.",
        "Discrepancies between the report’s modeled numbers and the airline’s internal figures are expected.",
    ]
    container_content.extend(
        [
            [Paragraph(text, style=bullet_style, bulletText="•")]
            for text in discrepancy_points
        ]
    )

    # Report Exclusions Section
    container_content.append([Paragraph("<b>Report Exclusions:</b>", body_style)])
    exclusion_points = [
        "Excludes aircraft types that don’t produce contrails, or flights with insufficient or corrupt data.",
        "Flights are excluded if the aircraft type isn’t in the database (mainly affecting propeller or some private aircraft).",
    ]
    container_content.extend(
        [
            [Paragraph(text, style=bullet_style, bulletText="•")]
            for text in exclusion_points
        ]
    )
    container_content.append([HALF_GRID_SPACER])

    container_table = Table(container_content, colWidths="100%")
    container_table.setStyle(container_table_style)

    return container_table


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


def build_impact_data_table(airline_name: str):
    """
    Constructs a T-shaped table. Table Structure:

    * Top Row: Impact Data Table
    * Bottom Row:
        Column 1: Global Warming Potential Section
        Column 2: Bar Chart
    """
    # Create impact data
    impact_data_rows = [
        # Title
        QUARTER_GRID_SPACER,
        Paragraph("Impact Data", section_title_style),
        HALF_GRID_SPACER,
    ]
    # Impact row content
    impact_data_rows.extend(
        [
            Paragraph(
                f"Based on our prediction model, we analyzed 1.4M flights, 5.5 Million km (55,501 flight hours) and of those, 4.4% of all {airline_name} flights generated warming contrails in 2024.",
                body_style,
            ),
            HALF_GRID_SPACER,
        ]
    )

    # Data for the table
    data = [
        ["Contrails percentage", "<font size='24'>4.4%</font> of flights km"],
        [
            f"{airline_name} Average CO2e/km flown",
            "<font size='24'>20.9</font> kg CO2e/km",
        ],
        ["All Airlines average CO2e/km", "<font size='24'>23.4</font> kg CO2e/km"],
        ["Average fuel burn", "<font size='24'>26.6</font> kg CO2e/km"],
    ]

    # Create stats table
    stats_data = [
        [Paragraph(line1, label_style) for line1, _ in data],
        [Paragraph(line2, body_style) for _, line2 in data],
    ]
    stats_table = Table(stats_data, colWidths=["25%", "27%", "24%", "24%"])
    stats_table.setStyle(four_column_table_style)

    impact_data_rows.extend([stats_table, GRID_SPACER])

    # Global warming potential section
    gwp_title = Paragraph(
        "<font size='11'>Global Warming</font>",
        body_style,
    )
    gwp_title_2 = Paragraph(
        "<font size='11'>potential 100, 50, 20</font>",
        body_style,
    )
    gwp_text = Paragraph(
        "Contrails are more warming in<br></br>the short term", body_style
    )
    plotly_chart_component = PlotlyChartFlowable(
        chart_function=create_interleaved_chart,
        image_name="interleaved_bar_chart.png",
    )

    data = [
        [impact_data_rows],
        [
            [
                GRID_SPACER,
                gwp_title,
                QUARTER_GRID_SPACER,
                gwp_title_2,
                HALF_GRID_SPACER,
                gwp_text,
            ],
            [HALF_GRID_SPACER, plotly_chart_component],
        ],
    ]

    return Table(data, colWidths=["25%", "75%"], style=t_shaped_table_style)
