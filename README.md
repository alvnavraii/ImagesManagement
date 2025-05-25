# ImagesManagement - Sistema de Procesamiento de Imágenes de Joyería

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green.svg)
![MongoDB](https://img.shields.io/badge/MongoDB-4.x+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

Sistema automatizado para el procesamiento, clasificación y almacenamiento de imágenes de productos de joyería. Utiliza técnicas de visión por computadora, OCR y machine learning para extraer códigos de producto e imágenes de catálogos escaneados.

## 🎯 **Objetivo Principal**

Automatizar el proceso de digitalización de catálogos de joyería mediante:
- **Extracción automática** de rectángulos (códigos + imágenes) de imágenes escaneadas
- **Clasificación inteligente** entre códigos de producto e imágenes usando ML
- **Corrección OCR** para errores comunes de lectura
- **Almacenamiento estructurado** en MongoDB con emparejamiento automático

## 🚀 **Características Principales**

### 📸 **Procesamiento de Imágenes**
- **Detección de rectángulos** automática usando OpenCV
- **Extracción de celdas** individuales de catálogos escaneados
- **Preprocesamiento** para mejorar calidad de OCR
- **Filtrado de imágenes en blanco** o irrelevantes

### 🔤 **OCR Inteligente**
- **Extracción de texto** usando Tesseract OCR
- **Corrección automática** de errores comunes ('ll' ↔ '11')
- **Detección de patrones** específicos de códigos de joyería
- **Soporte multiidioma** (español/inglés)

### 🤖 **Machine Learning**
- **Clasificador automático** código vs imagen
- **Detección de texto descriptivo** (pesos, medidas)
- **Soporte para códigos T** (TODZ1026, TODZ1002)
- **Sistema de confianza** para validación

### 🗄️ **Gestión de Datos**
- **Almacenamiento en MongoDB** con metadatos completos
- **Emparejamiento automático** código-imagen
- **Sistema de categorías** (anillos, pendientes, collares)
- **Historial de procesamiento** con timestamps

## 📁 **Estructura del Proyecto**

```
ImagesManagement/
├── 📄 main.py                                    # Script principal
├── 🔧 improved_classify_rectangles_ocr_fixed.py  # Procesador mejorado
├── 📐 extract_rectangles.py                      # Extracción de rectángulos
├── 🔗 connect_mongodb.py                         # Conexión a MongoDB
├── 📁 MachineLearning/                           # Módulo de ML
│   ├── 🧠 image_category_classifier.py          # Clasificador principal
│   ├── ⚙️ jewelry_integration.py                # Integración ML
│   ├── 🤖 jewelry_ml_classifier.py              # Clasificador ML
│   ├── 📋 jewelry_config.py                     # Configuración
│   └── 💾 models/jewelry_classifier.pkl         # Modelo entrenado
├── 📁 source_images/                            # Imágenes a procesar
├── 📁 rectangles_output/                        # Rectángulos extraídos
├── 📁 codes_output/                             # Códigos detectados
├── 📁 images_output/                            # Imágenes de productos
├── 📁 discards_output/                          # Elementos descartados
└── 📁 images_old/                               # Imágenes procesadas
```

## 🛠️ **Instalación**

### Prerrequisitos
```bash
# Python 3.8+
# MongoDB 4.0+
# Tesseract OCR
```

### Dependencias
```bash
pip install -r requirements.txt
```

**Principales librerías:**
- `opencv-python` - Procesamiento de imágenes
- `pytesseract` - OCR
- `pymongo` - Base de datos MongoDB
- `scikit-learn` - Machine Learning
- `numpy`, `pandas` - Procesamiento de datos
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

# Windows
# Descargar desde: https://github.com/UB-Mannheim/tesseract/wiki
```

## 🚀 **Uso**

### Procesamiento Básico
```bash
# Colocar imágenes en source_images/
python main.py
```

### Flujo de Procesamiento
1. **📥 Input**: Imágenes de catálogos en `source_images/`
2. **🔍 Extracción**: Detecta y extrae rectángulos
3. **🤖 Clasificación**: ML separa códigos vs imágenes
4. **📝 OCR**: Extrae texto de códigos
5. **🔗 Emparejamiento**: Asocia códigos con imágenes
6. **💾 Almacenamiento**: Guarda en MongoDB
7. **📁 Archivo**: Mueve imagen procesada a `images_old/`

### Ejemplo de Uso Programático
```python
from improved_classify_rectangles_ocr_fixed import process_rectangles_improved
from extract_rectangles import extract_rectangles
from connect_mongodb import return_mongo_client

# Extraer rectángulos
extract_rectangles(
    image_path="source_images/catalogo.jpg",
    output_dir="rectangles_output"
)

# Clasificar rectángulos
process_rectangles_improved(
    input_dir="rectangles_output",
    codes_dir="codes_output", 
    images_dir="images_output",
    discards_dir="discards_output"
)

# Conectar a MongoDB
client = return_mongo_client()
```

## 🧠 **Sistema de Machine Learning**

### Clasificador de Imágenes
El sistema utiliza un clasificador entrenado para distinguir entre:

**📝 Códigos de Producto:**
- Códigos alfanuméricos (ej: `TODZ1026`, `c1004290512`)
- Códigos numéricos largos (ej: `018114700`)
- Patrones específicos de joyería

**🖼️ Imágenes de Producto:**
- Fotos de anillos, pendientes, collares
- Siluetas y formas de joyería
- Imágenes con texto descriptivo

### Detección de Texto Descriptivo
Automáticamente descarta texto irrelevante:
- ✅ **Pesos**: `6.11g`, `7.3g`, `1.9kg`
- ✅ **Medidas**: `2.5cm`, `15.8mm`
- ✅ **Materiales**: `18K`, `ORO`, `PLATA`
- ✅ **Tallas**: `M`, `XL`, `7.5`

### Corrección OCR
Sistema avanzado de corrección para errores comunes:
- `6. llg` → `6.11g` (confusión ll/11)
- `TODZ I 026` → `TODZ1026` (espacios)
- `O18114700` → `018114700` (O/0)

## 📊 **Resultados**

### Estructura en MongoDB
```json
{
  "_id": "ObjectId(...)",
  "code": "TODZ1026",
  "category": "pendientes", 
  "image_bytes": BinData(...),
  "created_at": "2025-05-25T10:30:00Z",
  "updated_at": "2025-05-25T10:30:00Z",
  "ml_classification": {
    "type": "product_code",
    "confidence": 0.95,
    "method": "ml"
  }
}
```

### Estadísticas de Procesamiento
- **Precisión OCR**: ~95% con corrección automática
- **Clasificación ML**: ~92% de precisión
- **Procesamiento**: ~50-100 imágenes/minuto
- **Emparejamiento**: 95% automático código-imagen

## 🔧 **Configuración Avanzada**

### Parámetros de Detección
```python
# En extract_rectangles.py
THRESHOLD_AREA = 1000      # Área mínima de rectángulos
BINARY_THRESHOLD = 200     # Umbral de binarización
CONTOUR_APPROX = 0.02      # Aproximación de contornos
```

### Configuración OCR
```python
# En improved_classify_rectangles_ocr_fixed.py
OCR_CONFIG = '--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
```

### Umbrales ML
```python
# En MachineLearning/jewelry_config.py
CLASSIFICATION_THRESHOLDS = {
    'high_confidence': 0.8,
    'medium_confidence': 0.6,
    'low_confidence': 0.4
}
```

## 🐛 **Solución de Problemas**

### Problemas Comunes

**❌ Error: "No se detectan rectángulos"**
```bash
# Ajustar umbral de área en extract_rectangles.py
THRESHOLD_AREA = 500  # Reducir para imágenes pequeñas
```

**❌ Error: "OCR no detecta texto"**
```bash
# Verificar instalación de Tesseract
tesseract --version
# Instalar idiomas adicionales
sudo apt install tesseract-ocr-spa tesseract-ocr-eng
```

**❌ Error: "Conexión MongoDB"**
```bash
# Verificar MongoDB ejecutándose
sudo systemctl status mongod
# Verificar variables de entorno
cat .env
```

### Logs de Depuración
```bash
# Activar logs detallados
export DEBUG=1
python main.py
```

## 🤝 **Contribución**

### Estructura de Commits
```bash
git commit -m "feat: nueva funcionalidad OCR"
git commit -m "fix: corrección clasificador ML" 
git commit -m "docs: actualización README"
git commit -m "refactor: limpieza código"
```

### Desarrollo
1. Fork del proyecto
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -m 'feat: nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📈 **Roadmap**

### Versión Actual (v1.0)
- ✅ Extracción automática de rectángulos
- ✅ Clasificación ML básica
- ✅ OCR con corrección de errores
- ✅ Almacenamiento MongoDB

### Próximas Versiones
- 🔄 **v1.1**: API REST para integración
- 🔄 **v1.2**: Interface web para revisión manual
- 🔄 **v1.3**: Soporte para múltiples formatos de imagen
- 🔄 **v2.0**: Sistema de entrenamiento ML personalizable

## 📄 **Licencia**

Este proyecto está bajo la Licencia MIT. Ver `LICENSE` para más detalles.

## 👥 **Autores**

- **Desarrollo Principal**: [@alvnavraii](https://github.com/alvnavraii)
- **Contribuciones**: Ver [Contributors](https://github.com/alvnavraii/ImagesManagement/contributors)

## 🙏 **Agradecimientos**

- OpenCV comunidad por las herramientas de visión por computadora
- Tesseract OCR por el motor de reconocimiento de texto
- MongoDB por la base de datos NoSQL
- Scikit-learn por las herramientas de Machine Learning

---

<div align="center">

**⭐ Si este proyecto te es útil, considera darle una estrella!**

[![GitHub stars](https://img.shields.io/github/stars/alvnavraii/ImagesManagement.svg?style=social&label=Star)](https://github.com/alvnavraii/ImagesManagement)

</div>
