from reportlab.pdfgen import canvas

# create a Canvas object with a filename
c = canvas.Canvas(
    "sample_report_automation.pdf", pagesize=(595.27, 841.89)
)  # A4 pagesize
# draw a string at x=100, y=800 points
# point ~ standard desktop publishing (72 DPI)

# color palate
background_color = "#fafaff"
text_color = "#000000"
container_color = "#ffffff"
border_color = "#7d7d7d"

# fill background
c.setFillColor(background_color)
c.rect(0, 0, 595.27, 841.89, fill=1)

# title
c.setFillColor(text_color)
c.setFont("Helvetica", 18)
c.drawString(65, 770, "Contrail Impact Report")

# container 1
c.setStrokeColor(border_color, alpha=1)
c.setFillColor(container_color, alpha=1)
c.roundRect(65, 645, 420, 120, 5, stroke=1, fill=1)

# container 1 content
c.setFillColor(text_color)
c.setFont("Helvetica", 11)
c.drawString(70, 730, "What are Contrails?")

c.setFont("Helvetica", 6)
c.drawString(
    70, 715, "Contrails -- the thin, white lines you sometimes see behind airplanes"
)

r = c.drawImage(
    "flights_report_trajectories_D0_2024-08-01_2024-11-04_1730740341.png",
    100,
    100,
    width=320,
    height=240,
    mask=None,
)

c.showPage()  # move to next page

# export document
c.save()
