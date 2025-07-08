from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.colors import HexColor, lightgrey, gray
from reportlab.platypus import TableStyle
from reportlab.lib.units import cm

BLUE_HIGHLIGHT_COLOR = HexColor("#E8F0FE", 0.6)
GRID_UNIT = 0.525 * cm
HALF_GRID_UNIT = GRID_UNIT / 2

BLACK = HexColor("#000000")

report_title_style = ParagraphStyle(
    name="Title",
    fontName="Roboto-Light",
    fontSize=28,
    leading=28,
    alignment=TA_LEFT,
    textColor=BLACK,
    spaceBefore=GRID_UNIT,
    spaceAfter=GRID_UNIT,
)

section_title_style = ParagraphStyle(
    name="SectionHeader",
    fontName="Roboto-Light",
    fontSize=12,
    leading=15,
    alignment=TA_LEFT,
    textColor=BLACK,
    spaceBefore=HALF_GRID_UNIT,
    spaceAfter=HALF_GRID_UNIT,
)

body_style = ParagraphStyle(
    name="Body",
    fontName="Roboto-Light",
    fontSize=8,
    leading=11,
    textColor=BLACK,
)

label_style = ParagraphStyle(
    "LabelStyle",
    parent=body_style,
    fontSize=8,
    alignment=TA_LEFT,
    spaceAfter=0,
    textColor=gray,
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
    textColor=lightgrey,
)

# --- Table Styles ---
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
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
    ]
)
