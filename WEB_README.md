# 🖼️ Interfaz Web para Gestión de Imágenes

## 📋 Descripción

Esta aplicación web proporciona una interfaz visual intuitiva para el procesamiento automático de imágenes que contienen códigos de productos. Permite:

- **Drag & Drop**: Arrastra imágenes directamente al navegador
- **Procesamiento Automático**: Extrae códigos y productos automáticamente
- **Revisión Manual**: Reorganiza archivos cuando hay discrepancias
- **Integración MongoDB**: Almacena resultados automáticamente

## 🚀 Inicio Rápido

### 1. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 2. Configurar MongoDB
Asegúrate de que MongoDB esté ejecutándose y configurado en `connect_mongodb.py`

### 3. Ejecutar aplicación
```bash
python start_web.py
```

### 4. Abrir navegador
Visita: http://localhost:5000

## 🔧 Funcionalidades

### Subida de Imágenes
- **Drag & Drop**: Arrastra una imagen al área designada
- **Click to Upload**: Haz clic para seleccionar archivo
- **Formatos soportados**: PNG, JPG, JPEG (máx. 16MB)

### Procesamiento Automático
1. **Extracción**: Detecta y extrae rectángulos de la imagen
2. **Clasificación**: Separa códigos, imágenes y descartes
3. **Análisis**: Verifica coincidencias entre códigos e imágenes

### Revisión Manual (cuando es necesaria)

#### ¿Cuándo aparece?
- Número de códigos ≠ número de imágenes
- Hay archivos en la carpeta de descartes

#### Funcionalidades de revisión:
- **Vista de 3 columnas**: Códigos, Imágenes, Descartes
- **Miniaturas**: Vista previa de cada archivo
- **Drag & Drop entre carpetas**: Reorganiza archivos arrastrando
- **Contadores en tiempo real**: Muestra cantidad en cada carpeta
- **Actualización automática**: Refleja cambios inmediatamente

### Finalización
- **Procesamiento final**: Empareja códigos con imágenes
- **Subida a MongoDB**: Almacena resultados en base de datos
- **Categorización**: Asigna categorías automáticamente

## 🏗️ Estructura de Archivos

```
ImagesManagement/
├── web_app.py              # Aplicación Flask principal
├── start_web.py            # Script de inicio
├── templates/
│   └── index.html          # Interfaz de usuario
├── uploads/                # Imágenes subidas
├── codes_output/           # Códigos extraídos
├── images_output/          # Imágenes de productos
├── discards_output/        # Archivos descartados
└── rectangles_output/      # Rectángulos detectados
```

## 🔗 API Endpoints

### `POST /upload`
Procesa imagen subida
- **Input**: Archivo de imagen
- **Output**: Estadísticas de procesamiento

### `GET /get_contents`
Obtiene contenido de directorios
- **Output**: Listado de archivos en cada carpeta

### `POST /move_file`
Mueve archivo entre directorios
- **Input**: filename, source_dir, target_dir
- **Output**: Confirmación de movimiento

### `GET /process_final`
Finaliza proceso y sube a MongoDB
- **Output**: Confirmación de subida

### `GET /image/<directory>/<filename>`
Sirve imágenes para vista previa
- **Output**: Archivo de imagen

## 🎨 Características de la Interfaz

### Diseño Responsivo
- Grid layout adaptativo
- Compatible con móviles y escritorio
- Colores distintivos por tipo de archivo

### Drag & Drop Avanzado
- **Feedback visual**: Resalta áreas de drop
- **Estados de arrastre**: Indicadores visuales claros
- **Prevención de errores**: No permite drops inválidos

### Estados de la Aplicación
- **Loading**: Spinner durante procesamiento
- **Success/Error**: Mensajes de estado claros
- **Warnings**: Alertas para revisión manual

## 🔧 Configuración Avanzada

### Variables de Entorno
Configura en `.env`:
```env
MONGODB_URI=mongodb://localhost:27017/
DB_NAME=images_db
COLLECTION_NAME=codes_images
```

### Personalización de Categorías
Modifica la función de categorización en `web_app.py`:
```python
# En process_final()
category = 'tu_categoria_personalizada'
```

## 🐛 Resolución de Problemas

### Error de conexión MongoDB
```bash
# Verificar que MongoDB esté ejecutándose
sudo systemctl status mongod
sudo systemctl start mongod
```

### Error de dependencias
```bash
# Reinstalar dependencias
pip install -r requirements.txt --force-reinstall
```

### Permisos de archivos
```bash
# Dar permisos de ejecución
chmod +x start_web.py
```

### Puerto ocupado
```bash
# Cambiar puerto en web_app.py
app.run(debug=True, host='0.0.0.0', port=5001)
```

## 📊 Flujo de Trabajo Típico

1. **Inicio**: Ejecutar `python start_web.py`
2. **Subida**: Arrastrar imagen al navegador
3. **Espera**: Ver progreso de procesamiento
4. **Revisión** (si es necesaria):
   - Revisar archivos en cada columna
   - Mover archivos entre columnas arrastrando
   - Verificar que códigos e imágenes coincidan
5. **Finalización**: Hacer clic en "Finalizar Proceso"
6. **Confirmación**: Ver mensaje de éxito

## 🚀 Extensiones Futuras

- **Batch processing**: Procesar múltiples imágenes
- **Historial**: Ver imágenes procesadas anteriormente
- **Configuración**: Panel de ajustes en la interfaz
- **Exportación**: Descargar resultados en diferentes formatos
- **API REST**: Endpoints para integración externa

---

**💡 Consejo**: Para mejores resultados, usa imágenes con buena calidad y códigos claramente visibles.
