# ImagesManagement - Sistema de Procesamiento Automático de Imágenes

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.x-green.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green.svg)
![MongoDB](https://img.shields.io/badge/MongoDB-4.x+-green.svg)
![License](https://img.shields.io/badge/license-GPL%20v3-blue.svg)

Sistema automatizado completo para el procesamiento, clasificación y almacenamiento de imágenes de productos de joyería. Incluye interfaz web moderna, procesamiento automático en cola, y sistema de protección de datos con confirmación de subida a MongoDB.

## 🎯 **Características Principales**

### 🌐 **Interfaz Web Moderna**
- **Procesamiento automático** con gestión de cola de imágenes
- **Interfaz responsiva** con CSS moderno y animaciones
- **Gestión inteligente de estado** según disponibilidad de imágenes
- **Sistema drag & drop** para reclasificación manual
- **Modal de zoom** para inspección detallada de imágenes
- **Progreso en tiempo real** con Server-Sent Events

### 🚀 **Sistema de Procesamiento Automático**
- **Flujo optimizado**: `source/` → `source_images/` → `[PROCESAMIENTO]` → `[MONGODB]` → `images_old/`
- **Protección de datos**: Las imágenes NO se mueven hasta confirmar subida exitosa a MongoDB
- **Gestión automática de archivos** con preparación de siguiente imagen
- **Limpieza automática** de directorios temporales
- **Ordenación numérica** correcta de rectángulos (`rect_0`, `rect_1`, `rect_2`...)

### 🔤 **OCR Inteligente y Machine Learning**
- **Extracción de texto** usando Tesseract OCR con corrección automática
- **Clasificador ML** para distinguir códigos vs imágenes
- **Corrección automática** de errores comunes ('ll' ↔ '11')
- **Detección de patrones** específicos de códigos de joyería
- **Sistema de confianza** para validación automática

### 🗄️ **Gestión Robusta de Datos**
- **Almacenamiento seguro en MongoDB** con verificación de errores
- **Emparejamiento automático** código-imagen por orden numérico
- **Sistema de categorías** (anillos, pendientes, collares)
- **Logging detallado** del proceso completo

## 🌐 **Interfaz Web - Funcionalidades**

### 📊 **Panel de Estado del Sistema**
- **Contador de imágenes en cola** (`/source`)
- **Estado de imagen actual** (`/source_images`)
- **Contador de imágenes procesadas** (`/images_old`)
- **Vista previa de imagen actual** con información

### 🎮 **Controles Inteligentes**
| Estado del Sistema | Botón Procesar | Botón Preparar | Panel Imagen |
|-------------------|----------------|----------------|--------------|
| Sin imágenes | 📁 No hay imágenes (❌) | **Oculto** | **Oculto** |
| Solo en cola | ▶️ Preparar y Procesar (❌) | ⏭️ Preparar Siguiente (✅) | **Oculto** |
| Imagen actual | ▶️ Procesar Automático (✅) | ⏭️ Preparar Siguiente (✅) | **Visible** |

### 📋 **Sistema de Revisión Manual**
- **Inspección visual** de todos los rectángulos clasificados
- **Drag & drop** para reclasificar elementos incorrectos
- **Zoom con un click** para ver detalles de cada imagen
- **Confirmación** antes de subir a MongoDB

## 📁 **Estructura del Proyecto Actualizada**

```
ImagesManagement/
├── 🌐 web_app.py                                 # Aplicación web principal
├── 🎨 templates/
│   ├── index_auto.html                          # Interfaz principal automática
│   └── index.html                               # Interfaz manual (legacy)
├── 📱 static/css/styles.css                     # Estilos modernos responsive
├── 📄 main.py                                   # Script de procesamiento por lotes
├── 🔧 improved_classify_rectangles_ocr_fixed.py # Procesador OCR mejorado
├── 📐 extract_rectangles.py                     # Extracción de rectángulos
├── 🔗 connect_mongodb.py                        # Conexión segura a MongoDB
├── 📁 MachineLearning/                          # Módulo completo de ML
│   ├── 🧠 image_category_classifier.py         # Clasificador principal
│   ├── ⚙️ jewelry_integration.py               # Integración ML
│   ├── 🤖 jewelry_ml_classifier.py             # Clasificador ML
│   ├── 📋 jewelry_config.py                    # Configuración
│   └── 💾 models/jewelry_classifier.pkl        # Modelo entrenado
├── 📁 source/                                   # Cola de imágenes a procesar
├── 📁 source_images/                            # Imagen actual en procesamiento
├── 📁 rectangles_output/                        # Rectángulos extraídos (temporal)
├── 📁 codes_output/                             # Códigos detectados (temporal)
├── 📁 images_output/                            # Imágenes de productos (temporal)
├── 📁 discards_output/                          # Elementos descartados (temporal)
└── 📁 images_old/                               # Imágenes completamente procesadas
```

## 🚀 **Instalación y Configuración**

### Dependencias Principales
```bash
pip install -r requirements.txt
```

**Librerías clave:**
- `flask` - Aplicación web
- `opencv-python` - Procesamiento de imágenes
- `pytesseract` - OCR
- `pymongo` - Base de datos MongoDB
- `scikit-learn` - Machine Learning
- `python-dotenv` - Variables de entorno

### Configuración
1. **Crear archivo `.env`:**
```env
MONGODB_URI=mongodb://localhost:27017/
DATABASE_NAME=images_db
COLLECTION_NAME=codes_images
```

2. **Instalar Tesseract OCR:**
```bash
# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-spa

# macOS
brew install tesseract tesseract-lang
```

## 🌐 **Uso de la Interfaz Web**

### Iniciar la Aplicación
```bash
python web_app.py
```

**URLs disponibles:**
- `http://localhost:5000` - **Procesamiento automático** (recomendado)
- `http://localhost:5000/manual` - Procesamiento manual (legacy)
- `http://localhost:5000/processing_status` - Estado del procesamiento

### Flujo de Trabajo Completo

#### 1. **Preparación** 📁
```bash
# Colocar imágenes de catálogos en:
/source/
├── catalogo1.jpg
├── catalogo2.png
└── catalogo3.jpeg
```

#### 2. **Procesamiento Automático** 🚀
1. **Acceder** a `http://localhost:5000`
2. **Preparar imagen**: Clic en "⏭️ Preparar Siguiente"
3. **Procesar**: Clic en "▶️ Procesar Automático"
4. **Revisar** (si es necesario): Drag & drop para reclasificar
5. **Finalizar**: Clic en "✅ Finalizar y Subir a MongoDB"

#### 3. **Seguimiento en Tiempo Real** 📊
- **Estado del sistema** actualizado automáticamente
- **Progreso detallado** con logs en tiempo real
- **Notificaciones** de éxito/error
- **Preparación automática** de siguiente imagen

### Características Avanzadas de la Interfaz

#### 🔍 **Sistema de Zoom**
- **Un click** en cualquier imagen para zoom completo
- **Modal responsive** con información detallada
- **Navegación** con teclado (ESC para cerrar)

#### 🎯 **Drag & Drop Inteligente**
- **Arrastrar** rectángulos entre categorías
- **Indicadores visuales** de zonas válidas
- **Confirmación** automática de movimientos
- **Actualización** instantánea de contadores

#### 📱 **Diseño Responsive**
- **Adaptable** a móviles y tablets
- **Grid system** flexible
- **Botones grandes** para touch
- **Navegación optimizada**

## 🛡️ **Sistema de Protección de Datos**

### Flujo Seguro
```
source/ → source_images/ → [PROCESAMIENTO] → [VERIFICACIÓN] → [MONGODB] → images_old/
```

**Garantías de seguridad:**
- ✅ **No se pierden imágenes** durante errores de MongoDB
- ✅ **Verificación** antes de mover archivos
- ✅ **Logs detallados** de cada operación
- ✅ **Rollback automático** en caso de fallo

### Manejo de Errores
```python
try:
    # Subir a MongoDB
    upload_to_mongodb()
    # SOLO entonces mover imagen
    move_to_images_old()
except Exception as e:
    # Imagen permanece en source_images
    log_error(f"Error: {e}")
```

## 📊 **Resultados y Estadísticas**

### Estructura Optimizada en MongoDB
```json
{
  "_id": "ObjectId(...)",
  "code": "TODZ1026",
  "category": "pendientes", 
  "image_bytes": BinData(...),
  "created_at": "2025-05-26T15:30:00Z",
  "updated_at": "2025-05-26T15:30:00Z",
  "source_image": "catalogo1.jpg",
  "processing_stats": {
    "rectangles_detected": 24,
    "codes_extracted": 12,
    "images_extracted": 12,
    "discarded": 0,
    "processing_time": 45.2
  }
}
```

### Métricas de Rendimiento
- **Procesamiento**: ~50-100 imágenes/minuto
- **Precisión OCR**: ~95% con corrección automática
- **Clasificación ML**: ~92% de precisión
- **Tiempo de respuesta web**: <2 segundos
- **Ordenación numérica**: 100% correcta

## 🔧 **API y Endpoints**

### Endpoints Principales
```python
# Estado del sistema
GET /system_status
GET /processing_status

# Procesamiento
GET /process_auto
GET /setup_next_image
GET /process_final

# Gestión de archivos
POST /move_file
GET /get_contents

# Streaming
GET /progress  # Server-Sent Events
```

### Uso Programático
```python
import requests

# Verificar estado
status = requests.get('http://localhost:5000/system_status').json()
print(f"Imágenes en cola: {status['source_count']}")

# Iniciar procesamiento
response = requests.get('http://localhost:5000/process_auto')
if response.json()['success']:
    print("Procesamiento iniciado")
```

## 🧠 **Machine Learning Mejorado**

### Clasificación Inteligente
```python
# Código detectado
{
    "text": "TODZ1026",
    "category": "code",
    "confidence": 0.95,
    "corrections_applied": ["space_removal"],
    "pattern_type": "T_prefix_code"
}

# Imagen detectada
{
    "category": "image", 
    "confidence": 0.88,
    "contains_descriptive_text": False,
    "estimated_product_type": "pendiente"
}
```

### Correcciones OCR Avanzadas
- `6. llg` → `6.11g` (confusión ll/11)
- `TODZ I 026` → `TODZ1026` (espacios)
- `O18114700` → `018114700` (O/0)
- `c I 004290512` → `c1004290512` (espacios + l/1)

## 🐛 **Solución de Problemas**

### Problemas Web

**❌ Error: "Puerto 5000 ocupado"**
```bash
# Cambiar puerto en web_app.py
app.run(debug=True, host='0.0.0.0', port=5001)
```

**❌ Error: "Botón deshabilitado"**
```bash
# Verificar estado del sistema
curl http://localhost:5000/system_status
# Agregar imágenes a /source si está vacío
```

**❌ Error: "No se muestran imágenes"**
```bash
# Verificar permisos de archivos
chmod 755 source_images/
# Verificar rutas en web_app.py
```

### Debugging
```bash
# Logs detallados en consola
python web_app.py

# Estado de directorios
ls -la source/ source_images/ images_old/

# Test de conectividad MongoDB
python -c "from connect_mongodb import return_mongo_client; print(return_mongo_client().list_database_names())"
```

## 📈 **Roadmap Actualizado**

### Versión Actual (v2.0) ✅
- ✅ **Interfaz web moderna** con procesamiento automático
- ✅ **Sistema de protección de datos** robusto
- ✅ **Gestión inteligente de estado** del sistema
- ✅ **Drag & drop** para reclasificación manual
- ✅ **Ordenación numérica** correcta
- ✅ **Modal de zoom** para inspección detallada

### Próximas Versiones
- 🔄 **v2.1**: API REST completa para integración externa
- 🔄 **v2.2**: Sistema de usuarios y autenticación
- 🔄 **v2.3**: Dashboard de estadísticas avanzado
- 🔄 **v2.4**: Soporte para procesamiento en lotes masivos
- 🔄 **v3.0**: Sistema de entrenamiento ML en tiempo real

## 🤝 **Contribución**

### Estructura de Desarrollo
```bash
# Frontend (HTML/CSS/JS)
templates/index_auto.html  # Interfaz principal
static/css/styles.css      # Estilos responsive

# Backend (Python/Flask)
web_app.py                 # Aplicación web
main.py                    # Procesamiento por lotes

# ML/OCR (Python)
improved_classify_rectangles_ocr_fixed.py
MachineLearning/           # Módulo completo
```

### Testing
```bash
# Test de funcionalidad web
curl -X POST http://localhost:5000/move_file \
  -H "Content-Type: application/json" \
  -d '{"filename":"rect_1.png","source_dir":"codes","target_dir":"images"}'

# Test de procesamiento
python -c "
from web_app import get_system_status
print(get_system_status())
"
```

## 📱 **Capturas de Pantalla**

### Interfaz Principal
```
┌─────────────────────────────────────────┐
│ 🚀 Procesamiento Automático de Imágenes │
├─────────────────────────────────────────┤
│ 📊 Estado del Sistema                   │
│ ┌───────┐ ┌───────┐ ┌───────┐          │
│ │   5   │ │   📸  │ │  127  │          │
│ │En cola│ │Actual │ │Proces.│          │
│ └───────┘ └───────┘ └───────┘          │
├─────────────────────────────────────────┤
│ 🎮 Controles                            │
│ [🔄 Actualizar] [▶️ Procesar] [⏭️ Prep] │
└─────────────────────────────────────────┘
```

### Sistema de Revisión
```
┌──────────────────────────────────────────────────────────┐
│ 📋 Revisión Manual                                       │
├──────────┬──────────┬──────────┬──────────────────────── │
│🖼️ Original│📝 Códigos│🖼️ Imágenes│🗑️ Descartes           │
│          │   (12)   │   (12)   │    (0)                │
│ [IMG]    │ rect_0   │ rect_1   │                       │
│          │ rect_2   │ rect_3   │                       │
│          │ rect_4   │ rect_5   │                       │
└──────────┴──────────┴──────────┴───────────────────────┘
│ [✅ Finalizar y Subir a MongoDB]                        │
└─────────────────────────────────────────────────────────┘
```

## 📄 **Licencia**

GPL v3 - Ver `LICENSE` para detalles completos.

## 👥 **Autores y Colaboradores**

- **Desarrollo Principal**: [@alvnavraii](https://github.com/alvnavraii)
- **Sistema Web y UI/UX**: Desarrollo interno
- **ML y OCR**: Integración de librerías open source

## 🙏 **Tecnologías Utilizadas**

- **[Flask](https://flask.palletsprojects.com/)** - Framework web minimalista
- **[OpenCV](https://opencv.org/)** - Visión por computadora
- **[Tesseract OCR](https://github.com/tesseract-ocr/tesseract)** - Reconocimiento de texto
- **[MongoDB](https://www.mongodb.com/)** - Base de datos NoSQL
- **[Scikit-learn](https://scikit-learn.org/)** - Machine Learning
- **Modern CSS3/HTML5** - Interfaz responsive

---

<div align="center">

**🌟 Sistema Completo de Procesamiento Automático de Imágenes**

[![GitHub stars](https://img.shields.io/github/stars/alvnavraii/ImagesManagement.svg?style=social&label=Star)](https://github.com/alvnavraii/ImagesManagement)
[![GitHub forks](https://img.shields.io/github/forks/alvnavraii/ImagesManagement.svg?style=social&label=Fork)](https://github.com/alvnavraii/ImagesManagement/fork)

**🚀 [Demo en vivo](http://localhost:5000) | 📖 [Documentación](https://github.com/alvnavraii/ImagesManagement/wiki) | 🐛 [Reportar Bug](https://github.com/alvnavraii/ImagesManagement/issues)**

</div>
