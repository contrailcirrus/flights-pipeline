from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import lightgrey

from styles import GRID_UNIT

# --- Path Definitions ---
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
FONT_DIR = PROJECT_ROOT / "fonts" / "Roboto"
ASSETS_DIR = PROJECT_ROOT / "static"
LOGO_PATH = ASSETS_DIR / "logos" / "logo_demo.png"
OUTPUT_DIR = PROJECT_ROOT / "out" / "default"


def setup(output_path: str, debug: bool = False):
    print("\n 🛠️ Setting up the report... ")

    register_fonts()
    if debug:
        print("  Successfully registered Roboto font family.")

    # Create output directory if it doesn't exist
    global OUTPUT_DIR
    OUTPUT_DIR = Path(output_path)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if debug:
        print(f"  created output directory: {'/'.join(OUTPUT_DIR.parts[-3:])}")

    # Create figs directory
    figs_dir = OUTPUT_DIR / "figs"
    figs_dir.mkdir(parents=True, exist_ok=True)
    if debug:
        print(f"  created figs directory: {'/'.join(figs_dir.parts[-4:])}")


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

    pdfmetrics.registerFontFamily("Roboto", normal="Roboto", bold="Roboto-Bold")
    pdfmetrics.registerFontFamily(
        "Roboto-Light", normal="Roboto-Light", bold="Roboto-Medium"
    )


def draw_first_page_layout(canvas, doc, debug=False):
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
