from reportlab.platypus import Flowable

from setup import OUTPUT_DIR


class PlotlyChartFlowable(Flowable):
    """
    A self-contained Flowable that generates a Plotly chart, saves it as a
    temporary image, and draws it onto the PDF.
    """

    def __init__(self, chart_function, image_name):
        Flowable.__init__(self)
        self.chart_function = chart_function
        self.image_path = OUTPUT_DIR / "figs" / image_name
        self._final_width = 0
        self._final_height = 0

    def wrap(self, available_width, available_height):
        """Tells ReportLab how much space this component needs."""
        aspect_ratio = 7 / 3
        width = available_width
        height = width / aspect_ratio

        if height > available_height:
            height = available_height
            width = height * aspect_ratio

        self._final_width = width
        self._final_height = height
        return width, height

    def draw(self):
        """This method generates, saves, and draws the chart."""
        try:
            # 1. Call your function to create the Plotly figure object
            fig = self.chart_function()

            # 2. Save the figure to the temporary image file
            fig.write_image(
                self.image_path,
                scale=12,
                width=self._final_width,
                height=self._final_height,
            )
            # 3. Draw the newly created image onto the PDF canvas
            self.canv.drawImage(
                self.image_path,
                0,
                0,
                width=self._final_width,
                height=self._final_height,
                preserveAspectRatio=False,
                mask="auto",
            )

        except Exception as e:
            print(f"!!! ERROR creating or drawing Plotly chart: {e}")
            self.canv.drawString(
                10, self._final_height / 2, "Error: Could not generate Plotly chart."
            )
