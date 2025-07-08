from reportlab.platypus import (
    Paragraph,
    Spacer,
    Table,
    Image,
)
from reportlab.lib.units import cm
from pathlib import Path

from styles import (
    section_title_style,
    body_style,
    container_table_style,
    page_num_style,
    GRID_UNIT,
    inner_table_style,
)

TOTAL_PAGES = 5
GRID_SPACER = Spacer(1, GRID_UNIT)
HALF_GRID_SPACER = Spacer(1, GRID_UNIT / 2)
QUARTER_GRID_SPACER = Spacer(1, GRID_UNIT / 4)


def build_second_page(output_path: Path, airline_name: str):
    """
    Assembles the entire 2nd page for the report.
    """
    story = []

    # --- Page Number ---
    story.append(Table([[Paragraph(f"Page 2 of {TOTAL_PAGES}", page_num_style)]]))
    story.append(GRID_SPACER)

    # --- Contrails CONTAINER ---
    story.append(create_fuel_emissions_container(output_path))
    story.append(GRID_SPACER)
    story.append(create_Contrail_warming_container(output_path))
    story.append(GRID_SPACER)
    story.append(create_comparison_table_container(output_path))
    return story


def create_fuel_emissions_container(output_path: Path):
    """
    Assembles the fuel emissions contrails container with the bar chart.
    """
    container_content = [
        [HALF_GRID_SPACER],
        [
            Paragraph(
                "Fuel emissions (CO2) vs contrail warming (CO2e)", section_title_style
            )
        ],
        [GRID_SPACER],
    ]

    container_content.append(
        [
            Paragraph(
                "The contrail warming impact is often lower in the summertime and higher in dark months. This is because contrail<br></br>clouds that persist in the dark are the most warming.",
                body_style,
            )
        ]
    )

    chart_path = output_path / "figs" / "page2_stacked_gwp_chart.png"
    if chart_path.exists():
        chart_image = Image(chart_path, width=18 * cm, height=8 * cm)
    else:
        chart_image = Paragraph(f"Error: Chart not found at {chart_path}", body_style)

    container_content.extend([[HALF_GRID_SPACER], [chart_image], [HALF_GRID_SPACER]])

    container_table = Table(container_content, colWidths="100%")
    container_table.setStyle(container_table_style)

    return container_table


def create_Contrail_warming_container(output_path: Path):
    """
    Assembles the contrails warming container and add the Day vs Nighttime chart
    """
    container_content = [
        [HALF_GRID_SPACER],
        [Paragraph("Contrail warming - day time vs nighttime", section_title_style)],
        [GRID_SPACER],
    ]

    container_content.append(
        [
            Paragraph(
                "Night time is 3hours before sunrise and 3hours after sunset for the geographic location of the contrails forming. The majority of contrails warming flights are during nighttime. Reducing red-eye flights or optimizing those flight paths with vertical deviations is one of the most effective strategies for avoiding contrails.",
                body_style,
            )
        ]
    )

    chart_path = output_path / "figs" / "page2_day_night_chart.png"
    if chart_path.exists():
        chart_image = Image(chart_path, width=16 * cm, height=3 * cm)
    else:
        chart_image = Paragraph(f"Error: Chart not found at {chart_path}", body_style)

    container_content.extend([[HALF_GRID_SPACER], [chart_image], [HALF_GRID_SPACER]])

    container_table = Table(container_content, colWidths="100%")
    container_table.setStyle(container_table_style)

    return container_table


def create_comparison_table_container(output_path: Path):
    """
    Assembles the comparison table container.
    """
    # TODO: Add real data
    table_data = [
        [
            "Airline",
            "Contrails/km",
            "% of CO2 emissions",
            "% of Contrails (CO2e emissions)",
        ],
        ["[You] Airline X", "6.4%", "60%", "40%"],
        ["Average", "6.9%", "70%", "30%"],
        ["Median", "5.4%", "65%", "35%"],
    ]

    container_content = [
        [HALF_GRID_SPACER],
        [
            Paragraph(
                "[airline name] Contrails CO2e vs average airline CO2e",
                section_title_style,
            )
        ],
        [GRID_SPACER],
    ]

    container_content.append(
        [
            Paragraph(
                "See how your overall contrail impact compares to the average",
                body_style,
            )
        ]
    )

    container_content.append(
        [
            Table(
                table_data,
                colWidths=["10%", "10%", "15%", "22%"],
                style=inner_table_style,
            )
        ]
    )
    container_content.append([HALF_GRID_SPACER])

    container_table = Table(container_content, colWidths="100%")
    container_table.setStyle(container_table_style)

    return container_table
