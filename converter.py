"""
Módulo de conversión de documentos Word (.docx) a PDF utilizando LibreOffice en modo headless.
Garantiza el aislamiento de conversiones simultáneas y la limpieza inmediata de archivos temporales.
"""

import os
import shutil
import subprocess
import tempfile
import pathlib
import zipfile
import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Límite máximo de tamaño de archivo: 10 MB
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {'.docx'}


class ConversionError(Exception):
    """Excepción para errores controlados durante la conversión o validación."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def sanitize_download_filename(filename: str) -> str:
    """
    Genera un nombre seguro para la descarga del PDF basado en el nombre original.
    Preserva caracteres legibles pero elimina rutas relativas o caracteres peligrosos.
    """
    if not filename:
        return "documento.pdf"

    # Eliminar posibles rutas de directorios
    base_name = os.path.basename(filename)

    # Reemplazar la extensión .docx (insensible a mayúsculas) por .pdf
    if base_name.lower().endswith('.docx'):
        base_name = base_name[:-5]

    # Eliminar caracteres nulos o barras de control
    base_name = re.sub(r'[\r\n\t\x00/\\:*?"<>|]', '_', base_name).strip()

    if not base_name:
        base_name = "documento"

    return f"{base_name}.pdf"


def get_libreoffice_executable() -> str:
    """
    Localiza el ejecutable de LibreOffice / soffice en el sistema.
    Lanza ConversionError si no está instalado.
    """
    # 1. Comprobar en el PATH del sistema (común en Linux/Docker)
    for binary_name in ["libreoffice", "soffice"]:
        found = shutil.which(binary_name)
        if found:
            return found

    # 2. Rutas habituales en Windows para desarrollo local
    windows_candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for path in windows_candidates:
        if os.path.isfile(path):
            return path

    raise ConversionError(
        "LibreOffice no está instalado o no se encuentra en el PATH del sistema del servidor.",
        status_code=500
    )


def validate_docx_structure(filepath: str):
    """
    Valida que el archivo guardado sea un paquete OpenXML Word (.docx) legítimo.
    Un archivo .docx válido es un contenedor ZIP que contiene '[Content_Types].xml'.
    """
    if not zipfile.is_zipfile(filepath):
        raise ConversionError(
            "El archivo seleccionado no es un documento de Word (.docx) válido o está dañado.",
            status_code=400
        )

    try:
        with zipfile.ZipFile(filepath, 'r') as zf:
            namelist = zf.namelist()
            # Los documentos .docx siempre contienen [Content_Types].xml y habitualmente word/document.xml
            if '[Content_Types].xml' not in namelist:
                raise ConversionError(
                    "El archivo no contiene la estructura interna de un documento Word (.docx).",
                    status_code=400
                )
    except zipfile.BadZipFile:
        raise ConversionError(
            "El archivo Word está dañado o incompleto.",
            status_code=400
        )


def convert_docx_to_pdf(file_storage, original_filename: str, timeout_seconds: int = 60) -> Tuple[bytes, str]:
    """
    Convierte un documento .docx a PDF usando LibreOffice headless.
    
    Aislamiento y limpieza:
    - Utiliza un directorio temporal único por cada petición (tempfile.TemporaryDirectory).
    - Asigna un perfil de usuario aislado (-env:UserInstallation) para evitar bloqueos
      o interferencias si ocurren conversiones en paralelo.
    - Lee el PDF resultante en memoria (bytes) y elimina de inmediato todo el directorio
      temporal en el bloque 'finally', garantizando que no queden residuos en el disco.

    Retorna: (pdf_bytes, output_filename)
    """
    # 1. Validar extensión
    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ConversionError(
            f"Formato no permitido: '{ext}'. Solo se admiten archivos con extensión .docx.",
            status_code=400
        )

    # 2. Crear directorio temporal aislado para la petición actual
    with tempfile.TemporaryDirectory(prefix="word2pdf_") as temp_dir:
        input_path = os.path.join(temp_dir, "input.docx")
        output_dir = os.path.join(temp_dir, "output")
        profile_dir = os.path.join(temp_dir, "lo_profile")

        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(profile_dir, exist_ok=True)

        # 3. Guardar el archivo subido en el directorio temporal
        try:
            file_storage.seek(0)
            file_storage.save(input_path)
        except Exception as e:
            logger.error("Error al guardar archivo temporal: %s", e)
            raise ConversionError("No se pudo procesar el archivo temporal en el servidor.", status_code=500)

        # 4. Validar tamaño en disco (límite 10 MB)
        file_size = os.path.getsize(input_path)
        if file_size == 0:
            raise ConversionError("El archivo enviado está vacío (0 bytes).", status_code=400)
        if file_size > MAX_FILE_SIZE_BYTES:
            raise ConversionError(
                f"El archivo ({file_size / (1024 * 1024):.2f} MB) supera el límite máximo permitido de 10 MB.",
                status_code=413
            )

        # 5. Validar estructura interna de paquete .docx
        validate_docx_structure(input_path)

        # 6. Obtener ejecutable de LibreOffice
        lo_binary = get_libreoffice_executable()

        # 7. Construir comando LibreOffice headless con perfil aislado
        # El parámetro -env:UserInstallation previene conflictos de locks entre workers
        profile_uri = pathlib.Path(profile_dir).as_uri()

        cmd = [
            lo_binary,
            "--headless",
            "--nologo",
            "--nofirststartwizard",
            "--nodefault",
            "--norestore",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to",
            "pdf",
            "--outdir",
            output_dir,
            input_path
        ]

        logger.info("Iniciando conversión de %s con LibreOffice...", original_filename)

        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
                check=False
            )
        except subprocess.TimeoutExpired:
            logger.error("LibreOffice excedió el tiempo límite de %s segundos", timeout_seconds)
            raise ConversionError(
                f"La conversión excedió el tiempo límite de {timeout_seconds} segundos. El documento puede ser demasiado complejo o estar bloqueado.",
                status_code=504
            )
        except Exception as e:
            logger.error("Fallo inesperado al ejecutar LibreOffice: %s", e)
            raise ConversionError("Error interno al ejecutar el conversor de documentos.", status_code=500)

        # 8. Comprobar resultado del proceso
        if proc.returncode != 0:
            stderr_msg = proc.stderr.decode('utf-8', errors='replace').strip()
            logger.error("LibreOffice retornó código %s: %s", proc.returncode, stderr_msg)
            raise ConversionError(
                "No fue posible convertir el documento a PDF. Comprueba que el archivo no requiera contraseña ni esté protegido.",
                status_code=422
            )

        # 9. Localizar el archivo PDF generado en output_dir
        expected_pdf = os.path.join(output_dir, "input.pdf")
        if not os.path.isfile(expected_pdf):
            # En caso de que LibreOffice use otro nombre, buscar el primer .pdf en output_dir
            pdf_files = [f for f in os.listdir(output_dir) if f.lower().endswith('.pdf')]
            if pdf_files:
                expected_pdf = os.path.join(output_dir, pdf_files[0])
            else:
                stderr_msg = proc.stderr.decode('utf-8', errors='replace').strip()
                logger.error("No se encontró el PDF generado. stderr: %s", stderr_msg)
                raise ConversionError(
                    "El motor de conversión finalizó pero no generó el archivo PDF esperado.",
                    status_code=500
                )

        if os.path.getsize(expected_pdf) == 0:
            raise ConversionError(
                "El archivo PDF generado está vacío.",
                status_code=500
            )

        # 10. Leer el PDF generado en memoria antes de que se destruya el directorio temporal
        with open(expected_pdf, "rb") as f:
            pdf_bytes = f.read()

        logger.info("Conversión exitosa: %s (%d bytes)", original_filename, len(pdf_bytes))

        # 11. Generar nombre de descarga
        output_name = sanitize_download_filename(original_filename)

        return pdf_bytes, output_name
