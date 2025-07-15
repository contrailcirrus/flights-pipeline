from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import lightgrey
import json
import os
from typing import Optional, Dict, Any
from styles import GRID_UNIT

# --- Path Definitions ---
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "out"
FONT_DIR = PROJECT_ROOT / "fonts" / "Roboto"
ASSETS_DIR = PROJECT_ROOT / "static"
LOGO_PATH = ASSETS_DIR / "logos" / "logo_demo.png"

def setup(output_path: str, debug: bool = False):
    print("\n 🛠️ Setting up the report... ")

def setup(debug: bool = False):
    print("\n 🛠️ Setting up the report... ")

    register_fonts()
    if debug:
        print("  Successfully registered Roboto font family.")

def register_fonts():
    """
    Registers all necessary TTF fonts from the /fonts/Roboto directory
    and maps the font family for bold/normal variations.
    """
    font_map = {
        "Roboto": "Roboto-Regular.ttf",
        "Roboto-Bold": "Roboto-Bold.ttf",
        "Roboto-Medium": "Roboto-Medium.ttf",
        "Roboto-Light": "Roboto-Light.ttf",
    }

    for name, filename in font_map.items():
        font_path = FONT_DIR / filename
        if font_path.exists():
            pdfmetrics.registerFont(TTFont(name, font_path))
        else:
            print(f"  Warning: Font not found at '{font_path}'.")

    pdfmetrics.registerFontFamily("Roboto", normal="Roboto", bold="Roboto-Medium")
    pdfmetrics.registerFontFamily("Roboto-Light", normal="Roboto-Light", bold="Roboto")


def draw_page_layout(canvas, doc, debug=False):
    """
    Draws the layout for the very first page. In this case, it's clean.
    """
    canvas.saveState()
    if debug:
        draw_grid(canvas, doc)
    canvas.restoreState()


def draw_grid(canvas, doc):
    """Draws a light grey grid for visual alignment."""
    canvas.saveState()
    canvas.setStrokeColor(lightgrey)
    canvas.setLineWidth(0.25)
    page_width, page_height = doc.pagesize

    x = GRID_UNIT
    while x < page_width:
        canvas.line(x, 0, x, page_height)
        x += GRID_UNIT
    y = GRID_UNIT
    while y < page_height:
        canvas.line(0, y, page_width, y)
        y += GRID_UNIT
    canvas.restoreState()

def format_number(n: int, thsds: int = 0, width: int = 0) -> str:
    """
    String format with logic for thousands place suffixes.
    """

    def get_decimal_place(input_number: float) -> int:
        """
        Given a float and a fixed width, return the number of decimal places in order
        to get a fixed character width in formatting.
        """
        tens = [
            (10_000, 5), (1_000, 4), (100, 3),
            (10, 2), (1, 1),
        ]

        if input_number > 99_999:
            raise ValueError(f"unsupported input {input_number}. greater than max value: 99,999")

        for k, v in tens:
            if input_number >= k:
                if width < v:
                    raise ValueError(f"cannot format input {input_number} with fixed width {width}")
                if width == v or width == (v + 1):
                    return 0
                else:
                    return width - v - 1
        return width - 2  # assume 0.xxx float formatting

    place = None
    if thsds == 1:
        place = "thousand"
    elif thsds == 2:
        place = "million"
    elif thsds == 3:
        place = "billion"
    elif n >= 1_000_000_000:
        place = "billion"
    elif n >= 1_000_000:
        place = "million"
    elif n >= 1000:
        place = "thousand"

    if place == "billion":
        val = n / 1_000_000_000.0
        if width:
            dec_places = get_decimal_place(val)
            return f"{val:,.{dec_places}f}B"
        return f"{val:,.1f}B"
    elif place == "million":
        val = n / 1_000_000.0
        if width:
            dec_places = get_decimal_place(val)
            return f"{val:,.{dec_places}f}M"
        return f"{val:,.1f}M"
    elif place == "thousand":
        val = n / 1000.0
        if width:
            dec_places = get_decimal_place(val)
            return f"{val:,.{dec_places}f}k"
        return f"{val:,.1f}k"

    return f"{n:,.1f}"

def load_data(json_path: Path) -> Optional[Dict[str, Any]]:
    """
    Loads the summary data from the specified JSON file.
    """
    try:
        with open(json_path, "r") as f:
            data = json.load(f)

        # Add the base data path to the dictionary so it can be used later
        data["data_path"] = os.path.dirname(json_path)

        # TODO: Remove this and use the year from the data
        data["year"] = 2024

        if not isinstance(data, dict):
            raise ValueError("Invalid data structure: expected a dictionary")
        return data

    except FileNotFoundError:
        print(f"🚨 Error: Data file not found at '{json_path}'")
        return None
    except Exception as e:
        print(f"🚨 Error loading data: {e}")
        return None