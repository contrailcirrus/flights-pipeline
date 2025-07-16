from reportlab.platypus import (
    Paragraph,
    Spacer,
    Table,
    Image,
)
from reportlab.lib.units import cm
from pathlib import Path
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from styles import (
    section_title_style,
    body_style,
    label_style,
    container_table_style,
    page_num_style,
    OBSERVATION_COLOR,
    ALGORITHM_COLOR,
    LINE_COLOR,
    PREDICTED_COLOR,
    CONFIRMED_COLOR,
    map_legend_style,
    divider_line_style,
    three_col_stats_style,
    GRID_UNIT,
    HALF_GRID_SPACER,
    TOTAL_PAGES,
)






def build_fifth_page(data: dict, output_path: Path, airline_name: str):

    """
    Assembles the entire 5th page for the report.
    """
    story = []

    # Page number
    story.append(Table([[Paragraph(f"Page 5 of {TOTAL_PAGES}", page_num_style)]]))
    story.append(Spacer(1, GRID_UNIT))

    # Main content container
    story.append(Spacer(1, GRID_UNIT))
    story.append(create_observation_coverage_container(output_path))
    story.append(Spacer(1, GRID_UNIT))
    story.append(create_case_study_container(output_path))

    return story


def create_observation_coverage_container(output_path: Path):
    """
    Creates the observation coverage container with the exact 3-column statistics layout
    """
    container_content = []

    # Header section
    container_content.extend([
        [HALF_GRID_SPACER],
        [Paragraph("Observation coverage area & verification", section_title_style)],
        [HALF_GRID_SPACER],
        [Paragraph(
            "The yellow area shows the coverage region where our satellite imagery based verification has been validated. For the rest of the world, we use our algorithm predictions.",
            body_style,
        )],
        [Spacer(1, GRID_UNIT)],
    ])

    # Map section
    map_image_path = output_path / "figs" / "flight_paths_map.png"
    if map_image_path.exists():
        map_image = Image(str(map_image_path), width=17 * cm, height=11 * cm)
        map_container = Table([[map_image]], style=container_table_style)
        container_content.append([map_container])
        container_content.append([Spacer(1, GRID_UNIT)])
    else:
        container_content.append([Paragraph("Map image not found", body_style)])

    # Legend section
    legend_style = ParagraphStyle(
        name="LegendLabel", fontName="Helvetica", fontSize=10, textColor=colors.black
    )
    legend_data = Table(
        [[
            Paragraph(f'<font color="{OBSERVATION_COLOR.hexval()}">●</font> Observations area', legend_style),
            Paragraph(f'<font color="{ALGORITHM_COLOR.hexval()}">◯</font> Algorithm prediction area', legend_style),
            Paragraph(f'<font color="{LINE_COLOR.hexval()}">—</font> Flight paths', legend_style),
        ]],
        colWidths=["33%", "34%", "33%"],
    )
    legend_data.setStyle(map_legend_style) # Use new style
    container_content.append([legend_data])

    # Divider line
    divider = Table([[""]], colWidths=["100%"], style=divider_line_style, rowHeights=10) # Use new style
    container_content.append([divider])

    # Statistics section
    stat_label_style = ParagraphStyle("StatLabel", parent=body_style, fontSize=8, textColor=colors.black)
    stat_value_style = ParagraphStyle("StatValue", parent=body_style, fontSize=14, textColor=colors.black)
    stats_table = Table(
        [[
            Table([[Paragraph("Predicted contrails in observation area", stat_label_style)], [Spacer(1, 2)], [Paragraph("<font size='24'>1,218</font><font size='10'> km</font>", stat_value_style)]]),
            Table([[Paragraph("Verified contrails kilometers", stat_label_style)], [Spacer(1, 2)], [Paragraph("<font size='24'>1,850K</font><font size='10'> km</font>", stat_value_style)]]),
            Table([[Paragraph("Verification rate", stat_label_style)], [Spacer(1, 2)], [Paragraph("<font size='24'>80%</font><font size='10'> accuracy</font>", stat_value_style)]]),
        ]],
        colWidths=["35%", "34%", "31%"],
    )
    stats_table.setStyle(three_col_stats_style) # Use new style
    container_content.append([stats_table])
    container_content.append([HALF_GRID_SPACER])

    # Final container
    final_container = Table(container_content, colWidths="100%")
    final_container.setStyle(container_table_style)
    return final_container

def create_case_study_container(output_path: Path):
    """
    Assembles the 'Case study: predicted vs verified contrails' container
    """
    container_content = []

    # Title and Description
    title_style = ParagraphStyle('CaseStudyTitle', parent=section_title_style, spaceAfter=6)
    container_content.extend([
        [Spacer(1, GRID_UNIT)],
        [Paragraph("Case study: predicted vs verified contrails", title_style)],
        [HALF_GRID_SPACER],
        [Paragraph("The light yellow color shows the observation area...", body_style)],
        [Spacer(1, GRID_UNIT)],
        [Paragraph("HKG-CVG September 10, 2024", label_style)],
        [HALF_GRID_SPACER],
    ])

    # Chart Image
    chart_image_path = output_path / "figs" / "case_study_chart.png"
    try:
        image_width = 18 * cm
        image_height = image_width * (3 / 14)
        chart_image = Image(str(chart_image_path), width=image_width, height=image_height)
        container_content.append([chart_image])
    except Exception as e:
        container_content.append([Paragraph(f"Could not load chart: {e}", body_style)])

    # Legend
    container_content.append([HALF_GRID_SPACER])
    legend_style = ParagraphStyle("LegendLabel", fontName="Helvetica", fontSize=10, textColor=colors.black)
    legend_table = Table(
        [[
            Paragraph(f'<font color="{OBSERVATION_COLOR.hexval()}">●</font> Confirmed contrails', legend_style),
            Paragraph(f'<font color="{PREDICTED_COLOR.hexval()}">●</font> Predicted contrails ', legend_style),
            Paragraph(f'<font color="{CONFIRMED_COLOR.hexval()}">◯</font> Observation region', legend_style),
            Paragraph(f'<font color="{LINE_COLOR.hexval()}">—</font> Flight paths', legend_style),
        ]],
        colWidths=["33%", "34%", "33%"],
    )
    
    legend_table.setStyle(map_legend_style)
    container_content.append([legend_table])

    # Final Container
    final_container = Table(container_content, colWidths="100%")
    final_container.setStyle(container_table_style)
    return final_container