from reportlab.pdfgen import canvas

# create a Canvas object with a filename
c = canvas.Canvas("rl-hello_again.pdf", pagesize=(595.27, 841.89))  # A4 pagesize
# draw a string at x=100, y=800 points
# point ~ standard desktop publishing (72 DPI)
# coordinate system:
#   y
#   |
#   |   page
#   |
#   |
#   0-------x
c.drawString(50, 780, "Hello Again")
# finish page
c.showPage()
# construct and save file to .pdf
c.save()
