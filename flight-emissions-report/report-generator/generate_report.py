import argparse
import sys
from functools import partial
from reportlab.platypus import SimpleDocTemplate, PageBreak
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

from chart_generator import generate_figs
from page1_builder import build_first_page
from page2_builder import build_second_page
from page3_builder import build_third_page
from page4_builder import build_fourth_page
from page5_builder import build_fifth_page
from page6_builder import build_sixth_page
from setup import setup, draw_page_layout

from setup import OUTPUT_DIR, load_data

GRID_UNIT = 0.525 * cm
HALF_GRID_UNIT = GRID_UNIT / 2


def create_report(iata_codes: list[str], airline_name: str, debug: bool = False):
    """
    Generates the full PDF report for the given airline and IATA codes.
    """
    print(" ✨ Report Generation ")
    if debug:
        print("  🔍 DEBUG MODE ENABLED")

    # Setup fonts
    setup(debug=debug)

    # Create the document template

    pdf_file_name = f"{'_'.join(iata_codes)}_flights_report.pdf"
    doc = SimpleDocTemplate(
        str(OUTPUT_DIR / pdf_file_name),
        pagesize=A4,
        rightMargin=GRID_UNIT * 2,
        leftMargin=GRID_UNIT * 2,
        topMargin=HALF_GRID_UNIT,
        bottomMargin=GRID_UNIT,
    )

    # Generate figures and build pages for each IATA code
    report_content = []
    for iata_code in iata_codes:
        output_path = OUTPUT_DIR / iata_code
        data = load_data(output_path / "data_summary.json")
        if data is None:
            print(f"❌ Error: Could not load {output_path}/data_summary.json")
            return

        data["airline_name"] = airline_name
        data["iata_code"] = iata_code
        data["data_path"] = output_path

        generate_figs(data=data, output_path=output_path, debug=debug)

        # Build pages for this IATA code and append to the report_content
        print(f"📄 Building pages for {iata_code}...")
        report_content.extend(build_first_page(data, output_path, airline_name))
        report_content.append(PageBreak())
        report_content.extend(build_second_page(data, output_path, airline_name))
        report_content.append(PageBreak())
        report_content.extend(build_third_page(data, output_path, airline_name))
        report_content.append(PageBreak())
        report_content.extend(build_fourth_page(data, output_path, airline_name))
        report_content.append(PageBreak())
        report_content.extend(build_fifth_page(data, output_path, airline_name))
        report_content.append(PageBreak())
        report_content.extend(build_sixth_page(data, output_path, airline_name))
        report_content.append(PageBreak())

    #5. Build the PDF
    all_pages = partial(draw_page_layout, debug=debug)

    print("\n📁 Building PDF Report... ")
    try:
        doc.build(report_content, onFirstPage=all_pages, onLaterPages=all_pages)
        print("\n🎉  Report generated successfully!  🎉")
        print(f"  📄 Report saved to: \033[94m{output_path}\033[0m")
    except Exception as e:
        print(f"\n  AN ERROR OCCURRED {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate the Flight Emissions Report PDF"
    )

    parser.add_argument(
        "--iata_codes",
        type=str,
        required=True,
        help="Comma-separated list of IATA codes for processing",
    )
    parser.add_argument(
        "--airline_name",
        type=str,
        required=True,
        help="The friendly name of the airline (e.g., 'Turkish Airlines')",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode for extra output",
    )
    args = parser.parse_args()

    # Check if data_summary.json exists for each IATA code directory
    iata_codes = args.iata_codes.split(",")
    for iata_code in iata_codes:
        output_path = OUTPUT_DIR  / iata_code
        data_summary_path = output_path / "data_summary.json"
        if not data_summary_path.exists():
            print(f"❌ data_summary.json not found for IATA code '{iata_code}' in '{output_path}'.")
            sys.exit(1)

    create_report(
        iata_codes=iata_codes,
        airline_name=args.airline_name,
        debug=args.debug,
    )
