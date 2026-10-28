"""
Pruebas unitarias para la aplicación 'Word to PDF'.
Verifica validación de archivos, límites de tamaño, manejo de errores y endpoints.
"""

import io
import unittest
from unittest.mock import patch
import zipfile

from app import app
from converter import (
    sanitize_download_filename,
    validate_docx_structure,
    ConversionError,
    MAX_FILE_SIZE_BYTES
)


def create_dummy_docx() -> io.BytesIO:
    """Crea un archivo ZIP en memoria con estructura mínima de un .docx."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types></Types>')
        zf.writestr('word/document.xml', '<?xml version="1.0" encoding="UTF-8"?><document></document>')
    buffer.seek(0)
    return buffer


class TestConverterLogic(unittest.TestCase):
    def test_sanitize_filename(self):
        self.assertEqual(sanitize_download_filename("informe.docx"), "informe.pdf")
        self.assertEqual(sanitize_download_filename("INFORME.DOCX"), "INFORME.pdf")
        self.assertEqual(sanitize_download_filename("mi documento 2024.docx"), "mi documento 2024.pdf")
        self.assertEqual(sanitize_download_filename("reporte anual - español.docx"), "reporte anual - español.pdf")
        self.assertEqual(sanitize_download_filename("../../etc/passwd.docx"), "passwd.pdf")
        self.assertEqual(sanitize_download_filename(""), "documento.pdf")

    def test_validate_docx_structure_invalid_zip(self):
        # Archivo que no es ZIP
        invalid_buffer = io.BytesIO(b"Este no es un zip")
        with self.assertRaises(ConversionError) as ctx:
            validate_docx_structure(invalid_buffer)
        self.assertIn("no es un documento de Word", str(ctx.exception.message))

    def test_validate_docx_structure_zip_without_content_types(self):
        # ZIP válido pero que no es un Word docx
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tf:
            with zipfile.ZipFile(tf, 'w') as zf:
                zf.writestr("test.txt", "otro archivo")
            tf_path = tf.name

        try:
            with self.assertRaises(ConversionError) as ctx:
                validate_docx_structure(tf_path)
            self.assertIn("no contiene la estructura interna", str(ctx.exception.message))
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_validate_docx_structure_valid(self):
        valid_buffer = create_dummy_docx()
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tf:
            tf.write(valid_buffer.getvalue())
            tf_path = tf.name

        try:
            # No debe lanzar excepción
            validate_docx_structure(tf_path)
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)


class TestAppRoutes(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_health_check(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertEqual(json_data['status'], 'healthy')
        self.assertEqual(json_data['service'], 'Word to PDF')

    def test_index_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Word to PDF", response.data)
        self.assertIn(b"Convertir a PDF", response.data)

    def test_convert_missing_file(self):
        response = self.client.post('/convert', data={}, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertIn('error', json_data)

    def test_convert_empty_filename(self):
        data = {
            'file': (io.BytesIO(b""), '')
        }
        response = self.client.post('/convert', data=data, content_type='multipart/form-data', headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertIn('error', json_data)

    def test_convert_invalid_extension(self):
        data = {
            'file': (io.BytesIO(b"dummy content"), 'archivo.txt')
        }
        response = self.client.post('/convert', data=data, content_type='multipart/form-data', headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertIn('Solo se admiten archivos con extensión .docx', json_data['error'])

    def test_convert_corrupted_docx(self):
        data = {
            'file': (io.BytesIO(b"PK\x03\x04corrupted fake zip content"), 'documento.docx')
        }
        response = self.client.post('/convert', data=data, content_type='multipart/form-data', headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertIn('no es un documento de Word', json_data['error'])

    def test_convert_empty_file_content(self):
        data = {
            'file': (io.BytesIO(b""), 'vacio.docx')
        }
        response = self.client.post('/convert', data=data, content_type='multipart/form-data', headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertIn('vacío', json_data['error'])

    @patch('app.convert_docx_to_pdf')
    def test_convert_success_mocked(self, mock_convert):
        # Simular conversión exitosa
        dummy_pdf_bytes = b"%PDF-1.4 mock pdf binary content"
        mock_convert.return_value = (dummy_pdf_bytes, "reporte.pdf")

        valid_docx = create_dummy_docx()
        data = {
            'file': (valid_docx, 'reporte.docx')
        }
        response = self.client.post('/convert', data=data, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/pdf')
        self.assertEqual(response.data, dummy_pdf_bytes)
        self.assertIn('reporte.pdf', response.headers.get('Content-Disposition', ''))
        self.assertEqual(response.headers.get('Cache-Control'), 'no-cache, no-store, must-revalidate')


if __name__ == '__main__':
    unittest.main()
