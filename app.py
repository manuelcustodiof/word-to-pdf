"""
Aplicación Web 'Word to PDF'
Servicio ligero para convertir documentos Word (.docx) a PDF usando LibreOffice headless.
Sin bases de datos, con aislamiento concurrente y limpieza inmediata de archivos temporales.
"""

import io
import os
import logging
import urllib.parse
from flask import Flask, render_template, request, send_file, jsonify, Response
from werkzeug.exceptions import RequestEntityTooLarge

from converter import convert_docx_to_pdf, ConversionError, MAX_FILE_SIZE_BYTES

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("word_to_pdf")

app = Flask(__name__)

# Límite máximo de carga en Flask: 10 MB
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE_BYTES
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'word-to-pdf-insecure-dev-key')


@app.errorhandler(413)
@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(error):
    """Manejo de archivos que superan el límite de 10 MB."""
    mensaje = "El archivo supera el tamaño máximo permitido de 10 MB. Por favor, selecciona un documento más pequeño."
    if request.is_json or request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"error": mensaje}), 413
    return render_template('index.html', error_message=mensaje), 413


@app.errorhandler(400)
def handle_bad_request(error):
    mensaje = "Solicitud inválida. Asegúrate de enviar un archivo Word válido."
    if request.is_json or request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"error": mensaje}), 400
    return render_template('index.html', error_message=mensaje), 400


@app.errorhandler(500)
def handle_server_error(error):
    mensaje = "Se produjo un error interno al procesar el documento. Inténtalo nuevamente."
    if request.is_json or request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"error": mensaje}), 500
    return render_template('index.html', error_message=mensaje), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de comprobación de salud para Docker, balanceadores de carga y AWS EC2."""
    return jsonify({
        "status": "healthy",
        "service": "Word to PDF",
        "version": "1.0.0"
    }), 200


@app.route('/', methods=['GET'])
def index():
    """Página principal de la aplicación web."""
    return render_template('index.html')


@app.route('/convert', methods=['POST'])
def convert():
    """
    Ruta para procesar la subida y conversión de documentos .docx a PDF.
    Acepta envíos tanto mediante Fetch/AJAX (Blob) como mediante formulario tradicional.
    """
    # 1. Verificar presencia del archivo en la solicitud
    if 'file' not in request.files:
        error_msg = "No se ha seleccionado ningún archivo para convertir."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
            return jsonify({"error": error_msg}), 400
        return render_template('index.html', error_message=error_msg), 400

    uploaded_file = request.files['file']

    # 2. Verificar que el nombre del archivo no esté vacío
    if not uploaded_file or uploaded_file.filename.strip() == '':
        error_msg = "No se ha seleccionado ningún archivo."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
            return jsonify({"error": error_msg}), 400
        return render_template('index.html', error_message=error_msg), 400

    # 3. Procesar y convertir
    try:
        pdf_bytes, output_filename = convert_docx_to_pdf(uploaded_file, uploaded_file.filename)

        # Crear respuesta con el PDF en memoria
        response = send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=output_filename
        )

        # Encabezados para que el cliente JS obtenga el nombre original y evitar caché
        encoded_filename = urllib.parse.quote(output_filename)
        response.headers['X-Filename'] = encoded_filename
        response.headers['Access-Control-Expose-Headers'] = 'Content-Disposition, X-Filename'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

        return response

    except ConversionError as ce:
        logger.warning("Error de conversión en %s: %s", uploaded_file.filename, ce.message)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
            return jsonify({"error": ce.message}), ce.status_code
        return render_template('index.html', error_message=ce.message), ce.status_code

    except Exception as e:
        logger.exception("Error inesperado durante la conversión de %s: %s", uploaded_file.filename, e)
        error_msg = "Ocurrió un error inesperado al convertir el archivo. Asegúrate de que sea un archivo Word válido."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
            return jsonify({"error": error_msg}), 500
        return render_template('index.html', error_message=error_msg), 500


if __name__ == '__main__':
    # Escucha en 0.0.0.0 y puerto configurable mediante variable de entorno
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
