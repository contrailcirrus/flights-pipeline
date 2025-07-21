from reportlab.lib.colors import HexColor, lightgrey, gray
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import TableStyle, Spacer


DARK_DARK_GRAY = "#111111"
DARK_GRAY = "#444444"
MEDIUM_GRAY = "#B0B0B0"
BLACK = HexColor("#000000")
BLUE_HIGHLIGHT_COLOR = HexColor("#E8F0FE")
DIVIDER_COLOR = HexColor("#F5E6E8")
PREDICTED_COLOR = HexColor("#B1C6FD")
CONFIRMED_COLOR = HexColor("#F9DF92")


GRID_UNIT = 0.525 * cm
HALF_GRID_UNIT = GRID_UNIT / 2
TOTAL_PAGES = 6
GRID_SPACER = Spacer(1, GRID_UNIT)
HALF_GRID_SPACER = Spacer(1, GRID_UNIT / 2)
QUARTER_GRID_SPACER = Spacer(1, GRID_UNIT / 4)

report_title_style = ParagraphStyle(
    name="Title",
    fontName="Roboto",
    fontSize=25,
    leading=28,
    alignment=TA_LEFT,
    textColor=HexColor(DARK_DARK_GRAY),
    spaceBefore=GRID_UNIT,
    spaceAfter=GRID_UNIT,
)

section_title_style = ParagraphStyle(
    name="SectionHeader",
    fontName="Roboto-Light",
    fontSize=12,
    leading=13,
    alignment=TA_LEFT,
    textColor=HexColor(DARK_DARK_GRAY),
    spaceBefore=HALF_GRID_UNIT,
    spaceAfter=HALF_GRID_UNIT,
)

body_style = ParagraphStyle(
    name="Body",
    fontName="Roboto-Light",
    fontSize=7.5,
    leading=11,
    textColor=HexColor(DARK_GRAY),
    spaceAfter=0,
)

label_style = ParagraphStyle(
    name="LabelStyle",
    parent=body_style,
    fontSize=8,
    alignment=TA_LEFT,
    textColor=HexColor(MEDIUM_GRAY),
    leading=8,
)

bullet_style = ParagraphStyle(
    name="BulletStyle",
    parent=body_style,
    leftIndent=12,
    firstLineIndent=-6,
    bulletIndent=6,
)

page_num_style = ParagraphStyle(
    name="PageNum",
    fontName="Roboto-Light",
    fontSize=10,
    alignment=TA_RIGHT,
    textColor=gray,
)

legend_style = ParagraphStyle(
    "LegendLabel", fontName="Helvetica", fontSize=8, textColor=BLACK
)

container_table_style = TableStyle(
    [
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ("BOX", (0, 0), (-1, -1), 1, lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]
)

four_column_table_style = TableStyle(
    [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "LEFT"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]
)

t_shaped_table_style = TableStyle(
    [
        ("BOX", (0, 0), (-1, -1), 1, lightgrey),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("SPAN", (0, 0), (1, 0)),
        ("LINEBELOW", (0, 0), (-1, 0), 1, lightgrey),
    ]
)

inner_table_style = TableStyle(
    [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, lightgrey),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 0), (-1, -1), "Roboto-Light"),
        ("TEXTCOLOR", (0, 0), (-1, -1), BLACK),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
    ]
)

two_by_two_table_style = TableStyle(
    [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (1, 0), GRID_UNIT),
    ]
)

highlighted_box_style = TableStyle(
    [
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F7F2F2")),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, -1), "Roboto-Light"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]
)

blue_highlight_box_style = TableStyle(
    [
        ("BACKGROUND", (0, 0), (-1, -1), BLUE_HIGHLIGHT_COLOR),
        ("ROUND", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
    ]
)

two_column_stats_style = TableStyle(
    [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("TOPPADDING", (0, 0), (-1, 0), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]
)

od_pair_stats_table_style = TableStyle(
    [
        ("SPAN", (0, 0), (2, 0)),
        ("VALIGN", (0, 1), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 15),
    ]
)

map_legend_style = TableStyle(
    [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
)

three_col_stats_style = TableStyle(
    [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]
)

divider_line_style = TableStyle(
    [
        ("LINEBELOW", (0, 0), (-1, -1), 1, DIVIDER_COLOR),
    ]
)

valign_middle_style = TableStyle(
    [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
)
