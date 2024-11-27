"""
Generate a PDF report to match the google designed flight report template.
"""

import argparse
from datetime import datetime
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
import json
from typing import Optional, Dict, Any

# A4 size in points (595.27 x 841.89)
# 1 point = 1/72 inch
# A4 is 210mm × 297mm (8.27 × 11.69 inches)
page_width = 595.27
page_height = 841.89
title_color = "#111111"  # dark dark gray
text_color = "#444444"  # dark gray
container_color = "#ffffff"
background_text_color = "#808080"
left_margin = 30
vertical_spacing = 10
container_width = page_width - left_margin * 2 + 5
container_text_font_size = 8


def load_data(json_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
        if json_path is None:
            json_path = (
                "flights_report_summary_D0_2024-08-01_2024-08-31_1732590322.json"
            )
        with open(json_path, "r") as f:
            data = json.load(f)
        # Validate the data structure:
        if not isinstance(data, dict):
            raise ValueError("Invalid data structure: expected a dictionary")
        return data
    except Exception as e:
        print("Error loading data:", e)
        return None


def register_fonts() -> None:
    FONT_PATH = "freehand_design_assets/fonts/"
    pdfmetrics.registerFont(
        TTFont("Outfit", FONT_PATH + "Outfit/Outfit-VariableFont_wght.ttf")
    )
    pdfmetrics.registerFont(
        TTFont("Saira", FONT_PATH + "Saira/Saira-VariableFont_wdth,wght.ttf")
    )
    pdfmetrics.registerFont(
        TTFont(
            "Saira-italic", FONT_PATH + "Saira/Saira-Italic-VariableFont_wdth,wght.ttf"
        )
    )
    pdfmetrics.registerFontFamily(
        "Helvetica",
        normal="Helvetica",
        bold="Helvetica-Bold",
        italic="Helvetica-Oblique",
        boldItalic="Helvetica-BoldOblique",
    )


def draw_text_block(
    c, text, x, y, font_name, font_size, width=520, height=None
) -> float:
    """Draw a block of text"""
    from reportlab.lib.utils import simpleSplit

    c.setFont(font_name, font_size)
    # Split text into paragraphs
    paragraphs = text.split("\n\n")
    current_y = y

    for paragraph in paragraphs:
        lines = simpleSplit(paragraph.strip(), font_name, font_size, width)
        for line in lines:
            c.drawString(x, current_y, line)
            current_y -= font_size * 1.2
        # Add extra space between paragraphs
        current_y -= font_size * 0.8

    return current_y


def draw_container(
    c: Any, x: float, y: float, width: float, height: float, radius: float = 10
) -> None:
    """Helper function to draw rounded rectangle containers"""
    c.setStrokeColor(background_text_color)
    c.roundRect(x, y, width, height, radius, fill=0, stroke=1)
    c.setFillColor(text_color)


def create_page_one(c: Any, data: Dict[str, Any]) -> Any:
    """Generate the first page of the report"""

    c.setFont("Helvetica", 8)
    c.setFillColor("#808080")  # light gray
    c.drawString(left_margin + vertical_spacing, 50, "Page 1 of 4")

    c.setFillColor(title_color)
    c.setFont("Helvetica", 26)
    c.drawString(30, 750, "Airline Contrail Impact Report 2024")

    # What are Contrails? section
    draw_container(
        c=c, x=left_margin, y=540, width=page_width - left_margin * 2 + 5, height=195
    )

    c.setFont("Helvetica", 14)
    c.drawString(left_margin + vertical_spacing, 710, "What are Contrails?")

    contrails_text = """Contrails — the thin, white lines you sometimes see behind airplanes — have a surprisingly large impact on our climate. Contrails warm the planet because contrail clouds act like a blanket on Earth and have a net heating effect. The 2022 IPCC report noted that clouds created by contrails account for roughly 35% of aviation's global warming impact — over half the impact of the world's jet fuel. Find more info about contrails and the climate on our website """
    current_y = draw_text_block(
        c=c,
        text=contrails_text,
        x=left_margin + vertical_spacing,
        y=690,
        font_name="Helvetica",
        font_size=container_text_font_size,
    )

    # Add the hyperlink text and annotation
    link_text = "contrails.org"
    c.setFont("Helvetica", container_text_font_size)
    # Set the width of the text that comes before the link
    after_text_width = 92
    c.setFillColor(text_color)
    c.drawString(
        left_margin + after_text_width,
        current_y + (container_text_font_size * 2),
        link_text,
    )
    link_width = c.stringWidth(link_text, "Helvetica", container_text_font_size)
    c.linkURL(
        "https://www.contrails.org",
        (
            left_margin + after_text_width,
            current_y + (9 * 2) - 2,
            left_margin + after_text_width + link_width,
            current_y + (9 * 2) + 9,
        ),
    )
    c.setFillColor(text_color)

    # GWP Section
    c.setFont("Helvetica", 14)
    c.setFillColor(text_color)
    c.drawString(
        left_margin + vertical_spacing,
        current_y - vertical_spacing,
        "What is Global Warming Potential (GWP)?",
    )

    gwp_text = """GWP measures how much warming contrails cause over a number of years compared to CO2. Contrails heat the Earth quickly but for a short time, and GWP helps compare their short-term impact to the longer-lasting greenhouse gas, CO2.

    In this report we initially show the contrail impact in CO2e over 20, 50 and 100 years to align with the guidelines from the EU Non-CO2 MRV report starting in 2025. Wherever we only show one value for CO2e we use the middle value, GWP50, as default."""
    current_y = draw_text_block(
        c=c,
        text=gwp_text,
        x=left_margin + vertical_spacing,
        y=current_y - 40,
        font_name="Helvetica",
        font_size=container_text_font_size,
    )

    # Impact Data Section
    draw_container(
        c=c, x=left_margin, y=current_y - 230, width=container_width, height=200
    )
    c.setFont("Helvetica", 16)
    current_y = draw_text_block(
        c=c,
        text="Impact Data",
        x=left_margin + vertical_spacing,
        y=current_y - 55,
        font_name="Helvetica",
        font_size=16,
    )
    stats_text = """Based on our prediction model, 5.5 Million km (55,501 flight hours) or 4.4% of all [Airline] flights generate warming contrails in 2024."""
    current_y = draw_text_block(
        c=c,
        text=stats_text,
        x=left_margin + vertical_spacing,
        y=current_y + vertical_spacing,
        font_name="Helvetica",
        font_size=container_text_font_size,
    )

    # ruff: noqa: F841
    stats_data = {
        "# of Flights": f"{data['count_flights']:,} flights",
        "Flight hours": f"{data['flight_hours']['total']:,} hours",
        "Contrails Distance": f"{data['flight_distance_km']['with_contrails']['total']:,} km",
        "Warming Contrails": f"{data['flight_distance_km']['with_contrails']['is_warming']['total']:,} km",
    }

    # Draw stats
    # y = 440
    # for key, value in stats_data.items():

    return c


def draw_grid(c: Any, page_width: float, page_height: float) -> None:
    """Draw a grid with lines every 1/4 inch (18 points), with inch lines bolded"""
    c.saveState()
    c.setStrokeColor("#CCCCCC")

    # Grid spacing (1/4 inch = 18 points since 72 points = 1 inch),
    # but the example pdf looks to have 15 points (10 big segments across?)
    small_grid_spacing = 15
    inch_grid_spacing = 60

    # Thin lines
    c.setLineWidth(0.1)
    for x in range(0, int(page_width), small_grid_spacing):
        c.line(x, 0, x, page_height)

    for y in range(0, int(page_height), small_grid_spacing):
        c.line(0, y, page_width, y)

    # Bold lines
    c.setLineWidth(2)
    for x in range(0, int(page_width), inch_grid_spacing):
        c.line(x, 0, x, page_height)

    for y in range(0, int(page_height), inch_grid_spacing):
        c.line(0, y, page_width, y)

    c.restoreState()


def generate_pdf(output_path: str, data: Dict[str, Any]) -> None:
    register_fonts()

    c = canvas.Canvas(output_path, pagesize=(page_width, page_height))

    # Draw grid before creating each page
    draw_grid(c, page_width, page_height)
    create_page_one(c, data)
    c.showPage()

    # TODO: Add the other pages
    # create_page_two(c, data)
    # c.showPage()

    c.save()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a PDF report.")
    # parser.add_argument('--output', type=str, default=f"sample_report_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pdf", help='Output PDF file path')
    parser.add_argument(
        "--output", type=str, default=f"sample_report.pdf", help="Output PDF file path"
    )
    parser.add_argument(
        "--data",
        type=str,
        default="flights_report_summary_D0_2024-08-01_2024-08-31_1732590322.json",
        help="Path to JSON data file",
    )
    args = parser.parse_args()

    data = load_data(args.data)
    generate_pdf(args.output, data)


if __name__ == "__main__":
    main()
