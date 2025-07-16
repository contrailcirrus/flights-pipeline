from reportlab.platypus import Paragraph, Table, Image
from pathlib import Path
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
    TOTAL_PAGES,
    GRID_SPACER,
    HALF_GRID_SPACER,
    QUARTER_GRID_SPACER,
)
from setup import format_number


def build_first_page(data: dict, output_path: Path, airline_name: str):
    """Assembles the entire 1st page for the report."""
    page_content = []
    page_content.append(Table([[Paragraph(f"Page 1 of {TOTAL_PAGES}", page_num_style)]]))

    # --- Add Logo ---
    # TODO: Add logos of the airlines
    #page_content.append(
        #Table(
            #[[Image(str(LOGO_PATH), width=GRID_UNIT * 2, height=GRID_UNIT)]],
           # hAlign="LEFT",
        #)
    #)

    # --- Report Tilte ---
    page_content.append(Paragraph("Airline Contrail Impact Report 2024", report_title_style))

    # --- Contrails CONTAINER ---
    page_content.append(create_contrails_container(data))
    page_content.append(GRID_SPACER)

    # --- Impact Data CONTAINER ---
    page_content.append(build_impact_data_table(data, output_path, airline_name))
    return page_content


def create_contrails_container(data: dict):
    """Assembles the contrails container for page 1."""
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
        [Paragraph(f"<b>IATA Codes:</b> This report covers the {data['iata_code']} IATA code.", body_style)]
    )

    # Modeling Process Section and bullets
    container_content.append([Paragraph("<b>Modeling Process:</b>", body_style)])
    modeling_bullets = [
        "Flight trajectories are built from ADS-B data and undergo quality control, removing bad trajectories (this reduces the number of analyzed flights).",
        "The CoCiP physics-based model predicts contrails and CO2e impact.",
        "Aircraft type (e.g., B777) is used to select a default engine type for modeling, unless the airline provides specific aircraft-engine pairings.",
    ]
    container_content.extend(
        [[Paragraph(text, style=bullet_style, bulletText="•")] for text in modeling_bullets]
    )

    # Fuel Consumption Estimates Section
    container_content.append(
        [Paragraph("<b>Fuel Consumption Estimates:</b>", body_style)]
    )
    fuel_points = [
        "Fuel burn is based on the physics model, sensitive to engine type and assumed constant load factors (per aircraft type).",
        'It primarily reflects fuel consumption "during flight" or "at cruise," generally excluding taxi, and sometimes take-off/landing.',
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


def build_impact_data_table(data: dict, output_path: Path, airline_name: str):
    """Constructs a T-shaped table with dynamic data from the JSON file."""
    impact_data_rows = [
        QUARTER_GRID_SPACER,
        Paragraph("Impact Data", section_title_style),
    ]

    impact_text = (
        f"Based on our prediction model, we analyzed "
        f"{format_number(data['count_flights']['total'])} flights, "
        f"{format_number(data['flight_distance_km']['total'])} km "
        f"({format_number(data['flight_hours']['total'])} flight hours) and of those, "
        f"{data['percentages']['flight_distance_with_warming_contrails']}% of all "
        f"{airline_name} flights generated warming contrails in {data['year']}."
    )
    impact_data_rows.extend([Paragraph(impact_text, body_style), GRID_SPACER])

    # --- Calculate derived values for table display ---

    # Calculate airline's average CO2e per km (using GWP50)
    airline_total_co2e_gwp50 = data['co2e_metric_tons']['gwp50']['total']  # metric tons
    airline_total_distance_km = data['flight_distance_km']['total']         # km
    airline_avg_co2e_per_km = (airline_total_co2e_gwp50 * 1000) / airline_total_distance_km  # kg CO2e/km

    # Calculate average fuel burn per km (CO2 only)
    airline_total_co2 = data['co2_metric_tons']['total']  # metric tons
    avg_fuel_burn_per_km = (airline_total_co2 * 1000) / airline_total_distance_km  # kg CO2/km

    # TODO: Placeholder for all airlines average CO2e/km (to be replaced with real value)
    all_airlines_avg_co2e_per_km = "xx.x"

    # Prepare stats for display in the table
    stats_data_values = [
        (
            "Contrails percentage",
            f"<font size='23'>{data['percentages']['flight_distance_with_warming_contrails']}%</font> of flights km"
        ),
        (
            f"{airline_name} Average CO2e/km flown",
            f"<font size='22'>{airline_avg_co2e_per_km:.1f}</font> kg CO2e/km"
        ),
        (
            "All Airlines average CO2e/km",
            f"<font size='22'>{all_airlines_avg_co2e_per_km}</font> kg CO2e/km"
        ),
        (
            "Average fuel burn",
            f"<font size='22'>{avg_fuel_burn_per_km:.1f}</font> kg CO2/km"
        ),
    ]

    stats_data = [
        [Paragraph(label, label_style) for label, _ in stats_data_values],
        [Paragraph(value, body_style) for _, value in stats_data_values],
    ]
    stats_table = Table(stats_data, colWidths=["24%", "30%", "23%", "23%"])
    stats_table.setStyle(four_column_table_style)

    impact_data_rows.extend([stats_table, GRID_SPACER])
    
    gwp_title = Paragraph("<font size='10'>Global Warming</font>", body_style)
    gwp_title_2 = Paragraph("<font size='10'>potential 100, 50, 20</font>", body_style)
    gwp_text = Paragraph("Contrails are more warming in<br></br>the short term", body_style)
    chart_path = output_path / "figs" / "page1_gwp_bar_chart.png"
    
    if chart_path.exists():
        chart_image = Image(str(chart_path), width=385, height=165)
    else:
        chart_image = Paragraph(f"Error: Chart not found at {chart_path}", body_style)

    data_for_main_table = [
        [impact_data_rows],
        [
            [
                GRID_SPACER, gwp_title, QUARTER_GRID_SPACER,
                gwp_title_2, HALF_GRID_SPACER, gwp_text,
            ],
            [
                HALF_GRID_SPACER, chart_image, HALF_GRID_SPACER,
            ],
        ],
    ]
    return Table(data_for_main_table, colWidths=["25%", "75%"], style=t_shaped_table_style)
