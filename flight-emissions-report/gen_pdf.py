"""
Generate a PDF report to match the google designed flight report template.
"""

import argparse
import re
from datetime import datetime
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
import json
from typing import Optional, Dict, Any
from PIL import Image, ImageChops

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
horizontal_spacing = 10
vertical_spacing = 10
container_width = page_width - left_margin * 2 + 5
container_text_font_size = 8.5
container_title_font_size = 14
scaling_factor = 15 / 18


def trim_from_each_side(input_path: str, output_path: str, trim_pixels: int) -> None:
    image = Image.open(input_path)

    # Calculate the new bounding box
    width, height = image.size
    left = trim_pixels
    top = trim_pixels
    right = width - trim_pixels
    bottom = height - trim_pixels

    # Ensure the new bounding box is valid
    if right > left and bottom > top:
        image = image.crop((left, top, right, bottom))
    
    image.save(output_path)


def load_data(json_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
        if json_path is None:
            json_path = (
                "flights_report_summary_D0_2024-08-01_2024-08-31_1732590322.json"
            )
        with open(json_path, "r") as f:
            data = json.load(f)
        # Use regex to extract the airline code from the json path
        data["airline_iata"] = re.search(r"summary_(\w{2})_20", json_path).group(1)
        # TODO: integrate with lookup_airline_iata_to_name
        data["airline_name"] = data["airline_iata"]
        data["version_suffix"] = re.search(r"summary_(.*).json", json_path).group(1)
        # Validate the data structure:
        if not isinstance(data, dict):
            raise ValueError("Invalid data structure: expected a dictionary")
        return data
    except Exception as e:
        print("Error loading data:", e)
        return None


def register_fonts() -> None:
    FONT_PATH = "freehand_design_assets/fonts/"
    pdfmetrics.registerFont(TTFont("Roboto", FONT_PATH + "Roboto/Roboto-Regular.ttf"))
    pdfmetrics.registerFont(
        TTFont("Roboto-Light", FONT_PATH + "Roboto/Roboto-Light.ttf")
    )


def format_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:,.1f}M"
    elif n >= 1000:
        return f"{n/1000:,.0f}k"
    return f"{n:,}"


def draw_grid(c: Any, page_width: float, page_height: float) -> None:
    """Draw a grid with lines every 1/4 inch (18 points), with inch lines bolded"""
    c.saveState()
    c.setStrokeColor("#808080")  # muted red

    # Grid spacing (1/4 inch = 18 points since 72 points = 1 inch),
    # but the example pdf looks to have 15 points (10 big segments across?)
    small_grid_spacing = int(18 * scaling_factor)
    inch_grid_spacing = int(72 * scaling_factor)

    c.setLineWidth(0.1)
    for x in range(0, int(page_width), small_grid_spacing):
        c.line(x, 0, x, page_height)

    for y in range(0, int(page_height), small_grid_spacing):
        c.line(0, y, page_width, y)

    c.setLineWidth(2)
    for x in range(0, int(page_width), inch_grid_spacing):
        c.line(x, 0, x, page_height)

    for y in range(0, int(page_height), inch_grid_spacing):
        c.line(0, y, page_width, y)

    c.restoreState()


def draw_text_block(
    c, text, x, y, font_name="Roboto", font_size=container_text_font_size, width=520, height=None
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
) -> float:
    """Helper function to draw rounded rectangle containers"""
    c.setStrokeColor(background_text_color)
    c.roundRect(x, y, width, height, radius, fill=0, stroke=1)
    c.setFillColor(text_color)
    return y - vertical_spacing


def draw_stat_with_info_symbol(
    c, key, number, unit, x, y, font_name="Roboto", font_size=8, number_font_size=24
) -> float:
    """Draw a statistic with an info symbol next to it."""
    c.setFont(font_name, font_size)
    c.setFillColor(background_text_color)
    label_width = c.stringWidth(key, font_name, font_size)
    circle_y = y + 3
    c.drawString(x, y, key)

    # Draw info symbol (circle with i)
    circle_x = x + label_width + horizontal_spacing
    c.circle(circle_x, circle_y, 3.5, stroke=1, fill=0)
    c.setFont(font_name, 7)
    i_width = c.stringWidth("i", font_name, 7)
    c.drawString(circle_x - i_width / 2, circle_y - 2.25, "i")

    c.setFont(font_name, number_font_size)
    c.setFillColor(text_color)
    number_width = c.stringWidth(number, font_name, number_font_size)
    c.drawString(x, y - (number_font_size - font_size) - 10, number)

    c.setFont(font_name, font_size)
    c.drawString(
        x + number_width + 5,
        y - (number_font_size - font_size) - horizontal_spacing,
        unit,
    )

    current_y = y - (number_font_size - font_size) - 20
    return current_y


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
    c.drawString(30, 750 - 28, "Airline Contrail Impact Report 2024")

    # What are Contrails? section
    draw_container(
        c=c,
        x=left_margin,
        y=540 - 28,
        width=page_width - left_margin * 2 + 5,
        height=195,
    )

    c.setFont("Roboto", container_title_font_size)
    c.drawString(left_margin + horizontal_spacing, 710 - 28, "What are Contrails?")

    contrails_text = """Contrails — the thin, white lines you sometimes see behind airplanes — have a surprisingly large impact on our climate. Contrails warm the planet because contrail clouds act like a blanket on Earth and have a net heating effect. The 2022 IPCC report noted that clouds created by contrails account for roughly 35% of aviation's global warming impact — over half the impact of the world's jet fuel. Find more info about contrails and the climate on our website """
    current_y = draw_text_block(
        c=c,
        text=contrails_text,
        x=left_margin + horizontal_spacing,
        y=690 - 28,
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
    c.setFont("Roboto", container_title_font_size)
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
        x=left_margin + horizontal_spacing,
        y=current_y - 40,
        font_name="Roboto",
        font_size=container_text_font_size,
    )

    draw_container(
        c=c,
        x=left_margin,
        y=current_y - (467 + 18) * scaling_factor,
        width=container_width,
        height=6.25 * 72 * scaling_factor,
    )
    c.setFont("Roboto", 16)
    current_y = draw_text_block(
        c=c,
        text="Impact Data",
        x=left_margin + horizontal_spacing,
        y=current_y - 55,
        font_name="Roboto",
        font_size=container_title_font_size,
    )
    stats_text = """Based on our prediction model, 5.5 Million km (55,501 flight hours) or 4.4% of all [Airline] flights generate warming contrails in 2024."""
    current_y = draw_text_block(
        c=c,
        text=stats_text,
        x=left_margin + horizontal_spacing,
        y=current_y + vertical_spacing,
        font_name="Roboto",
        font_size=container_text_font_size,
    )

    stats_data = {
        "# of Flights": {"value": f"{data['count_flights']:,}", "unit": "flights"},
        "Flight hours": {
            "value": f"{data['flight_hours']['total']:,}",
            "unit": "hours",
        },
        "Contrails (GWP 50)": {
            "value": f"{format_number(data['co2e_metric_tons']['gwp50']['total'])}",
            "unit": "metric tons CO2e",
        },
        "Fuel Burn": {
            "value": f"{format_number(data['total_co2_metric_tons'])}",
            "unit": "metric tons CO2",
        },
    }

    y = current_y - 20
    x = left_margin + horizontal_spacing
    spacing_between_stats = 140

    for key, stat in stats_data.items():
        number = stat["value"]
        unit = stat["unit"]

        draw_stat_with_info_symbol(
            c=c,
            key=key,
            number=number,
            unit=unit,
            x=x,
            y=y,
            font_name="Roboto",
            font_size=8,
            number_font_size=24,
        )

        x += spacing_between_stats

    c.setStrokeColor(background_text_color)
    c.setLineWidth(0.5)
    c.line(left_margin, y - 55, page_width - left_margin + 5, y - 55)

    container_bottom = y - (467 + 18) * scaling_factor
    midpoint_x = (left_margin + (page_width - left_margin + 5)) / 2
    midpoint_y = (y - 118 + container_bottom) / 2

    c.line(midpoint_x, y - 30, midpoint_x, midpoint_y - 5)

    draw_text_block(
        c=c,
        text=f"What percentage of {data['airline_name']} flights created warming contrails",
        x=left_margin + horizontal_spacing,
        y=midpoint_y + 180,
        font_name="Roboto",
        font_size=container_title_font_size - 2,
        width=midpoint_x - left_margin - horizontal_spacing,
    )

    current_y = draw_text_block(
        c=c,
        text="How many flight kilometers of warming contrails?",
        x=midpoint_x + horizontal_spacing,
        y=midpoint_y + 180,
        font_name="Roboto",
        font_size=container_title_font_size - 2,
        width=midpoint_x - left_margin - horizontal_spacing,
    )

    current_y = draw_stat_with_info_symbol(
        c,
        key="Flight kilometers for all flights",
        number=format_number(data["flight_distance_km"]["total"]),
        unit="km",
        x=midpoint_x + horizontal_spacing,
        y=current_y,
    )
    # TODO: Insert circle plot png
    # TODO: Add color legend

    draw_stat_with_info_symbol(
        c,
        key="Flight kilometers creating warming contrails",
        number=format_number(
            data["flight_distance_km"]["with_contrails"]["is_warming"]["total"]
        ),
        unit="km",
        x=midpoint_x + horizontal_spacing,
        y=current_y - 50,
    )
    # TODO: Insert horizontal bar plot png
    # TODO: Add color legends

    return c


def create_page_two(c: Any, data: Dict[str, Any]) -> None:

    c.setFillColor(background_text_color)
    c.drawString(525, 812, "Page 2 of 4")

    # Euro section
    container_y = draw_container(
        c=c,
        x=left_margin,
        y=555,
        width=page_width - left_margin * 2 + 5,
        height=72 * 4 * scaling_factor,
    )

    c.setFont("Roboto", 16)
    c.drawString(left_margin + horizontal_spacing, 765, "Impact Data: intra-European flights only")

    description = """Based on our prediction model, this is the impact from the DHL flights that are included in the EU's non-CO2 reporting requirements. The EU ETS area covers flights within and between countries in the European Economic Area (EEA), which consists of EU member states and Iceland, Norway, and Liechtenstein, and from the EEA to the UK and Switzerland. It also covers the EU's nine, so-called outermost regions: French Guiana, Guadeloupe, Martinique, Mayotte, Réunion Island, Saint-Martin, Azores, Madeira, and The Canary Islands."""
    current_y = draw_text_block(
        c=c,
        text=description,
        x=left_margin + horizontal_spacing,
        y=746,
    )

    stats_data = {
        "# of Flights": {"value": f"{data   ['count_flights']:,}", "unit": "flights"},
        "Flight hours": {
            "value": f"{data['flight_hours']['total']:,}",
            "unit": "hours",
        },
        "Contrails (GWP 50)": {
            "value": f"{format_number(data['co2e_metric_tons']['gwp50']['total'])}",
            "unit": "metric tons CO2e",
        },
        "Fuel burn": {
            "value": f"{format_number(data['total_co2_metric_tons'])}",
            "unit": "metric tons CO2",
        },
    }
    y = current_y - 20
    x = left_margin + horizontal_spacing
    spacing_between_stats = 140

    counter = 0
    for key, stat in stats_data.items():
        number = stat["value"]
        unit = stat["unit"]
        if counter > 1:
            x = left_margin + horizontal_spacing
            y -= 70
            counter = 0
        draw_stat_with_info_symbol(
            c=c,
            key=key,
            number=number,
            unit=unit,
            x=x,
            y=y,
            font_name="Roboto",
            font_size=8,
            number_font_size=24,
        )
        counter += 1
        x += spacing_between_stats


    # Observation coverage area & verification section
    draw_container(
        c=c,
        x=left_margin,
        y=2.25 * 72 * scaling_factor,
        width=page_width / 2 - left_margin - horizontal_spacing-3,
        height=72 * 6.75 * scaling_factor,
    )

    current_y = draw_text_block(
        c=c,
        text="Observation coverage area & verification",
        x=left_margin + horizontal_spacing,
        y=510,
        width=page_width / 2 -65,
        font_size=container_title_font_size,
    )
    current_y = draw_text_block(
        c=c,
        text="""The yellow area shows the coverage region where our satellite imager based verification has been validated. For the rest of the world, we use our algorithm predictions""",
        x=left_margin + horizontal_spacing,
        y=current_y+5,
        width=page_width / 2 -65,
        font_size=container_text_font_size,
    )

    c.drawImage(
        f"trimmed_flights_report_trajectories_{data['version_suffix']}.png",
        x=left_margin,
        y=4.75 * 72 * scaling_factor,
        width=page_width / 2 - left_margin - horizontal_spacing - 8,
        height=72 * 2.75 * scaling_factor,
    )
    # TODO: Add color legend, being a yellow circle, and then a gray and white circle
    
    current_y = draw_stat_with_info_symbol(
        c=c,
        x=left_margin+5,
        y=230,
        key="Predicted contrails in observation area",
        number=format_number(data['flight_distance_km']['with_contrails']['total']),
        unit="km",
    )
    current_y = draw_stat_with_info_symbol(
        c=c,
        x=left_margin+5,
        y=current_y-vertical_spacing*2.2,
        key="Verified contrails kilometers",
        number=format_number(data['flight_distance_km']['with_contrails']['goog_sat_verified']),
        unit="km",
    )

    # Contrail warming section
    draw_container(
        c=c,
        x=left_margin/2 + page_width / 2 +3,
        y=2.25 * 72 * scaling_factor,
        width=page_width / 2 - left_margin - horizontal_spacing-3,
        height=72 * 6.75 * scaling_factor,
    )

    current_y = draw_text_block(
        c=c,
        x=left_margin/2 + horizontal_spacing + page_width / 2 +3,
        y=510,
        text="Contrail warming using different time horizons: GWP20, GWP50, and GWP100.",
        width=page_width / 2 - 65,
        font_size=container_title_font_size,
    )

    current_y = draw_text_block(
        c=c,
        x=left_margin/2 + horizontal_spacing + page_width / 2 +3,
        y=current_y+vertical_spacing,
        text="""There is no single “correct” way to convert contrail warming to CO2e. This is partly because the lifetime of a single contrail (hours) is much shorter than the lifetime of CO2 in the atmosphere (hundreds to thousands of years). So when using the Global Warming Potential (GWP) metric and comparing contrail warming to the warming from CO2 over 20 years, the contrail warming will be about four times higher than if comparing to CO2 over 100 years. We use GWP20, GWP50, and GWP100 to align with the EU MRV guidelines. The middle value, GWP50, is used as the default in the report""",
        width=page_width / 2 - 65,
        font_size=container_text_font_size,
    )


    current_y = draw_stat_with_info_symbol(
        c=c,
        x=left_margin/2 + horizontal_spacing + page_width / 2 +3,
        y=current_y-vertical_spacing,
        key="GWP 100",
        number=format_number(data['co2e_metric_tons']['gwp100']['total']),
        unit="metric tons",
    )
    current_y = draw_stat_with_info_symbol(
        c=c,
        x=left_margin/2 + horizontal_spacing + page_width / 2 +3,
        y=current_y-vertical_spacing*3,
        key="GWP 50",
        number=format_number(data['co2e_metric_tons']['gwp50']['total']),
        unit="metric tons",
    )
    current_y = draw_stat_with_info_symbol(
        c=c,
        x=left_margin/2 + horizontal_spacing + page_width / 2 +3,
        y=current_y-vertical_spacing*3,
        key="GWP 20",
        number=format_number(data['co2e_metric_tons']['gwp20']['total']),
        unit="metric tons",
    )


def create_page_three(c: Any, data: Dict[str, Any]) -> Any:
    """Generate the third page of the report"""
    

    c.setFillColor(background_text_color)
    c.setFont("Roboto", 12)
    c.drawString(525, 812, "Page 3 of 4")

    # Fuel emissions (CO2) vs contrail warming (CO2e) GWP50
    draw_container(
        c=c,
        x=left_margin,
        y=615,
        width=page_width - left_margin * 2 + 5,
        height=72 * 3 * scaling_factor,
    )

    c.setFont("Roboto", container_title_font_size)
    c.drawString(left_margin + horizontal_spacing, 765, "Fuel emissions (CO2) vs contrail warming (CO2e) GWP50")

    description = """The contrail warming impact is often lower in the summer time and higher in dark months. This is because contrail clouds that persist in the dark are the most warming."""
    current_y = draw_text_block(
        c=c,
        text=description,
        x=left_margin + horizontal_spacing,
        y=746,
    )

    # TODO: add bar plot of fuel emissions and contrail warming in tco2e

    # Contrail warming - daytime vs nighttime (GWP50)
    draw_container(
        c=c,
        x=left_margin,
        y=405,
        width=page_width - left_margin * 2 + 5,
        height=3.25 * 72 * scaling_factor,
    )

    current_y = draw_text_block(
        c=c,
        text="Contrail warming - daytime vs nighttime (GWP50)",
        x=left_margin + horizontal_spacing,
        y=575,
        font_size=container_title_font_size,
    )

    draw_text_block(
        c=c,
        text="""In the daytime, contrails sometimes have a cooling effect when reflecting some of the sun's heat back into space. But at all times, contrails have a warming effect by acting like a blanket on Earth. This is evident at night when there is no sunlight to reflect, and all contrails are warming""",
        x=left_margin + horizontal_spacing,
        y=current_y+vertical_spacing,
        font_size=container_text_font_size,
    )
    # TODO: add bar plot of nighttime and daytime tco2e 

    # Origin-Destination pairs with the highest average total contrail warming (GWP50 CO2e)
    draw_container(
        c=c,
        x=left_margin,
        y=90,
        width=page_width - left_margin * 2 + 5,
        height=5 * 72 * scaling_factor,
    )

    current_y = draw_text_block(
        c=c,
        text="Origin-Destination pairs with the highest average total contrail warming (GWP50 CO2e)",
        x=left_margin + horizontal_spacing,
        y=365,
        font_size=container_title_font_size,
    )

    draw_text_block(
        c=c,
        text=f"""The ten OD pairs are responsible for 63% of {data['airline_name']}'s total contrail warming.  
        The most warming OD pairs are often very long flights where the majority of the journey takes place in the dark, when contrails are most warming""",
        x=left_margin + horizontal_spacing,
        y=current_y+vertical_spacing,
        font_size=container_text_font_size,
    )

    # BEWARE hardcoded version suffix.  File name does not conform to the naming convention
    c.drawImage(
        f"flights_report_od_by_net_co2e_D0_1732590322.png",
        x=left_margin*1.25,
        y=90,
        width=page_width - left_margin - horizontal_spacing - 30,
        height=72 * 3.5 * scaling_factor,
    )

    return c



def create_page_four(c: Any, data: Dict[str, Any]) -> Any:
    """Generate the fourth page of the report"""
    

    c.setFillColor(background_text_color)
    c.setFont("Roboto", 12)
    c.drawString(525, 812, "Page 4 of 4")

    # Fuel emissions (CO2) vs contrail warming (CO2e) GWP50
    draw_container(
        c=c,
        x=left_margin,
        y=480,
        width=page_width - left_margin * 2 + 5,
        height=72 * 5.25 * scaling_factor,
    )

    c.setFont("Roboto", container_title_font_size)
    c.drawString(left_margin + horizontal_spacing, 765, "Origin-Destination pairs with the highest average total contrail warming per flown kilometer (CO2e/km) GWP50")

    description = f"""The average carbon dioxide emissions per kilometer for {data['airline_name']} in September was 21 kg CO2 / km. The OD pair with the highest contrail warming per kilometer is EMA - CPH  adding 49  kg CO2e/ km - or 2.3 times the average warming from the CO2 alone. The most warming OD pairs per flown kilometer are often flights that fly through contrail-prone zones (for example the Eastern part of the US) at night, when contrails are most warming"""
    current_y = draw_text_block(
        c=c,
        text=description,
        x=left_margin + horizontal_spacing,
        y=746,
    )

    c.drawImage(
        f"flights_report_od_by_impact_density_D0_1732590322.png",
        x=left_margin*1.25,
        y=490,
        width=page_width - left_margin - horizontal_spacing - 30,
        height=72 * 3.75 * scaling_factor,
    )

    # Case study: predicted vs. verified contrails.
    draw_container(
        c=c,
        x=left_margin,
        y=210,
        width=page_width - left_margin * 2 + 5,
        height=4.25 * 72 * scaling_factor,
    )

    current_y = draw_text_block(
        c=c,
        text="Contrail warming - daytime vs nighttime (GWP50)",
        x=left_margin + horizontal_spacing,
        y=440,
        font_size=container_title_font_size,
    )

    draw_text_block(
        c=c,
        text="""In the daytime, contrails sometimes have a cooling effect when reflecting some of the sun's heat back into space. But at all times, contrails have a warming effect by acting like a blanket on Earth. This is evident at night when there is no sunlight to reflect, and all contrails are warming""",
        x=left_margin + horizontal_spacing,
        y=current_y+vertical_spacing,
        font_size=container_text_font_size,
    )

    c.drawImage(
        f"flights_report_flight_case_study_7cafc3e0-9f3c-44cf-b151-992f47f86627_1732590214.png",
        x=left_margin*1.25,
        y=212,
        width=page_width - left_margin - horizontal_spacing - 30,
        height=72 * 3 * scaling_factor,
    )
    # Origin-Destination pairs with the highest average total contrail warming (GWP50 CO2e)
    draw_container(
        c=c,
        x=left_margin,
        y=10,
        width=page_width - left_margin * 2 + 5,
        height=3.25 * 72 * scaling_factor,
    )



    current_y = draw_text_block(
        c=c,
        text="""Did you know?""",
        x=left_margin + horizontal_spacing,
        y=180,
        font_size=container_title_font_size,
    )

    draw_text_block(
        c=c,
        text="""Some flight planning software providers, like Flight keys and CAE, have implemented contrail avoidance in their flight planning tools (or are about to). 
        

        In 2023, American Airlines, Google Research, and Reviate conducted a trial in which they avoided 54% of contrail kilometers by flying under 
        contrail-prone areas.  
        

        In 2024, an extensive study of over 84,000 flights showed that, theoretically, it was possible to eliminate 73% of the contrail warming from these 
        flights by spending 0.11% more jet fuel to adjust some of the flight paths.

        See where contrails are forming right now on this world map of contrails.
        Read more about contrails on our websites: Reviate, Google Research.
        """,
        x=left_margin + horizontal_spacing,
        y=current_y+vertical_spacing,
        font_size=container_text_font_size,
    )

    return c

def generate_pdf(output_path: str, data: Dict[str, Any]) -> None:
    register_fonts()

    c = canvas.Canvas(output_path, pagesize=(page_width, page_height))

    # Draw grid before creating each page
    draw_grid(c, page_width, page_height)
    create_page_one(c, data)
    c.showPage()

    draw_grid(c, page_width, page_height)
    create_page_two(c, data)
    c.showPage()

    draw_grid(c, page_width, page_height)
    create_page_three(c, data)
    c.showPage()

    draw_grid(c, page_width, page_height)
    create_page_four(c, data)
    c.showPage()

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

    input_image_path = f"flights_report_trajectories_{data['version_suffix']}.png"
    output_image_path = f"trimmed_flights_report_trajectories_{data['version_suffix']}.png"
    trim_from_each_side(input_image_path, output_image_path,trim_pixels=55)
    generate_pdf(args.output, data)


if __name__ == "__main__":
    main()
