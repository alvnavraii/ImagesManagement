# ImagesManagement - Procesamiento de Imágenes de Joyería

Sistema para procesamiento y clasificación automática de imágenes de joyería.

## 📁 Estructura del Proyecto

```
ImagesManagement/
├── main.py                    # Aplicación principal OCR
├── extract_rectangles.py     # Extracción de rectángulos
├── classify_rectangles.py    # Clasificación de rectángulos
├── ml_bridge.py              # Puente hacia sistema ML
│
├── MachineLearning/          # 🤖 Sistema ML completo
│   ├── classify_image.py     # Clasificar imágenes individuales
│   ├── setup_step_by_step.py # Configuración paso a paso
│   ├── test_system.py        # Pruebas del sistema
│   └── [otros archivos ML]   # Modelos, configuración, etc.
│
├── codes_output/             # Códigos de producto detectados
├── images_output/            # Categorías de imagen detectadas
└── rectangles_output/        # Rectángulos extraídos
```

## 🚀 Inicio Rápido

### Para tu aplicación OCR existente:
```bash
python main.py
```

### Para usar Machine Learning (clasificación automática):
```bash
# 1. Configurar ML (solo una vez)
cd MachineLearning
python setup_step_by_step.py

# 2. Clasificar una imagen
python classify_image.py /path/to/imagen.jpg

# 3. Probar el sistema
python test_system.py
```

## 🔗 Integración con Machine Learning

Para integrar ML en tu aplicación principal:

```python
# En tu main.py
import sys
sys.path.append('./MachineLearning')
from image_category_classifier import ImageCategoryClassifier

classifier = ImageCategoryClassifier()
result = classifier.classify_image('/path/to/imagen.jpg')

if result['final_category'] == 'product_code':
    # Procesar como código de producto
    save_to_codes_output(result['product_code'])
else:
    # Procesar como categoría de imagen
    save_to_images_output(result['category'])
```

## 📋 Flujo de Trabajo

1. **OCR Tradicional**: Tu sistema actual extrae texto de imágenes
2. **ML Opcional**: El sistema ML clasifica automáticamente el texto como:
   - 📝 Código de producto (ej: "c1004290512")
   - 🏷️ Categoría de imagen (ej: "anillos")

## 🛠️ Configuración

### Dependencias principales (tu app):
```bash
pip install opencv-python pillow pytesseract
```

### Dependencias ML (opcional):
```bash
cd MachineLearning
pip install -r requirements.txt
```

## 📞 Información sobre ML

Para información completa sobre el sistema de Machine Learning:
```bash
python ml_bridge.py
```

O consulta: `MachineLearning/README.md`
    """
    Identifica si el contenido es código o descripción de imagen
    """
    is_code = quick_classify(content)
    prediction, confidence = classify_with_confidence(content)
    
    return {
        'is_code': is_code,
        'type': prediction,
        'confidence': confidence,
        'action': 'process_as_code' if is_code else 'process_as_image'
    }

# Ejemplo de uso en tu aplicación
user_input = "def calculate_area(width, height): return width * height"
result = identify_content(user_input)

if result['is_code']:
    print("Detectado código fuente")
    # Procesar como código
else:
    print("Detectado descripción de imagen")
    # Procesar como imagen
```

## 📝 Casos de Uso

### 1. Filtrado Automático
```python
def auto_categorize_uploads(content_list):
    categorized = {'code': [], 'images': []}
    
    for content in content_list:
        if quick_classify(content):
            categorized['code'].append(content)
        else:
            categorized['images'].append(content)
    
    return categorized
```

### 2. Análisis de Confianza
```python
def smart_classification(content):
    prediction, confidence = classify_with_confidence(content)
    
    if confidence > 0.8:
        return f"Muy seguro: {prediction}"
    elif confidence > 0.6:
        return f"Moderadamente seguro: {prediction}"
    else:
        return "Clasificación incierta, requiere revisión manual"
```

### 3. Procesamiento por Lotes
```python
def process_mongodb_collection():
    from production_classifier import ProductionClassifier
    import pymongo
    
    classifier = ProductionClassifier()
    client = pymongo.MongoClient("mongodb://localhost:27017/")
    db = client['images_db']
    collection = db['codes_images']
    
    # Clasificar todos los documentos
    for doc in collection.find():
        if 'content' in doc:
            result = classifier.classify_content(doc['content'])
            
            # Actualizar documento con clasificación
            collection.update_one(
                {'_id': doc['_id']},
                {'$set': {
                    'ml_prediction': result['prediction'],
                    'ml_confidence': result['confidence'],
                    'ml_is_code': result['is_code']
                }}
            )
```

## 🔧 Personalización

### Agregar Nuevas Características

Para agregar características personalizadas, edita `ml_classifier.py`:

```python
def extract_custom_features(self, text: str) -> Dict[str, float]:
    """Agregar características personalizadas"""
    
    # Ejemplo: detectar URLs
    url_count = len(re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+])+', text))
    
    # Ejemplo: detectar emails
    email_count = len(re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text))
    
    return {
        'url_count': url_count,
        'email_count': email_count,
        'has_urls': 1 if url_count > 0 else 0,
        'has_emails': 1 if email_count > 0 else 0
    }
```

### Ajustar Umbrales

Modifica `config.py` para ajustar umbrales de clasificación:

```python
CLASSIFICATION_THRESHOLDS = {
    'high_confidence': 0.9,    # Muy seguro
    'medium_confidence': 0.7,  # Moderadamente seguro
    'low_confidence': 0.5      # Poco seguro
}
```

## 🛠️ Troubleshooting

### Problema: Modelo no entrena
- Verificar conexión a MongoDB
- Verificar que hay datos en la colección
- Revisar formato de los datos

### Problema: Baja precisión
- Aumentar cantidad de datos de entrenamiento
- Ajustar parámetros del modelo
- Agregar más características relevantes

### Problema: Error de importación
- Verificar que todas las dependencias están instaladas
- Verificar la ruta del proyecto en sys.path

## 📈 Monitoreo y Mejora Continua

### Logs de Clasificación
```python
import logging
from config import LOGGING_CONFIG

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

def classify_with_logging(content):
    result = classify_with_confidence(content)
    logger.info(f"Clasificación: {result[0]} (confianza: {result[1]:.2f})")
    return result
```

### Métricas de Rendimiento
```python
def evaluate_model_performance():
    """Evaluar rendimiento del modelo en producción"""
    # Implementar métricas personalizadas
    # Almacenar resultados para análisis
    pass
```

## 🤝 Contribuciones

Para contribuir al proyecto:

1. Crea pruebas para nuevas características
2. Mantén la documentación actualizada
3. Sigue las convenciones de código existentes
4. Agrega ejemplos de uso

## 📞 Soporte

Para dudas o problemas:
- Revisar logs en `/logs/ml_classifier.log`
- Ejecutar pruebas con `python test_classifier.py`
- Verificar configuración en `config.py`

---

**Nota**: Este clasificador está diseñado para distinguir entre código fuente y descripciones de imágenes basándose en características textuales. Su precisión depende de la calidad y cantidad de datos de entrenamiento disponibles en MongoDB.
