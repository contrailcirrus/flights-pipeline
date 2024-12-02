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
scaling_factor = 15/18


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
        TTFont("Roboto", FONT_PATH + "Roboto/Roboto-Regular.ttf")
    )
    pdfmetrics.registerFont(TTFont('Roboto-Light', FONT_PATH + 'Roboto/Roboto-Light.ttf'))


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
    c.drawImage(
        "logo_demo.png",
        left_margin,
        770,
        width=60,
        height=30,
    )

    c.setFillColor(background_text_color)
    c.setFont("Roboto", 12)
    c.drawString(525, 812, "Page 1 of 4")

    c.setFillColor(title_color)
    c.setFont("Roboto", 26)
    c.drawString(30, 750-28, "Airline Contrail Impact Report 2024")

    # What are Contrails? section
    draw_container(
        c=c, x=left_margin, y=540-28, width=page_width - left_margin * 2 + 5, height=195
    )

    c.setFont("Roboto", 14)
    c.drawString(left_margin + vertical_spacing, 710-28, "What are Contrails?")

    contrails_text = """Contrails — the thin, white lines you sometimes see behind airplanes — have a surprisingly large impact on our climate. Contrails warm the planet because contrail clouds act like a blanket on Earth and have a net heating effect. The 2022 IPCC report noted that clouds created by contrails account for roughly 35% of aviation's global warming impact — over half the impact of the world's jet fuel. Find more info about contrails and the climate on our website """
    current_y = draw_text_block(
        c=c,
        text=contrails_text,
        x=left_margin + vertical_spacing,
        y=690-28,
        font_name="Roboto",
        font_size=container_text_font_size,
    )

    link_text = "contrails.org"
    c.setFont("Roboto", container_text_font_size)
    after_text_width = 92
    c.setFillColor(text_color)
    c.drawString(
        left_margin + after_text_width,
        current_y + (container_text_font_size * 2),
        link_text,
    )
    link_width = c.stringWidth(link_text, "Roboto", container_text_font_size)
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
    c.setFont("Roboto", 14)
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
        font_name="Roboto",
        font_size=container_text_font_size,
    )


    draw_container(
        c=c,
        x=left_margin,
        y=current_y - (467+18) * scaling_factor,
        width=container_width,
        height=6.25 * 72 * scaling_factor,
    )
    c.setFont("Roboto", 16)
    current_y = draw_text_block(
        c=c,
        text="Impact Data",
        x=left_margin + vertical_spacing,
        y=current_y - 55,
        font_name="Roboto",
        font_size=16,
    )
    stats_text = """Based on our prediction model, 5.5 Million km (55,501 flight hours) or 4.4% of all [Airline] flights generate warming contrails in 2024."""
    current_y = draw_text_block(
        c=c,
        text=stats_text,
        x=left_margin + vertical_spacing,
        y=current_y + vertical_spacing,
        font_name="Roboto",
        font_size=container_text_font_size,
    )


    def format_number(n: int) -> str:
        if n >= 1_000_000:
            return f"{n/1_000_000:,.1f}M"
        elif n >= 1000:
            return f"{n/1000:,.0f}k"
        return f"{n:,}"

    stats_data = {
        "# of Flights": {
            "value": f"{data['count_flights']:,}",
            "unit": "flights"
        },
        "Flight hours": {
            "value": f"{data['flight_hours']['total']:,}",
            "unit": "hours"
        },
        "Contrails (GWP 50)": {
            "value": f"{format_number(data['co2e_metric_tons']['gwp50']['total'])}",
            "unit": "metric tons CO2e"
        },
        "Fuel Burn": {
            "value": f"{format_number(data['total_co2_metric_tons'])}",
            "unit": "metric tons CO2"
        }
    }

    y = current_y - 50
    x = left_margin + vertical_spacing
    spacing_between_stats = 140

    for key, stat in stats_data.items():
        number = stat["value"]
        unit = stat["unit"]

        c.setFont("Roboto", 8)
        c.setFillColor(background_text_color)
        label_width = c.stringWidth(key, "Roboto", 8)
        circle_y = y + 29
        c.drawString(x, circle_y-3, key)
        
        # Draw info symbol (circle with i)
        circle_x = x + label_width + 8
        c.circle(circle_x, circle_y, 4, stroke=1, fill=0)
        c.setFont("Roboto", 7)
        i_width = c.stringWidth('i', "Roboto", 7)
        c.drawString(circle_x - i_width/2, circle_y - 2.25, 'i')

        c.setFont("Roboto", 24)
        c.setFillColor(text_color)
        number_width = c.stringWidth(number, "Roboto", 20)
        c.drawString(x, y, number)

        c.setFont("Roboto", 8)
        c.drawString(x + number_width + 10, y, unit)

        x += spacing_between_stats

    c.setStrokeColor(background_text_color)
    c.setLineWidth(0.5)
    c.line(left_margin, y-32, page_width - left_margin+5, y-32)

    container_bottom = y - (467+18) * scaling_factor
    midpoint_x = (left_margin + (page_width - left_margin + 5)) / 2
    midpoint_y = (y - 118 + container_bottom) / 2

    c.line(midpoint_x, y - 32, midpoint_x, midpoint_y)

    c.setStrokeColor(background_text_color)
    c.setLineWidth(0.5)
    c.line(left_margin, y-118, page_width - left_margin+5, y-118)

    return c


def draw_grid(c: Any, page_width: float, page_height: float) -> None:
    """Draw a grid with lines every 1/4 inch (18 points), with inch lines bolded"""
    c.saveState()
    c.setStrokeColor("#CCCCCC")

    # Grid spacing (1/4 inch = 18 points since 72 points = 1 inch),
    # but the example pdf looks to have 15 points (10 big segments across?)
    small_grid_spacing = int(18 * scaling_factor)
    inch_grid_spacing = int(72 * scaling_factor)

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
