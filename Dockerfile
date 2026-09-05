FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglu1-mesa \
    libgl1 \
    libxrender1 \
    libxcursor1 \
    libxft2 \
    libxinerama1 \
    libgomp1 \
    libx11-6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md MANIFEST.in ./
COPY src ./src
COPY frontend/dist ./frontend/dist
COPY dependencies /tmp/dependencies
COPY ["Step 2 Math Core/step2_math_core", "./Step 2 Math Core/step2_math_core"]
COPY ["Step 2 Math Core/Plate-Shell-Buckling/Plate-Shell-Buckling/python_math_core/plate_shell_buckling_core", "./Step 2 Math Core/Plate-Shell-Buckling/Plate-Shell-Buckling/python_math_core/plate_shell_buckling_core"]
COPY ["Step 2 Math Core/Shell-Instability-Research_Math-Core-Guide/Shell-Instability-Research_Math-Core-Guide/09_Python数学核心/src/shell_instability_math", "./Step 2 Math Core/Shell-Instability-Research_Math-Core-Guide/Shell-Instability-Research_Math-Core-Guide/09_Python数学核心/src/shell_instability_math"]
COPY ["Step 2 Math Core/Shell-Instability-Research_Math-Core-Guide/Shell-Instability-Research_Math-Core-Guide/09_Python数学核心/run_validation_problems.py", "./Step 2 Math Core/Shell-Instability-Research_Math-Core-Guide/Shell-Instability-Research_Math-Core-Guide/09_Python数学核心/run_validation_problems.py"]
COPY ["Step 2 Math Core/Constitutive Nonlinearity/Constitutive-Nonlinearity_Weeks10-14_Core-Guide/04_可复现算例/reference_material_point.py", "./Step 2 Math Core/Constitutive Nonlinearity/Constitutive-Nonlinearity_Weeks10-14_Core-Guide/04_可复现算例/reference_material_point.py"]
COPY ["Step 2 Math Core/General Nonlinear Shell/4_General-Nonlinear-Shell_16-24周/08_Python数学核心/general_nonlinear_shell_math", "./Step 2 Math Core/General Nonlinear Shell/4_General-Nonlinear-Shell_16-24周/08_Python数学核心/general_nonlinear_shell_math"]

RUN pip install --no-cache-dir \
        /tmp/dependencies/continuum \
        /tmp/dependencies/frame \
        /tmp/dependencies/plate \
        /tmp/dependencies/shell \
    && pip install --no-cache-dir -e . \
    && rm -rf /tmp/dependencies

ENV NONLINEAR_HOST=0.0.0.0 \
    NONLINEAR_API_PORT=8007 \
    NONLINEAR_DATA_DIR=/data \
    NONLINEAR_COOKIE_SECURE=1 \
    NONLINEAR_FRONTEND_DIST=/app/frontend/dist \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MPLCONFIGDIR=/tmp/matplotlib

EXPOSE 8007

CMD ["uvicorn", "nonlinear_api.main:app", "--host", "0.0.0.0", "--port", "8007", "--proxy-headers", "--forwarded-allow-ips", "*"]
