from reportlab.platypus import (
    Paragraph,
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
    inner_table_style,
    TOTAL_PAGES,
    GRID_SPACER,
    HALF_GRID_SPACER,
)


def build_second_page(data: dict, output_path: Path, airline_name: str):
    """Assembles the entire 2nd page for the report."""
    page_content = []

    # --- Page Number ---
    page_content.append(Table([[Paragraph(f"Page 2 of {TOTAL_PAGES}", page_num_style)]]))
    page_content.append(GRID_SPACER)

    # --- Page Content ---
    page_content.append(create_p2_stacked_gwp_container(output_path))
    page_content.append(GRID_SPACER)
    page_content.append(create_p2_day_night_container(output_path))
    page_content.append(GRID_SPACER)
    page_content.append(create_comparison_table_container(data, airline_name))
    
    return page_content


def create_p2_stacked_gwp_container(output_path: Path):
    """Assembles the 'Fuel emissions vs contrail warming' container."""
    chart_path = output_path / "figs" / "page2_stacked_gwp_chart.png"

    container_content = [
        [HALF_GRID_SPACER],
        [Paragraph("Fuel emissions (CO2) vs contrail warming (CO2e)", section_title_style)],
        [HALF_GRID_SPACER],
        [Paragraph(
            "The contrail warming impact is often lower in the summer time and higher in dark months. This is because contrail<br></br>clouds that persist in the dark are the most warming.",
            body_style
        )],
        [GRID_SPACER],
    ]

    if chart_path.exists():
        container_content.append([Image(str(chart_path), width=500, height=200)])
    else:
        container_content.append([Paragraph("Chart not available", body_style)])

    container_content.append([HALF_GRID_SPACER])
    return Table(container_content, colWidths="100%", style=container_table_style)


def create_p2_day_night_container(output_path: Path):
    """Assembles the 'Contrail warming - daytime vs nighttime' container."""
    chart_path = output_path / "figs" / "page2_day_night_chart.png"

    image_width = 17 * cm
    image_height = image_width * (150 / 800)

    container_content = [
        [HALF_GRID_SPACER],
        [Paragraph("Contrail warming - daytime vs nighttime", section_title_style)],
        [HALF_GRID_SPACER],
        [Paragraph(
            "Night time is 3hours before sunrise and 3hours after sunset for the geographic location of the contrails forming. The<br></br>majority of contrails warming flights are during nighttime. Reducing red-eye flights or optimizing those flight paths with<br></br>vertical deviations is one of the most effective strategies for avoiding contrails.",
            body_style
        )],
        [GRID_SPACER],
    ]

    if chart_path.exists():
        container_content.append([Image(str(chart_path), width=image_width, height=image_height)])
    else:
        container_content.append([Paragraph("Chart not available", body_style)])

    container_content.append([HALF_GRID_SPACER])
    return Table(container_content, colWidths="100%", style=container_table_style)


def create_comparison_table_container(data: dict, airline_name: str):
    """Assembles the comparison table, using real data for the user's airline and placeholders for benchmark data."""
    total_co2 = data["co2_metric_tons"]["total"]
    gwp50_co2e = data["co2e_metric_tons"]["gwp50"]["total"]
    total_warming = total_co2 + gwp50_co2e

    your_contrails_km_pct = data['percentages']['flight_distance_with_warming_contrails']
    your_co2_pct = (total_co2 / total_warming) * 100
    your_contrail_pct = 100 - your_co2_pct
    
    table_data = [
        [
            Paragraph("<b>Airline</b>", body_style),
            Paragraph("<b>Contrails/km</b>", body_style),
            Paragraph("<b>% of CO₂ emissions</b>", body_style),
            Paragraph("<b>% of Contrails (CO2e emissions)</b>", body_style),
        ],
        [
            f"{airline_name}",
            f"{your_contrails_km_pct:.1f}%",
            f"{your_co2_pct:.0f}%",
            f"{your_contrail_pct:.0f}%",
        ],
        # TODO: Replace with real data
        ["Average", "x.x%", "xx%", "xx%"],
        ["Median", "x.x%", "xx%", "xx%"],
    ]

    container_content = [
        [HALF_GRID_SPACER],
        [Paragraph(f"{airline_name} Contrails CO2e vs average airline CO2e", section_title_style)],
        [HALF_GRID_SPACER],
        [Paragraph("See how your overall contrail impact compares to the average.", body_style)],
        [GRID_SPACER],
        [Table(table_data, style=inner_table_style, colWidths=["15%", "15%", "15%", "30%"])],
        [HALF_GRID_SPACER],
    ]

    return Table(container_content, colWidths="100%", style=container_table_style)