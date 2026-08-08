FROM python:3.12-slim

WORKDIR /app

# System libraries needed by WeasyPrint (Pango, Cairo, GDK-Pixbuf) and fonts
# for the fpdf2 fallback (DejaVu/Liberation cover Latin + Filipino text).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        shared-mime-info \
        fonts-dejavu \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt gunicorn==23.0.0

COPY . .

# Export folder for generated lesson plans (no Desktop on a server).
ENV LAMDAG_EXPORT_DIR=/app/export
ENV PORT=5000

EXPOSE 5000

# Single worker is fine for a small app; 4 threads handle concurrent users.
# Render/Railway inject their own $PORT, so bind to it when present.
CMD ["sh", "-c", "gunicorn wsgi:app --bind 0.0.0.0:${PORT:-5000} --workers 1 --threads 4 --timeout 120"]

