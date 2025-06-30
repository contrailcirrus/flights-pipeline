import argparse
import sys
from pathlib import Path
from functools import partial
from reportlab.platypus import SimpleDocTemplate
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

from setup import setup, draw_first_page_layout, PROJECT_ROOT
from page_one_builder import build_first_page
from chart_generator import generate_figs

GRID_UNIT = 0.525 * cm
AIRLINE_NAME = None


def create_report(output_path: Path, airline_name: str, debug: bool = False):
    """
    Generates the full PDF report by orchestrating the other modules.
    """
    print(" ✨ Report Generation ")
    if debug:
        print("  🔍 DEBUG MODE ENABLED")

    # 1. Setup fonts
    setup(output_path, debug=debug)

    # 2. Generate figures
    generate_figs(output_path, debug=debug)

    # 3. Create the document template
    doc = SimpleDocTemplate(
        str(output_path / "flight_contrails_impact_report.pdf"),
        pagesize=A4,
        rightMargin=GRID_UNIT * 2,
        leftMargin=GRID_UNIT * 2,
        topMargin=GRID_UNIT,
        bottomMargin=GRID_UNIT,
    )

    # 4. Build the first page content
    print("\n📄 Building the first page content... ")
    story = build_first_page(airline_name)

    # 5. Build the PDF
    on_first = partial(draw_first_page_layout, debug=debug)

    print("\n📁 Building PDF Report... ")
    try:
        doc.build(story, onFirstPage=on_first)
        print("\n🎉  Report generated successfully!  🎉")
        # blue color to the file path
        print(f"  📄 Report saved to: \033[94m{output_path}\033[0m")
    except Exception as e:
        print(f"\n  AN ERROR OCCURRED {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the Flight Emissions Report PDF"
    )
    parser.add_argument(
        "-p",
        "--data_path",
        type=str,
        help="path to data directory. e.g. out/D0",
    )
    parser.add_argument(
        "-a",
        "--airline_name",
        type=str,
        required=True,
        help="airline friendly name",
    )
    parser.add_argument("-d", "--debug", action="store_true", help="debug mode")
    args = parser.parse_args()

    if not args.airline_name:
        print("🚨 Error: Airline name is required 🚨")
        sys.exit(1)

    output_path = None
    if args.data_path:
        output_path = PROJECT_ROOT / Path(args.output_path)
    else:
        output_path = PROJECT_ROOT / "out" / args.airline_name
        print(
            f"⚠️ Warning: Output directory not found, Using default path: \033[94m{output_path}\033[0m \n"
        )

    create_report(
        output_path=output_path,
        airline_name=args.airline_name,
        debug=args.debug,
    )
