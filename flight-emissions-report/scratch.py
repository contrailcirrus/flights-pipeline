"""
Scratch space for hacking.
"""

from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Circle, Rect
from reportlab.lib import colors
from reportlab.graphics.charts.piecharts import Pie


# A4 size in points (595.27 x 841.89)
# 1 point = 1/72 inch
# A4 is 210mm × 297mm (8.27 × 11.69 inches)
page_width = 595.27
page_height = 841.89
title_color = "#111111"  # dark dark gray
text_color = "#444444"  # dark gray
container_color = "#ffffff"
background_text_color = "#C4C7C5"
left_margin = 30
horizontal_spacing = 10
vertical_spacing = 10
container_width = page_width - left_margin * 2 + 5
container_text_font_size = 8.5
container_title_font_size = 14
scaling_factor = 15 / 18

c = canvas.Canvas("scratch.pdf", pagesize=(page_width, page_height))

dark_blue = "#2C2857"
medium_blue = "#4285F4"
light_blue = "#D3E3FD"
yellow = "#F7CA45"

# ---------
# FIGURE 1
# arc pie-chart; pg 1 (what percentage of airline flights created warming contrails?)
# ---------
km_w_warming = 1200
km_wo_warming = 8990

pie_diameter = 112  # 112pts ~= 4cm

drawing1_arc_pie = Drawing(pie_diameter, pie_diameter)

pc = Pie()
pc.x = 0
pc.y = 0
pc.width = pie_diameter
pc.height = pie_diameter
pc.data = [km_w_warming, km_wo_warming]

# modify warming contrails style
pc.slices[0].fillColor = colors.HexColor(medium_blue)
pc.slices[0].strokeColor = colors.HexColor(medium_blue)

# modify non-warming contrails style
pc.slices[1].fillColor = colors.HexColor(light_blue)
pc.slices[1].strokeColor = colors.HexColor(light_blue)
drawing1_arc_pie.add(pc)

# overlay white circle mask to emulate an arc pie chart
arc_thickness = 9  # 0.3cm -> ~9pts
radius = (pie_diameter / 2) - arc_thickness
circ_mask = Circle(pie_diameter / 2, pie_diameter / 2, radius)
circ_mask.fillColor = colors.white
circ_mask.strokeColor = colors.white
drawing1_arc_pie.add(circ_mask)

# ---------
# FIGURE 2
# horizontal stacked rounded-edge bars; pg 1
# (how many flight km of warming contrails...)
# ---------
all_flight_km = 46
warming_flight_km = 6

bar_height = 15  # 0.5cm ~= 15pt
bar_edge_radius = 3

# top fig dimensioning
# ----------------
top_tot_width = 235  # 7cm ~= 200pt
# bottom fig dimensioning
# ----------------
# (we scale down the total width of the bottom bar, roughly
# (in proportion to warming_flight_km / all_flight_km)
bottom_tot_width = int(top_tot_width * warming_flight_km / all_flight_km)
bottom_tot_width = 55 if bottom_tot_width < 55 else bottom_tot_width  # 2cm ~= 55pt

# create drawing for both bars
drawing2_stacked_bars = Drawing(top_tot_width, 135)  # 3.5cm ~= 135pt

# draw top bars
top_y_pos = 86  # 3cm ~= 86pt; y-pos of top bars in Drawing
top_daytime_perc = 25.7
top_nighttime_perc = 74.3
top_bar_nighttime_width = top_nighttime_perc / 100.0 * top_tot_width
top_bar_daytime_width = top_daytime_perc / 100.0 * top_tot_width

top_bar_nighttime = Rect(
    0, top_y_pos, top_bar_nighttime_width, bar_height, bar_edge_radius
)
top_bar_nighttime.strokeColor = colors.HexColor(dark_blue)
top_bar_nighttime.fillColor = colors.HexColor(dark_blue)

top_bar_daytime = Rect(
    top_bar_nighttime_width,
    top_y_pos,
    top_bar_daytime_width,
    bar_height,
    bar_edge_radius,
)
top_bar_daytime.strokeColor = colors.HexColor(yellow)
top_bar_daytime.fillColor = colors.HexColor(yellow)

drawing2_stacked_bars.add(top_bar_nighttime)
drawing2_stacked_bars.add(top_bar_daytime)

# draw bottom bars
bottom_y_pos = 0  # on bottom-lhs of Drawing space
bottom_daytime_perc = 15.3
bottom_nighttime_perc = 84.7

bottom_bar_nighttime_width = bottom_nighttime_perc / 100.0 * bottom_tot_width
bottom_bar_daytime_width = bottom_daytime_perc / 100.0 * bottom_tot_width

bottom_bar_nighttime = Rect(
    0, bottom_y_pos, bottom_bar_nighttime_width, bar_height, bar_edge_radius
)
bottom_bar_nighttime.strokeColor = colors.HexColor(dark_blue)
bottom_bar_nighttime.fillColor = colors.HexColor(dark_blue)

bottom_bar_daytime = Rect(
    bottom_bar_nighttime_width,
    bottom_y_pos,
    bottom_bar_daytime_width,
    bar_height,
    bar_edge_radius,
)
bottom_bar_daytime.strokeColor = colors.HexColor(yellow)
bottom_bar_daytime.fillColor = colors.HexColor(yellow)

drawing2_stacked_bars.add(bottom_bar_nighttime)
drawing2_stacked_bars.add(bottom_bar_daytime)

# ----------------
# ----------------
drawing1_arc_pie.drawOn(c, 100, 500)
drawing2_stacked_bars.drawOn(c, 100, 100)

c.save()
