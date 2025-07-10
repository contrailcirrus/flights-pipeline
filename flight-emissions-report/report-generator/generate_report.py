import argparse
from pathlib import Path
from functools import partial
from reportlab.platypus import SimpleDocTemplate
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

from setup import setup, draw_first_page_layout, PROJECT_ROOT
from page_one_builder import build_first_page

GRID_UNIT = 0.525 * cm
AIRLINE_NAME = None


def create_report(output_path: Path, airline_name: str, grid: bool = False):
    """
    Generates the full PDF report by orchestrating the other modules.
    """
    print("---  Starting Report Generation ---")

    # 1. Setup fonts
    setup(output_path)

    # 2. Create the document template
    doc = SimpleDocTemplate(
        str(output_path / "flight_contrails_impact_report.pdf"),
        pagesize=A4,
        rightMargin=GRID_UNIT * 2,
        leftMargin=GRID_UNIT * 2,
        topMargin=GRID_UNIT,
        bottomMargin=GRID_UNIT,
    )

    # 3. Build the first page content
    print("Building the first page content...")
    story = build_first_page(airline_name)

    # 4. Build the PDF
    on_first = partial(draw_first_page_layout, grid=grid)

    print(f"Building PDF at '{output_path}' (Debug Mode: {grid})...")
    try:
        doc.build(story, onFirstPage=on_first)
        print("---  Report Generated Successfully ---")
    except Exception as e:
        print(f"---  AN ERROR OCCURRED --- \n{e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the Flight Emissions Report PDF"
    )
    parser.add_argument(
        "-p",
        "--data_path",
        type=str,
        default="out/default",
        help="path to data directory. e.g. out/D0",
    )
    parser.add_argument(
        "-a",
        "--airline_name",
        type=str,
        help="airline friendly name",
    )
    parser.add_argument(
        "-g", "--grid", action="store_true", help="add grid to pdf overlay (True/False)"
    )
    args = parser.parse_args()

    create_report(
        output_path=PROJECT_ROOT / Path(args.data_path),
        airline_name=args.airline_name,
        grid=args.grid,
    )
