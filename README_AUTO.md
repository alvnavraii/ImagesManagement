# 🚀 Sistema de Procesamiento Automático de Imágenes

Sistema completamente automatizado para procesar imágenes y extraer códigos y productos usando OCR.

## 📁 Estructura de Directorios

```
/source/           # Imágenes pendientes de procesar (cola)
/images_sources/   # Imagen actual siendo procesada (solo una)
/images_old/       # Imágenes ya procesadas (archivo)
/codes_output/     # Códigos extraídos de la imagen actual
/images_output/    # Imágenes de productos extraídas
/discards_output/  # Elementos descartados automáticamente
```

## 🔄 Flujo Automatizado

1. **Preparación**: Coloca todas las imágenes a procesar en `/source/`
2. **Inicio**: El sistema automáticamente mueve una imagen de `/source/` a `/images_sources/`
3. **Procesamiento**: 
   - Detecta rectángulos en la imagen
   - Clasifica automáticamente usando OCR
   - Separa códigos, imágenes y descartes
4. **Finalización**:
   - Imagen procesada se mueve a `/images_old/`
   - Siguiente imagen se mueve automáticamente de `/source/` a `/images_sources/`
5. **Repetición**: Continúa hasta que `/source/` esté vacía

## 🌐 Interfaces Web

### Procesamiento Automático (Principal)
- **URL**: http://localhost:5000
- **Características**:
  - Dashboard de estado en tiempo real
  - Procesamiento completamente automatizado
  - Zoom de imágenes mejorado
  - Revisión manual cuando sea necesario

### Procesamiento Manual (Legacy)
- **URL**: http://localhost:5000/manual
- **Características**:
  - Upload manual de imágenes
  - Funcionalidad drag & drop eliminada
  - Interfaz clásica

## 🚀 Cómo Usar

### 1. Preparar Imágenes
```bash
# Copiar todas las imágenes a procesar
cp *.jpg /path/to/ImagesManagement/source/
```

### 2. Iniciar Sistema
```bash
cd /path/to/ImagesManagement
python web_app.py
```

### 3. Preparar Primera Imagen
- Abre http://localhost:5000
- Click en "⏭️ Preparar Siguiente" para mover la primera imagen a `/images_sources/`

### 4. Procesar Automáticamente
- Click en "▶️ Procesar Automático"
- El sistema procesa la imagen actual
- Automáticamente prepara la siguiente imagen
- Continúa hasta completar todas las imágenes

### 5. Revisión Manual (si es necesaria)
- Si los números no coinciden, aparece la interfaz de revisión
- Zoom de imágenes con un click
- Verificar clasificación automática
- Click en "✅ Finalizar y Subir a MongoDB"

## 🎮 Controles Principales

| Botón | Función |
|-------|---------|
| 🔄 Actualizar Estado | Refresca información del sistema |
| ▶️ Procesar Automático | Inicia procesamiento de imagen actual |
| ⏭️ Preparar Siguiente | Mueve siguiente imagen de source a images_sources |
| ✅ Finalizar y Subir | Completa proceso y sube a MongoDB |
| 🔄 Procesar Siguiente Automático | Finaliza actual y procesa siguiente |

## 📊 Estado del Sistema

El dashboard muestra:
- **En cola**: Imágenes pendientes en `/source/`
- **Actual**: Imagen siendo procesada
- **Procesadas**: Imágenes completadas en `/images_old/`

## 🔧 API Endpoints

- `GET /` - Interfaz principal (automática)
- `GET /manual` - Interfaz manual (legacy)
- `GET /process_auto` - Procesar imagen actual
- `GET /system_status` - Estado del sistema
- `GET /setup_next_image` - Preparar siguiente imagen
- `POST /upload` - Upload manual (legacy)
- `GET /get_contents` - Contenido de directorios de salida
- `GET /process_final` - Finalizar y subir a MongoDB

## 🎯 Ventajas del Sistema Automatizado

1. **Sin Intervención Manual**: Procesa todas las imágenes automáticamente
2. **Gestión de Archivos**: Organiza automáticamente los archivos procesados
3. **Interfaz Moderna**: Dashboard en tiempo real con estado del sistema
4. **Zoom Mejorado**: Revisión de imágenes con un solo click
5. **Flujo Continuo**: Procesa lote completo sin parar
6. **Trazabilidad**: Historial completo en `/images_old/`

## 🚨 Solución de Problemas

### No hay imagen para procesar
- Verificar que hay imágenes en `/source/`
- Click en "⏭️ Preparar Siguiente"

### Error en procesamiento
- Verificar logs en consola del navegador
- Comprobar que todos los directorios existen
- Revisar permisos de archivos

### Zoom no funciona
- Verificar que el servidor Flask esté corriendo
- Comprobar URLs de imágenes en Network tab (F12)
- Verificar que las imágenes existan en los directorios

## 📈 Monitoreo

El sistema proporciona logs detallados en:
- **Consola del servidor**: Logs de Python/Flask
- **Consola del navegador**: Logs de JavaScript
- **Interfaz web**: Progreso en tiempo real

¡El sistema está completamente automatizado y listo para procesar lotes grandes de imágenes! 🎉
