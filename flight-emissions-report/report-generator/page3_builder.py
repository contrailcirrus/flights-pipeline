from reportlab.platypus import (
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)
from pathlib import Path

from styles import (
    body_style,
    container_table_style,
    highlighted_box_style,
    inner_table_style,
    label_style,
    page_num_style,
    section_title_style,
    two_by_two_table_style,
    two_column_stats_style,
    TOTAL_PAGES,
    GRID_SPACER,
    HALF_GRID_SPACER,
)
from setup import ASSETS_DIR




def build_third_page(data: dict, output_path: Path, airline_name: str):
    """
    Assembles the entire 3rd page for the report.
    """
    page_content = []

    # --- Page Number ---
    page_content.append(Table([[Paragraph(f"Page 3 of {TOTAL_PAGES}", page_num_style)]]))
    page_content.append(GRID_SPACER)

    # --- Addressing Contrail Warming CONTAINER ---
    page_content.append(create_addressing_contrail_warming())
    page_content.append(GRID_SPACER)
    page_content.append(create_impact_data_container(data))

    return page_content


def create_addressing_contrail_warming():
    """
    Assembles the 'Addressing 80% of contrail warming' container.
    """
    container_content = [
        [HALF_GRID_SPACER],
        [Paragraph("Addressing 80% of contrail warming", section_title_style)],
        [HALF_GRID_SPACER],
        [
            Paragraph(
                "<font size=10>To avoid 80% of the contrail warming, 5% of flights need to be adjusted. We call these the “problem flights.”</font>",
                body_style,
            )
        ],
        [GRID_SPACER],
    ]

    stat_block_1 = Table(
        [
            [Paragraph('% of flights that are "problem flights"', label_style)],
            [Paragraph("<font size=23>x.x%</font> flights", body_style)],
        ]
    )

    stat_block_2 = Table(
        [
            [Paragraph('Average CO2e for "problem flights"', label_style)],
            [Paragraph("<font size=23>x</font> kg CO2e/km", body_style)],
        ]
    )

    stat_block_3 = Table(
        [
            [Paragraph("For 1M flights per year, that is on average", label_style)],
            [Paragraph("<font size=23>x</font> flights / day to re-route", body_style)],
        ]
    )

    left_column_table = Table(
        [[stat_block_1, stat_block_2], [GRID_SPACER], [stat_block_3, ""]],
        colWidths=["52%", "48%"],
        style=two_by_two_table_style,
    )

    fuel_burn_content = [
        [HALF_GRID_SPACER],
        [
            Paragraph(
                "Estimated fuel burn to avoid 80% of contrails warming",
                section_title_style,
            )
        ],
        [HALF_GRID_SPACER],
        [Paragraph("Based on XXX study by XX published on XX date.", body_style)],
        [GRID_SPACER],
        [Paragraph("Average additional fuel burn ⓘ", label_style)],
        [Paragraph("<font size=23>x-x%</font> more fuel", body_style)],
    ]
    right_column_table = Table(
        fuel_burn_content, style=highlighted_box_style, rowHeights=[None] * 6 + [60]
    )

    stats_container = Table(
        [[left_column_table, right_column_table]],
        colWidths=["62%", "38%"],
        style=two_column_stats_style,
    )

    container_content.append([stats_container])
    container_content.append([HALF_GRID_SPACER])

    final_container = Table(container_content, colWidths="100%")
    final_container.setStyle(container_table_style)

    return final_container


def create_impact_data_container(data: dict):
    """
    Assembles the 'Impact Data: Intra-European flights only' container
    with the correct full-width and two-column sections.
    """
    main_content_flow = []

    main_content_flow.append(
        Paragraph("Impact Data: Intra-European flights only", section_title_style)
    )
    main_content_flow.append(HALF_GRID_SPACER)
    main_content_flow.append(
        Paragraph(
            (
                f"Based on our prediction model, this is the impact from the {data['airline_name']} flights that are included in the EU’s non-CO2 reporting requirements."
                "<br></br>"
                "The EU ETS area covers flights within and between countries in the European Economic Area (EEA), "
                "which consists of EU member states<br></br>"
                "and Iceland, Norway, and Liechtenstein), and from the EEA to the UK and Switzerland. "
                "It also covers the EU’s nine, so called outermost<br></br>"
                "regions: French Guiana, Guadeloupe, Martinique, Mayotte, Reunion island, Saint-Martin, Azores, Madeira, and The Canary Islands."
            ),
            body_style,
        )
    )
    main_content_flow.append(HALF_GRID_SPACER)
    main_content_flow.append(
        Paragraph(
            "Based on our prediction model, we analyzed X.X flights, X.X Million km (55,501 flight hours). Of those, X.X% of all "
            f"{data['airline_name']} flights generated warming contrails in 2024 within intra-European flights.",
            body_style,
        )
    )
    main_content_flow.append(GRID_SPACER)
    main_content_flow.append(HALF_GRID_SPACER)



    left_column_content = [
        Table(
            [
                [Paragraph("% of contrails warming flights ⓘ", label_style)],
                [Paragraph("<font size=23>x%</font> flights", body_style)],
            ],
            style=TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0)]),
        ),
        GRID_SPACER,
        GRID_SPACER,
        Paragraph("2025-2026: Intra-European Flights only", section_title_style),
        HALF_GRID_SPACER,
        Paragraph(
            "Multiply the cost per 1000 km flown with total km flown (in thousands) within Europe to find total possible cost",
            body_style,
        ),
        HALF_GRID_SPACER,
        Table(
            [
                ["GWP", "Contrail Warming", "€50 / ton CO2e", "€100 / ton CO2e"],
                [
                    "GWP 20",
                    "x.x kg CO2e/1000 km flown",
                    "€x.x per 1000 km flown",
                    "€x.x per 1000 km flown",
                ],
                [
                    "GWP 50",
                    "x.x kg CO2e/1000 km flown",
                    "€x.x per 1000 km flown",
                    "€x.x per 1000 km flown",
                ],
                [
                    "GWP 100",
                    "x.x kg CO2e/1000 km flown",
                    "€x.x per 1000 km flown",
                    "€x.x per 1000 km flown",
                ],
            ],
            style=inner_table_style,
        ),
        GRID_SPACER,
        Paragraph(
            "From 2027: All flights taking off in Europe (EEA)", section_title_style
        ),
        HALF_GRID_SPACER,
        Paragraph(
            "Multiply the cost per 1000 km flown with total km flown (in thousands) for flights taking off in Europe to find total possible cost",
            body_style,
        ),
        HALF_GRID_SPACER,
        Table(
            [
                ["GWP", "Contrail Warming", "€50 / ton CO2e", "€100 / ton CO2e"],
                [
                    "GWP 20",
                    "x.x kg CO2e/1000 km flown",
                    "€x.x per 1000 km flown",
                    "€x.x per 1000 km flown",
                ],
                [
                    "GWP 50",
                    "x.x kg CO2e/1000 km flown",
                    "€x.x per 1000 km flown",
                    "€x.x per 1000 km flown",
                ],
                [
                    "GWP 100",
                    "x.x kg CO2e/1000 km flown",
                    "€x.x per 1000 km flown",
                    "€x.x per 1000 km flown",
                ],
            ],
            style=inner_table_style,
        ),
    ]
    europe_map_path = ASSETS_DIR / "images" / "europe_map.png"
    right_column_content = [
        Spacer(1, -30),
        Image(europe_map_path, width=130, height=130),
    ]

    two_column_table = Table(
        data=[[left_column_content, right_column_content]],
        colWidths=["68%", "32%"],
        style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]),
    )

    main_content_flow.append(two_column_table)

    final_container_content = [[item] for item in main_content_flow]
    final_container_content.insert(0, [HALF_GRID_SPACER])
    final_container_content.append([HALF_GRID_SPACER])

    final_container = Table(final_container_content, colWidths="100%")
    final_container.setStyle(container_table_style)

    return final_container
