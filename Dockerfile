# ==============================================================================
# Dockerfile para 'Word to PDF'
# Base: Debian Bookworm Slim con Python 3.12 y LibreOffice Headless (no-gui)
# Usuario no privilegiado (appuser) para máxima seguridad en producción
# ==============================================================================

FROM python:3.12-slim-bookworm

# Variables de entorno para optimizar la ejecución de Python y evitar prompts en apt
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# 1. Instalar LibreOffice Writer Headless (sin GUI ni librerías X11 de escritorio)
#    y paquetes de fuentes tipográficas para garantizar renderizado idéntico a MS Office
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer-nogui \
    fonts-liberation \
    fonts-dejavu-core \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2. Crear un usuario y grupo sin privilegios root
RUN groupadd --gid 10001 appgroup && \
    useradd --uid 10001 --gid appgroup --create-home --home-dir /home/appuser --shell /bin/bash appuser

WORKDIR /app

# 3. Instalar dependencias Python utilizando caché de capas de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copiar código de la aplicación y asignar permisos al usuario no root
COPY --chown=appuser:appgroup . .

# 5. Cambiar al usuario no privilegiado
USER appuser
ENV HOME=/home/appuser

# 6. Exponer puerto interno de la aplicación
EXPOSE 8000

# 7. Verificación periódica de estado del contenedor (Healthcheck)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health').read()" || exit 1

# 8. Comando de arranque: Gunicorn escuchando en 0.0.0.0:8000
#    Configurado con 2 workers y 2 threads por worker, ideal para instancias EC2 (t3.micro / t3.small)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
