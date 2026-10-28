# Word to PDF 📄➡️📑

Aplicación web completa, moderna y minimalista para convertir documentos de Microsoft Word (`.docx`) a formato PDF en el servidor, utilizando **LibreOffice en modo headless**.

Diseñada para ser desplegada en **AWS EC2 con Ubuntu Server 24.04 LTS y Docker Compose**.

---

## 🚀 Características Principales

- **Interfaz Moderna en Español**: Diseño limpio, adaptativo (móvil y escritorio), con soporte de arrastrar y soltar (*drag & drop*).
- **Conversión Real con LibreOffice**: Procesamiento headless en el servidor que conserva tipografías, tablas, alineaciones e imágenes con fidelidad.
- **Límite de 10 MB**: Validación inmediata en el navegador (cliente) y estricta en el servidor (HTTP 413).
- **Aislamiento Total de Archivos Concurrente**: Cada conversión se ejecuta en un directorio temporal único con un perfil de usuario aislado de LibreOffice (`-env:UserInstallation`), garantizando que peticiones simultáneas nunca colisionen ni mezclen archivos.
- **Limpieza Inmediata**: Los archivos temporales generados se eliminan inmediatamente tras completar la conversión y enviar la respuesta en memoria al usuario.
- **Sin Base de Datos**: Arquitectura *stateless* (sin estado), sin almacenamiento persistente ni retención de datos o metadatos.
- **Seguridad en Contenedor**: Ejecución bajo un usuario sin privilegios root (`appuser`, UID 10001).

---

## 📁 Estructura del Proyecto

```text
word-to-pdf/
├── app.py                 # Servidor web Flask, rutas (/health, /, /convert) y manejo de errores
├── converter.py           # Lógica de conversión con LibreOffice headless, validaciones y perfiles aislados
├── requirements.txt       # Dependencias de Python fijadas (Flask, Gunicorn, Werkzeug)
├── Dockerfile             # Imagen Docker basada en Debian Bookworm Slim, LibreOffice no-gui y appuser
├── compose.yaml           # Definición de Docker Compose para orquestación en EC2
├── .dockerignore          # Archivos excluidos del contexto de construcción de Docker
├── .gitignore             # Archivos y carpetas ignorados por Git
├── README.md              # Documentación detallada de instalación y despliegue
├── templates/
│   └── index.html         # Plantilla HTML con diseño responsivo en español
├── static/
│   ├── css/
│   │   └── style.css      # Estilos CSS modernos (100% autocontenido, sin dependencias externas/CDN)
│   └── js/
│       └── main.js        # Lógica del cliente (drag & drop, validaciones, fetch asíncrono y descarga)
└── tests/
    └── test_app.py        # Pruebas unitarias de rutas, validaciones y formato docx
```

---

## ⚙️ Configuración de Red y Puertos

La aplicación dentro del contenedor escucha en la dirección **`0.0.0.0`** y en el puerto interno **`8000`**.

### Mapeo en `compose.yaml`:
En el archivo `compose.yaml` se define el mapeo en formato `"PUERTO_EXTERNO_HOST:PUERTO_INTERNO_CONTENEDOR"`:

```yaml
ports:
  - "8080:8000"
```

- **Puerto interno**: `8000` (puerto donde corre Gunicorn dentro del contenedor).
- **Puerto externo**: `8080` (puerto expuesto en el servidor EC2 hacia Internet o la red local).

> [!TIP]
> **¿Deseas acceder directamente por el puerto estándar HTTP (80)?**  
> Cambia la línea en `compose.yaml` a:
> ```yaml
> ports:
>   - "80:8000"
> ```
> Asegúrate de que el puerto 80 no esté ocupado por Apache, Nginx u otro servicio en la instancia EC2.

---

## 🧪 Pruebas en Entorno Local

### Opción A: Con Docker Compose (Recomendado si tienes Docker instalado)

1. Clona o ubícate en la carpeta del proyecto:
   ```bash
   cd word-to-pdf
   ```

2. Construye e inicia el contenedor en segundo plano:
   ```bash
   docker compose up --build -d
   ```

3. Abre en tu navegador web:
   ```text
   http://localhost:8080
   ```

---

### Opción B: Ejecución nativa con Python (para desarrollo)

> **Nota**: Para que la conversión funcione localmente sin Docker, debes tener LibreOffice instalado en tu sistema operativo.

1. Crear y activar un entorno virtual:
   - **Linux / macOS**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```

2. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

3. Ejecutar pruebas unitarias:
   ```bash
   python -m unittest discover tests
   ```

4. Iniciar la aplicación web:
   ```bash
   python app.py
   ```
   Estará disponible en `http://localhost:8000`.

---

## ☁️ Guía Paso a Paso para Despliegue en AWS EC2

### 1. Lanzar una Instancia EC2 en AWS

1. Ingresa a la consola de AWS y ve a **EC2 > Launch an instance**.
2. **Nombre**: `word-to-pdf-server` (o el de tu preferencia).
3. **AMI (Amazon Machine Image)**: Selecciona **Ubuntu Server 24.04 LTS** (64-bit x86).
4. **Tipo de instancia**: `t3.micro` (elegible para la capa gratuita de AWS) o `t3.small` (recomendado si prevés múltiples conversiones simultáneas).
5. **Key pair**: Selecciona un par de claves existente o crea uno nuevo (ej. `mi-clave.pem`) para conectarte vía SSH.
6. **Network settings / Security Group (Grupo de Seguridad)**:
   Configura las siguientes **Reglas de entrada (Inbound rules)**:
   - **SSH** (Puerto 22 TCP): Origen `Mi IP` (o `0.0.0.0/0`).
   - **Regla TCP personalizada** (Puerto `8080` TCP) o **HTTP** (Puerto `80` TCP si mapeaste al puerto 80): Origen `0.0.0.0/0` (Anywhere IPv4).
7. **Storage**: El volumen EBS por defecto de 8 GB o 15 GB gp3 es suficiente.
8. Haz clic en **Launch instance**.

---

### 2. Conectarse a la Instancia por SSH

Abre tu terminal y ejecuta:

```bash
chmod 400 mi-clave.pem
ssh -i mi-clave.pem ubuntu@<IP-PUBLICA-DE-TU-EC2>
```

---

### 3. Instalar Docker Engine y Docker Compose en Ubuntu 24.04 LTS

Ejecuta los siguientes comandos oficiales para instalar Docker Engine y el plugin Compose:

```bash
# 1. Actualizar repositorios e instalar paquetes previos
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# 2. Agregar la clave GPG oficial de Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 3. Configurar el repositorio oficial de Docker
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 4. Instalar Docker Engine y el plugin Docker Compose
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 5. (Opcional pero recomendado) Permitir ejecutar docker sin sudo
sudo usermod -aG docker $USER
newgrp docker
```

Verifica la instalación:
```bash
docker --version
docker compose version
```

---

### 4. Clonar el Repositorio de GitHub y Desplegar

1. Clona tu repositorio en la instancia:
   ```bash
   git clone https://github.com/<tu-usuario>/word-to-pdf.git
   cd word-to-pdf
   ```

2. Construye la imagen y levanta los contenedores en segundo plano:
   ```bash
   docker compose up --build -d
   ```

3. Verifica que el contenedor esté corriendo y saludable:
   ```bash
   docker compose ps
   ```

4. Comprueba el endpoint de salud:
   ```bash
   curl http://localhost:8080/health
   # Respuesta esperada: {"app":"Word to PDF","status":"healthy","version":"1.0.0"}
   ```

5. **¡Listo!** Abre tu navegador y accede a:
   ```text
   http://<IP-PUBLICA-DE-TU-EC2>:8080
   ```
   *(O `http://<IP-PUBLICA-DE-TU-EC2>` si configuraste el puerto 80).*

---

## 🛠️ Comandos de Mantenimiento y Operación

### Ver logs en tiempo real
Para observar los accesos web, conversiones y posibles errores del sistema:
```bash
docker compose logs -f
```

Para ver solo las últimas 100 líneas:
```bash
docker compose logs --tail=100 -f
```

### Detener la aplicación
Detiene y remueve los contenedores en ejecución:
```bash
docker compose down
```

### Reiniciar la aplicación
Reinicia el servicio sin reconstruir la imagen:
```bash
docker compose restart
```

### Actualizar la aplicación (después de hacer `git push`)
Cuando subas cambios a tu repositorio de GitHub, actualiza la instancia ejecutando:
```bash
git pull origin main
docker compose up --build -d
```
Docker reconstruirá únicamente las capas que hayan cambiado y reemplazará el contenedor con tiempo de inactividad mínimo.

---

## 🔒 Mecanismos de Seguridad y Resiliencia

1. **Usuario no privilegiado (`appuser`)**: El contenedor no se ejecuta como `root`, reduciendo la superficie de ataque frente a posibles vulnerabilidades en bibliotecas de procesamiento de documentos.
2. **Aislamiento concurrente de LibreOffice**: Cada conversión invoca `libreoffice --headless` con `-env:UserInstallation=file://...` apuntando a un directorio temporal privado. Esto evita que instancias paralelas bloqueen el perfil de usuario o se sobrescriban entre sí.
3. **Limpieza estricta de temporales**: La conversión utiliza `tempfile.TemporaryDirectory()`. El archivo PDF generado se carga en memoria (`io.BytesIO`) para su transmisión, y el bloque `finally` garantiza la eliminación completa de los archivos y directorios del disco inmediatamente, incluso si ocurre un error.
4. **Validación de contenido OpenXML**: Además de validar la extensión `.docx`, el backend verifica la firma de contenedor ZIP y la presencia de `[Content_Types].xml`, rechazando archivos manipulados o ejecutables renombrados.
5. **Rotación automática de logs**: Docker Compose limita los archivos de log a 3 archivos de máximo 10 MB cada uno, impidiendo el llenado del volumen EBS de AWS.
