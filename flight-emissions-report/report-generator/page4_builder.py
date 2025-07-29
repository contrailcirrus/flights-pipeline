from reportlab.platypus import (
    Paragraph,
    Table,
    Image,
)
from pathlib import Path
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle

from styles import (
    section_title_style,
    body_style,
    label_style,
    container_table_style,
    page_num_style,
    od_pair_stats_table_style,
    blue_highlight_box_style,
    GRID_SPACER,
    HALF_GRID_SPACER,
    TOTAL_PAGES,
)


def build_fourth_page(data: dict, output_path: Path, airline_name: str):
    """
    Assembles the entire 4th page for the report.
    """
    page_content = []

    page_content.append(Table([[Paragraph(f"Page 4 of {TOTAL_PAGES}", page_num_style)]]))
    page_content.append(GRID_SPACER)
    page_content.append(create_top_flights_container(data, output_path))
    page_content.append(GRID_SPACER)

    page_content.append(create_actionable_insights_container(data, airline_name))
    page_content.append(GRID_SPACER)

    return page_content


def create_top_flights_container(data: dict, output_path: Path):
    """
    Creates the top flights chart container.
    """
    chart_path = output_path / "figs" / "top_flights_chart.png"

    container_content = [
        [HALF_GRID_SPACER],
        [
            Paragraph(
                "Flights with the highest average contrail warming intensity (CO2e/km)",
                section_title_style
            )
        ],
        [HALF_GRID_SPACER],
        [
            Paragraph(
                (
                    f"These are the OD pairs to focus on for navigational avoidance trials. "
                    f"The average carbon dioxide emissions per kilometer for {data.get('airline_name')} in<br/>"
                    f"September was XX kg CO2/km. "
                    f"The OD pair with the highest contrail warming per kilometer is EMA - CPH adding XX kg CO2e/km - or<br/>"
                    f"X.X times the average warming from the CO2 alone."
                ),
                body_style
            )
        ],
        [
            Paragraph(
                "The most warming OD pairs per flown kilometer are often flights that fly through contrail-prone zones (for example the Eastern part of<br/>the US) at night, when contrails are most warming.",
                body_style
            )
        ],
        [HALF_GRID_SPACER],
        [
            Image(
                str(chart_path),
                width=17 * cm,
                height=7 * cm
            )
        ],
        [HALF_GRID_SPACER],
    ]

    return Table(container_content, colWidths="100%", style=container_table_style)


def create_actionable_insights_container(data: dict, airline_name: str):
    """
    Assembles the 'Actionable Contrails Flights' container with corrected vertical spacing.
    """
    # Left column with actionable insights text
    left_column_content = [
        [Paragraph("Actionable Contrails Flights", section_title_style)],
        [Paragraph(
            "Contrails are considered actionable if their warming impact is above xx<br/>kg CO2e/km, their lifespan is more than XX minutes, and they exists<br/>outside of extremely congested airspace areas",
            body_style,
        )],
        [HALF_GRID_SPACER],
        [Paragraph("Actionable contrails flights ⓘ", label_style)],
        [Paragraph(f"<font size=24>X%</font> of all {airline_name} flights are good candidates to reroute", body_style)],
        [GRID_SPACER],[GRID_SPACER],
        [Paragraph("Top 10 OD pairs responsible for ⓘ", label_style)],
        [Paragraph("<font size=24>x%</font> of total airline contrails warming", body_style)],
    ]
    left_column_table = Table(left_column_content, colWidths='100%')

    blue_box_content = [
        [Paragraph("Top ways to reduce contrails", section_title_style)],
        [Paragraph(
            "1) Reduce nighttime flights<br/>"
            "2) Do vertical or lateral deviations to avoid the<br/>  flight levels with contrails predicted zones<br/>"
            "3) SAFs and low-aromatic fuels can also reduce<br/> contrail formation",
            ParagraphStyle(name='List', parent=body_style, fontSize=8, leading=12)
        )],
    ]
    blue_box_table = Table(blue_box_content, style=blue_highlight_box_style)
    
    # Bottom statistics table
    bottom_stats_table = Table(
        [
            [Paragraph("OD pair with the highest contrail warming per/km is EMA - CPH ⓘ", label_style), None, None],
            [
                Paragraph("<font size=24>x</font> kg CO2e/km", body_style),
                Paragraph("<font size=24>x</font> kg CO2e/km in fuel emissions", body_style),
                Paragraph("<font size=24>x</font> average warming from CO2 alone", body_style)
            ],
        ],
        colWidths=["20%", "25%", "45%"],
        style=od_pair_stats_table_style
    )

    # Assemble final container with all components
    final_container_content = [
        [HALF_GRID_SPACER],
        [Table([[left_column_table, blue_box_table]], colWidths=["60%", "40%"], style=[('VALIGN', (0,0), (-1,-1), 'TOP')])],
        [GRID_SPACER],[GRID_SPACER],
        [bottom_stats_table],
        [GRID_SPACER],
        [GRID_SPACER],
    ]
    return Table(final_container_content, colWidths="100%", style=container_table_style)
