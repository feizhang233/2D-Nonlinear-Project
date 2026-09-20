"""PNG diagrams of all six positive-x section action components."""

import base64
from io import BytesIO
from threading import Lock

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

COMPONENTS = {
    "axial_force": ("N", "N"),
    "shear_force_y": ("Vy", "N"),
    "shear_force_z": ("Vz", "N"),
    "torsional_moment": ("Tx", "N m"),
    "bending_moment_y": ("My", "N m"),
    "bending_moment_z": ("Mz", "N m"),
}
_LOCK = Lock()


def render_internal_force_plot(elements, component, *, dpi=140):
    if component not in COMPONENTS:
        raise ValueError("unknown internal force component")
    if isinstance(dpi, bool) or not isinstance(dpi, int) or not 72 <= dpi <= 300:
        raise ValueError("dpi must be an integer between 72 and 300")
    elements = tuple(elements)
    if not elements:
        raise ValueError("elements must be nonempty")
    symbol, unit = COMPONENTS[component]
    with _LOCK:
        figure = Figure(figsize=(8, 4.8), dpi=dpi, layout="constrained")
        FigureCanvasAgg(figure)
        axes = figure.subplots()
        for element in elements:
            axes.plot(
                element.fields.x_local,
                getattr(element.fields, component),
                label=f"Element {element.element_id}",
            )
        axes.axhline(0, color="#777777", linewidth=0.8)
        axes.set(
            title=f"Space frame: {symbol} (positive-x section)",
            xlabel="Local x [m]",
            ylabel=f"{symbol} [{unit}]",
        )
        axes.grid(alpha=0.25)
        axes.legend()
        output = BytesIO()
        figure.savefig(output, format="png")
        figure.clear()
    return output.getvalue()


def png_data_uri(png):
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")
