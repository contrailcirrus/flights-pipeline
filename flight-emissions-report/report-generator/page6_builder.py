from reportlab.platypus import Paragraph, Spacer, Table, Image
from pathlib import Path
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors  # Import the colors module

# Add new imports for drawing legend shapes
from reportlab.graphics.shapes import Drawing, Rect
from styles import (
    section_title_style,
    body_style,
    container_table_style,
    page_num_style,
    valign_middle_style, # New import
    HALF_GRID_SPACER,
    QUARTER_GRID_SPACER,
    TOTAL_PAGES,
)


def build_sixth_page(data: dict, output_path: Path, airline_name: str):
    """
    Assembles the entire 6th page for the report.
    """
    story = []
    story.append(Table([[Paragraph(f"Page 6 of {TOTAL_PAGES}", page_num_style)]]))
    story.append(HALF_GRID_SPACER)

    story.append(create_warming_by_month_container(output_path))
    story.append(HALF_GRID_SPACER)
    story.append(create_warming_per_flight_container(output_path))
    story.append(HALF_GRID_SPACER)
    story.append(create_warming_by_departure_container(output_path))
    
    return story


def create_legend(legend_items: list):
    """
    Creates a simple, single-row table for the legend with EXPLICIT widths
    to guarantee a single-line layout.
    """
    legend_style = ParagraphStyle(name='Legend', parent=body_style, fontSize=9)
    
    row_of_cells = []
    col_widths = []
    
    for i, (color, text) in enumerate(legend_items):
        key = Drawing(width=10, height=10)
        key.add(Rect(0, 0, 10, 10, fillColor=color, strokeColor=None))
        row_of_cells.extend([key, Paragraph(text, legend_style)])
        col_widths.extend([12, 140])
        
        if i < len(legend_items) - 1:
            gap_width = 20
            row_of_cells.append(Spacer(width=gap_width, height=0))
            col_widths.append(gap_width)

    legend_table = Table([row_of_cells], colWidths=col_widths)
    legend_table.hAlign = 'RIGHT'
    
    # Use the new style from styles.py
    legend_table.setStyle(valign_middle_style)
    
    return legend_table
def create_warming_by_month_container(output_path: Path):
    """Assembles the 'Contrail warming by month' container."""
    chart_path = output_path / "figs" / "page6_warming_by_month.png"
    
    image_width = 16 * cm
    image_height = image_width * (3 / 10)

    container_content = [
        [HALF_GRID_SPACER],
        [Paragraph("Contrail warming by month", section_title_style)],
        [HALF_GRID_SPACER],
        [Paragraph("During the darker winter months, contrails have a higher warming effect as the days are shorter and there is less sunlight to reflect.", body_style)],
        [HALF_GRID_SPACER],
        [Image(str(chart_path), width=image_width, height=image_height)],
        [HALF_GRID_SPACER],
    ]

    legend_items = [
        (HexColor("#F72525"), "CO₂ Emissions (tCO₂e)"),
        (HexColor("#C3B8B3"), "Contrail Warming (tCO₂e)")
    ]
    legend_table = create_legend(legend_items)
    container_content.append([legend_table])
    container_content.append([HALF_GRID_SPACER])

    return Table(container_content, colWidths="100%", style=container_table_style)

def create_warming_per_flight_container(output_path: Path):
    """Assembles the 'Contrail Warming per Flight' container."""
    chart_path = output_path / "figs" / "page6_warming_per_flight.png"
    
    image_width = 16 * cm
    image_height = image_width * (4 / 10)
    
    container_content = [
        [HALF_GRID_SPACER],
        [Paragraph("Contrail Warming per Flight by Most Used Aircraft", section_title_style)],
        [HALF_GRID_SPACER],
        [Paragraph("Short-haul aircraft types generally produce fewer contrails than larger size planes that fly through the high-altitude contrail-prone areas for longer.", body_style)],
        [HALF_GRID_SPACER],
        [Image(str(chart_path), width=image_width, height=image_height)],
        [HALF_GRID_SPACER],
    ]
    

    legend_items = [
        (colors.gray, "Number of Flights"),
        (colors.red, "Contrail Warming per Flight")
    ]
    legend_table = create_legend(legend_items)
    container_content.append([legend_table])
    container_content.append([HALF_GRID_SPACER])

    return Table(container_content, colWidths="100%", style=container_table_style)

def create_warming_by_departure_container(output_path: Path):
    """Assembles the 'Contrail warming by local departure time' container."""
    chart_path = output_path / "figs" / "page6_warming_by_departure.png"

    image_width = 16 * cm
    image_height = image_width * (4 / 10)

    container_content = [
        [HALF_GRID_SPACER],
        [Paragraph("Contrail warming by local departure time", section_title_style)],
        [HALF_GRID_SPACER],
        [Paragraph("Contrails created later in the day have a higher warming effect because they last into the night and trap the Earth’s heat, whereas contrails created earlier in the day are able to dissipate before night falls.", body_style)],
        [HALF_GRID_SPACER],
        [Image(str(chart_path), width=image_width, height=image_height)],
        [HALF_GRID_SPACER],
    ]

    
    legend_items = [
        (colors.gray, "Contrail warming"),
        (colors.red, "Number of flights")
    ]
    legend_table = create_legend(legend_items)
    container_content.append([legend_table])
    container_content.append([QUARTER_GRID_SPACER])
    

    return Table(container_content, colWidths="100%", style=container_table_style)