from __future__ import annotations

import hashlib
import html
import math
import os
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Image as RLImage,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from generate_plate_shell_buckling_pdf import (
    BODY,
    BULLET,
    CALLOUT,
    CAPTION,
    CONTENT_W,
    CylinderSchematic,
    EQ_STYLE,
    H1,
    H2,
    H3,
    INK,
    LIGHT,
    MARGIN_B,
    MARGIN_L,
    MARGIN_R,
    MARGIN_T,
    MID,
    NAVY,
    PAGE_H,
    PAGE_W,
    PALE_GOLD,
    SMALL,
    SOURCE,
    TEAL,
    WARNING,
    bullet,
    make_table,
    source,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "Shell_Instability_Research_完整數學邏輯推導與例題_繁中.pdf"
EQUATION_DIR = ROOT / "tmp" / "pdfs" / "shell_equations"
MPL_VENDOR = ROOT / "tmp" / "pdfs" / "pydeps312"
MPL_CONFIG = ROOT / "tmp" / "pdfs" / "mplconfig"
MPL_CACHE = ROOT / "tmp" / "pdfs" / "xdgcache"


def _load_math_renderer():
    if str(MPL_VENDOR) not in sys.path:
        sys.path.insert(0, str(MPL_VENDOR))
    os.environ.setdefault("MPLCONFIGDIR", str(MPL_CONFIG))
    os.environ.setdefault("XDG_CACHE_HOME", str(MPL_CACHE))
    try:
        from matplotlib.font_manager import FontProperties
        from matplotlib.mathtext import math_to_image
    except ImportError as exc:
        raise RuntimeError(
            "需要 Matplotlib 以產生標準數學公式。請先將 matplotlib 安裝到 tmp/pdfs/pydeps312。"
        ) from exc
    return math_to_image, FontProperties


MATH_TO_IMAGE, FONT_PROPERTIES = _load_math_renderer()


LATEX_OVERRIDES = {
    "(1-1)": r"\Pi(\mathbf{q};\lambda)=U(\mathbf{q})-\lambda\,\mathbf{f}^{\mathsf T}\mathbf{q}",
    "(1-2)": r"\delta\Pi=\left(\frac{\partial U}{\partial\mathbf{q}}\right)^{\mathsf T}\delta\mathbf{q}-\lambda\,\mathbf{f}^{\mathsf T}\delta\mathbf{q}",
    "(1-3)": r"\delta\Pi=\left[\mathbf{f}_{\mathrm{int}}(\mathbf{q})-\lambda\mathbf{f}\right]^{\mathsf T}\delta\mathbf{q}=\mathbf{r}(\mathbf{q},\lambda)^{\mathsf T}\delta\mathbf{q}",
    "(1-4)": r"\mathbf{r}(\mathbf{q},\lambda)=\mathbf{f}_{\mathrm{int}}(\mathbf{q})-\lambda\mathbf{f}=\mathbf{0}",
    "(1-5)": r"\Pi(\mathbf{q}_e+\varepsilon\boldsymbol{\eta})=\Pi(\mathbf{q}_e)+\varepsilon\,\delta\Pi[\boldsymbol{\eta}]+\frac{\varepsilon^2}{2}\,\delta^2\Pi[\boldsymbol{\eta},\boldsymbol{\eta}]+\mathcal{O}(\varepsilon^3)",
    "(1-6)": r"\Pi(\mathbf{q}_e+\varepsilon\boldsymbol{\eta})-\Pi(\mathbf{q}_e)=\frac{\varepsilon^2}{2}\,\boldsymbol{\eta}^{\mathsf T}\mathbf{K}_T\boldsymbol{\eta}+\mathcal{O}(\varepsilon^3)",
    "(1-7)": r"\mathbf{K}_T=\frac{\partial\mathbf{r}}{\partial\mathbf{q}}=\frac{\partial^2\Pi}{\partial\mathbf{q}^2}",
    "(1-8)": r"\mathbf{K}_T\,d\mathbf{q}-\mathbf{f}\,d\lambda=\mathbf{0}",
    "(1-9)": r"\mathbf{v}_1^{\mathsf T}\mathbf{K}_T\,d\mathbf{q}-\mathbf{v}_1^{\mathsf T}\mathbf{f}\,d\lambda=0",
    "(1-10)": r"-\left(\mathbf{v}_1^{\mathsf T}\mathbf{f}\right)d\lambda=0",
    "(1-11)": r"d\mathbf{q}^{*}=d\mathbf{q}+\gamma\mathbf{v}_1",
    "(2-1)": r"\delta^2\Pi_c[\boldsymbol{\phi},\boldsymbol{\zeta}]=0\qquad\forall\,\boldsymbol{\zeta}\in\mathcal{V}_{\mathrm{adm}}",
    "(2-2)": r"\mathbf{u}=a\boldsymbol{\phi}+\mathbf{z},\qquad\langle\boldsymbol{\phi},\mathbf{z}\rangle=0",
    "(2-3)": r"\Pi[a\boldsymbol{\phi}+\mathbf{z};\lambda]=\Pi_2+\Pi_3+\Pi_4+\mathcal{O}(\|\mathbf{u}\|^5)",
    "(2-4)": r"\Pi_2[\mathbf{u};\lambda]=\Pi_2[\mathbf{u};\lambda_c]+\Delta\lambda\,\Pi_2'[\mathbf{u};\lambda_c]+\mathcal{O}(\Delta\lambda^2\|\mathbf{u}\|^2)",
    "(2-5)": r"\Pi_z=\Pi_2[\mathbf{z}]+\frac{a^2}{2}\,\Pi_{111}[\boldsymbol{\phi},\boldsymbol{\phi},\mathbf{z}]+\mathcal{O}(a^3\|\mathbf{z}\|,\|\mathbf{z}\|^3)",
    "(2-6)": r"\delta_z\Pi=\Pi_{11}[\mathbf{z},\boldsymbol{\eta}]+\frac{a^2}{2}\,\Pi_{111}[\boldsymbol{\phi},\boldsymbol{\phi},\boldsymbol{\eta}]=0",
    "(2-7)": r"\Pi_{11}[\mathbf{z}_2,\boldsymbol{\eta}]=-\frac12\Pi_{111}[\boldsymbol{\phi},\boldsymbol{\phi},\boldsymbol{\eta}]\qquad\forall\,\boldsymbol{\eta}\perp\boldsymbol{\phi}",
    "(2-8)": r"F(a,\lambda)=(1-\lambda)a^2+A_3a^3+A_4a^4+\text{higher-order terms}",
    "(2-9)": r"A_3=\Pi_3[\boldsymbol{\phi}]",
    "(2-10)": r"A_4=\Pi_4[\boldsymbol{\phi}]-\Pi_2[\mathbf{z}_2]",
    "(3-1)": r"F^{*}(a,\lambda,\mu)=(1-\lambda)a^2+A_3a^3+A_4a^4+\mu Ba",
    "(3-17)": r"w_0=\kappa h\,[\cos(p_0x/R)+4\cos(mx/R)\cos(my/R)]\exp\!\left[-\frac{\mu_g^2(x^2+y^2)}{2R^2}\right]",
    "(3-18)": r"F^{**}=C\left[(1-\lambda)b_0^2+\frac{2c}{3}b_0^3-2\lambda\kappa b_0\right]",
    "(3-15)": r"1-\lambda^{*}=6|A_4|\left(\frac{|\mu|}{8|A_4|}\right)^{2/3}",
    "(3-16)": r"1-\lambda^{*}=\frac32|A_4|^{1/3}|\mu|^{2/3}",
    "(4-2)": r"N_x=\frac{Eh}{1-\nu^2}(\varepsilon_x+\nu\varepsilon_y),\quad N_y=\frac{Eh}{1-\nu^2}(\nu\varepsilon_x+\varepsilon_y),\quad N_{xy}=\frac{Eh}{2(1+\nu)}\gamma_{xy}",
    "(4-6)": r"\varepsilon_{x,yy}+\varepsilon_{y,xx}-\gamma_{xy,xy}=\frac{w_{,yy}}{R_1}+\frac{w_{,xx}}{R_2}+w_{,xy}^2-w_{,xx}w_{,yy}",
    "(4-7)": r"\frac{\Phi_{,yyyy}+\Phi_{,xxxx}+(-\nu-\nu+2+2\nu)\Phi_{,xxyy}}{Eh}",
    "(4-9)": r"\nabla^4\Phi=Eh\left(\frac{w_{,yy}}{R_1}+\frac{w_{,xx}}{R_2}\right)+Eh\left(w_{,xy}^2-w_{,xx}w_{,yy}\right)",
    "(4-10a)": r"U_b=\frac{D}{2}\int_S\!\left[w_{,xx}^2+w_{,yy}^2+2\nu w_{,xx}w_{,yy}+2(1-\nu)w_{,xy}^2\right]dA",
    "(4-10b)": r"\delta U_b=\int_S D\nabla^4w\,\delta w\,dA+\text{boundary terms}",
    "(4-10c)": r"\delta U_m=\int_S\left(N_x\delta\varepsilon_x+N_y\delta\varepsilon_y+N_{xy}\delta\gamma_{xy}\right)dA",
    "(4-10d)": r"\delta\varepsilon_x=\frac{\delta w}{R_1}+w_{,x}\delta w_{,x},\qquad\delta\varepsilon_y=\frac{\delta w}{R_2}+w_{,y}\delta w_{,y}",
    "(4-10e)": r"\delta\gamma_{xy}=w_{,y}\delta w_{,x}+w_{,x}\delta w_{,y}",
    "(4-10f)": r"\delta U_m=\int_S\!\left[\frac{N_x}{R_1}+\frac{N_y}{R_2}-N_xw_{,xx}-2N_{xy}w_{,xy}-N_yw_{,yy}\right]\delta w\,dA+\text{boundary terms}",
    "(4-11)": r"D\nabla^4w+\frac{\Phi_{,yy}}{R_1}+\frac{\Phi_{,xx}}{R_2}-\Phi_{,yy}w_{,xx}-\Phi_{,xx}w_{,yy}+2\Phi_{,xy}w_{,xy}=p",
    "(5-9)": r"N(\alpha,\beta)=\frac{Dq^4}{\alpha^2}+\frac{Eh\,\alpha^2}{R^2q^4}",
    "(5-10)": r"N(X)=DX+\frac{Eh}{R^2X}",
    "(5-11)": r"\frac{dN}{dX}=D-\frac{Eh}{R^2X^2}",
    "(5-13)": r"X^{*}=\frac{1}{R}\sqrt{\frac{Eh}{D}}",
    "(5-15)": r"N_{\mathrm{cr}}=\frac{\sqrt{DEh}}{R}+\frac{\sqrt{DEh}}{R}=\frac{2\sqrt{DEh}}{R}",
    "(5-16)": r"N_{\mathrm{cr}}=\frac{Eh^2}{R\sqrt{3(1-\nu^2)}}",
    "(5-17)": r"\sigma_{\mathrm{cr}}=\frac{N_{\mathrm{cr}}}{h}=\frac{E(h/R)}{\sqrt{3(1-\nu^2)}}",
    "(5-23)": r"N(q)=Dq^2+\frac{Eh}{R^2q^2}",
    "(5-26)": r"p_{\mathrm{cr}}=\frac{2E}{\sqrt{3(1-\nu^2)}}\left(\frac{h}{R}\right)^2",
    "(5-27)": r"U_h=\frac12\int_S\!\left[h\,\boldsymbol{\varepsilon}_m^{\mathsf T}\mathbf{C}\boldsymbol{\varepsilon}_m+\frac{h^3}{12}\,\boldsymbol{\kappa}^{\mathsf T}\mathbf{C}\boldsymbol{\kappa}\right]dA",
    "(6-1)": r"\mathbf{r}(\mathbf{q},\lambda)=\mathbf{f}_{\mathrm{int}}(\mathbf{q})-\lambda\mathbf{f}_{\mathrm{ref}}=\mathbf{0}",
    "(6-2)": r"\mathbf{r}(\mathbf{q}_j+\delta\mathbf{q},\lambda_j+\delta\lambda)\approx\mathbf{r}_j+\mathbf{K}_{T,j}\delta\mathbf{q}-\mathbf{f}_{\mathrm{ref}}\delta\lambda",
    "(6-3)": r"\mathbf{K}_T=\frac{\partial\mathbf{f}_{\mathrm{int}}}{\partial\mathbf{q}}=\mathbf{K}_{\mathrm{mat}}+\mathbf{K}_{\mathrm{geo}}+\mathbf{K}_{\mathrm{other}}",
    "(6-4)": r"\delta^2\Pi=\int_V\!\left[\delta\boldsymbol{\varepsilon}_L^{\mathsf T}\mathbf{C}\,\delta\boldsymbol{\varepsilon}_L+\sigma_{ij}\,\delta u_{k,i}\delta u_{k,j}\right]dV",
    "(6-5)": r"\delta^2\Pi=\delta\mathbf{q}^{\mathsf T}\left[\int_V\mathbf{B}^{\mathsf T}\mathbf{C}\mathbf{B}\,dV+\int_V\mathbf{G}^{\mathsf T}\mathbf{S}(\boldsymbol{\sigma})\mathbf{G}\,dV\right]\delta\mathbf{q}",
    "(6-6)": r"\mathbf{K}_{\mathrm{mat}}=\int_V\mathbf{B}^{\mathsf T}\mathbf{C}\mathbf{B}\,dV,\qquad\mathbf{K}_{\mathrm{geo}}=\int_V\mathbf{G}^{\mathsf T}\mathbf{S}(\boldsymbol{\sigma})\mathbf{G}\,dV",
    "(6-7)": r"\mathbf{K}_T(\lambda)\approx\mathbf{K}_M+\lambda\mathbf{K}_{\sigma}^{\mathrm{ref}}",
    "(6-8)": r"\left(\mathbf{K}_M+\lambda\mathbf{K}_{\sigma}^{\mathrm{ref}}\right)\boldsymbol{\phi}=\mathbf{0}",
    "(6-9)": r"\mathbf{K}_M\boldsymbol{\phi}=\lambda\mathbf{K}_G\boldsymbol{\phi}",
    "(6-10)": r"g(\Delta\mathbf{q},\Delta\lambda)=\Delta\mathbf{q}^{\mathsf T}\Delta\mathbf{q}+\beta^2\Delta\lambda^2\mathbf{f}_{\mathrm{ref}}^{\mathsf T}\mathbf{f}_{\mathrm{ref}}-\Delta s^2=0",
    "(6-14)": r"g+2\Delta\mathbf{q}^{\mathsf T}\delta\mathbf{q}+2\beta^2\Delta\lambda\,\delta\lambda\,\mathbf{f}_{\mathrm{ref}}^{\mathsf T}\mathbf{f}_{\mathrm{ref}}=0",
    "(6-15)": r"g+2\Delta\mathbf{q}^{\mathsf T}\delta\mathbf{q}_I+2\delta\lambda\left(\Delta\mathbf{q}^{\mathsf T}\delta\mathbf{q}_{II}+\beta^2\Delta\lambda\,\mathbf{f}_{\mathrm{ref}}^{\mathsf T}\mathbf{f}_{\mathrm{ref}}\right)=0",
    "(6-16)": r"\delta\lambda=-\frac{g/2+\Delta\mathbf{q}^{\mathsf T}\delta\mathbf{q}_I}{\Delta\mathbf{q}^{\mathsf T}\delta\mathbf{q}_{II}+\beta^2\Delta\lambda\,\mathbf{f}_{\mathrm{ref}}^{\mathsf T}\mathbf{f}_{\mathrm{ref}}}",
    "(6-17)": r"\Delta\lambda_p=\pm\frac{\Delta s}{\sqrt{\mathbf{q}_t^{\mathsf T}\mathbf{q}_t+\beta^2\mathbf{f}_{\mathrm{ref}}^{\mathsf T}\mathbf{f}_{\mathrm{ref}}}}",
    "(6-23)": r"\Delta\mathbf{q}^{*}=\Delta\mathbf{q}-\frac{\Delta\mathbf{q}^{\mathsf T}\Delta\mathbf{q}}{\mathbf{v}_1^{\mathsf T}\Delta\mathbf{q}}\,\mathbf{v}_1",
    "(E3-1)": r"U=2\left[\frac{EA(l-L_0)^2}{2L_0}\right]=\frac{EA(l-L_0)^2}{L_0}",
    "(E3-4)": r"P=\frac{2EA\,y(L_0-l)}{L_0l}",
    "(E3-9)": r"\frac{d}{ds}\left(\frac{s}{r}\right)=\frac1r-\frac{s^2}{r^3}=\frac{r^2-s^2}{r^3}=\frac{\alpha^2}{r^3}",
    "(E3-10)": r"\frac{dp}{ds}=\frac{\alpha^2}{r^3}-1=0\quad\Longrightarrow\quad r^{*}=\alpha^{2/3}",
    "(E3-11)": r"(s^{*})^2=(r^{*})^2-\alpha^2=\alpha^{4/3}-\alpha^2",
    "(E5-1)": r"p_{\mathrm{cr}}=\frac{2E(h/R)^2}{\sqrt{3(1-\nu^2)}}=0.34250\ \mathrm{MPa}",
    "(E6-5)": r"\lambda=\frac{12.8\pm\sqrt{12.8^2-4(0.46)(68)}}{0.92}",
}


def P(text: str, style=BODY):
    return Paragraph(text, style)


def _replace_balanced_sqrt(text: str) -> str:
    r"""Convert √(...) and √[...] to mathtext-compatible \sqrt{...}."""
    while "√" in text:
        pos = text.find("√")
        if pos + 1 >= len(text) or text[pos + 1] not in "([":
            text = text[:pos] + r"\sqrt{}" + text[pos + 1 :]
            continue
        opening = text[pos + 1]
        closing = ")" if opening == "(" else "]"
        depth = 0
        end = None
        for idx in range(pos + 1, len(text)):
            if text[idx] == opening:
                depth += 1
            elif text[idx] == closing:
                depth -= 1
                if depth == 0:
                    end = idx
                    break
        if end is None:
            raise ValueError(f"Unbalanced square-root expression: {text}")
        inside = text[pos + 2 : end]
        text = text[:pos] + r"\sqrt{" + inside + "}" + text[end + 1 :]
    return text


def legacy_formula_to_latex(text: str) -> str:
    """Translate the legacy ReportLab inline markup to MathText syntax."""
    value = html.unescape(text)
    value = re.sub(r"<font[^>]*>", "", value)
    value = value.replace("</font>", "")
    value = re.sub(r"<b>(.*?)</b>", r"\1", value)
    value = re.sub(r"<sub>(.*?)</sub>", r"_{\1}", value)
    value = re.sub(r"<super>(.*?)</super>", r"^{\1}", value)
    value = _replace_balanced_sqrt(value)

    replacements = {
        "Π": r"\Pi ",
        "δ": r"\delta ",
        "λ": r"\lambda ",
        "φ": r"\phi ",
        "Φ": r"\Phi ",
        "ζ": r"\zeta ",
        "η": r"\eta ",
        "ε": r"\varepsilon ",
        "σ": r"\sigma ",
        "ν": r"\nu ",
        "γ": r"\gamma ",
        "κ": r"\kappa ",
        "μ": r"\mu ",
        "α": r"\alpha ",
        "β": r"\beta ",
        "π": r"\pi ",
        "∇": r"\nabla ",
        "∂": r"\partial ",
        "∫": r"\int ",
        "Δ": r"\Delta ",
        "×": r"\times ",
        "±": r"\pm ",
        "≈": r"\approx ",
        "⇒": r"\Longrightarrow ",
        "→": r"\to ",
        "≥": r"\geq ",
        "≤": r"\leq ",
        "≠": r"\neq ",
        "∈": r"\in ",
        "∞": r"\infty ",
        "∝": r"\propto ",
        "⟨": r"\langle ",
        "⟩": r"\rangle ",
        "‖": r"\Vert ",
        "−": "-",
        "，": r"\qquad ",
        "　": r"\quad ",
        "或": r"\quad\mathrm{or}\quad ",
        "平衡：": r"\mathrm{equilibrium:}\quad ",
        "極限點：": r"\mathrm{limit\ point:}\quad ",
        "波長": r"\lambda_{\mathrm{wave}}=",
        "有限長度取鄰近整數": r"\mathrm{choose}\ ",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = re.sub(r"\b(sin|cos|exp|det)\b", lambda m: "\\" + m.group(1), value)
    value = re.sub(r"\b(MPa|kN|N|mm)\b", r"\\mathrm{\1}", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _formula_image(latex: str, label: str, font_size: float = 13.2):
    latex = latex.replace(r"\mathsf T", r"\mathrm{T}")
    latex = re.sub(r"\\mathrm\s+([A-Za-z])", r"\\mathrm{\1}", latex)
    latex = re.sub(r"\\(mathbf|mathcal)\s+([A-Za-z0-9])", r"\\\1{\2}", latex)
    latex = re.sub(r"\\boldsymbol\\([A-Za-z]+)", r"\\boldsymbol{\\\1}", latex)
    latex = re.sub(r"\\frac([0-9A-Za-z])([0-9A-Za-z])", r"\\frac{\1}{\2}", latex)

    def _text_to_roman(match: re.Match[str]) -> str:
        content = match.group(1).replace("-", r"\!-!").replace(" ", r"\ ")
        return r"\mathrm{" + content + "}"

    latex = re.sub(r"\\text\{([^{}]*)\}", _text_to_roman, latex)
    EQUATION_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{latex}|{font_size}".encode("utf-8")).hexdigest()[:20]
    path = EQUATION_DIR / f"eq_{key}.png"
    if not path.exists():
        prop = FONT_PROPERTIES(family="STIXGeneral", size=font_size)
        try:
            MATH_TO_IMAGE(
                f"${latex}$",
                path,
                prop=prop,
                dpi=320,
                format="png",
                color="#1D2731",
            )
        except Exception as exc:
            raise ValueError(f"Formula render failed for {label}: {latex}") from exc

    from PIL import Image as PILImage, ImageOps

    # Matplotlib MathText writes a white canvas by default.  Converting that
    # luminance to an alpha channel lets the pale equation-box background show
    # through, so equations look like native typesetting instead of pasted
    # screenshots.
    with PILImage.open(path).convert("RGBA") as rendered:
        # multiBuild lays out the story more than once to resolve the TOC.
        # Skip conversion when this cached image already has a non-opaque alpha
        # channel; applying luminance-to-alpha twice would create a dark block.
        if rendered.getchannel("A").getextrema() == (255, 255):
            grayscale = rendered.convert("L")
            alpha = ImageOps.invert(grayscale).point(
                lambda pixel: 0 if pixel < 3 else min(255, int(pixel * 1.18))
            )
            transparent = PILImage.new("RGBA", rendered.size, "#1D2731")
            transparent.putalpha(alpha)
            transparent.save(path)

    with PILImage.open(path) as im:
        width_px, height_px = im.size
    width = width_px * 72.0 / 320.0
    height = height_px * 72.0 / 320.0
    max_width = CONTENT_W - 28 * mm
    max_height = 15 * mm
    scale = min(1.0, max_width / width, max_height / height)
    image = RLImage(str(path), width=width * scale, height=height * scale)
    image.hAlign = "CENTER"
    return image


def eq_latex(latex: str | list[str] | tuple[str, ...], label: str):
    lines = [latex] if isinstance(latex, str) else list(latex)
    images = [[_formula_image(line, label)] for line in lines]
    inner = Table(images, colWidths=[CONTENT_W - 25 * mm], hAlign="CENTER")
    inner.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
            ]
        )
    )
    table = Table(
        [[inner, Paragraph(label, EQ_STYLE)]],
        colWidths=[CONTENT_W - 19 * mm, 19 * mm],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F7FA")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD6DF")),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return [Spacer(1, 2.5), table, Spacer(1, 5.5)]


def eq(text: str, label: str):
    latex = LATEX_OVERRIDES.get(label, legacy_formula_to_latex(text))
    return eq_latex(latex, label)


class MatrixPairEquation(Flowable):
    """Draw two compact 2x2 matrices with true multi-line brackets."""

    def __init__(self):
        super().__init__()
        self.width = 122 * mm
        self.height = 15 * mm

    def _matrix(self, canvas, x, y, values):
        w = 24 * mm
        h = 12 * mm
        canvas.setStrokeColor(NAVY)
        canvas.setLineWidth(0.8)
        canvas.line(x, y, x, y + h)
        canvas.line(x, y + h, x + 2.2 * mm, y + h)
        canvas.line(x, y, x + 2.2 * mm, y)
        canvas.line(x + w, y, x + w, y + h)
        canvas.line(x + w - 2.2 * mm, y + h, x + w, y + h)
        canvas.line(x + w - 2.2 * mm, y, x + w, y)
        canvas.setFillColor(INK)
        canvas.setFont("Times-Roman", 9.8)
        cols = [x + 7.5 * mm, x + 17.2 * mm]
        rows = [y + 7.7 * mm, y + 2.2 * mm]
        for row_index, row in enumerate(values):
            for col_index, value in enumerate(row):
                canvas.drawCentredString(cols[col_index], rows[row_index], str(value))
        return x + w

    def _symbol(self, canvas, x, y, subscript):
        canvas.setFillColor(INK)
        canvas.setFont("Times-BoldItalic", 12)
        canvas.drawString(x, y + 4.1 * mm, "K")
        canvas.setFont("Times-Roman", 7.2)
        canvas.drawString(x + 3.8 * mm, y + 2.7 * mm, subscript)
        canvas.setFont("Times-Roman", 12)
        canvas.drawString(x + 8.2 * mm, y + 4.1 * mm, "=")
        return x + 15 * mm

    def draw(self):
        canvas = self.canv
        canvas.saveState()
        y = 1.2 * mm
        x = 2 * mm
        x = self._symbol(canvas, x, y, "M")
        x = self._matrix(canvas, x, y, ((12, -2), (-2, 6)))
        canvas.setFont("Times-Roman", 12)
        canvas.drawString(x + 3 * mm, y + 4.1 * mm, ",")
        x = self._symbol(canvas, x + 10 * mm, y, "G")
        self._matrix(canvas, x, y, ((1, 0.2), (0.2, 0.5)))
        canvas.restoreState()


def matrix_pair_equation(label: str):
    inner = MatrixPairEquation()
    table = Table(
        [[inner, Paragraph(label, EQ_STYLE)]],
        colWidths=[CONTENT_W - 19 * mm, 19 * mm],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F7FA")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD6DF")),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return [Spacer(1, 2.5), table, Spacer(1, 5.5)]


class ShellInstabilityDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, **kwargs):
        super().__init__(filename, **kwargs)
        frame = Frame(
            MARGIN_L,
            MARGIN_B,
            CONTENT_W,
            PAGE_H - MARGIN_T - MARGIN_B,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
            id="body",
        )
        self.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=draw_page)])
        self._bookmark_id = 0

    def beforeDocument(self):
        self._bookmark_id = 0

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name in {
            "Heading1Custom",
            "Heading2Custom",
            "Heading3Custom",
        }:
            level = {
                "Heading1Custom": 0,
                "Heading2Custom": 1,
                "Heading3Custom": 2,
            }[flowable.style.name]
            text = flowable.getPlainText()
            self._bookmark_id += 1
            key = f"shell_instability_{self._bookmark_id}"
            self.canv.bookmarkPage(key)
            try:
                self.canv.addOutlineEntry(text, key, level=level, closed=False)
            except Exception:
                pass
            self.notify("TOCEntry", (level, text, self.page, key))


def draw_page(canvas, doc):
    canvas.saveState()
    page = canvas.getPageNumber()
    if page == 1:
        canvas.setFillColor(NAVY)
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#65B8C4"))
        canvas.rect(0, PAGE_H - 11 * mm, PAGE_W, 11 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("HeitiL", 8.5)
        canvas.drawCentredString(PAGE_W / 2, 10 * mm, "依工作區原書與索引重建 · 繁體中文研究講義")
        canvas.restoreState()
        return

    canvas.setStrokeColor(LIGHT)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN_L, PAGE_H - 11.5 * mm, PAGE_W - MARGIN_R, PAGE_H - 11.5 * mm)
    canvas.line(MARGIN_L, 12 * mm, PAGE_W - MARGIN_R, 12 * mm)
    canvas.setFont("HeitiL", 7.8)
    canvas.setFillColor(MID)
    canvas.drawString(MARGIN_L, PAGE_H - 8.5 * mm, "Shell Instability Research：完整數學邏輯推導")
    canvas.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 8.5 * mm, "Koiter 漸近 · 缺陷敏感性 · 路徑追蹤")
    canvas.drawString(MARGIN_L, 8 * mm, "Koiter · Timoshenko-Gere · de Borst · Chapelle-Bathe")
    canvas.drawRightString(PAGE_W - MARGIN_R, 8 * mm, f"第 {page} 頁")
    canvas.restoreState()


class StabilityMap(Flowable):
    def __init__(self, width=CONTENT_W, height=58 * mm):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        c.saveState()
        c.setStrokeColor(NAVY)
        c.setFillColor(INK)
        c.setLineWidth(1.0)

        panels = [
            (8 * mm, "穩定基本路徑", "stable"),
            (67 * mm, "極限點", "limit"),
            (126 * mm, "分岔點", "bif"),
        ]
        for x0, title, kind in panels:
            y0 = 11 * mm
            w = 48 * mm
            h = 34 * mm
            c.roundRect(x0, y0, w, h, 3, stroke=1, fill=0)
            c.setFont("HeitiM", 8)
            c.drawCentredString(x0 + w / 2, 48 * mm, title)
            c.setStrokeColor(LIGHT)
            c.line(x0 + 7 * mm, y0 + 6 * mm, x0 + 7 * mm, y0 + 29 * mm)
            c.line(x0 + 7 * mm, y0 + 6 * mm, x0 + 42 * mm, y0 + 6 * mm)
            c.setStrokeColor(TEAL)
            c.setLineWidth(1.6)
            if kind == "stable":
                p = c.beginPath()
                p.moveTo(x0 + 9 * mm, y0 + 8 * mm)
                p.curveTo(x0 + 18 * mm, y0 + 10 * mm, x0 + 26 * mm, y0 + 18 * mm, x0 + 40 * mm, y0 + 27 * mm)
                c.drawPath(p)
            elif kind == "limit":
                p = c.beginPath()
                p.moveTo(x0 + 9 * mm, y0 + 8 * mm)
                p.curveTo(x0 + 22 * mm, y0 + 10 * mm, x0 + 35 * mm, y0 + 28 * mm, x0 + 39 * mm, y0 + 20 * mm)
                c.drawPath(p)
                c.setFillColor(colors.HexColor("#B44949"))
                c.circle(x0 + 36.5 * mm, y0 + 25 * mm, 1.6 * mm, fill=1, stroke=0)
            else:
                p = c.beginPath()
                p.moveTo(x0 + 9 * mm, y0 + 8 * mm)
                p.lineTo(x0 + 40 * mm, y0 + 27 * mm)
                c.drawPath(p)
                p2 = c.beginPath()
                p2.moveTo(x0 + 23 * mm, y0 + 16.5 * mm)
                p2.curveTo(x0 + 27 * mm, y0 + 15 * mm, x0 + 34 * mm, y0 + 11 * mm, x0 + 41 * mm, y0 + 9 * mm)
                c.drawPath(p2)
                c.setFillColor(colors.HexColor("#B44949"))
                c.circle(x0 + 23 * mm, y0 + 16.5 * mm, 1.6 * mm, fill=1, stroke=0)
            c.setStrokeColor(NAVY)
            c.setFillColor(INK)
        c.setFont("HeitiL", 6.8)
        c.setFillColor(MID)
        c.drawString(4 * mm, 3 * mm, "縱軸：載重參數 λ；橫軸：廣義位移 a。紅點表示 K_T 出現零特徵值。")
        c.restoreState()


def add_toc(story):
    story.append(P("目錄", H2))
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            "ShellTOC1",
            fontName="HeitiM",
            fontSize=9.5,
            leading=15,
            leftIndent=0,
            firstLineIndent=0,
            textColor=NAVY,
        ),
        ParagraphStyle(
            "ShellTOC2",
            fontName="HeitiL",
            fontSize=8.7,
            leading=14,
            leftIndent=10 * mm,
            firstLineIndent=0,
            textColor=INK,
        ),
        ParagraphStyle(
            "ShellTOC3",
            fontName="HeitiL",
            fontSize=8.1,
            leading=13,
            leftIndent=18 * mm,
            firstLineIndent=0,
            textColor=MID,
        ),
    ]
    story.append(toc)


def build_story() -> list:
    story = []

    cover_title = ParagraphStyle(
        "ShellCoverTitle",
        fontName="HeitiM",
        fontSize=26,
        leading=35,
        textColor=colors.white,
        alignment=TA_CENTER,
        wordWrap="CJK",
    )
    cover_sub = ParagraphStyle(
        "ShellCoverSub",
        fontName="HeitiL",
        fontSize=13,
        leading=21,
        textColor=colors.HexColor("#CFE8EE"),
        alignment=TA_CENTER,
        wordWrap="CJK",
    )
    cover_note = ParagraphStyle(
        "ShellCoverNote",
        fontName="HeitiL",
        fontSize=9.2,
        leading=15,
        textColor=colors.HexColor("#E7F2F5"),
        alignment=TA_CENTER,
        leftIndent=18 * mm,
        rightIndent=18 * mm,
        wordWrap="CJK",
    )

    story.append(Spacer(1, 30 * mm))
    story.append(P("Shell Instability Research", cover_title))
    story.append(Spacer(1, 4 * mm))
    story.append(P("殼體失穩研究所需之完整數學邏輯推導", cover_title))
    story.append(Spacer(1, 7 * mm))
    story.append(
        P(
            "從勢能、二次變分與切線剛度<br/>推導至 Koiter 分岔漸近、缺陷敏感性、淺殼方程與弧長法",
            cover_sub,
        )
    )
    story.append(Spacer(1, 19 * mm))
    story.append(
        P(
            "包含：穩定/極限點/分岔判別、二階與四階約化勢能、2/3 次方缺陷律、"
            "軸壓圓柱殼、外壓球殼、有限元素特徵值、分支切換與 6 組例題",
            cover_note,
        )
    )
    story.append(Spacer(1, 25 * mm))
    story.append(P("語言：繁體中文　｜　建議單位：N、mm、MPa", cover_note))
    story.append(Spacer(1, 4 * mm))
    story.append(P("修訂日期：2026-08-03　｜　公式重排與物理解說增訂版", cover_note))
    story.append(PageBreak())

    story.append(P("使用說明與研究範圍", H1))
    story.append(
        P(
            "本講義將「殼體失穩」視為一個連續邏輯鏈，而不是若干孤立公式："
            "三維或殼體運動學先決定非線性應變；應變進入總勢能；平衡來自一階變分；"
            "穩定性來自二階變分；二階變分退化時，以高階能量決定分岔方向；"
            "初始缺陷再把理想分岔轉化為提前出現的極限點；最後才離散成有限元素切線剛度、"
            "廣義特徵值與弧長路徑追蹤。"
        )
    )
    story.append(
        P(
            "<b>適用前提：</b>除另有說明，假設材料線彈性、薄殼、小應變、中等轉角、準靜態、"
            "保守死載重與充分光滑的位移場。若含塑性、黏彈性、接觸、非保守跟隨力或強烈動態效應，"
            "勢能正定性不再是完整判據，必須改用對應的一致切線與動力穩定分析。",
            WARNING,
        )
    )
    story.extend(
        source(
            "[B07 | §1.1, §2.2-2.6 | PDF p.11-64] 穩定、勢能、二次變分、分岔鄰域與缺陷；"
            "[B07 | §3.14-3.18 | PDF p.176-236] von Kármán-Föppl、淺殼、球殼、圓柱殼與局部缺陷；"
            "[B04 | §3.5, §4.2, §4.4 | PDF p.119-152] 線性屈曲、弧長、穩定與分支切換。"
        )
    )
    story.append(P("統一符號", H2))
    story.append(
        make_table(
            ["符號", "意義", "備註"],
            [
                ["Π 或 P", "總勢能：內部應變能減外力勢能", "平衡時 δΠ=0"],
                ["δΠ, δ<super>2</super>Π", "一階變分與二階變分", "分別控制平衡與局部穩定"],
                ["λ", "載重參數；理想臨界值常正規化為 1", "λ=1 不必等於實際破壞載重"],
                ["a, a<sub>i</sub>", "臨界模態振幅或多模態座標", "小量；可正可負"],
                ["φ, v<sub>1</sub>", "臨界模態/最低切線特徵向量", "正規化方式必須明定"],
                ["μ", "初始缺陷幅度參數", "正負號表示與危險模態同向或反向"],
                ["R, h, L", "殼體半徑、厚度與軸向長度", "薄殼 h/R≪1"],
                ["N<sub>x</sub>, N<sub>y</sub>, N<sub>xy</sub>", "膜力合力", "N/mm；本文壓縮量常取正值 N"],
                ["D", "彎曲剛度 Eh<super>3</super>/[12(1-ν<super>2</super>)]", "N·mm"],
                ["K<sub>T</sub>", "一致切線剛度 ∂r/∂q", "對保守彈性死載重通常對稱"],
            ],
            widths=[35 * mm, 82 * mm, CONTENT_W - 117 * mm],
        )
    )
    add_toc(story)
    story.append(PageBreak())

    # 0. Physical quantities and mathematical toolbox
    story.append(P("0. 物理量詞典與數學工具箱", H1))
    story.append(
        P(
            "本章先回答兩個閱讀障礙：每個符號在真實殼體上代表什麼，以及後續的「變分、正定、投影、"
            "高階小量」究竟在做什麼。若只想查符號，可看 0.1；若對推導中的數學步驟不熟，"
            "建議先讀 0.2–0.7，再進入第 1 章。"
        )
    )

    story.append(P("0.1 幾何、位移、內力與剛度的物理意義", H2))
    story.append(
        make_table(
            ["物理量", "常用單位", "在殼體上的意義", "如何直觀理解"],
            [
                ["R<sub>1</sub>, R<sub>2</sub>", "mm", "中面兩個主曲率半徑", "1/R 越大，表面越彎；R→∞ 即平板方向"],
                ["h", "mm", "殼厚", "h/R≪1 表示厚度遠小於曲率尺度，屬薄殼"],
                ["x, y, z", "mm", "中面兩個座標與厚度座標", "z=0 為中面；z∈[-h/2,h/2]"],
                ["u, v", "mm", "沿中面切向的位移", "改變面內長度，主要產生膜應變"],
                ["w", "mm", "沿殼面法向的位移", "既會彎曲，也因原有曲率產生 w/R 膜伸長"],
                ["ε<sub>x</sub>, ε<sub>y</sub>, γ<sub>xy</sub>", "無因次", "中面正應變與工程剪應變", "10<super>-3</super> 表示每 1000 mm 約改變 1 mm"],
                ["κ<sub>x</sub>, κ<sub>y</sub>, κ<sub>xy</sub>", "mm<super>-1</super>", "曲率變化", "約等於 w 的二階空間導數；半波越短，曲率越大"],
            ],
            widths=[35 * mm, 25 * mm, 62 * mm, CONTENT_W - 122 * mm],
        )
    )
    story.append(
        make_table(
            ["物理量", "常用單位", "定義或來源", "物理解讀"],
            [
                ["σ<sub>αβ</sub>", "MPa=N/mm<super>2</super>", "三維 Cauchy 應力", "材料內一個小面積上承受的力密度"],
                ["N<sub>αβ</sub>", "N/mm", "厚度方向積分後的膜力合力", "每 1 mm 殼邊寬度所傳遞的面內力"],
                ["M<sub>αβ</sub>", "N", "應力對中面的第一矩", "每單位邊長的彎矩；量綱為 N·mm/mm=N"],
                ["p", "MPa=N/mm<super>2</super>", "作用於殼面的法向壓力", "球殼膜平衡中 pR/2 轉成膜力 N"],
                ["D", "N·mm", "等向薄殼彎曲剛度", "與 h<super>3</super> 成正比，厚度減半時只剩 1/8"],
                ["Π", "N·mm", "內部應變能減外力勢能", "平衡看斜率 δΠ；穩定看曲率 δ<super>2</super>Π"],
                ["λ", "無因次", "參考載重的倍率", "實際載重向量為 λf<sub>ref</sub>"],
                ["φ", "依正規化而定", "臨界模態形狀", "只決定形狀；振幅由 a 承擔，φ 的尺度可自由選"],
                ["μ 或 w<sub>0</sub>", "無因次或 mm", "初始幾何缺陷", "與危險模態同形、同向時通常最不利"],
            ],
            widths=[35 * mm, 29 * mm, 61 * mm, CONTENT_W - 125 * mm],
        )
    )
    story.append(P("膜力與彎矩不是新的材料應力，而是把厚度方向的應力濃縮成中面量："))
    story.extend(
        eq_latex(
            [
                r"N_{\alpha\beta}=\int_{-h/2}^{h/2}\sigma_{\alpha\beta}(z)\,dz",
                r"M_{\alpha\beta}=\int_{-h/2}^{h/2}z\,\sigma_{\alpha\beta}(z)\,dz",
            ],
            "(0-1)",
        )
    )
    story.append(
        P(
            "若應力沿厚度均勻，第一式直接成為 <font name='ArialU'>N=σh</font>。"
            "若應力以中面為零點呈線性反對稱分布，正負面應力合力互相抵消，卻留下彎矩 M。"
            "這就是膜作用與彎曲作用的最簡單區別。",
            CALLOUT,
        )
    )
    story.extend(eq_latex(r"D=\frac{Eh^3}{12(1-\nu^2)}", "(0-2)"))
    story.append(
        P(
            "量綱檢查：<font name='ArialU'>[E]=N/mm<super>2</super></font>，乘上 "
            "<font name='ArialU'>h<super>3</super></font> 後得到 <font name='ArialU'>N·mm</font>，"
            "正好是薄板/殼每單位寬度的彎曲剛度。量綱不一致通常表示公式漏了 h、R 或空間導數。"
        )
    )

    story.append(P("0.2 變分不是神祕符號：它是對整個函數做方向微分", H2))
    story.append(
        P(
            "對普通純量函數 <font name='ArialU'>f(x)</font>，在 x 沿方向 η 移動 εη，Taylor 展開為："
        )
    )
    story.extend(
        eq_latex(
            r"f(x+\varepsilon\eta)=f(x)+\varepsilon f'(x)\eta+\frac{\varepsilon^2}{2}f''(x)\eta^2+\mathcal{O}(\varepsilon^3)",
            "(0-3)",
        )
    )
    story.append(
        P(
            "殼體未知量不是單一 x，而是整個位移場 <font name='ArialU'>u(x,y)</font>。"
            "因此把試探方向 η 也換成一個可容許函數，普通導數便成為第一變分："
        )
    )
    story.extend(
        eq_latex(
            r"\delta\Pi[\mathbf{u};\boldsymbol{\eta}]=\left.\frac{d}{d\varepsilon}\Pi[\mathbf{u}+\varepsilon\boldsymbol{\eta}]\right|_{\varepsilon=0}",
            "(0-4)",
        )
    )
    story.extend(
        eq_latex(
            r"\delta^2\Pi[\mathbf{u};\boldsymbol{\eta},\boldsymbol{\eta}]=\left.\frac{d^2}{d\varepsilon^2}\Pi[\mathbf{u}+\varepsilon\boldsymbol{\eta}]\right|_{\varepsilon=0}",
            "(0-5)",
        )
    )
    story.append(
        P(
            "第一變分回答「沿任意虛位移方向，能量斜率是否為零」；第二變分回答「斜率為零後，"
            "能量曲面向上彎還是向下彎」。η 是用來探測能量地形的方向，不是另一個真實載重步。"
        )
    )

    story.append(P("0.3 正定矩陣、特徵值與 Rayleigh 商", H2))
    story.append(
        P(
            "對稱切線剛度可寫成正交特徵向量展開。令 "
            "<font name='ArialU'>K<sub>T</sub>v<sub>i</sub>=κ<sub>i</sub>v<sub>i</sub></font>，"
            "且任意擾動 <font name='ArialU'>η=Σc<sub>i</sub>v<sub>i</sub></font>，則："
        )
    )
    story.extend(
        eq_latex(
            r"\boldsymbol{\eta}^{\mathrm T}\mathbf K_T\boldsymbol{\eta}=\sum_{i=1}^{n}\kappa_i c_i^2",
            "(0-6)",
        )
    )
    story.append(
        P(
            "因 <font name='ArialU'>c<sub>i</sub><super>2</super>≥0</font>，只有所有 κ<sub>i</sub> 都為正時，"
            "每一方向都增加能量。最小特徵值也可由 Rayleigh 商求得："
        )
    )
    story.extend(
        eq_latex(
            r"\kappa_1=\min_{\boldsymbol{\eta}\ne\mathbf 0}\frac{\boldsymbol{\eta}^{\mathrm T}\mathbf K_T\boldsymbol{\eta}}{\boldsymbol{\eta}^{\mathrm T}\boldsymbol{\eta}}",
            "(0-7)",
        )
    )
    story.append(
        P(
            "這個最小化的物理意義是：在所有同樣大小的擾動中，尋找增加能量最少的形狀。"
            "當 κ<sub>1</sub> 下降到零，對應模態 φ 就是最容易被激發的中性形狀。"
        )
    )

    story.append(P("0.4 積分分部、強式、弱式與兩類邊界條件", H2))
    story.append(
        P(
            "高階殼方程常由能量變分而來。以一維彎曲項為最小例子："
        )
    )
    story.extend(
        eq_latex(
            r"\delta U_b=EI\int_0^L w''\,\delta w''\,dx",
            "(0-8)",
        )
    )
    story.append(P("第一次積分分部把一個導數從 δw 移到 w："))
    story.extend(
        eq_latex(
            r"\int_0^L w''\delta w''dx=\left[w''\delta w'\right]_0^L-\int_0^Lw'''\delta w'dx",
            "(0-9)",
        )
    )
    story.append(P("再積分分部一次："))
    story.extend(
        eq_latex(
            r"\int_0^L w''\delta w''dx=\left[w''\delta w'-w'''\delta w\right]_0^L+\int_0^Lw''''\delta w\,dx",
            "(0-10)",
        )
    )
    story.append(
        make_table(
            ["項目", "數學角色", "工程例子"],
            [
                ["必要（essential）邊界條件", "直接限制試函數與虛位移", "指定 w 或轉角；該處 δw=0 或 δw′=0"],
                ["自然（natural）邊界條件", "由積分分部後的邊界項讀出", "指定彎矩 EIw″ 或剪力 -EIw‴"],
                ["強式", "要求內域每點滿足微分方程", "EIw⁗=p"],
                ["弱式", "要求對所有可容許 δw 的積分平衡", "有限元素實際離散的形式"],
            ],
            widths=[43 * mm, 64 * mm, CONTENT_W - 107 * mm],
        )
    )

    story.append(P("0.5 小量階次與為何有些項可以刪除", H2))
    story.append(
        P(
            "漸近展開不是任意丟項，而是先指定臨界振幅 a 很小，再比較每一項縮小的速度。"
            "若 <font name='ArialU'>a=0.1</font>，則 a<super>2</super>=0.01、"
            "a<super>3</super>=0.001；階次越高，靠近臨界點時通常越小。"
        )
    )
    story.append(
        make_table(
            ["情況", "主導平衡", "必須採用的載重尺度", "保留到哪一階"],
            [
                ["A<sub>3</sub>≠0", "Δλa<super>2</super> 與 a<super>3</super> 平衡", "Δλ=O(a)", "三次項先決定最近分支"],
                ["對稱使 A<sub>3</sub>=0", "Δλa<super>2</super> 與 a<super>4</super> 平衡", "Δλ=O(a<super>2</super>)", "必須保留四次項"],
                ["補空間修正 z", "線性 Lz 與 a<super>2</super> 強迫平衡", "z=O(a<super>2</super>)", "z 對約化能量貢獻為 O(a<super>4</super>)"],
            ],
            widths=[39 * mm, 65 * mm, 46 * mm, CONTENT_W - 150 * mm],
        )
    )
    story.extend(
        eq_latex(
            r"\mathcal{O}(a^m)\,\mathcal{O}(a^n)=\mathcal{O}(a^{m+n}),\qquad \mathcal{O}(a^m)+\mathcal{O}(a^n)=\mathcal{O}(a^{\min(m,n)})",
            "(0-11)",
        )
    )

    story.append(P("0.6 正交投影與 Lyapunov–Schmidt 約化", H2))
    story.append(
        P(
            "臨界點只有 φ 方向失去剛度，其餘方向仍可逆。若 φ 已正規化為 "
            "<font name='ArialU'>φ<super>T</super>φ=1</font>，定義投影："
        )
    )
    story.extend(
        eq_latex(
            r"\mathbf P\mathbf u=\langle\boldsymbol{\phi},\mathbf u\rangle\boldsymbol{\phi},\qquad \mathbf Q\mathbf u=(\mathbf I-\mathbf P)\mathbf u",
            "(0-12)",
        )
    )
    story.append(
        make_table(
            ["步驟", "運算", "目的"],
            [
                ["1. 分解", "u=aφ+z，且 z=Qu", "把唯一的軟方向與其餘硬方向分開"],
                ["2. 解 Q 方程", "Q∇Π(aφ+z,λ)=0", "因 Q 空間切線可逆，可求 z=z(a,λ)"],
                ["3. 代回", "F(a,λ)=Π(aφ+z(a,λ),λ)", "把無限維/高維問題縮成一個純量能量"],
                ["4. 解 P 方程", "∂F/∂a=0", "得到分岔分支、穩定性與缺陷尺度律"],
            ],
            widths=[31 * mm, 67 * mm, CONTENT_W - 98 * mm],
        )
    )
    story.append(
        P(
            "這個方法不是把其他自由度設為零；相反地，它先讓其他自由度在每個 a 下重新平衡，"
            "再把其鬆弛效果帶回約化能量。因此第 2 章的 z<sub>2</sub> 是必要修正，而非裝飾項。"
        )
    )

    story.append(P("0.7 Laplacian、雙調和算子與 Airy 函數", H2))
    story.extend(
        eq_latex(
            [
                r"\nabla^2 f=f_{,xx}+f_{,yy}",
                r"\nabla^4f=(\nabla^2)^2f=f_{,xxxx}+2f_{,xxyy}+f_{,yyyy}",
            ],
            "(0-13)",
        )
    )
    story.append(
        P(
            "Laplacian 衡量場量相對周圍平均值的彎曲；雙調和算子是對 Laplacian 再作用一次，"
            "自然出現在彎曲能含 w 的二階導數、而平衡又再積分分部兩次的問題。"
            "Airy 應力函數則用一個純量 Φ 的二階導數表示三個膜力分量，"
            "使兩條面內平衡式因混合偏導可交換而自動滿足。"
        )
    )
    story.extend(
        source(
            "[B07 | §1.1, §2.2-2.4 | PDF p.11-50] 變分穩定與臨界空間約化；"
            "[B04 | §4.4.1 | PDF p.147-148] 離散二次變分與切線特徵值；"
            "[B07 | §3.14-3.15 | PDF p.176-191] 淺殼雙調和與 Airy 表示。"
        )
    )
    story.append(PageBreak())

    # 1. Stability
    story.append(P("1. 從總勢能到穩定判據", H1))
    story.append(P("1.1 保守系統、平衡與總勢能", H2))
    story.append(
        P(
            "令離散廣義座標為 <font name='ArialU'>q∈R<super>n</super></font>，內部應變能為 "
            "<font name='ArialU'>U(q)</font>，外載重向量為 <font name='ArialU'>f</font>。"
            "死載重不隨變形方向改變，因此外力勢能為 <font name='ArialU'>f<super>T</super>q</font>，"
            "總勢能定義為："
        )
    )
    story.extend(eq("Π(q;λ)=U(q)-λ f<super>T</super>q", "(1-1)"))
    story.append(P("令任意可容許虛位移為 <font name='ArialU'>δq</font>。一階變分逐項計算："))
    story.extend(eq("δΠ=(∂U/∂q)<super>T</super>δq-λf<super>T</super>δq", "(1-2)"))
    story.extend(eq("δΠ=[f<sub>int</sub>(q)-λf]<super>T</super>δq=r(q,λ)<super>T</super>δq", "(1-3)"))
    story.append(
        P(
            "若 (1-3) 對所有可容許 <font name='ArialU'>δq</font> 都等於零，"
            "線性代數基本引理要求括號內每一自由度的係數皆為零，因此："
        )
    )
    story.extend(eq("r(q,λ)=f<sub>int</sub>(q)-λf=0", "(1-4)"))
    story.append(P("式 (1-4) 就是非線性有限元素的離散平衡方程。"))

    story.append(P("1.2 二次變分為何決定局部穩定", H2))
    story.append(
        P(
            "在平衡點 <font name='ArialU'>q<sub>e</sub></font> 附近，取擾動 "
            "<font name='ArialU'>q=q<sub>e</sub>+εη</font>，其中 "
            "<font name='ArialU'>ε</font> 是小純量、<font name='ArialU'>η</font> 是固定方向。"
            "對總勢能作 Taylor 展開："
        )
    )
    story.extend(
        eq(
            "Π(q<sub>e</sub>+εη)=Π(q<sub>e</sub>)+εδΠ[η]+(ε<super>2</super>/2)δ<super>2</super>Π[η,η]+O(ε<super>3</super>)",
            "(1-5)",
        )
    )
    story.append(P("由於 <font name='ArialU'>q<sub>e</sub></font> 已平衡，<font name='ArialU'>δΠ=0</font>，故："))
    story.extend(
        eq(
            "Π(q<sub>e</sub>+εη)-Π(q<sub>e</sub>)=(ε<super>2</super>/2)η<super>T</super>K<sub>T</sub>η+O(ε<super>3</super>)",
            "(1-6)",
        )
    )
    story.extend(eq("K<sub>T</sub>=∂r/∂q=∂<super>2</super>Π/∂q<super>2</super>", "(1-7)"))
    story.append(
        P(
            "因此，若對每一非零可容許方向都有 "
            "<font name='ArialU'>η<super>T</super>K<sub>T</sub>η&gt;0</font>，"
            "平衡點是總勢能的嚴格局部極小值，微小擾動會提高勢能，故為穩定。"
            "若存在方向使二次型小於零，沿該方向的勢能下降，平衡不穩定。若最小值恰為零，"
            "二階判據失效，必須保留三次或四次項。"
        )
    )
    story.append(
        make_table(
            ["二次型/特徵值", "勢能幾何", "結論"],
            [
                ["η<super>T</super>K<sub>T</sub>η&gt;0；所有 κ<sub>i</sub>&gt;0", "嚴格局部極小", "穩定"],
                ["存在 η 使二次型&lt;0；至少一個 κ<sub>i</sub>&lt;0", "鞍點或局部極大", "不穩定"],
                ["最小 κ<sub>1</sub>=0", "中性方向", "臨界；檢查高階項"],
            ],
            widths=[62 * mm, 55 * mm, CONTENT_W - 117 * mm],
        )
    )
    story.extend(source("[B07 | §1.1 | PDF p.11-16] 勢能正定充分判據；[B04 | §4.4.1 | PDF p.147-148] 離散系統 δ²U=(1/2)q̇ᵀKq̇ 與 det K=0。"))

    story.append(P("1.3 極限點與分岔點的代數分類", H2))
    story.append(StabilityMap())
    story.append(P("圖 1-1　三種典型載重-位移局部幾何。", CAPTION))
    story.append(
        P(
            "沿平衡路徑 <font name='ArialU'>r(q,λ)=0</font> 微分，得到增量方程："
        )
    )
    story.extend(eq("K<sub>T</sub>dq-f dλ=0", "(1-8)"))
    story.append(
        P(
            "在臨界點令最小特徵值 <font name='ArialU'>κ<sub>1</sub>=0</font>，"
            "<font name='ArialU'>K<sub>T</sub>v<sub>1</sub>=0</font>，且 "
            "<font name='ArialU'>v<sub>1</sub><super>T</super>v<sub>1</sub>=1</font>。"
            "以 <font name='ArialU'>v<sub>1</sub><super>T</super></font> 左乘 (1-8)："
        )
    )
    story.extend(eq("v<sub>1</sub><super>T</super>K<sub>T</sub>dq-v<sub>1</sub><super>T</super>f dλ=0", "(1-9)"))
    story.extend(eq("0-(v<sub>1</sub><super>T</super>f)dλ=0", "(1-10)"))
    story.append(
        P(
            "式 (1-10) 只有兩種基本可能。若 "
            "<font name='ArialU'>v<sub>1</sub><super>T</super>f≠0</font>，"
            "必須 <font name='ArialU'>dλ=0</font>，載重在該點達到局部極值，稱為<b>極限點</b>。"
            "若 <font name='ArialU'>v<sub>1</sub><super>T</super>f=0</font>，"
            "即使 <font name='ArialU'>dλ≠0</font> 也可滿足方程，齊次解可任意加入 "
            "<font name='ArialU'>γv<sub>1</sub></font>，增量解失去唯一性，稱為<b>分岔點</b>："
        )
    )
    story.extend(eq("dq<super>*</super>=dq+γv<sub>1</sub>", "(1-11)"))
    story.append(
        P(
            "極限點描述同一路徑的載重轉折；分岔點描述同一載重附近出現另一條平衡分支。"
            "兩者都會使 <font name='ArialU'>K<sub>T</sub></font> 奇異，但物理意義與數值策略不同。"
        )
    )
    story.extend(source("[B04 | §4.4.2 | PDF p.148-151] 由最低特徵值與載重向量正交性區分極限點與分岔。"))

    # 2. Koiter reduction
    story.append(PageBreak())
    story.append(P("2. Koiter 分岔鄰域的漸近約化", H1))
    story.append(P("2.1 位移分解：臨界子空間加正交補空間", H2))
    story.append(
        P(
            "令理想臨界載重為 <font name='ArialU'>λ=λ<sub>c</sub></font>。"
            "臨界二次變分存在零模態 <font name='ArialU'>φ</font>："
        )
    )
    story.extend(eq("δ<super>2</super>Π<sub>c</sub>[φ,ζ]=0　對所有可容許 ζ", "(2-1)"))
    story.append(
        P(
            "對單一臨界模態，把鄰近位移寫成："
        )
    )
    story.extend(eq("u=aφ+z，　⟨φ,z⟩=0", "(2-2)"))
    story.append(
        P(
            "其中 <font name='ArialU'>aφ</font> 是臨界方向，<font name='ArialU'>z</font> "
            "位於二次型仍正定的補空間。這不是近似，而是先作正交分解；近似發生在後續只保留有限階小量。"
        )
    )
    story.append(
        P(
            "在 <font name='ArialU'>λ<sub>c</sub></font> 附近展開總勢能，記 "
            "<font name='ArialU'>Δλ=λ-λ<sub>c</sub></font>："
        )
    )
    story.extend(
        eq(
            "Π(aφ+z;λ)=Π<sub>2</sub>+Π<sub>3</sub>+Π<sub>4</sub>+O(‖u‖<super>5</super>)",
            "(2-3)",
        )
    )
    story.append(P("二次項的載重展開為："))
    story.extend(
        eq(
            "Π<sub>2</sub>[u;λ]=Π<sub>2</sub>[u;λ<sub>c</sub>]+Δλ Π′<sub>2</sub>[u;λ<sub>c</sub>]+O(Δλ<super>2</super>‖u‖<super>2</super>)",
            "(2-4)",
        )
    )
    story.append(
        P(
            "由 (2-1)，<font name='ArialU'>Π<sub>2</sub>[aφ;λ<sub>c</sub>]=0</font>，"
            "而混合二次項也為零。保留到四階，可把與 <font name='ArialU'>z</font> 有關的最低階項整理為："
        )
    )
    story.extend(
        eq(
            "Π<sub>z</sub>=Π<sub>2</sub>[z]+(a<super>2</super>/2)Π<sub>111</sub>[φ,φ,z]+O(a<super>3</super>‖z‖,‖z‖<super>3</super>)",
            "(2-5)",
        )
    )
    story.append(
        P(
            "對 <font name='ArialU'>z</font> 取駐值。令任意補空間變分為 <font name='ArialU'>η</font>："
        )
    )
    story.extend(
        eq(
            "δ<sub>z</sub>Π=Π<sub>11</sub>[z,η]+(a<super>2</super>/2)Π<sub>111</sub>[φ,φ,η]=0",
            "(2-6)",
        )
    )
    story.append(
        P(
            "把雙線性型 <font name='ArialU'>Π<sub>11</sub>[z,η]</font> 寫成"
            " <font name='ArialU'>η<super>T</super>Lz</font>，並令 Q 為投影到 φ 的正交補空間。"
            "因 η 可在 Q 空間任意選取，(2-6) 等價於一個向量/函數方程："
        )
    )
    story.extend(
        eq_latex(
            r"\mathbf L_Q\mathbf z+\frac{a^2}{2}\,\mathbf Q\mathbf g_{11}+\mathcal{O}(a^3,a\Delta\lambda,\|\mathbf z\|^2)=\mathbf 0",
            "(2-6a)",
        )
    )
    story.append(
        P(
            "其中 <font name='ArialU'>η<super>T</super>g<sub>11</sub>="
            "Π<sub>111</sub>[φ,φ,η]</font>。臨界點只有 P 空間的一個零特徵值；"
            "在 Q 空間中 <font name='ArialU'>L<sub>Q</sub></font> 仍可逆，所以可逐步移項："
        )
    )
    story.extend(
        eq_latex(
            r"\mathbf L_Q\mathbf z=-\frac{a^2}{2}\mathbf Q\mathbf g_{11}+\mathcal{O}(a^3,a\Delta\lambda,\|\mathbf z\|^2)",
            "(2-6b)",
        )
    )
    story.extend(
        eq_latex(
            r"\mathbf z=-\frac{a^2}{2}\mathbf L_Q^{-1}\mathbf Q\mathbf g_{11}+\mathcal{O}(a^3,a\Delta\lambda)=a^2\mathbf z_2+\mathcal{O}(a^3,a\Delta\lambda)",
            "(2-6c)",
        )
    )
    story.append(
        P(
            "這裡沒有 O(a) 的 z，原因是線性 O(a) 強迫正好沿零模態 φ，已全部放進 aφ；"
            "非臨界方向第一次受到強迫，是兩個一階模態相乘產生的 O(a<super>2</super>) 幾何非線性。"
        )
    )
    story.append(
        P(
            "因補空間上的 <font name='ArialU'>Π<sub>11</sub></font> 可逆，解必為 "
            "<font name='ArialU'>z=a<super>2</super>z<sub>2</sub>+O(aΔλ,a<super>3</super>)</font>，其中："
        )
    )
    story.extend(
        eq(
            "Π<sub>11</sub>[z<sub>2</sub>,η]=-(1/2)Π<sub>111</sub>[φ,φ,η]　對所有 η⊥φ",
            "(2-7)",
        )
    )
    story.append(
        P(
            "式 (2-7) 是「二階場修正」的線性邊值問題。它說明四階約化係數不只是直接四階能量，"
            "還必須扣除結構在非臨界方向鬆弛所釋放的能量。"
        )
    )

    story.append(P("2.2 約化勢能的三次與四次係數", H2))
    story.append(
        P(
            "把 <font name='ArialU'>z=a<super>2</super>z<sub>2</sub></font> 代回並收集同階項。"
            "先將臨界模態正規化，使載重導數二次型為 "
            "<font name='ArialU'>Π′<sub>2</sub>[φ]=-1</font>。若再把 "
            "<font name='ArialU'>λ<sub>c</sub></font> 正規化為 1，單模態約化勢能為："
        )
    )
    story.extend(
        eq(
            "F(a,λ)=(1-λ)a<super>2</super>+A<sub>3</sub>a<super>3</super>+A<sub>4</sub>a<super>4</super>+高階項",
            "(2-8)",
        )
    )
    story.extend(eq("A<sub>3</sub>=Π<sub>3</sub>[φ]", "(2-9)"))
    story.extend(
        eq(
            "A<sub>4</sub>=Π<sub>4</sub>[φ]-Π<sub>2</sub>[z<sub>2</sub>]",
            "(2-10)",
        )
    )
    story.append(P("下面把式 (2-10) 的負號完整算出。四階中與 z<sub>2</sub> 有關的部分是："))
    story.extend(
        eq_latex(
            r"a^4\left\{\Pi_2[\mathbf z_2]+\frac12\Pi_{111}[\boldsymbol\phi,\boldsymbol\phi,\mathbf z_2]\right\}",
            "(2-10a)",
        )
    )
    story.append(P("由二次能量的定義與 (2-7) 取 η=z<sub>2</sub>："))
    story.extend(
        eq_latex(
            r"\Pi_2[\mathbf z_2]=\frac12\Pi_{11}[\mathbf z_2,\mathbf z_2]=-\frac14\Pi_{111}[\boldsymbol\phi,\boldsymbol\phi,\mathbf z_2]",
            "(2-10b)",
        )
    )
    story.extend(
        eq_latex(
            r"\frac12\Pi_{111}[\boldsymbol\phi,\boldsymbol\phi,\mathbf z_2]=-2\Pi_2[\mathbf z_2]",
            "(2-10c)",
        )
    )
    story.append(P("代回 (2-10a) 即得："))
    story.extend(
        eq_latex(
            r"a^4\left(\Pi_2[\mathbf z_2]-2\Pi_2[\mathbf z_2]\right)=-a^4\Pi_2[\mathbf z_2]",
            "(2-10d)",
        )
    )
    story.append(
        P(
            "式 (2-10) 的負號可由平方完成直接看出。若 "
            "<font name='ArialU'>Q(z)=Π<sub>2</sub>[z]+L(z)</font>，且駐值解為 "
            "<font name='ArialU'>z<sub>*</sub></font>，則 "
            "<font name='ArialU'>L(z<sub>*</sub>)=-2Π<sub>2</sub>[z<sub>*</sub>]</font>，"
            "故 <font name='ArialU'>Q(z<sub>*</sub>)=-Π<sub>2</sub>[z<sub>*</sub>]</font>。"
        )
    )

    story.append(P("2.3 非對稱分岔：A₃ 不為零", H2))
    story.append(P("若 <font name='ArialU'>A<sub>3</sub>≠0</font>，四次項在最靠近臨界點時為高階，可先略去："))
    story.extend(eq("F=(1-λ)a<super>2</super>+A<sub>3</sub>a<super>3</super>", "(2-11)"))
    story.append(P("平衡條件逐步為："))
    story.extend(eq("∂F/∂a=2(1-λ)a+3A<sub>3</sub>a<super>2</super>=0", "(2-12)"))
    story.extend(eq("a[2(1-λ)+3A<sub>3</sub>a]=0", "(2-13)"))
    story.extend(eq("a=0　或　a= -2(1-λ)/(3A<sub>3</sub>)", "(2-14)"))
    story.append(P("二階導數為："))
    story.extend(eq("∂<super>2</super>F/∂a<super>2</super>=2(1-λ)+6A<sub>3</sub>a", "(2-15)"))
    story.append(
        P(
            "基本路徑 <font name='ArialU'>a=0</font> 在 <font name='ArialU'>λ&lt;1</font> 穩定、"
            "<font name='ArialU'>λ&gt;1</font> 不穩定。將分支解 (2-14) 代入 (2-15)："
        )
    )
    story.extend(
        eq(
            "2(1-λ)+6A<sub>3</sub>[-2(1-λ)/(3A<sub>3</sub>)]=-2(1-λ)",
            "(2-16)",
        )
    )
    story.append(P("故分支在 <font name='ArialU'>λ&gt;1</font> 才局部穩定；在臨界載重以下出現的下降分支不穩定。"))

    story.append(P("2.4 對稱分岔：A₃=0，四階項決定性質", H2))
    story.extend(eq("F=(1-λ)a<super>2</super>+A<sub>4</sub>a<super>4</super>", "(2-17)"))
    story.extend(eq("∂F/∂a=2(1-λ)a+4A<sub>4</sub>a<super>3</super>=0", "(2-18)"))
    story.extend(eq("a=0　或　a<super>2</super>=-(1-λ)/(2A<sub>4</sub>)", "(2-19)"))
    story.append(
        P(
            "因 <font name='ArialU'>a<super>2</super>≥0</font>，若 "
            "<font name='ArialU'>A<sub>4</sub>&gt;0</font>，非零分支只存在於 "
            "<font name='ArialU'>λ&gt;1</font>，稱為超臨界或穩定上升型。若 "
            "<font name='ArialU'>A<sub>4</sub>&lt;0</font>，非零分支存在於 "
            "<font name='ArialU'>λ&lt;1</font>，稱為次臨界或下降型。"
        )
    )
    story.append(P("把 (2-19) 代入二階導數："))
    story.extend(eq("F<sub>,aa</sub>=2(1-λ)+12A<sub>4</sub>a<super>2</super>", "(2-20)"))
    story.extend(eq("F<sub>,aa</sub>=2(1-λ)-6(1-λ)=-4(1-λ)", "(2-21)"))
    story.append(
        P(
            "因此超臨界分支 <font name='ArialU'>λ&gt;1</font> 有 "
            "<font name='ArialU'>F<sub>,aa</sub>&gt;0</font>，而次臨界分支 "
            "<font name='ArialU'>λ&lt;1</font> 有 <font name='ArialU'>F<sub>,aa</sub>&lt;0</font>。"
            "薄圓柱殼與球殼最危險的後屈曲分支通常具有強烈下降性，這正是缺陷敏感的能量根源。"
        )
    )
    story.extend(source("[B07 | §2.4 | PDF p.37-50] 位移分解、二階修正、三次/四次約化能量與分支穩定性。"))

    # 3. Imperfections
    story.append(PageBreak())
    story.append(P("3. 初始缺陷如何把分岔變成極限點", H1))
    story.append(P("3.1 缺陷線性項的來源", H2))
    story.append(
        P(
            "理想結構的基本路徑是精確平衡，所以勢能展開沒有一階項。初始幾何缺陷使理想基本狀態不再是"
            "實際結構的精確平衡；對小缺陷，只需在約化能量加入同時對缺陷幅度與模態振幅皆線性的項："
        )
    )
    story.extend(
        eq(
            "F<super>*</super>(a,λ,μ)=(1-λ)a<super>2</super>+A<sub>3</sub>a<super>3</super>+A<sub>4</sub>a<super>4</super>+μBa",
            "(3-1)",
        )
    )
    story.append(
        P(
            "係數 <font name='ArialU'>B</font> 是缺陷形狀對臨界模態的投影。"
            "若缺陷與最陡下降方向一致，<font name='ArialU'>|B|</font> 最大，通常最危險。"
            "線性項的二階導數為零，因此它不直接改變切線穩定式；它透過改變平衡振幅，"
            "使系統在 <font name='ArialU'>λ&lt;1</font> 先遇到極限點。"
        )
    )

    story.append(P("3.2 非對稱型：臨界載重折減與 |μ|¹ᐟ² 成正比", H2))
    story.append(P("令 <font name='ArialU'>B=1</font> 且先略去四次項："))
    story.extend(eq("F<super>*</super>=(1-λ)a<super>2</super>+A<sub>3</sub>a<super>3</super>+μa", "(3-2)"))
    story.extend(eq("平衡：　2(1-λ)a+3A<sub>3</sub>a<super>2</super>+μ=0", "(3-3)"))
    story.extend(eq("極限點：　2(1-λ)+6A<sub>3</sub>a=0", "(3-4)"))
    story.append(P("由 (3-4) 得 <font name='ArialU'>1-λ=-3A<sub>3</sub>a</font>，代入 (3-3)："))
    story.extend(eq("-6A<sub>3</sub>a<super>2</super>+3A<sub>3</sub>a<super>2</super>+μ=0", "(3-5)"))
    story.extend(eq("3A<sub>3</sub>a<super>2</super>=μ", "(3-6)"))
    story.extend(eq("(1-λ<super>*</super>)<super>2</super>=3μA<sub>3</sub>", "(3-7)"))
    story.append(
        P(
            "危險符號使右側為正，因此 "
            "<font name='ArialU'>1-λ<super>*</super>∝|μ|<super>1/2</super></font>。"
            "缺陷縮小 100 倍，載重折減只縮小 10 倍。"
        )
    )

    story.append(P("3.3 對稱次臨界型：Koiter 2/3 次方律", H2))
    story.append(P("令 <font name='ArialU'>A<sub>3</sub>=0</font>、<font name='ArialU'>A<sub>4</sub>&lt;0</font>："))
    story.extend(eq("F<super>*</super>=(1-λ)a<super>2</super>+A<sub>4</sub>a<super>4</super>+μa", "(3-8)"))
    story.extend(eq("平衡：　2(1-λ)a+4A<sub>4</sub>a<super>3</super>+μ=0", "(3-9)"))
    story.extend(eq("極限點：　2(1-λ)+12A<sub>4</sub>a<super>2</super>=0", "(3-10)"))
    story.extend(eq("1-λ=-6A<sub>4</sub>a<super>2</super>", "(3-11)"))
    story.append(P("把 (3-11) 逐項代回 (3-9)："))
    story.extend(eq("2[-6A<sub>4</sub>a<super>2</super>]a+4A<sub>4</sub>a<super>3</super>+μ=0", "(3-12)"))
    story.extend(eq("-8A<sub>4</sub>a<super>3</super>+μ=0", "(3-13)"))
    story.extend(eq("|a<super>*</super>|=[|μ|/(8|A<sub>4</sub>|)]<super>1/3</super>", "(3-14)"))
    story.append(P("再代回 (3-11)："))
    story.extend(
        eq(
            "1-λ<super>*</super>=6|A<sub>4</sub>|[|μ|/(8|A<sub>4</sub>|)]<super>2/3</super>",
            "(3-15)",
        )
    )
    story.extend(
        eq(
            "1-λ<super>*</super>=(3/2)|A<sub>4</sub>|<super>1/3</super>|μ|<super>2/3</super>",
            "(3-16)",
        )
    )
    story.append(
        P(
            "式 (3-16) 是 Koiter 缺陷敏感性的核心尺度律。因指數 "
            "<font name='ArialU'>2/3&lt;1</font>，微小缺陷造成的載重折減相對很大；"
            "當缺陷再縮小 1000 倍，折減只縮小 100 倍。"
        )
    )
    story.extend(source("[B07 | §2.5 | PDF p.51-56] 缺陷線性項、最危險方向與式 (1-λ*)³ᐟ²∝|μ|；[B07 | §3.15, §3.18 | PDF p.179-191, 231-236] 球殼與圓柱殼之具體缺陷折減。"))

    story.append(P("3.4 局部凹陷與週期缺陷", H2))
    story.append(
        P(
            "對軸壓圓柱殼，Koiter 以快速衰減的高斯包絡描述局部凹陷："
        )
    )
    story.extend(
        eq(
            "w<sub>0</sub>=κh[cos(p<sub>0</sub>x/R)+4cos(mx/R)cos(my/R)]exp[-μ<sub>g</sub><super>2</super>(x<super>2</super>+y<super>2</super>)/(2R<super>2</super>)]",
            "(3-17)",
        )
    )
    story.append(
        P(
            "以同形 Rayleigh-Ritz 位移代入能量並只保留主導短波項，可化成："
        )
    )
    story.extend(
        eq(
            "F<super>**</super>=C[(1-λ)b<sub>0</sub><super>2</super>+(2c/3)b<sub>0</sub><super>3</super>-2λκb<sub>0</sub>]",
            "(3-18)",
        )
    )
    story.extend(eq("平衡：　2(1-λ)b<sub>0</sub>+2cb<sub>0</sub><super>2</super>-2λκ=0", "(3-19)"))
    story.append(P("二次方程根消失時為極限點，判別式等於零："))
    story.extend(eq("(1-λ<super>*</super>)<super>2</super>=-4λ<super>*</super>cκ，　κ&lt;0", "(3-20)"))
    story.append(
        P(
            "負 <font name='ArialU'>κ</font> 代表向內凹陷，會明顯降低臨界載重；"
            "向外凸起在此一階模型中反而穩定。式 (3-20) 亦提醒研究者：缺陷的符號、位置與空間尺度，"
            "不能只用單一最大振幅取代。"
        )
    )

    # 4. Shell equations
    story.append(PageBreak())
    story.append(P("4. 淺殼幾何非線性方程的逐步建立", H1))
    story.append(P("4.1 由度量變化得到中面應變", H2))
    story.append(
        P(
            "取殼面局部主曲率座標 <font name='ArialU'>x,y</font>，主曲率半徑為 "
            "<font name='ArialU'>R<sub>1</sub>,R<sub>2</sub></font>，中面位移為 "
            "<font name='ArialU'>(u,v,w)</font>。在切平面上的初始面可寫成 "
            "<font name='ArialU'>z=Z(x,y)</font>，於切點有 "
            "<font name='ArialU'>Z<sub>,x</sub>=Z<sub>,y</sub>=0</font>、"
            "<font name='ArialU'>Z<sub>,xx</sub>=1/R<sub>1</sub></font>、"
            "<font name='ArialU'>Z<sub>,yy</sub>=1/R<sub>2</sub></font>。"
            "本文選擇法向正號，使正 <font name='ArialU'>w</font> 造成正的曲率膜伸長 "
            "<font name='ArialU'>+w/R<sub>i</sub></font>；若翻轉殼面法向，"
            "<font name='ArialU'>w</font> 與所有線性曲率項會同時變號，但臨界載重不變。"
        )
    )
    story.append(
        P(
            "變形後位置向量在一階曲率近似下為 "
            "<font name='ArialU'>(x+u+Z<sub>,x</sub>w, y+v+Z<sub>,y</sub>w, Z+w)</font>。"
            "以 <font name='ArialU'>d s̄<super>2</super>-ds<super>2</super>=2ε<sub>αβ</sub>dx<super>α</super>dx<super>β</super></font> "
            "比較變形前後線元素平方，保留 <font name='ArialU'>u<sub>,x</sub>,v<sub>,y</sub></font> 的一階項與 "
            "<font name='ArialU'>w</font> 斜率平方項，得到："
        )
    )
    story.extend(eq("ε<sub>x</sub>=u<sub>,x</sub>+w/R<sub>1</sub>+(1/2)w<sub>,x</sub><super>2</super>", "(4-1a)"))
    story.extend(eq("ε<sub>y</sub>=v<sub>,y</sub>+w/R<sub>2</sub>+(1/2)w<sub>,y</sub><super>2</super>", "(4-1b)"))
    story.extend(eq("γ<sub>xy</sub>=u<sub>,y</sub>+v<sub>,x</sub>+w<sub>,x</sub>w<sub>,y</sub>", "(4-1c)"))
    story.append(
        make_table(
            ["應變中的項", "幾何來源", "物理效果", "保留理由"],
            [
                ["u<sub>,x</sub>、v<sub>,y</sub>", "切向位移梯度", "直接拉長或縮短中面線段", "小應變的一階主項"],
                ["w/R<sub>i</sub>", "有曲率的中面沿法向平移", "即使沒有斜率，也改變圓弧周長", "殼與平板的關鍵差異"],
                ["(w<sub>,i</sub>)<super>2</super>/2", "線段斜率的畢氏長度", "大轉角可產生有限膜伸長", "中等轉角的主導二次項"],
                ["w<sub>,x</sub>w<sub>,y</sub>", "兩方向斜率耦合", "產生工程剪應變", "與正應變平方項同為二階"],
            ],
            widths=[39 * mm, 55 * mm, 54 * mm, CONTENT_W - 148 * mm],
        )
    )
    story.append(
        P(
            "以一條原長 dx 的平板線段為例，法向位移造成高差 dw=w<sub>,x</sub>dx，"
            "新長度為 <font name='ArialU'>√(dx<super>2</super>+dw<super>2</super>)="
            "dx√(1+w<sub>,x</sub><super>2</super>)</font>。用 "
            "<font name='ArialU'>√(1+s)≈1+s/2</font>，便得到"
            " <font name='ArialU'>(1/2)w<sub>,x</sub><super>2</super></font>；"
            "它不是材料非線性，而是純粹的幾何非線性。"
        )
    )
    story.append(
        P(
            "曲率變化在淺殼近似下為 "
            "<font name='ArialU'>κ<sub>x</sub>=-w<sub>,xx</sub></font>、"
            "<font name='ArialU'>κ<sub>y</sub>=-w<sub>,yy</sub></font>、"
            "<font name='ArialU'>κ<sub>xy</sub>=-2w<sub>,xy</sub></font>。"
            "與平板相比，決定性的新增線性項是 <font name='ArialU'>+w/R<sub>i</sub></font>；"
            "法向位移必然產生膜應變，形成曲率剛化。"
        )
    )

    story.append(P("4.2 膜力本構、Airy 應力函數與面內平衡", H2))
    story.append(
        P(
            "等向性平面應力本構積分過厚度後為："
        )
    )
    story.extend(
        eq(
            "{N<sub>x</sub>,N<sub>y</sub>,N<sub>xy</sub>}<super>T</super>=[Eh/(1-ν<super>2</super>)] [[1,ν,0],[ν,1,0],[0,0,(1-ν)/2]] {ε<sub>x</sub>,ε<sub>y</sub>,γ<sub>xy</sub>}<super>T</super>",
            "(4-2)",
        )
    )
    story.append(P("無面內體力時，面內平衡為："))
    story.extend(eq("N<sub>x,x</sub>+N<sub>xy,y</sub>=0", "(4-3a)"))
    story.extend(eq("N<sub>xy,x</sub>+N<sub>y,y</sub>=0", "(4-3b)"))
    story.append(P("定義 Airy 應力函數 <font name='ArialU'>Φ</font>："))
    story.extend(eq("N<sub>x</sub>=Φ<sub>,yy</sub>，N<sub>y</sub>=Φ<sub>,xx</sub>，N<sub>xy</sub>=-Φ<sub>,xy</sub>", "(4-4)"))
    story.append(
        P(
            "代入 (4-3a)：<font name='ArialU'>Φ<sub>,xyy</sub>-Φ<sub>,xyy</sub>=0</font>；"
            "代入 (4-3b)：<font name='ArialU'>-Φ<sub>,xxy</sub>+Φ<sub>,xxy</sub>=0</font>。"
            "因此 (4-4) 自動滿足面內平衡。"
        )
    )

    story.append(P("4.3 相容方程的完整消去", H2))
    story.append(P("先把本構反解成應變："))
    story.extend(eq("ε<sub>x</sub>=(Φ<sub>,yy</sub>-νΦ<sub>,xx</sub>)/(Eh)", "(4-5a)"))
    story.extend(eq("ε<sub>y</sub>=(Φ<sub>,xx</sub>-νΦ<sub>,yy</sub>)/(Eh)", "(4-5b)"))
    story.extend(eq("γ<sub>xy</sub>=-2(1+ν)Φ<sub>,xy</sub>/(Eh)", "(4-5c)"))
    story.append(
        P(
            "對運動學式 (4-1) 作相容組合 "
            "<font name='ArialU'>ε<sub>x,yy</sub>+ε<sub>y,xx</sub>-γ<sub>xy,xy</sub></font>。"
            "所有 <font name='ArialU'>u,v</font> 的混合導數抵消。曲率線性項與斜率平方項留下："
        )
    )
    story.append(P("先單獨展開三個非線性微分，避免直接跳到最終 Hessian 行列式："))
    story.extend(
        eq_latex(
            r"\left(\frac12w_{,x}^2\right)_{,yy}=w_{,xy}^2+w_{,x}w_{,xyy}",
            "(4-6a)",
        )
    )
    story.extend(
        eq_latex(
            r"\left(\frac12w_{,y}^2\right)_{,xx}=w_{,xy}^2+w_{,y}w_{,xxy}",
            "(4-6b)",
        )
    )
    story.extend(
        eq_latex(
            r"(w_{,x}w_{,y})_{,xy}=w_{,xx}w_{,yy}+w_{,xy}^2+w_{,x}w_{,xyy}+w_{,y}w_{,xxy}",
            "(4-6c)",
        )
    )
    story.append(P("依照 ε<sub>x,yy</sub>+ε<sub>y,xx</sub>-γ<sub>xy,xy</sub> 組合，逐項相消："))
    story.extend(
        eq_latex(
            [
                r"(w_{,xy}^2+w_{,x}w_{,xyy})+(w_{,xy}^2+w_{,y}w_{,xxy})",
                r"-\left(w_{,xx}w_{,yy}+w_{,xy}^2+w_{,x}w_{,xyy}+w_{,y}w_{,xxy}\right)",
                r"=w_{,xy}^2-w_{,xx}w_{,yy}",
            ],
            "(4-6d)",
        )
    )
    story.append(
        P(
            "最後一項是位移曲面 Hessian 的負行列式："
            "<font name='ArialU'>w<sub>,xy</sub><super>2</super>-w<sub>,xx</sub>w<sub>,yy</sub>"
            "=-det(Hess w)</font>。它量測兩主方向曲率的非線性不相容程度。"
        )
    )
    story.extend(
        eq(
            "ε<sub>x,yy</sub>+ε<sub>y,xx</sub>-γ<sub>xy,xy</sub>=w<sub>,yy</sub>/R<sub>1</sub>+w<sub>,xx</sub>/R<sub>2</sub>+w<sub>,xy</sub><super>2</super>-w<sub>,xx</sub>w<sub>,yy</sub>",
            "(4-6)",
        )
    )
    story.append(P("再將 (4-5) 代入左側，逐項合併混合導數係數："))
    story.extend(
        eq(
            "[Φ<sub>,yyyy</sub>+Φ<sub>,xxxx</sub>+(-ν-ν+2+2ν)Φ<sub>,xxyy</sub>]/(Eh)",
            "(4-7)",
        )
    )
    story.extend(eq("-ν-ν+2+2ν=2", "(4-8)"))
    story.extend(
        eq(
            "∇<super>4</super>Φ=Eh(w<sub>,yy</sub>/R<sub>1</sub>+w<sub>,xx</sub>/R<sub>2</sub>)+Eh(w<sub>,xy</sub><super>2</super>-w<sub>,xx</sub>w<sub>,yy</sub>)",
            "(4-9)",
        )
    )
    story.append(
        P(
            "平板極限 <font name='ArialU'>R<sub>1</sub>,R<sub>2</sub>→∞</font> 使線性曲率項消失，"
            "即得 von Kármán-Föppl 相容式。若只做線性屈曲，亦可刪除右側的二次 <font name='ArialU'>w</font> 項。"
        )
    )

    story.append(P("4.4 法向平衡方程", H2))
    story.append(
        P(
            "先寫彎曲能，其中 <font name='ArialU'>D=Eh<super>3</super>/[12(1-ν<super>2</super>)]</font>："
        )
    )
    story.extend(
        eq(
            "U<sub>b</sub>=(D/2)∫<sub>S</sub>[w<sub>,xx</sub><super>2</super>+w<sub>,yy</sub><super>2</super>+2νw<sub>,xx</sub>w<sub>,yy</sub>+2(1-ν)w<sub>,xy</sub><super>2</super>]dA",
            "(4-10a)",
        )
    )
    story.append(P("對 <font name='ArialU'>w</font> 變分並在面積內積分分部兩次，內域項為："))
    story.extend(eq("δU<sub>b</sub>=∫<sub>S</sub>D∇<super>4</super>w δw dA+邊界項", "(4-10b)"))
    story.append(P("膜能的一階變分以膜力表示："))
    story.extend(
        eq(
            "δU<sub>m</sub>=∫<sub>S</sub>[N<sub>x</sub>δε<sub>x</sub>+N<sub>y</sub>δε<sub>y</sub>+N<sub>xy</sub>δγ<sub>xy</sub>]dA",
            "(4-10c)",
        )
    )
    story.append(P("只取與 <font name='ArialU'>δw</font> 有關的部分："))
    story.extend(
        eq(
            "δε<sub>x</sub>=δw/R<sub>1</sub>+w<sub>,x</sub>δw<sub>,x</sub>，δε<sub>y</sub>=δw/R<sub>2</sub>+w<sub>,y</sub>δw<sub>,y</sub>",
            "(4-10d)",
        )
    )
    story.extend(
        eq(
            "δγ<sub>xy</sub>=w<sub>,y</sub>δw<sub>,x</sub>+w<sub>,x</sub>δw<sub>,y</sub>",
            "(4-10e)",
        )
    )
    story.append(
        P(
            "將含 <font name='ArialU'>δw<sub>,x</sub>,δw<sub>,y</sub></font> 的項積分分部一次，"
            "再用面內平衡 (4-3) 消去膜力梯度，得到內域係數："
        )
    )
    story.extend(
        eq(
            "δU<sub>m</sub>=∫<sub>S</sub>[N<sub>x</sub>/R<sub>1</sub>+N<sub>y</sub>/R<sub>2</sub>-N<sub>x</sub>w<sub>,xx</sub>-2N<sub>xy</sub>w<sub>,xy</sub>-N<sub>y</sub>w<sub>,yy</sub>]δw dA+邊界項",
            "(4-10f)",
        )
    )
    story.append(
        P(
            "令外壓虛功為 <font name='ArialU'>∫<sub>S</sub>pδw dA</font>，"
            "代入 Airy 定義 (4-4)，一般淺殼法向平衡為："
        )
    )
    story.extend(
        eq(
            "D∇<super>4</super>w+(1/R<sub>1</sub>)Φ<sub>,yy</sub>+(1/R<sub>2</sub>)Φ<sub>,xx</sub>-Φ<sub>,yy</sub>w<sub>,xx</sub>-Φ<sub>,xx</sub>w<sub>,yy</sub>+2Φ<sub>,xy</sub>w<sub>,xy</sub>=p",
            "(4-11)",
        )
    )
    story.append(
        P(
            "式 (4-9) 與 (4-11) 是以 <font name='ArialU'>w,Φ</font> 為未知量的非線性淺殼方程。"
            "做線性分岔時，將 <font name='ArialU'>Φ=Φ<sub>0</sub>+φ</font>，"
            "只保留擾動 <font name='ArialU'>(w,φ)</font> 的一次項；做後屈曲時，"
            "必須保留括號型非線性。"
        )
    )
    story.extend(source("[B07 | §3.14-3.15 | PDF p.176-191] von Kármán-Föppl 與淺殼運動學、能量及變分方程。"))

    # 5. Classical shells
    story.append(PageBreak())
    story.append(P("5. 經典殼體臨界載重：從方程到最小化", H1))
    story.append(CylinderSchematic())
    story.append(P("圖 5-1　軸壓圓柱殼；展開座標 y=Rθ，軸向長度 L。", CAPTION))
    story.append(P("5.1 軸壓圓柱殼的線性方程", H2))
    story.append(
        P(
            "圓柱殼有 <font name='ArialU'>R<sub>1</sub>=∞</font>、"
            "<font name='ArialU'>R<sub>2</sub>=R</font>。令屈曲前軸向壓縮膜力大小為 "
            "<font name='ArialU'>N&gt;0</font>，即張力正號下 "
            "<font name='ArialU'>N<sub>x</sub><super>0</super>=-N</font>。"
            "線性化 (4-9)、(4-10) 得："
        )
    )
    story.extend(eq("∇<super>4</super>Φ=(Eh/R)w<sub>,xx</sub>", "(5-1)"))
    story.extend(eq("D∇<super>4</super>w+(1/R)Φ<sub>,xx</sub>+Nw<sub>,xx</sub>=0", "(5-2)"))
    story.append(
        P(
            "取滿足軸向簡支與圓周週期性的模態："
        )
    )
    story.extend(eq("w=W sin(αx)cos(βy)，Φ=F sin(αx)cos(βy)", "(5-3)"))
    story.extend(eq("α=mπ/L，β=n/R，q<super>2</super>=α<super>2</super>+β<super>2</super>", "(5-4)"))
    story.append(P("因 <font name='ArialU'>∇<super>4</super>→q<super>4</super></font>、<font name='ArialU'>∂<super>2</super>/∂x<super>2</super>→-α<super>2</super></font>，由 (5-1)："))
    story.extend(eq("q<super>4</super>F=-(Eh/R)α<super>2</super>W", "(5-5)"))
    story.extend(eq("F=-Ehα<super>2</super>W/(Rq<super>4</super>)", "(5-6)"))
    story.append(P("將 (5-6) 代入 (5-2)："))
    story.extend(
        eq(
            "Dq<super>4</super>W+(1/R)(-α<super>2</super>)F+N(-α<super>2</super>)W=0",
            "(5-7)",
        )
    )
    story.extend(
        eq(
            "Dq<super>4</super>+[Ehα<super>4</super>/(R<super>2</super>q<super>4</super>)]-Nα<super>2</super>=0",
            "(5-8)",
        )
    )
    story.extend(
        eq(
            "N(α,β)=Dq<super>4</super>/α<super>2</super>+Ehα<super>2</super>/(R<super>2</super>q<super>4</super>)",
            "(5-9)",
        )
    )

    story.append(P("5.2 對連續波數不跳步最小化", H2))
    story.append(
        P(
            "式 (5-9) 由兩個競爭機制組成。第一項是彎曲成本：波形越短，q 越大，"
            "曲率與彎曲能迅速增加。第二項是圓柱曲率造成的膜約束：若波形選得過長，"
            "法向位移難以用面內位移釋放，膜能反而升高。臨界模態就是兩種成本的最佳折衷。"
        )
    )
    story.append(
        make_table(
            ["項", "來源", "X 增大時", "單位"],
            [
                ["DX", "曲率變化造成的彎曲能", "線性增加", "(N·mm)(mm<super>-2</super>)=N/mm"],
                ["Eh/(R<super>2</super>X)", "殼曲率耦合造成的膜能", "反比下降", "N/mm"],
            ],
            widths=[43 * mm, 68 * mm, 34 * mm, CONTENT_W - 145 * mm],
        )
    )
    story.append(P("定義 <font name='ArialU'>X=q<super>4</super>/α<super>2</super>&gt;0</font>，則："))
    story.extend(eq("N(X)=DX+Eh/(R<super>2</super>X)", "(5-10)"))
    story.extend(eq("dN/dX=D-Eh/(R<super>2</super>X<super>2</super>)", "(5-11)"))
    story.extend(eq("dN/dX=0　⇒　X<super>2</super>=Eh/(DR<super>2</super>)", "(5-12)"))
    story.extend(eq("X<sub>*</sub>=√(Eh/D)/R", "(5-13)"))
    story.append(P("又 <font name='ArialU'>d<super>2</super>N/dX<super>2</super>=2Eh/(R<super>2</super>X<super>3</super>)&gt;0</font>，故為最小值。"))
    story.append(P("由駐值條件 (5-12)，在最佳波數處兩個能量成本恰好相等："))
    story.extend(
        eq_latex(
            r"D=\frac{Eh}{R^2(X^{*})^2}\quad\Longrightarrow\quad DX^{*}=\frac{Eh}{R^2X^{*}}",
            "(5-13a)",
        )
    )
    story.append(
        P(
            "所以不需要再做繁複代數：最小值必定是任一成本的兩倍。"
            "這也提供數值檢查；若最佳離散模態的彎曲能與曲率膜能相差很大，"
            "通常表示有限長度、邊界條件或網格已把理想連續最小值移開。"
        )
    )
    story.extend(eq("N<sub>cr</sub>=DX<sub>*</sub>+Eh/(R<super>2</super>X<sub>*</sub>)", "(5-14)"))
    story.extend(eq("N<sub>cr</sub>=√(DEh)/R+√(DEh)/R=2√(DEh)/R", "(5-15)"))
    story.extend(
        eq(
            "N<sub>cr</sub>=Eh<super>2</super>/[R√(3(1-ν<super>2</super>))]",
            "(5-16)",
        )
    )
    story.extend(
        eq(
            "σ<sub>cr</sub>=N<sub>cr</sub>/h=E(h/R)/√[3(1-ν<super>2</super>)]",
            "(5-17)",
        )
    )
    story.append(
        P(
            "最佳波數族滿足 "
            "<font name='ArialU'>(α<super>2</super>+β<super>2</super>)/α=[12(1-ν<super>2</super>)]<super>1/4</super>/√(Rh)</font>。"
            "因此特徵波長尺度為 <font name='ArialU'>O(√Rh)</font>。"
            "有限元素網格若不能在一個半波內配置足夠單元，會人為提高臨界值。"
        )
    )
    story.append(P("波長尺度 <font name='ArialU'>√(Rh)</font> 可直接由量綱與剛度比例看出："))
    story.extend(
        eq_latex(
            r"X^{*}=\frac{1}{R}\sqrt{\frac{Eh}{D}}=\frac{\sqrt{12(1-\nu^2)}}{Rh}",
            "(5-17a)",
        )
    )
    story.append(
        P(
            "因 <font name='ArialU'>X=q<super>4</super>/α<super>2</super></font>，"
            "最危險波數族通常有 <font name='ArialU'>q</font> 與 <font name='ArialU'>α</font> 同階，"
            "故 <font name='ArialU'>X=O(q<super>2</super>)</font>。由 "
            "<font name='ArialU'>q<super>2</super>=O(1/(Rh))</font> 得"
            " <font name='ArialU'>q=O((Rh)<super>-1/2</super>)</font>，"
            "因此實體波長 <font name='ArialU'>2π/q=O(√(Rh))</font>。"
        )
    )

    story.append(P("5.3 均勻外壓完整球殼", H2))
    story.append(
        P(
            "球殼有 <font name='ArialU'>R<sub>1</sub>=R<sub>2</sub>=R</font>。"
            "取局部平面波 <font name='ArialU'>exp(i k·x)</font>，"
            "<font name='ArialU'>q=|k|</font>。線性方程為："
        )
    )
    story.extend(eq("D∇<super>4</super>w+(1/R)∇<super>2</super>Φ+N∇<super>2</super>w=0", "(5-18)"))
    story.extend(eq("∇<super>4</super>Φ=(Eh/R)∇<super>2</super>w", "(5-19)"))
    story.append(P("以 <font name='ArialU'>∇<super>2</super>→-q<super>2</super></font> 代入 (5-19)："))
    story.extend(eq("q<super>4</super>F=-(Eh/R)q<super>2</super>W", "(5-20)"))
    story.extend(eq("F=-EhW/(Rq<super>2</super>)", "(5-21)"))
    story.append(P("代入 (5-18)："))
    story.extend(eq("Dq<super>4</super>+Eh/R<super>2</super>-Nq<super>2</super>=0", "(5-22)"))
    story.extend(eq("N(q)=Dq<super>2</super>+Eh/(R<super>2</super>q<super>2</super>)", "(5-23)"))
    story.append(P("令 <font name='ArialU'>Y=q<super>2</super></font>，則 <font name='ArialU'>N(Y)=DY+Eh/(R<super>2</super>Y)</font>，最小化與 (5-10)-(5-15) 相同："))
    story.extend(eq("N<sub>cr</sub>=2√(DEh)/R", "(5-24)"))
    story.append(P("球殼膜平衡給 <font name='ArialU'>N=pR/2</font>，所以："))
    story.extend(eq("p<sub>cr</sub>=2N<sub>cr</sub>/R", "(5-25)"))
    story.extend(
        eq(
            "p<sub>cr</sub>=2E(h/R)<super>2</super>/√[3(1-ν<super>2</super>)]",
            "(5-26)",
        )
    )
    story.extend(
        source(
            "[B06 | §11.1-11.4 | PDF p.347-361] 軸壓圓柱殼理論與試驗；"
            "[B06 | §11.13 | PDF p.397-406] 均勻外壓球殼；"
            "[B07 | §3.16-3.17 | PDF p.192-230] 球殼與圓柱殼的臨界、後屈曲與缺陷敏感性。"
        )
    )

    story.append(P("5.4 厚度漸近與研究尺度", H2))
    story.append(
        P(
            "對基本薄殼模型，厚度積分後的線彈性能量可寫成："
        )
    )
    story.extend(
        eq(
            "U<sub>h</sub>=(1/2)∫<sub>S</sub>[h ε<sub>m</sub><super>T</super>C ε<sub>m</sub>+(h<super>3</super>/12)κ<super>T</super>Cκ]dA",
            "(5-27)",
        )
    )
    story.append(
        P(
            "膜能為 <font name='ArialU'>O(h)</font>，彎曲能為 <font name='ArialU'>O(h<super>3</super>)</font>。"
            "若邊界與幾何容許近似純彎曲位移，極薄殼會由低成本彎曲機制主導；若純彎曲被抑制，"
            "膜能控制。數值鎖定的本質，是離散空間錯誤地無法表示連續純彎曲子空間，"
            "因而製造出不應存在的 <font name='ArialU'>O(h)</font> 能量。"
        )
    )
    story.extend(
        source(
            "[B03 | Ch.5, §5.1-5.4 | PDF p.127-181] 殼模型厚度漸近、純彎曲子空間、載重與膜/彎曲主導機制。"
        )
    )

    # 6. FE and arc length
    story.append(PageBreak())
    story.append(P("6. 有限元素失穩方程、弧長法與分支切換", H1))
    story.append(P("6.1 一致線性化與切線剛度", H2))
    story.append(P("非線性有限元素殘量為："))
    story.extend(eq("r(q,λ)=f<sub>int</sub>(q)-λf<sub>ref</sub>=0", "(6-1)"))
    story.append(P("在第 <font name='ArialU'>j</font> 次迭代，以 <font name='ArialU'>(q<sub>j</sub>,λ<sub>j</sub>)</font> 為展開點："))
    story.extend(
        eq(
            "r(q<sub>j</sub>+δq,λ<sub>j</sub>+δλ)≈r<sub>j</sub>+K<sub>T,j</sub>δq-f<sub>ref</sub>δλ",
            "(6-2)",
        )
    )
    story.extend(eq("K<sub>T</sub>=∂f<sub>int</sub>/∂q=K<sub>mat</sub>+K<sub>geo</sub>+K<sub>other</sub>", "(6-3)"))
    story.append(
        P(
            "<font name='ArialU'>K<sub>mat</sub></font> 來自材料應力對應變增量；"
            "<font name='ArialU'>K<sub>geo</sub></font> 來自既有應力與位移梯度的二次變分；"
            "壓縮預應力通常使某些方向的幾何剛度為負。"
        )
    )
    story.append(P("以連續體形式看，平衡狀態附近的二次變分可分成："))
    story.extend(
        eq(
            "δ<super>2</super>Π=∫<sub>V</sub>[δε<sub>L</sub><super>T</super>C δε<sub>L</sub>+σ<sub>ij</sub>δu<sub>k,i</sub>δu<sub>k,j</sub>]dV",
            "(6-4)",
        )
    )
    story.append(
        P(
            "令有限元素插值 <font name='ArialU'>δu=Nδq</font>、線性應變 "
            "<font name='ArialU'>δε<sub>L</sub>=Bδq</font>、位移梯度 "
            "<font name='ArialU'>∇δu=Gδq</font>。代入 (6-4) 並把任意 "
            "<font name='ArialU'>δq</font> 提出："
        )
    )
    story.extend(
        eq(
            "δ<super>2</super>Π=δq<super>T</super>[∫<sub>V</sub>B<super>T</super>CB dV+∫<sub>V</sub>G<super>T</super>S(σ)G dV]δq",
            "(6-5)",
        )
    )
    story.extend(eq("K<sub>mat</sub>=∫B<super>T</super>CB dV，K<sub>geo</sub>=∫G<super>T</super>S(σ)G dV", "(6-6)"))
    story.append(
        P(
            "因此幾何剛度必須由<b>已平衡的屈曲前應力</b>積分，不能只由外載重數字直接猜測。"
            "若殼體使用局部座標，<font name='ArialU'>σ</font>、<font name='ArialU'>G</font> "
            "與厚度積分方向也必須位於同一座標系。"
        )
    )

    story.append(P("6.2 線性特徵屈曲的來源", H2))
    story.append(
        P(
            "若屈曲前基本路徑近似線性，參考載重造成的預應力與 <font name='ArialU'>λ</font> 成正比，"
            "因此臨界附近可寫："
        )
    )
    story.extend(eq("K<sub>T</sub>(λ)≈K<sub>M</sub>+λK<sub>σ</sub><super>ref</super>", "(6-7)"))
    story.append(P("中性平衡要求存在非零 <font name='ArialU'>φ</font> 使："))
    story.extend(eq("[K<sub>M</sub>+λK<sub>σ</sub><super>ref</super>]φ=0", "(6-8)"))
    story.append(
        P(
            "若定義壓縮削弱的正號矩陣 "
            "<font name='ArialU'>K<sub>G</sub>=-K<sub>σ</sub><super>ref</super></font>，則："
        )
    )
    story.extend(eq("K<sub>M</sub>φ=λK<sub>G</sub>φ", "(6-9)"))
    story.append(
        P(
            "若 <font name='ArialU'>K<sub>G</sub></font> 在所考慮方向為正，"
            "以 φ<super>T</super> 左乘 (6-9) 並除以分母，可得到廣義 Rayleigh 商："
        )
    )
    story.extend(
        eq_latex(
            r"\lambda(\boldsymbol\phi)=\frac{\boldsymbol\phi^{\mathrm T}\mathbf K_M\boldsymbol\phi}{\boldsymbol\phi^{\mathrm T}\mathbf K_G\boldsymbol\phi}",
            "(6-9a)",
        )
    )
    story.append(
        P(
            "分子是該變形形狀的材料/彈性剛度成本；分母是單位參考壓縮預應力能夠削弱的剛度。"
            "最小正特徵值是在所有可容許形狀中，使兩者比例最小者。"
            "若某方向的分母≤0，它不是此一壓縮載重下的候選屈曲方向，不能把商機械地取最小。"
        )
    )
    story.append(
        P(
            "式 (6-9) 的最小正特徵值只代表完美結構基本路徑上的第一次線性中性點。"
            "它不含缺陷誘發的屈曲前彎曲、後屈曲軟化、材料非線性與實際極限點。"
        )
    )
    story.extend(source("[B04 | §3.5 | PDF p.119-121] 由相鄰增量解相減得到齊次線性屈曲特徵式。"))

    story.append(P("6.3 球形弧長約束的完整 Newton 修正", H2))
    story.append(
        P(
            "載重控制在極限點失效，因 <font name='ArialU'>dλ=0</font> 後載重必須下降。"
            "弧長法把 <font name='ArialU'>λ</font> 也當未知量，並加入步長約束。"
            "令本步累積增量為 <font name='ArialU'>Δq=q-q<sub>n</sub></font>、"
            "<font name='ArialU'>Δλ=λ-λ<sub>n</sub></font>："
        )
    )
    story.extend(
        eq(
            "g(Δq,Δλ)=Δq<super>T</super>Δq+β<super>2</super>Δλ<super>2</super>f<sub>ref</sub><super>T</super>f<sub>ref</sub>-Δs<super>2</super>=0",
            "(6-10)",
        )
    )
    story.append(
        P(
            "第一項量測本步位移增量的平方；第二項把載重增量換算成等效位移尺度。"
            "因 <font name='ArialU'>f<sub>ref</sub></font> 的單位為 N，β 應具有 mm/N，"
            "使兩項都為 mm<super>2</super>。β 太小時接近載重控制，太大時接近位移控制；"
            "它是數值尺度參數，不是材料常數。"
        )
    )
    story.append(P("平衡修正方程由 (6-2) 令新殘量為零："))
    story.extend(eq("K<sub>T</sub>δq-f<sub>ref</sub>δλ=-r", "(6-11)"))
    story.append(P("平衡式與弧長式的 Newton 線性化可視為同一個增廣系統的兩個方程列："))
    story.extend(
        eq_latex(
            [
                r"\mathbf K_T\delta\mathbf q-\mathbf f_{\mathrm{ref}}\delta\lambda=-\mathbf r",
                r"2\Delta\mathbf q^{\mathrm T}\delta\mathbf q+2\beta^2\Delta\lambda\,\mathbf f_{\mathrm{ref}}^{\mathrm T}\mathbf f_{\mathrm{ref}}\,\delta\lambda=-g",
            ],
            "(6-11a)",
        )
    )
    story.append(
        P(
            "未知數由只有 δq 增加成 (δq,δλ)，同時也多了一條弧長方程，因此方程數仍與未知數相同。"
            "在普通極限點，單獨的 K<sub>T</sub> 沿路徑切向失去可逆性，但弧長列限制了"
            "增量必須落在增量球面的切平面上；只要該切平面不與零模態退化，增廣系統仍可解。"
        )
    )
    story.append(P("把位移修正分裂為："))
    story.extend(eq("δq=δq<sub>I</sub>+δλ δq<sub>II</sub>", "(6-12)"))
    story.extend(eq("K<sub>T</sub>δq<sub>I</sub>=-r", "(6-13a)"))
    story.extend(eq("K<sub>T</sub>δq<sub>II</sub>=f<sub>ref</sub>", "(6-13b)"))
    story.append(P("弧長約束的一階線性化為："))
    story.extend(
        eq(
            "g+2Δq<super>T</super>δq+2β<super>2</super>Δλδλ f<sub>ref</sub><super>T</super>f<sub>ref</sub>=0",
            "(6-14)",
        )
    )
    story.append(P("代入 (6-12) 並收集 <font name='ArialU'>δλ</font>："))
    story.extend(
        eq(
            "g+2Δq<super>T</super>δq<sub>I</sub>+2δλ[Δq<super>T</super>δq<sub>II</sub>+β<super>2</super>Δλ f<sub>ref</sub><super>T</super>f<sub>ref</sub>]=0",
            "(6-15)",
        )
    )
    story.extend(
        eq(
            "δλ= -[g/2+Δq<super>T</super>δq<sub>I</sub>]/[Δq<super>T</super>δq<sub>II</sub>+β<super>2</super>Δλ f<sub>ref</sub><super>T</super>f<sub>ref</sub>]",
            "(6-16)",
        )
    )
    story.append(
        P(
            "式 (6-16) 的分母是「沿載重方向修正時，弧長約束的一階變化率」。"
            "分母接近零表示當前校正方向幾乎與約束曲面相切，Newton 修正會變得很大；"
            "實作上應縮小 Δs、更新切線，或改用完整增廣方程直接分解，而不是接受巨大步長。"
        )
    )
    story.append(
        P(
            "求得 <font name='ArialU'>δλ</font> 後，用 (6-12) 得 <font name='ArialU'>δq</font>，"
            "更新狀態並重複直到殘量與弧長誤差同時收斂。預測步方向的正負號應與上一收斂步切向量"
            "內積為正，避免無故折返。"
        )
    )
    story.append(P("新步的切線預測先解 <font name='ArialU'>K<sub>T,n</sub>q<sub>t</sub>=f<sub>ref</sub></font>，再以弧長正規化："))
    story.extend(
        eq(
            "Δλ<sub>p</sub>=±Δs/√[q<sub>t</sub><super>T</super>q<sub>t</sub>+β<super>2</super>f<sub>ref</sub><super>T</super>f<sub>ref</sub>]",
            "(6-17)",
        )
    )
    story.extend(eq("Δq<sub>p</sub>=Δλ<sub>p</sub>q<sub>t</sub>", "(6-18)"))
    story.append(
        P(
            "選號可用上一收斂增量：要求 "
            "<font name='ArialU'>Δq<sub>p</sub><super>T</super>Δq<sub>n</sub>+β<super>2</super>Δλ<sub>p</sub>Δλ<sub>n</sub>f<sub>ref</sub><super>T</super>f<sub>ref</sub>&gt;0</font>。"
        )
    )
    story.extend(source("[B04 | §4.2 | PDF p.134-141] 路徑追蹤、球形/法向弧長約束與增量線性化。"))

    story.append(P("6.4 分支切換", H2))
    story.append(
        P(
            "在分岔點附近，基本路徑增量為 <font name='ArialU'>Δq</font>，零特徵向量為 "
            "<font name='ArialU'>v<sub>1</sub></font>。另一可容許起始方向可寫成："
        )
    )
    story.extend(eq("Δq<super>*</super>=Δq+γv<sub>1</sub>", "(6-19)"))
    story.append(P("要求新方向與基本方向正交："))
    story.extend(eq("Δq<super>T</super>Δq<super>*</super>=0", "(6-20)"))
    story.extend(eq("Δq<super>T</super>Δq+γΔq<super>T</super>v<sub>1</sub>=0", "(6-21)"))
    story.extend(eq("γ= -Δq<super>T</super>Δq/(v<sub>1</sub><super>T</super>Δq)", "(6-22)"))
    story.extend(
        eq(
            "Δq<super>*</super>=Δq-[Δq<super>T</super>Δq/(v<sub>1</sub><super>T</super>Δq)]v<sub>1</sub>",
            "(6-23)",
        )
    )
    story.append(
        P(
            "式 (6-23) 只提供非平凡分支的初始搜尋方向；有限步長下仍須 Newton 平衡迭代。"
            "若 <font name='ArialU'>v<sub>1</sub><super>T</super>Δq</font> 太小，"
            "應改用受控模態擾動與正交約束，而不能直接套公式。"
        )
    )
    story.extend(source("[B04 | §4.4.3 | PDF p.152] 以最低特徵向量擾動並用正交條件估計分支切換幅度。"))

    # 7 Examples
    story.append(PageBreak())
    story.append(P("7. 完整例題", H1))
    story.append(P("例題 1：一自由度勢能的穩定分類", H2))
    story.append(
        P(
            "考慮 <font name='ArialU'>Π(q;λ)=(1/2)(10-2λ)q<super>2</super>+(1/4)q<super>4</super></font>。"
            "求基本平衡、臨界載重與分支穩定性。"
        )
    )
    story.extend(eq("∂Π/∂q=(10-2λ)q+q<super>3</super>=0", "(E1-1)"))
    story.extend(eq("q[(10-2λ)+q<super>2</super>]=0", "(E1-2)"))
    story.extend(eq("q=0　或　q<super>2</super>=2λ-10", "(E1-3)"))
    story.append(P("非零實根要求 <font name='ArialU'>λ≥5</font>。基本路徑切線為："))
    story.extend(eq("K<sub>T</sub>=∂<super>2</super>Π/∂q<super>2</super>=10-2λ+3q<super>2</super>", "(E1-4)"))
    story.append(P("在 <font name='ArialU'>q=0</font>，<font name='ArialU'>K<sub>T</sub>=10-2λ</font>，故 <font name='ArialU'>λ<sub>c</sub>=5</font>。"))
    story.append(P("在非零分支代入 <font name='ArialU'>q<super>2</super>=2λ-10</font>："))
    story.extend(eq("K<sub>T</sub>=10-2λ+3(2λ-10)=4λ-20", "(E1-5)"))
    story.append(
        P(
            "所以 <font name='ArialU'>λ&gt;5</font> 時非零分支穩定。這是 "
            "<font name='ArialU'>A<sub>4</sub>&gt;0</font> 的對稱超臨界分岔。"
        )
    )

    story.append(P("例題 2：Koiter 2/3 次方缺陷折減", H2))
    story.append(
        P(
            "令約化勢能的 <font name='ArialU'>A<sub>4</sub>=-1</font>，缺陷幅度 "
            "<font name='ArialU'>|μ|=0.01</font>。由 (3-16)："
        )
    )
    story.extend(eq("1-λ<super>*</super>=(3/2)(1)<super>1/3</super>(0.01)<super>2/3</super>", "(E2-1)"))
    story.extend(eq("(0.01)<super>2/3</super>=10<super>-4/3</super>=0.0464159", "(E2-2)"))
    story.extend(eq("1-λ<super>*</super>=1.5×0.0464159=0.0696238", "(E2-3)"))
    story.extend(eq("λ<super>*</super>=0.930376", "(E2-4)"))
    story.append(P("極限點模態振幅由 (3-14)："))
    story.extend(eq("|a<super>*</super>|=(0.01/8)<super>1/3</super>=0.107722", "(E2-5)"))
    story.append(
        P(
            "雖然無因次缺陷只有 1%，理想臨界載重已折減約 6.96%。"
            "這個例子展示次臨界薄殼不能用「缺陷很小所以影響可忽略」的線性直覺判斷。"
        )
    )

    story.append(P("例題 3：淺兩桿拱的極限點", H2))
    story.append(
        P(
            "兩根相同桿件鉸接於頂點，水平半跨 <font name='ArialU'>a</font>、初始高度 "
            "<font name='ArialU'>h<sub>0</sub></font>、初始桿長 "
            "<font name='ArialU'>L<sub>0</sub>=√(a<super>2</super>+h<sub>0</sub><super>2</super>)</font>。"
            "頂點向下位移 <font name='ArialU'>w</font>，當前高度 "
            "<font name='ArialU'>y=h<sub>0</sub>-w</font>，當前桿長 "
            "<font name='ArialU'>l=√(a<super>2</super>+y<super>2</super>)</font>。"
        )
    )
    story.append(P("兩桿總軸向能量與外力勢能："))
    story.extend(eq("U=2×[EA(l-L<sub>0</sub>)<super>2</super>/(2L<sub>0</sub>)]=EA(l-L<sub>0</sub>)<super>2</super>/L<sub>0</sub>", "(E3-1)"))
    story.extend(eq("Π(w)=U-Pw", "(E3-2)"))
    story.append(P("由 <font name='ArialU'>dl/dw=-(h<sub>0</sub>-w)/l=-y/l</font>："))
    story.extend(eq("dU/dw=[2EA(l-L<sub>0</sub>)/L<sub>0</sub>](-y/l)", "(E3-3)"))
    story.append(P("平衡 <font name='ArialU'>dΠ/dw=0</font> 給："))
    story.extend(eq("P=2EA y(L<sub>0</sub>-l)/(L<sub>0</sub>l)", "(E3-4)"))
    story.append(P("定義 <font name='ArialU'>α=a/L<sub>0</sub></font>、<font name='ArialU'>s=y/L<sub>0</sub></font>、<font name='ArialU'>r=l/L<sub>0</sub>=√(α<super>2</super>+s<super>2</super>)</font>、<font name='ArialU'>p=P/(2EA)</font>："))
    story.extend(eq("p=s(1/r-1)", "(E3-5)"))
    story.append(P("極限點要求 <font name='ArialU'>dP/dw=0</font>。因 <font name='ArialU'>ds/dw=-1/L<sub>0</sub>≠0</font>，等價於 <font name='ArialU'>dp/ds=0</font>："))
    story.extend(eq("dp/ds=d(s/r)/ds-1", "(E3-6)"))
    story.extend(eq("d(s/r)/ds=1/r-s(r<sub>,s</sub>)/r<super>2</super>", "(E3-7)"))
    story.extend(eq("r<sub>,s</sub>=s/r", "(E3-8)"))
    story.extend(eq("d(s/r)/ds=1/r-s<super>2</super>/r<super>3</super>=(r<super>2</super>-s<super>2</super>)/r<super>3</super>=α<super>2</super>/r<super>3</super>", "(E3-9)"))
    story.extend(eq("dp/ds=α<super>2</super>/r<super>3</super>-1=0　⇒　r<super>*</super>=α<super>2/3</super>", "(E3-10)"))
    story.extend(eq("s<super>*2</super>=r<super>*2</super>-α<super>2</super>=α<super>4/3</super>-α<super>2</super>", "(E3-11)"))
    story.append(
        P(
            "取 <font name='ArialU'>a=1000 mm</font>、<font name='ArialU'>h<sub>0</sub>=200 mm</font>、"
            "<font name='ArialU'>E=210000 MPa</font>、<font name='ArialU'>A=100 mm<super>2</super></font>："
        )
    )
    l0 = math.sqrt(1000.0**2 + 200.0**2)
    alpha = 1000.0 / l0
    r_star = alpha ** (2.0 / 3.0)
    s_star = math.sqrt(r_star**2 - alpha**2)
    p_star = s_star * (1.0 / r_star - 1.0)
    p_force = 2.0 * 210000.0 * 100.0 * p_star
    w_star = 200.0 - s_star * l0
    story.extend(eq(f"L<sub>0</sub>={l0:.3f} mm，α={alpha:.6f}", "(E3-12)"))
    story.extend(eq(f"r<super>*</super>={r_star:.6f}，s<super>*</super>={s_star:.6f}", "(E3-13)"))
    story.extend(eq(f"w<super>*</super>=h<sub>0</sub>-s<super>*</super>L<sub>0</sub>={w_star:.3f} mm", "(E3-14)"))
    story.extend(eq(f"p<super>*</super>={p_star:.8f}，P<super>*</super>=2EA p<super>*</super>={p_force/1000:.3f} kN", "(E3-15)"))
    story.append(P("這是幾何非線性造成的極限點；載重控制會在此處失效，弧長法可繼續追蹤下降路徑。"))

    story.append(P("例題 4：軸壓鋁圓柱殼的理想臨界載重", H2))
    story.append(
        P(
            "取 <font name='ArialU'>E=70000 MPa</font>、<font name='ArialU'>ν=0.33</font>、"
            "<font name='ArialU'>R=500 mm</font>、<font name='ArialU'>h=1 mm</font>、"
            "<font name='ArialU'>L=1000 mm</font>。由 (5-17)："
        )
    )
    sigma_cr = 70000.0 * (1.0 / 500.0) / math.sqrt(3.0 * (1.0 - 0.33**2))
    n_cr = sigma_cr * 1.0
    p_cr_cyl = 2.0 * math.pi * 500.0 * n_cr
    alpha_wave = (12.0 * (1.0 - 0.33**2)) ** 0.25 / math.sqrt(500.0)
    wave = 2.0 * math.pi / alpha_wave
    m_cont = alpha_wave * 1000.0 / math.pi
    story.extend(eq(f"σ<sub>cr</sub>={sigma_cr:.3f} MPa", "(E4-1)"))
    story.extend(eq(f"N<sub>cr</sub>=σ<sub>cr</sub>h={n_cr:.3f} N/mm", "(E4-2)"))
    story.extend(eq(f"P<sub>cr</sub>=2πRN<sub>cr</sub>={p_cr_cyl/1000:.3f} kN", "(E4-3)"))
    story.append(P("若先取軸對稱族 <font name='ArialU'>β=0</font>，由最佳波數條件："))
    story.extend(eq(f"α={alpha_wave:.6f} mm<super>-1</super>，波長 2π/α={wave:.3f} mm", "(E4-4)"))
    story.extend(eq(f"m≈αL/π={m_cont:.3f}　⇒　有限長度取鄰近整數 m=26", "(E4-5)"))
    story.append(
        P(
            "理想值是元素與單位的驗證基準，不是直接設計值；實際薄圓柱殼常因端部、殘餘應力與局部凹陷"
            "在明顯較低載重下失穩。"
        )
    )

    story.append(P("例題 5：同尺寸球殼的理想外壓", H2))
    p_sphere = 2.0 * 70000.0 * (1.0 / 500.0) ** 2 / math.sqrt(3.0 * (1.0 - 0.33**2))
    story.extend(eq(f"p<sub>cr</sub>=2E(h/R)<super>2</super>/√[3(1-ν<super>2</super>)]={p_sphere:.5f} MPa", "(E5-1)"))
    story.extend(eq(f"N=p<sub>cr</sub>R/2={p_sphere*500.0/2.0:.3f} N/mm", "(E5-2)"))
    story.append(
        P(
            "式 (E5-2) 與例題 4 的 <font name='ArialU'>N<sub>cr</sub></font> 相同，"
            "因兩者的局部短波最小化都得到 <font name='ArialU'>2√(DEh)/R</font>。"
        )
    )

    story.append(P("例題 6：二自由度有限元素廣義特徵值", H2))
    story.append(P("令（參考載重取 10 kN，臨界載重在求得 λ<sub>1</sub> 後乘以 10 kN）："))
    story.extend(matrix_pair_equation("(E6-1)"))
    story.append(P("由 <font name='ArialU'>det(K<sub>M</sub>-λK<sub>G</sub>)=0</font>："))
    story.extend(eq("(12-λ)(6-0.5λ)-(-2-0.2λ)<super>2</super>=0", "(E6-2)"))
    story.extend(eq("72-12λ+0.5λ<super>2</super>-[4+0.8λ+0.04λ<super>2</super>]=0", "(E6-3)"))
    story.extend(eq("0.46λ<super>2</super>-12.8λ+68=0", "(E6-4)"))
    disc = 12.8**2 - 4 * 0.46 * 68
    lam1 = (12.8 - math.sqrt(disc)) / (2 * 0.46)
    lam2 = (12.8 + math.sqrt(disc)) / (2 * 0.46)
    story.extend(eq("λ=[12.8±√(12.8<super>2</super>-4×0.46×68)]/(0.92)", "(E6-5)"))
    story.extend(eq(f"λ<sub>1</sub>={lam1:.4f}，λ<sub>2</sub>={lam2:.4f}", "(E6-6)"))

    # 8 Research checklist
    story.append(P("8. 研究實作矩陣與驗證關卡", H1))
    story.append(P("8.1 建議分析層級", H2))
    story.append(
        make_table(
            ["層級", "數學模型", "主要輸出", "不能回答的問題"],
            [
                ["L1 線性屈曲", "[K<sub>M</sub>-λK<sub>G</sub>]φ=0", "理想 λ、模態、網格/邊界敏感性", "缺陷後極限載重與後屈曲"],
                ["L2 完美殼 GNA", "幾何非線性 + 弧長", "理想後屈曲分支、極限點、分岔", "製造缺陷造成的散佈"],
                ["L3 缺陷 GNIA", "量測/模態/局部凹陷缺陷", "載重折減曲線、危險缺陷位置", "材料屈服與殘餘應力"],
                ["L4 GMNIA", "幾何 + 材料 + 缺陷 + 接觸/邊界", "工程極限載重與失效模式", "超出材料模型與缺陷統計的風險"],
            ],
            widths=[28 * mm, 55 * mm, 61 * mm, CONTENT_W - 144 * mm],
        )
    )

    story.append(P("8.2 參數掃描最小集合", H2))
    for item in [
        "<b>幾何：</b>h/R、L/R、端部加厚、開孔、接頭與局部曲率。",
        "<b>缺陷：</b>幅值、符號、軸向/周向波數、局部化尺度、位置、單模態與實測場。",
        "<b>邊界：</b>徑向/切向/轉動拘束、載重引入長度、端部摩擦與剛性環。",
        "<b>數值：</b>元素型式、每半波單元數、積分法、鑽孔自由度、幾何更新方式、弧長步長。",
        "<b>材料：</b>E、ν、屈服、硬化、殘餘應力與厚度偏差。",
        "<b>輸出：</b>最低切線特徵值、負特徵值數、載重-位移、能量分量、模態投影與局部曲率。",
    ]:
        story.append(bullet(item))

    story.append(P("8.3 必做驗證", H2))
    story.append(
        make_table(
            ["關卡", "檢查方法", "接受準則"],
            [
                ["變分/切線", "有限差分比較 r(q+εδq)-r(q)", "K<sub>T</sub>δq 相對誤差隨 ε 先一階下降"],
                ["剛體模式", "零載重自由殼體特徵值", "只出現理論剛體模態；無額外零能模態"],
                ["經典值", "圓柱 σ<sub>cr</sub>、球殼 p<sub>cr</sub>", "網格加密後收斂且量綱正確"],
                ["短波解析", "元素尺寸對 O(√Rh) 半波", "每半波至少約 6-10 個低階單元"],
                ["路徑", "縮小弧長步長、改變預測方向", "極限點與主要分支對步長穩健"],
                ["缺陷", "正負號、幅值與位置掃描", "折減趨勢連續；無網格鎖定造成的假強化"],
            ],
            widths=[28 * mm, 76 * mm, CONTENT_W - 104 * mm],
        )
    )
    story.append(
        P(
            "<b>最重要的結果解讀：</b>線性特徵值是完美基本路徑的局部中性條件；"
            "實際殼體承載力通常是含缺陷非線性路徑上的第一個相關極限點。"
            "若報告只列一個 eigenvalue 而沒有缺陷、路徑、網格、邊界與最低切線特徵值歷程，"
            "便尚未完成殼體失穩研究。",
            CALLOUT,
        )
    )

    # 9 Sources
    story.append(P("9. 原書來源與頁碼對照", H1))
    story.append(
        P(
            "以下頁碼為工作區 PDF 閱讀器的一基底實體頁碼。本講義依原書公式與索引重新組織、"
            "補齊中間代數步驟並加入自編例題，不是原書逐字翻譯。"
        )
    )
    story.append(
        make_table(
            ["代碼", "書籍", "本講義使用範圍"],
            [
                [
                    "B07",
                    "W. T. Koiter / A. M. A. van der Heijden (ed.), <i>W. T. Koiter's Elastic Stability of Solids and Structures</i>",
                    "§1.1 p.11-16；§2.2-2.6 p.21-64；§3.14-3.18 p.176-236。",
                ],
                [
                    "B04",
                    "R. de Borst, M. A. Crisfield et al., <i>Non-Linear Finite Element Analysis of Solids and Structures</i>, 2nd ed.",
                    "§3.5 p.119-121；§4.2 p.134-141；§4.4 p.147-152。",
                ],
                [
                    "B06",
                    "S. P. Timoshenko, J. M. Gere, <i>Theory of Elastic Stability</i>",
                    "§11.1-11.4 p.347-361；§11.13 p.397-406。",
                ],
                [
                    "B03",
                    "D. Chapelle, K. J. Bathe, <i>The Finite Element Analysis of Shells - Fundamentals</i>",
                    "Ch.5 p.127-181：厚度漸近、純彎曲子空間與載重機制。",
                ],
            ],
            widths=[14 * mm, 95 * mm, CONTENT_W - 109 * mm],
        )
    )
    story.append(Spacer(1, 8))
    story.append(
        P(
            "<b>完整概念鏈：</b>殼面度量 → 非線性膜應變與曲率 → 總勢能 → 一階變分平衡 → "
            "二階變分與切線正定性 → 零特徵值 → 極限點/分岔分類 → Koiter 高階約化 → "
            "缺陷線性項與 1/2、2/3 尺度律 → 淺殼/圓柱/球殼解析基準 → "
            "有限元素 K<sub>T</sub>、弧長與分支切換 → 含缺陷非線性極限載重。",
            CALLOUT,
        )
    )
    return story


def build_pdf() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = ShellInstabilityDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T,
        bottomMargin=MARGIN_B,
        title="Shell Instability Research 完整數學邏輯推導與例題",
        author="Codex",
        subject="殼體穩定、Koiter 分岔漸近、缺陷敏感性、淺殼方程與有限元素路徑追蹤",
    )
    doc.multiBuild(build_story())
    print(OUTPUT)


if __name__ == "__main__":
    build_pdf()
