/**
 * Word to PDF - Lógica de Interfaz de Usuario
 * - Arrastrar y soltar (Drag and drop)
 * - Validación inmediata en cliente (formato .docx y tamaño <= 10 MB)
 * - Petición asíncrona mediante Fetch API
 * - Descarga automática y control de reintentos
 */

document.addEventListener('DOMContentLoaded', () => {
  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB en bytes

  // Elementos DOM
  const form = document.getElementById('convertForm');
  const fileInput = document.getElementById('fileInput');
  const dropZone = document.getElementById('dropZone');
  const fileCard = document.getElementById('fileCard');
  const fileNameEl = document.getElementById('fileName');
  const fileSizeEl = document.getElementById('fileSize');
  const removeFileBtn = document.getElementById('removeFileBtn');
  const convertBtn = document.getElementById('convertBtn');
  
  const statusLoading = document.getElementById('statusLoading');
  const statusError = document.getElementById('statusError');
  const errorMessageEl = document.getElementById('errorMessage');
  const dismissErrorBtn = document.getElementById('dismissErrorBtn');
  
  const statusSuccess = document.getElementById('statusSuccess');
  const reDownloadBtn = document.getElementById('reDownloadBtn');
  const newConvertBtn = document.getElementById('newConvertBtn');

  // Estado local
  let currentFile = null;
  let lastGeneratedBlobUrl = null;
  let lastGeneratedFilename = null;

  // Formatear tamaño de bytes a formato legible (KB / MB)
  function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  // Ocultar todas las alertas de estado
  function resetStatusMessages() {
    statusLoading.classList.add('hidden');
    statusError.classList.add('hidden');
    statusSuccess.classList.add('hidden');
  }

  // Mostrar mensaje de error en español
  function showError(message) {
    resetStatusMessages();
    errorMessageEl.textContent = message;
    statusError.classList.remove('hidden');
    convertBtn.disabled = !currentFile;
  }

  // Validar y seleccionar archivo
  function handleFileSelected(file) {
    if (!file) return;

    resetStatusMessages();

    // 1. Validar extensión (.docx)
    const fileName = file.name.toLowerCase();
    if (!fileName.endsWith('.docx')) {
      showError('Formato no permitido. Solo se aceptan archivos de Word con extensión .docx.');
      clearFileSelection();
      return;
    }

    // 2. Validar tamaño (máximo 10 MB)
    if (file.size > MAX_FILE_SIZE) {
      showError(`El archivo "${file.name}" pesa ${formatBytes(file.size)}, superando el límite máximo permitido de 10 MB.`);
      clearFileSelection();
      return;
    }

    if (file.size === 0) {
      showError(`El archivo "${file.name}" está vacío (0 bytes). Selecciona un documento válido.`);
      clearFileSelection();
      return;
    }

    // Archivo válido
    currentFile = file;
    fileNameEl.textContent = file.name;
    fileNameEl.title = file.name;
    fileSizeEl.textContent = formatBytes(file.size);

    fileCard.classList.remove('hidden');
    convertBtn.disabled = false;
  }

  // Limpiar selección de archivo
  function clearFileSelection() {
    currentFile = null;
    fileInput.value = '';
    fileCard.classList.add('hidden');
    convertBtn.disabled = true;
  }

  // Eventos de selección de archivo manual
  dropZone.addEventListener('click', () => fileInput.click());
  
  dropZone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInput.click();
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });

  removeFileBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    clearFileSelection();
  });

  dismissErrorBtn.addEventListener('click', () => {
    statusError.classList.add('hidden');
  });

  // Eventos de Arrastrar y Soltar (Drag and Drop)
  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add('drag-over');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('drag-over');
    });
  });

  dropZone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    if (dt && dt.files && dt.files.length > 0) {
      handleFileSelected(dt.files[0]);
    }
  });

  // Descarga del archivo PDF
  function triggerDownload(blobUrl, filename) {
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = blobUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
    }, 100);
  }

  // Envío del Formulario vía Fetch
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!currentFile) {
      showError('Por favor selecciona primero un documento Word (.docx).');
      return;
    }

    // Preparar estado de carga
    resetStatusMessages();
    statusLoading.classList.remove('hidden');
    convertBtn.disabled = true;

    const formData = new FormData();
    formData.append('file', currentFile);

    try {
      const response = await fetch('/convert', {
        method: 'POST',
        body: formData,
        headers: {
          'X-Requested-With': 'XMLHttpRequest'
        }
      });

      if (!response.ok) {
        // Intentar leer mensaje de error del backend en formato JSON
        let serverErrorMsg = 'Error al convertir el documento.';
        try {
          const errorData = await response.json();
          if (errorData && errorData.error) {
            serverErrorMsg = errorData.error;
          }
        } catch (_) {
          if (response.status === 413) {
            serverErrorMsg = 'El archivo supera el límite de 10 MB permitido por el servidor.';
          } else {
            serverErrorMsg = `Error del servidor (código ${response.status}).`;
          }
        }
        showError(serverErrorMsg);
        return;
      }

      // Obtener el nombre del archivo PDF generado
      let pdfFilename = currentFile.name.replace(/\.docx$/i, '.pdf');
      const xFilename = response.headers.get('X-Filename');
      if (xFilename) {
        try {
          pdfFilename = decodeURIComponent(xFilename);
        } catch (_) {
          // Si falla la decodificación, mantener el nombre calculado
        }
      }

      // Obtener los datos binarios del PDF
      const blob = await response.blob();

      // Liberar URL anterior si existía
      if (lastGeneratedBlobUrl) {
        window.URL.revokeObjectURL(lastGeneratedBlobUrl);
      }

      lastGeneratedBlobUrl = window.URL.createObjectURL(blob);
      lastGeneratedFilename = pdfFilename;

      // Descargar automáticamente
      triggerDownload(lastGeneratedBlobUrl, pdfFilename);

      // Mostrar estado de éxito
      resetStatusMessages();
      statusSuccess.classList.remove('hidden');

    } catch (err) {
      console.error('Error de red o procesamiento:', err);
      showError('No se pudo conectar con el servidor. Verifica tu conexión de red e inténtalo de nuevo.');
    } finally {
      statusLoading.classList.add('hidden');
      convertBtn.disabled = false;
    }
  });

  // Botón: Descargar de nuevo
  reDownloadBtn.addEventListener('click', () => {
    if (lastGeneratedBlobUrl && lastGeneratedFilename) {
      triggerDownload(lastGeneratedBlobUrl, lastGeneratedFilename);
    }
  });

  // Botón: Convertir otro archivo
  newConvertBtn.addEventListener('click', () => {
    clearFileSelection();
    resetStatusMessages();
  });
});
