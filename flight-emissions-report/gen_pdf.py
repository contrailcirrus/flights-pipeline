#!/usr/bin/env python3

"""
Generate a PDF report to match the google designed flight report template.
"""

import argparse
import os
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
container_color = "#C4C7C5"
background_text_color = "#868686"  # This might be C4C7C5 according to the reference pdf..but it looks too light.
left_margin = 30
horizontal_spacing = 13
vertical_spacing = 10
container_width = page_width - left_margin * 2 + 5
container_text_font_size = 8.5
container_title_font_size = 14
scaling_factor = 15 / 18
paragraph_spacing = 10
line_spacing = 10
text_width = 520


def load_data(json_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        data["data_path"] = os.path.dirname(json_path)

        # Validate the data structure:
        if not isinstance(data, dict):
            raise ValueError("Invalid data structure: expected a dictionary")
        return data
    except Exception as e:
        print("Error loading data:", e)
        return None


def register_fonts() -> None:
    FONT_PATH = "fonts/"
    pdfmetrics.registerFont(TTFont("Roboto", FONT_PATH + "Roboto/Roboto-Regular.ttf"))
    pdfmetrics.registerFont(
        TTFont("Roboto-Light", FONT_PATH + "Roboto/Roboto-Light.ttf")
    )
    pdfmetrics.registerFont(TTFont("Roboto-Medium", FONT_PATH + "Roboto/Roboto-Medium.ttf"))


def format_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:,.1f}M"
    elif n >= 1000:
        return f"{n/1000:,.0f}k"
    return f"{n:,}"


def draw_grid(c: Any, page_width: float, page_height: float) -> None:
    """Draw a grid with lines every 1/4 inch (18 points), with inch lines bolded"""
    c.saveState()
    # Set stroke color with transparency (alpha value)
    c.setStrokeColorRGB(
        0.5, 0.5, 0.5, alpha=0.3
    )  # RGB values for gray with 30% opacity

    # Grid spacing (1/4 inch = 18 points since 72 points = 1 inch),
    # but the example pdf looks to have 15 points (10 big segments across?)
    small_grid_spacing = int(18 * scaling_factor)
    inch_grid_spacing = int(72 * scaling_factor)

    c.setLineWidth(0.1)
    for x in range(0, int(page_width), small_grid_spacing):
        c.line(x, 0, x, page_height)

    for y in range(0, int(page_height), small_grid_spacing):
        c.line(0, y, page_width, y)

    c.setLineWidth(1)
    for x in range(0, int(page_width), inch_grid_spacing):
        c.line(x, 0, x, page_height)

    for y in range(0, int(page_height), inch_grid_spacing):
        c.line(0, y, page_width, y)

    c.restoreState()


def draw_text_block(
    c,
    text,
    x,
    y,
    font_name="Roboto",
    font_size=container_text_font_size,
    width=520,
    height=None,
    align="left",
    color=text_color,
) -> float:
    """Draw a block of text"""
    from reportlab.lib.utils import simpleSplit

    c.setFont(font_name, font_size)
    c.setFillColor(color)  # Set the text color

    # Split text into paragraphs
    paragraphs = text.split("\n\n")
    current_y = y

    for paragraph in paragraphs:
        lines = simpleSplit(paragraph.strip(), font_name, font_size, width)
        for line in lines:
            if align == "center":
                line_width = c.stringWidth(line, font_name, font_size)
                line_x = x + (width - line_width) / 2
            elif align == "right":
                line_width = c.stringWidth(line, font_name, font_size)
                line_x = x + width - line_width
            else:  # left align (default)
                line_x = x

            c.drawString(line_x, current_y, line)
            current_y -= font_size * 1.2
        # Add extra space between paragraphs
        current_y -= font_size * 0.8

    return current_y


def draw_container(
    c: Any, x: float, y: float, width: float, height: float, radius: float = 10
) -> float:
    """Helper function to draw rounded rectangle containers"""
    c.setStrokeColor(container_color)
    c.roundRect(x, y, width, height, radius, fill=0, stroke=1)
    c.setFillColor(text_color)
    return y - vertical_spacing


def draw_stat_with_info_symbol(
    c, key, number, unit, x, y, font_name="Roboto-Medium", font_size=8, number_font_size=24
) -> float:
    """Draw a statistic with an info symbol next to it."""
    c.setFont(font_name, font_size)
    c.setFillColor(background_text_color)
    c.drawString(x, y, key)


    c.setFont(font_name, number_font_size)
    c.setFillColor(text_color)
    number_width = c.stringWidth(number, font_name, number_font_size)
    c.drawString(x, y - (number_font_size - font_size) - 10, number)

    c.setFont(font_name, font_size)
    c.drawString(
        x + number_width + 5,
        y - 26,
        unit,
    )

    current_y = y - (number_font_size - font_size) - 20
    return current_y


def draw_stat_for_plots(
    c,
    key,
    number,
    unit,
    x,
    y,
    font_name="Roboto",
    font_size=8,
    number_font_size=22,
    text_color=background_text_color,
) -> float:
    """Draw a statistic with the unit next to it, and the description smaller and just above it.."""
    c.setFont(font_name, font_size)
    c.setFillColor(text_color)
    c.drawString(x, y, key)

    c.setFont(font_name, number_font_size)
    c.setFillColor(text_color)
    c.drawString(x, y - (number_font_size - font_size) - 10, number + " " + unit)

    current_y = y - (number_font_size - font_size) - 20
    return current_y


def create_page_one(c: Any, data: Dict[str, Any]) -> Any:
    """Generate the first page of the report"""
    # TODO: Add real logo
    c.drawImage(
        "static/logo_demo.png",
        left_margin,
        770,
        width=60,
        height=30,
    )

    c.setFillColor(background_text_color)
    c.setFont("Roboto", 10)
    c.drawString(525, 812, "Page 1 of 4")

    c.setFillColor(title_color)
    c.setFont("Roboto", 26)
    c.drawString(30, 750 - 28, "Airline Contrail Impact Report 2024")

    # What are Contrails? section
    draw_container(
        c=c,
        x=left_margin,
        y=510,
        width=page_width - left_margin * 2 + 5,
        height=195,
    )

    c.setFont("Roboto", container_title_font_size)
    current_y = draw_text_block(
        c=c,
        text="What are Contrails?",
        x=left_margin + horizontal_spacing,
        y=710 - 28,
        font_name="Roboto", 
        font_size=container_title_font_size,
    )

    contrails_text = """Contrails — the thin, white lines you sometimes see behind airplanes — have a surprisingly large impact on our climate. Contrails warm the planet because contrail clouds act like a blanket on Earth and have a net heating effect. The 2022 IPCC report noted that clouds created by contrails account for roughly 35% of aviation's global warming impact — over half the impact of the world's jet fuel. Find more info about contrails and the climate on our website """
    current_y = draw_text_block(
        c=c,
        text=contrails_text,
        x=left_margin + horizontal_spacing,
        y=current_y,
        font_name="Roboto",
        font_size=container_text_font_size,
    )

    # Highly finicky spacing here
    link_text = "contrails.org"
    c.setFont("Roboto", container_text_font_size)
    after_text_width = 187
    c.setFillColor(text_color)
    
    # Draw the text
    c.drawString(
        x=left_margin + after_text_width+2,
        y=current_y + 17,
        text=link_text,
    )
    
    # Calculate dimensions
    link_width = c.stringWidth(link_text, "Roboto", container_text_font_size)
    
    # Draw the underline
    c.line(
        left_margin + after_text_width + 2,
        current_y + 15,  # Slightly below text
        left_margin + after_text_width + link_width + 2,
        current_y + 15
    )
    
    # Add the clickable link
    c.linkURL(
        "https://www.contrails.org",
        (
            left_margin + after_text_width + 2,
            current_y + (9 * 2) - 1,
            left_margin + after_text_width + link_width + 2,
            current_y + (9 * 2) + 8,
        ),
    )
    c.setFillColor(text_color)

    current_y = draw_text_block(
        c=c,
        text="What is Global Warming Potential (GWP)?",
        x=left_margin + horizontal_spacing,
        y=current_y - vertical_spacing,
        font_name="Roboto",
        font_size=container_title_font_size,
    )

    gwp_text = """GWP measures how much warming contrails cause over a number of years compared to CO2. Contrails heat the Earth quickly but for a short time, and GWP helps compare their short-term impact to the longer-lasting greenhouse gas, CO2.

    In this report we initially show the contrail impact in CO2e over 20, 50 and 100 years to align with the guidelines from the EU Non-CO2 MRV report starting in 2025. Wherever we only show one value for CO2e we use the middle value, GWP50, as default."""
    current_y = draw_text_block(
        c=c,
        text=gwp_text,
        x=left_margin + horizontal_spacing,
        y=current_y,
        font_name="Roboto",
        font_size=container_text_font_size,
    )

    draw_container(
        c=c,
        x=left_margin,
        y=120 ,
        width=container_width,
        height=6.25 * 72 * scaling_factor,
    )
    c.setFont("Roboto", 16)
    current_y = draw_text_block(
        c=c,
        text="Impact Data",
        x=left_margin + horizontal_spacing,
        y=472,
        font_name="Roboto",
        font_size=container_title_font_size,
    )
    stats_text = """Based on our prediction model, 5.5 Million km (55,501 flight hours) or 4.4% of all [Airline] flights generate warming contrails in 2024."""
    current_y = draw_text_block(
        c=c,
        text=stats_text,
        x=left_margin + horizontal_spacing,
        y=current_y,
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

    c.line(midpoint_x, y - 55, midpoint_x, midpoint_y - 33)

    # Pie chart
    c.drawImage(
        data["data_path"] + "/fig_contrail_warming_percentage.png",
        x=60,
        y=121,
        width=72 * 3.5 * scaling_factor,
        height=72 * 3.4 * scaling_factor,
    )

    draw_text_block(
        c=c,
        text=f"What percentage of {data['airline_name']} flights created warming contrails?",
        x=left_margin + horizontal_spacing,
        y=midpoint_y + 180,
        font_name="Roboto",
        font_size=container_title_font_size - 2,
        width=midpoint_x - left_margin - horizontal_spacing,
    )

    draw_text_block(
        c=c,
        text=f"{data['flight_distance_km']['with_contrails']['total'] / data['flight_distance_km']['total'] * 100:.1f}%",
        x=midpoint_x / 3 + 35,
        y=237,
        font_name="Roboto",
        font_size=24,
        width=midpoint_x - left_margin - horizontal_spacing,
    )
    draw_text_block(
        c=c,
        text=f"of {data['airline_name']} flight distance generated warming contrails",
        x=midpoint_x / 3 + 15,
        y=220,
        font_name="Roboto",
        font_size=container_text_font_size,
        width=100,
        color=background_text_color,
        align="center",
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
    c.drawImage(
        data["data_path"] + "/fig_contrail_distance_daytime_nighttime.png",
        x=midpoint_x + horizontal_spacing-3,
        y=215,
        width=72 * 4 * scaling_factor,
        height=72 * 1 * scaling_factor,
    )
    current_y = draw_stat_with_info_symbol(
        c,
        key="Flight kilometers for all flights",
        number=format_number(data["flight_distance_km"]["total"]),
        unit="km",
        x=midpoint_x + horizontal_spacing,
        y=current_y,
    )

    c.drawImage(
        data["data_path"] + "/fig_contrail_distance_warming_daytime_nighttime.png",
        x=midpoint_x + horizontal_spacing-3,
        y=123,
        width=72 * 2.9 * scaling_factor,
        height=72 * 1.11* scaling_factor,
    )
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

    return c


def create_page_two(c: Any, data: Dict[str, Any]) -> None:
    """Generate the second page of the report"""
    c.setFont("Roboto", 10)
    c.setFillColor(background_text_color)
    c.drawString(525, 812, "Page 2 of 4")

    # Euro section
    draw_container(
        c=c,
        x=left_margin,
        y=555,
        width=page_width - left_margin * 2 + 5,
        height=72 * 4 * scaling_factor,
    )

    current_y = draw_text_block(
        c=c,
        text="Impact Data: intra-European flights only",
        x=left_margin + horizontal_spacing,
        y=770,
        font_size=16
    )
    c.drawImage(
        "static/Europe Map_trimmed.png",
        x=page_width / 2 + 90,
        y=555,
        width=72 * 2.55 * scaling_factor,
        height=72 * 2.7 * scaling_factor,
    )

    description = """Based on our prediction model, this is the impact from the DHL flights that are included in the EU's non-CO2 reporting requirements. The EU ETS area covers flights within and between countries in the European Economic Area (EEA), which consists of EU member states and Iceland, Norway, and Liechtenstein, and from the EEA to the UK and Switzerland. It also covers the EU's nine, so-called outermost regions: French Guiana, Guadeloupe, Martinique, Mayotte, Réunion Island, Saint-Martin, Azores, Madeira, and The Canary Islands."""
    current_y = draw_text_block(
        c=c,
        text=description,
        x=left_margin + horizontal_spacing,
        y=current_y,
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
        width=page_width / 2 - left_margin - horizontal_spacing - 3,
        height=72 * 6.75 * scaling_factor,
    )

    current_y = draw_text_block(
        c=c,
        text="Observation coverage area & verification",
        x=left_margin + horizontal_spacing,
        y=517,
        width=page_width / 2 - 65,
        font_size=container_title_font_size,
    )
    c.drawImage(
        data["data_path"] + "/trajectories.png",
        x=left_margin * 1.1 - 0.5,
        y=4.75 * 72 * scaling_factor,
        width=page_width / 2 - left_margin - horizontal_spacing - 8,
        height=72 * 2.75 * scaling_factor,
    )
    # TODO: Add color legend, being a yellow circle, and then a gray and white circle

    current_y = draw_text_block(
        c=c,
        text="""The yellow area shows the coverage region where our satellite imager based verification has been validated. For the rest of the world, we use our algorithm predictions""",
        x=left_margin + horizontal_spacing,
        y=current_y + 5,
        width=page_width / 2 - 65,
        font_size=container_text_font_size,
    )

    current_y = draw_stat_with_info_symbol(
        c=c,
        x=left_margin + 5,
        y=230,
        key="Predicted contrails in observation area",
        number=format_number(data["flight_distance_km"]["with_contrails"]["total"]),
        unit="km",
    )
    current_y = draw_stat_with_info_symbol(
        c=c,
        x=left_margin + 5,
        y=current_y - vertical_spacing * 2.2,
        key="Verified contrails kilometers",
        number=format_number(
            data["flight_distance_km"]["with_contrails"]["goog_sat_verified"]
        ),
        unit="km",
    )

    # Contrail warming section
    draw_container(
        c=c,
        x=left_margin / 2 + page_width / 2 + 3,
        y=2.25 * 72 * scaling_factor,
        width=page_width / 2 - left_margin - horizontal_spacing - 3,
        height=72 * 6.75 * scaling_factor,
    )

    current_y = draw_text_block(
        c=c,
        x=left_margin / 2 + horizontal_spacing + page_width / 2 + 3,
        y=515,
        text="Contrail warming using different time horizons: GWP20, GWP50, and GWP100.",
        width=page_width / 2 - 65,
        font_size=container_title_font_size,
    )

    current_y = draw_text_block(
        c=c,
        x=left_margin / 2 + horizontal_spacing + page_width / 2 + 3,
        y=current_y,
        text="""There is no single “correct” way to convert contrail warming to CO2e. This is partly because the lifetime of a single contrail (hours) is much shorter than the lifetime of CO2 in the atmosphere (hundreds to thousands of years). So when using the Global Warming Potential (GWP) metric and comparing contrail warming to the warming from CO2 over 20 years, the contrail warming will be about four times higher than if comparing to CO2 over 100 years. We use GWP20, GWP50, and GWP100 to align with the EU MRV guidelines. The middle value, GWP50, is used as the default in the report""",
        width=page_width / 2 - 65,
        font_size=container_text_font_size,
    )

    current_y = draw_stat_with_info_symbol(
        c=c,
        x=left_margin / 2 + horizontal_spacing + page_width / 2 + 3,
        y=current_y - vertical_spacing,
        key="GWP 100",
        number=format_number(data["co2e_metric_tons"]["gwp100"]["total"]),
        unit="metric tons",
    )
    denom = data["co2e_metric_tons"]["gwp20"]["total"]
    bar_widths_fractions = [
        data["co2e_metric_tons"]["gwp100"]["total"] / denom,
        data["co2e_metric_tons"]["gwp50"]["total"] / denom,
        1,
    ]

    c.drawImage(
        "static/horizontal_bar_gwp_warming.png",
        x=left_margin / 2 + horizontal_spacing + page_width / 2,
        y=current_y - vertical_spacing * 1.2,
        width=bar_widths_fractions[0] * page_width / 2.45,
        height=72 * 0.25 * scaling_factor,
    )
    current_y = draw_stat_with_info_symbol(
        c=c,
        x=left_margin / 2 + horizontal_spacing + page_width / 2 + 3,
        y=current_y - vertical_spacing * 3,
        key="GWP 50",
        number=format_number(data["co2e_metric_tons"]["gwp50"]["total"]),
        unit="metric tons",
    )
    c.drawImage(
        "static/horizontal_bar_gwp_warming.png",
        x=left_margin / 2 + horizontal_spacing + page_width / 2 - 0.5,
        y=current_y - vertical_spacing * 1.2,
        width=bar_widths_fractions[1] * page_width / 2.45,
        height=72 * 0.25 * scaling_factor,
    )
    current_y = draw_stat_with_info_symbol(
        c=c,
        x=left_margin / 2 + horizontal_spacing + page_width / 2 + 3,
        y=current_y - vertical_spacing * 3,
        key="GWP 20",
        number=format_number(data["co2e_metric_tons"]["gwp20"]["total"]),
        unit="metric tons",
    )
    c.drawImage(
        "static/horizontal_bar_gwp_warming.png",
        x=left_margin / 2 + horizontal_spacing + page_width / 2 - 2.25,
        y=current_y - vertical_spacing * 1.2,
        width=page_width / 2.45,
        height=72 * 0.25 * scaling_factor,
    )


def create_page_three(c: Any, data: Dict[str, Any]) -> Any:
    """Generate the third page of the report"""

    c.setFillColor(background_text_color)
    c.setFont("Roboto", 10)
    c.drawString(525, 812, "Page 3 of 4")

    # Fuel emissions (CO2) vs contrail warming (CO2e) GWP50
    draw_container(
        c=c,
        x=left_margin,
        y=615,
        width=page_width - left_margin * 2 + 5,
        height=72 * 3 * scaling_factor,
    )

    current_y = draw_text_block(
        c=c,
        text="Fuel emissions (CO2) vs contrail warming (CO2e) GWP50",
        x=left_margin + horizontal_spacing,
        y=771,
        font_size=container_title_font_size,
    )

    description = """The contrail warming impact is often lower in the summer time and higher in dark months. This is because contrail clouds that persist in the dark are the most warming."""
    current_y = draw_text_block(
        c=c,
        text=description,
        x=left_margin + horizontal_spacing,
        y=current_y,
    )
    c.drawImage(
        data["data_path"] + "/fig_fuel_emissions_vs_contrail_warming.png",
        x=39,
        y=616,
        width=page_width - left_margin * 3 + 14,
        height=72 * 1.75 * scaling_factor,
    )
    fuel_percent_of_total = 100*(data["total_co2_metric_tons"] / (data["total_co2_metric_tons"] + data["co2e_metric_tons"]["gwp50"]["total"]))
    contrail_percent_of_total = 100*(data["co2e_metric_tons"]["gwp50"]["total"] / (data["total_co2_metric_tons"] + data["co2e_metric_tons"]["gwp50"]["total"]))
    
    # TODO: harden this, as the number spacing will be different as the bar values change.
    draw_stat_for_plots(
        c,
        key=f"Fuel emissions (metric tons CO2)",
        number=format_number(data["total_co2_metric_tons"]),
        unit=f"({fuel_percent_of_total:.0f}%)",
        x=55, # TODO: harden this, as the number spacing will be different as the bar values change.
        y=current_y - vertical_spacing * 2.2,
        text_color="white",
    )
    # Todo: fix this?
    draw_stat_for_plots(
        c,
        key="Contrails (metric tons CO2e)",
        number=format_number(data["co2e_metric_tons"]["gwp50"]["total"]),
        unit=f"({contrail_percent_of_total:.0f}%)",
        x=449, # TODO: harden this, as the number spacing will be different as the bar values change.
        y=current_y - vertical_spacing * 2.2,
        text_color="white",
    )

    # Contrail warming - daytime vs nighttime (GWP50)
    draw_container(
        c=c,
        x=left_margin,
        y=410,
        width=page_width - left_margin * 2 + 5,
        height=3.25 * 72 * scaling_factor - 5,
    )

    current_y = draw_text_block(
        c=c,
        text="Contrail warming - daytime vs nighttime (GWP50)",
        x=left_margin + horizontal_spacing,
        y=576,
        font_size=container_title_font_size,
    )

    current_y = draw_text_block(
        c=c,
        text="""In the daytime, contrails sometimes have a cooling effect when reflecting some of the sun's heat back into space. But at all times, contrails have a warming effect by acting like a blanket on Earth. This is evident at night when there is no sunlight to reflect, and all contrails are warming""",
        x=left_margin + horizontal_spacing,
        y=current_y,
        font_size=container_text_font_size,
    )

    c.drawImage(
        data["data_path"] + "/fig_contrail_warming_daytime_vs_nighttime.png",
        x=38,
        y=current_y - vertical_spacing * 10,
        width=page_width - left_margin * 5.2,
        height=72 * 1.75 * scaling_factor,
    )
    nighttime_percent_of_total = 100*(data["co2e_metric_tons"]["gwp50"]["nighttime"]["total"] / (data["co2e_metric_tons"]["gwp50"]["daytime"]["total"] + data["co2e_metric_tons"]["gwp50"]["nighttime"]["total"]))
    daytime_percent_of_total = 100*(data["co2e_metric_tons"]["gwp50"]["daytime"]["total"] / (data["co2e_metric_tons"]["gwp50"]["daytime"]["total"] + data["co2e_metric_tons"]["gwp50"]["nighttime"]["total"]))
    draw_stat_for_plots(
        c,
        key="Nighttime (metric tons CO2e)",
        number=format_number(data["co2e_metric_tons"]["gwp50"]["nighttime"]["total"]),
        unit=f"({nighttime_percent_of_total:.0f}%)",
        x=55, # TODO: harden this, as the number spacing will be different as the bar values change.
        y=current_y - vertical_spacing * 2.4,
        text_color="white",
    )

    draw_stat_for_plots(
        c,
        key="Daytime (metric tons CO2e)",
        number=format_number(data["co2e_metric_tons"]["gwp50"]["daytime"]["total"]),
        unit=f"({daytime_percent_of_total:.0f}%)",
        x=447, # TODO: harden this, as the number spacing will be different as the bar values change.
        y=current_y - vertical_spacing * 2.4,
        text_color=background_text_color,
    )
    
    # Origin-Destination pairs with the highest average total contrail warming (GWP50 CO2e)
    c.drawImage(
        data["data_path"] + "/fig_od_by_net_co2e.png",
        x=10,
        y=85,
        width=580,
        height=250,
    )
    current_y = draw_text_block(
        c=c,
        text="Origin-Destination pairs with the highest average total contrail warming (GWP50 CO2e)",
        x=left_margin + horizontal_spacing,
        y=370,
        font_size=container_title_font_size,
    )
    current_y = draw_text_block(
        c=c,
        text=f"""The ten OD pairs are responsible for 63% of {data['airline_name']}'s total contrail warming.  The most warming OD pairs are often very long flights where the majority of the journey takes place in the dark, when contrails are most warming""",
        x=left_margin + horizontal_spacing,
        y=current_y,
        font_size=container_text_font_size,
    )


    draw_container(
        c=c,
        x=left_margin,
        y=85,
        width=page_width - left_margin * 2 + 5,
        height=5 * 72 * scaling_factor + 10,
    )
    return c


def create_page_four(c: Any, data: Dict[str, Any]) -> Any:
    """Generate the fourth page of the report"""

    c.setFillColor(background_text_color)
    c.setFont("Roboto", 10)
    c.drawString(525, 812, "Page 4 of 4")

    # Fuel emissions (CO2) vs contrail warming (CO2e) GWP50

    current_y = draw_text_block(
        c=c,
        text="Origin-Destination pairs with the highest average total contrail warming per flown kilometer (CO2e/km) GWP50",
        x=left_margin + horizontal_spacing,
        y=772,
        font_size=container_title_font_size,
    )

    # TODO: this is hard coded, need to make it dynamic

    c.drawImage(
        data["data_path"] + "/fig_od_by_impact_density.png",
        x=10,
        y=473,
        width=580,
        height=250,
    )
    description = f"""The average carbon dioxide emissions per kilometer for {data['airline_name']} in September was 21 kg CO2 / km. The OD pair with the highest contrail warming per kilometer is EMA - CPH  adding 49  kg CO2e/ km - or 2.3 times the average warming from the CO2 alone. The most warming OD pairs per flown kilometer are often flights that fly through contrail-prone zones (for example the Eastern part of the US) at night, when contrails are most warming"""
    current_y = draw_text_block(
        c=c,
        text=description,
        x=left_margin + horizontal_spacing,
        y=current_y,
        width=515,
    )
    draw_container(
        c=c,
        x=left_margin,
        y=480,
        width=page_width - left_margin * 2 + 5,
        height=72 * 5.25 * scaling_factor,
    )
    # Case study: predicted vs. verified contrails.
    c.drawImage(
        data["data_path"] + "/fig_case_study_0.png",
        x=40,
        y=210,
        width=520,
        height=175,
    )
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
        y=current_y,
        font_size=container_text_font_size,
    )


    # TODO: add color legend

    # Origin-Destination pairs with the highest average total contrail warming (GWP50 CO2e)
    draw_container(
        c=c,
        x=left_margin,
        y=10,
        width=page_width - left_margin * 2 + 5,
        height=3.1 * 72 * scaling_factor,
    )

    current_y = draw_text_block(
        c=c,
        text="""Did you know?""",
        x=left_margin + horizontal_spacing,
        y=170,
        font_size=container_title_font_size,
    )

    current_x = left_margin + horizontal_spacing
    y = current_y

    # First paragraph
    first_text = "Some flight planning software providers, like "
    width = add_plain_text(c, first_text, current_x, y, font_size=container_text_font_size)
    current_x += width

    width = add_text_with_link(c, "Flightkeys", "https://www.flightkeys.com", current_x, y)
    current_x += width

    width = add_plain_text(c, " and ", current_x, y)
    current_x += width

    width = add_text_with_link(
        c, "CAE",
        "https://www.cae.com/civil-aviation/aviation-software/flight-operations-solutions/flight-management/",
        current_x, y
    )
    current_x += width

    remaining_text = ", have implemented contrail avoidance in their flight planning tools (or are about to)."
    lines = wrap_text(c, remaining_text, text_width - (current_x - (left_margin + horizontal_spacing)))
    for i, line in enumerate(lines):
        if i == 0:
            add_plain_text(c, line, current_x, y)
        else:
            y -= line_spacing
            add_plain_text(c, line, left_margin + horizontal_spacing, y)

    # Move to next paragraph with extra spacing to prevent overlap
    y -= paragraph_spacing + line_spacing

    # Second paragraph
    current_x = left_margin + horizontal_spacing
    intro_text = "In 2023, American Airlines, Google Research, and Reviate conducted a "
    width = add_plain_text(c, intro_text, current_x, y)
    current_x += width

    width = add_text_with_link(
        c, "trial",
        "https://www.theguardian.com/environment/2023/aug/09/ai-helps-airline-pilots-avoid-areas-that-create-polluting-contrails",
        current_x, y
    )
    current_x += width

    remaining_text = " in which they avoided 54% of contrail kilometers by flying under contrail-prone areas."
    lines = wrap_text(c, remaining_text, text_width - (current_x - (left_margin + horizontal_spacing)))
    for i, line in enumerate(lines):
        if i == 0:
            add_plain_text(c, line, current_x, y)
        else:
            y -= line_spacing
            add_plain_text(c, line, left_margin + horizontal_spacing, y)

    y -= paragraph_spacing + line_spacing

    # Third paragraph
    current_x = left_margin + horizontal_spacing
    intro_text = "In 2024, an "
    width = add_plain_text(c, intro_text, current_x, y)
    current_x += width

    width = add_text_with_link(
        c, "extensive study",
        "https://www.researchgate.net/publication/378811848_Feasibility_of_contrail_avoidance_in_a_commercial_flight_planning_system_an_operational_analysis",
        current_x, y
    )
    current_x += width

    remaining_text = " of over 84,000 flights showed that, theoretically, it was possible to eliminate 73% of the contrail warming from these flights by spending 0.11% more jet fuel to adjust some of the flight paths."
    lines = wrap_text(c, remaining_text, text_width - (current_x - (left_margin + horizontal_spacing)))
    for i, line in enumerate(lines):
        if i == 0:
            add_plain_text(c, line, current_x, y)
        else:
            y -= line_spacing
            add_plain_text(c, line, left_margin + horizontal_spacing, y)

    y -= paragraph_spacing + line_spacing

    # Fourth paragraph
    current_x = left_margin + horizontal_spacing
    intro_text = "See where contrails are forming right now on this "
    width = add_plain_text(c, intro_text, current_x, y)
    current_x += width

    width = add_text_with_link(
        c, "world map of contrails",
        "https://map.contrails.org",
        current_x, y
    )
    current_x += width

    add_plain_text(c, ".", current_x, y)

    y -= paragraph_spacing + line_spacing

    # Fifth paragraph
    current_x = left_margin + horizontal_spacing
    intro_text = "Read more about contrails on our websites: "
    width = add_plain_text(c, intro_text, current_x, y)
    current_x += width

    width = add_text_with_link(
        c, "Reviate",
        "https://contrails.org",
        current_x, y
    )
    current_x += width

    width = add_plain_text(c, ", ", current_x, y)
    current_x += width

    width = add_text_with_link(
        c, "Google Research",
        "https://sites.research.google/contrails/",
        current_x, y
    )
    current_x += width

    add_plain_text(c, ".", current_x, y)

    return c


def wrap_text(c, text, width, font="Roboto", font_size=container_text_font_size):
    """Split text into lines that fit within given width"""
    words = text.split()
    lines = []
    current_line = []
    current_width = 0

    for word in words:
        word_width = c.stringWidth(word + " ", font, font_size)
        if current_width + word_width <= width:
            current_line.append(word)
            current_width += word_width
        else:
            lines.append(" ".join(current_line))
            current_line = [word]
            current_width = word_width

    if current_line:
        lines.append(" ".join(current_line))
    return lines


def add_text_with_link(c, text, link_url, x, y, font="Roboto", font_size=container_text_font_size):
    """Helper function to add text with a clickable link"""
    c.setFont(font, font_size)
    c.drawString(x=x, y=y, text=text)
    text_width = c.stringWidth(text, font, font_size)
    c.linkURL(
        link_url,
        (x, y - 2, x + text_width, y + 9),
    )
    return text_width


def add_plain_text(c, text, x, y, font="Roboto", font_size=container_text_font_size):
    """Helper function to add plain text and return its width"""
    c.setFont(font, font_size)
    c.drawString(x=x, y=y, text=text)
    return c.stringWidth(text, font, font_size)


def generate_pdf(output_path: str, data: Dict[str, Any]) -> None:
    register_fonts()

    c = canvas.Canvas(output_path, pagesize=(page_width, page_height))


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
    parser.add_argument(
        "--data_path",
        type=str,
        default="out/D0",
        help="Path to data folder",
    )

    parser.add_argument(
        "--airline_name",
        type=str,
        default="American Airlines",
        help="Airline name",
    )
    args = parser.parse_args()

    data = load_data(json_path=args.data_path + "/data_summary.json")
    data["airline_name"] = args.airline_name
    generate_pdf(output_path=args.data_path + "/flights_report.pdf", data=data)


if __name__ == "__main__":
    main()
