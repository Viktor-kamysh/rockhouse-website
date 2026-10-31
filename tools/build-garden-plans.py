"""Lay out TH03/TH06 without covering or reconstructing outdoor areas.

TH03 uses the complete existing illustration. TH06 uses the complete figure
from the original PDF because its later colour render cuts off a garden.
The original PDF's outdated room table is deliberately outside the excerpt.
"""

import io
import json
import subprocess
from copy import deepcopy
from pathlib import Path

from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "tmp/pdfs/gardens"
OUTPUT = ROOT / "output/pdf"
FONT_DIR = Path("/System/Library/Fonts/Supplemental")
pdfmetrics.registerFont(TTFont("Plan", str(FONT_DIR / "Arial.ttf")))
pdfmetrics.registerFont(TTFont("PlanBold", str(FONT_DIR / "Arial Bold.ttf")))
INK = "#292d28"
OLIVE = "#53674b"
MUTED = "#666c64"


def page_stream(width, height, draw):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))
    draw(c)
    c.showPage()
    c.save()
    return PdfReader(buffer).pages[0]


def write_pdf(page, path, title):
    writer = PdfWriter()
    writer.add_page(page)
    writer.add_metadata({"/Title": title, "/Author": "Trade Estate Group"})
    with path.open("wb") as output:
        writer.write(output)


def text(c, x, y, value, size=10, bold=False, color=INK):
    c.setFillColor(color)
    c.setFont("PlanBold" if bold else "Plan", size)
    c.drawString(x, y, value)


def area(value):
    return value.replace(".", ",")


def th03_figure():
    # Keep the full source, including all three gardens and the section diagram.
    return page_stream(540, 540, lambda c: c.drawImage(
        str(ROOT / "assets/floorplans/source/townhouse-03-visual.png"),
        0, 0, width=540, height=540, preserveAspectRatio=True,
    ))


def th06_figure():
    result = page_stream(540, 440, lambda c: None)
    source = PdfReader(ROOT / "assets/images/TOWNHOUSE-06.pdf").pages[0]
    size = float(source.mediabox.width)
    # One contiguous excerpt keeps the original relative placement and scale.
    left, top, right, bottom = 0.025, 0.040, 0.970, 0.755
    part = deepcopy(source)
    rect = RectangleObject((left * size, (1 - bottom) * size,
                           right * size, (1 - top) * size))
    part.cropbox = rect
    part.trimbox = rect
    drawn_size = 540 / (right - left)
    result.merge_transformed_page(part, Transformation().scale(drawn_size / size).translate(
        -left * drawn_size, 28 - (1 - bottom) * drawn_size,
    ))
    overlay = page_stream(540, 440, lambda c:
        text(c, 10, 8, "Zahrada 30,6 m² + 18,7 m²", 11, True, OLIVE)
    )
    result.merge_page(overlay)
    return result


def sales_sheet(unit, figure):
    width, height = 842, 595

    def draw(c):
        c.setFillColor("#ffffff")
        c.rect(0, 0, width, height, fill=1, stroke=0)
        c.setStrokeColor("#dce1d8")
        c.setLineWidth(0.6)
        c.line(582, 64, 582, 557)
        x = 604
        text(c, x, 547, "ROCK HOUSE PRAGUE", 10, True)
        text(c, x, 510, unit["residence"], 24, True)
        text(c, x, 487, f'{unit["layout"]}   ·   {unit["building"]}', 11, color=MUTED)

        text(c, x, 451, "Plocha včetně vnitřních konstrukcí", 9, color=MUTED)
        text(c, x, 425, area(unit["nvArea"]), 23, True)
        text(c, x, 396, "Zahrada", 9, color=MUTED)
        text(c, x, 372, area(unit["outdoorArea"]), 21, True, OLIVE)
        c.line(x, 354, 818, 354)

        text(c, x, 334, "MÍSTNOSTI", 9, True, MUTED)
        y = 312
        for room in unit["rooms"]:
            text(c, x, y, room["name"], 9)
            c.setFont("PlanBold", 9)
            c.drawRightString(818, y, area(room["area"]))
            y -= 18

        text(c, 24, 43, "Plocha jednotky dle prohlášení vlastníka. Vybavení a zeleň jsou ilustrativní.", 8, color=MUTED)
        text(c, 24, 29, "Závazné vymezení jednotky a venkovních ploch stanoví smluvní dokumentace.", 8, color=MUTED)
        text(c, 604, 43, "TRADE ESTATE GROUP", 9, True)
        text(c, 604, 29, "rockhouseprague.cz", 9, color=MUTED)

    page = page_stream(width, height, draw)
    figure_height = float(figure.mediabox.height)
    figure_y = 58 if figure_height == 540 else 91
    figure_scale = 0.95 if figure_height == 540 else 1
    # The entire figure fits in a dedicated region; no table overlays the image.
    assert figure_y + figure_height * figure_scale <= height
    page.merge_transformed_page(figure, Transformation().scale(figure_scale).translate(24, figure_y))
    return page


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    units = json.loads((ROOT / "bookings.json").read_text())["apartments"]
    for unit_id, make_figure in (("03", th03_figure), ("06", th06_figure)):
        unit = next(item for item in units if item["id"] == unit_id)
        figure = make_figure()
        figure_pdf = WORK / f"townhouse-{unit_id}-figure.pdf"
        write_pdf(figure, figure_pdf, unit["residence"] + " - půdorys a zahrady")
        sheet = sales_sheet(unit, figure)
        published = ROOT / f"assets/floorplans/pdf/townhouse-{unit_id}-plan.pdf"
        write_pdf(sheet, published, unit["residence"] + " - Rock House Prague")
        write_pdf(sheet, OUTPUT / f"Rock-House-TH{unit_id}-2026-10-30.pdf", unit["residence"])
        preview = ROOT / f"assets/floorplans/presentation/townhouse-{unit_id}-plan"
        subprocess.run(["pdftoppm", "-singlefile", "-scale-to", "2200", "-jpeg",
                        "-jpegopt", "quality=92,optimize=y", str(figure_pdf), str(preview)], check=True)
        print(f"Built {unit['residence']}: {unit['nvArea']}, garden {unit['outdoorArea']}")


if __name__ == "__main__":
    main()
