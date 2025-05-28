from flask import Flask, render_template, request, jsonify, send_file, Response
import os
import shutil
import time
import json
import queue
import threading
from werkzeug.utils import secure_filename
import cv2
from connect_mongodb import return_mongo_client
from extract_rectangles import extract_rectangles
# IMPORTAR DIRECTAMENTE LAS FUNCIONES QUE FUNCIONAN
from main import pair_and_upload_codes_images_by_order
# Importar la función original pero la vamos a modificar
import sys
import re
from pathlib import Path
from datetime import datetime

# NUEVO: Importar clasificador con categorías
try:
    from enhanced_classifier_with_categories import process_rectangles_with_categories, EnhancedJewelryClassifier
    ENHANCED_CATEGORIES_AVAILABLE = True
    print("✅ Clasificador con categorías cargado")
except ImportError as e:
    print(f"⚠️ Clasificador con categorías no disponible: {e}")
    ENHANCED_CATEGORIES_AVAILABLE = False

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Cola para mensajes de progreso
progress_queue = queue.Queue()

# Crear directorios necesarios
for directory in ['uploads', 'codes_output', 'images_output', 'discards_output', 'rectangles_output', 'source_images', 'images_old', 'source']:
    if not os.path.exists(directory):
        os.makedirs(directory)

def clean_output_dirs(*dirs):
    """Limpia los directorios de salida - MISMA FUNCIÓN QUE EN MAIN.PY"""
    for d in dirs:
        if os.path.exists(d):
            for f in os.listdir(d):
                fp = os.path.join(d, f)
                if os.path.isfile(fp):
                    os.remove(fp)

def send_progress(message, step=None, total=None):
    """Envía mensaje de progreso"""
    progress_data = {
        'message': message,
        'timestamp': time.strftime('%H:%M:%S'),
        'step': step,
        'total': total
    }
    progress_queue.put(progress_data)
    print(f"[{progress_data['timestamp']}] {message}")

def get_image_from_sources():
    """Obtiene la imagen de source_images (debe haber solo una)"""
    source_images = 'source_images'
    if not os.path.exists(source_images):
        return None
    
    files = [f for f in os.listdir(source_images) 
             if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    if len(files) == 0:
        return None
    elif len(files) == 1:
        return os.path.join(source_images, files[0])
    else:
        # Si hay más de una imagen, tomar la primera
        send_progress(f"⚠️ Hay {len(files)} imágenes en source_images, procesando la primera")
        return os.path.join(source_images, files[0])

def move_next_image_to_sources():
    """Mueve la siguiente imagen de source a source_images"""
    source_dir = 'source'
    source_images = 'source_images'
    
    if not os.path.exists(source_dir):
        send_progress("❌ Directorio source no existe")
        return False
    
    # Obtener archivos de imagen de source
    source_files = [f for f in os.listdir(source_dir) 
                   if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    if not source_files:
        send_progress("✅ No hay más imágenes en source - proceso completado")
        return False
    
    # Tomar la primera imagen
    source_file = source_files[0]
    source_path = os.path.join(source_dir, source_file)
    target_path = os.path.join(source_images, source_file)
    
    try:
        shutil.move(source_path, target_path)
        send_progress(f"📁 Movida imagen: {source_file} → source_images")
        return True
    except Exception as e:
        send_progress(f"❌ Error moviendo imagen: {e}")
        return False

def move_processed_image_to_old(image_path):
    """Mueve la imagen procesada de source_images a images_old"""
    images_old = 'images_old'
    
    if not os.path.exists(image_path):
        send_progress("❌ Imagen a mover no existe")
        return False
    
    filename = os.path.basename(image_path)
    target_path = os.path.join(images_old, filename)
    
    try:
        shutil.move(image_path, target_path)
        send_progress(f"📁 Imagen procesada movida a images_old: {filename}")
        return True
    except Exception as e:
        send_progress(f"❌ Error moviendo imagen a old: {e}")
        return False

def get_system_status():
    """Obtiene el estado del sistema (cuántas imágenes quedan)"""
    source_dir = 'source'
    images_sources = 'source_images'
    images_old = 'images_old'
    
    status = {
        'source_count': 0,
        'current_image': None,
        'processed_count': 0,
        'total_original': 0
    }
    
    # Contar imágenes en source
    if os.path.exists(source_dir):
        status['source_count'] = len([f for f in os.listdir(source_dir) 
                                     if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    
    # Imagen actual en images_sources
    if os.path.exists(images_sources):
        current_files = [f for f in os.listdir(images_sources) 
                        if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        status['current_image'] = current_files[0] if current_files else None
    
    # Imágenes procesadas
    if os.path.exists(images_old):
        status['processed_count'] = len([f for f in os.listdir(images_old) 
                                       if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    
    # Total original
    status['total_original'] = status['source_count'] + (1 if status['current_image'] else 0) + status['processed_count']
    
    return status

def get_directory_contents(directory):
    """Obtiene el contenido de un directorio con metadatos, ordenado numéricamente"""
    if not os.path.exists(directory):
        return []
    
    files = []
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath) and filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            files.append({
                'name': filename,
                'path': filepath,
                'size': os.path.getsize(filepath)
            })
    
    # Función para extraer el número del nombre del archivo
    def extract_rect_number(filename):
        match = re.search(r'rect_(\d+)', filename)
        return int(match.group(1)) if match else float('inf')
    
    # Ordenar por número de rectángulo
    files.sort(key=lambda x: extract_rect_number(x['name']))
    
    return files

def get_directory_contents_with_categories(directory):
    """Obtiene contenido de directorio CON información de categorías de joyería"""
    if not os.path.exists(directory):
        return []
    
    files = []
    
    print(f"Buscando archivos de imagen y categorías en {directory}")
    all_files = os.listdir(directory)
    image_files = [f for f in all_files if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    json_files = [f for f in all_files if f.lower().endswith('.json')]
    
    print(f"Encontrados {len(image_files)} archivos de imagen y {len(json_files)} archivos JSON")
    
    for filename in image_files:
        filepath = os.path.join(directory, filename)
        if os.path.isfile(filepath):
            # Información básica del archivo
            file_info = {
                'name': filename,
                'path': filepath,
                'size': os.path.getsize(filepath),
                'category': 'sin_categoria',
                'category_display': '❓ Sin Categoría (0%)',
                'css_class': 'category-unknown',
                'jewelry_confidence': 0.0,
                'confidence_level': 'baja'
            }
            
            # Buscar archivo JSON de categoría correspondiente
            base_name = os.path.splitext(filename)[0]
            category_json_path = os.path.join(directory, f"{base_name}_category.json")
            
            print(f"Verificando JSON para {filename}: {category_json_path}")
            print(f"¿Existe? {os.path.exists(category_json_path)}")
            
            if os.path.exists(category_json_path):
                try:
                    import json
                    with open(category_json_path, 'r', encoding='utf-8') as f:
                        category_data = json.load(f)
                    
                    # Obtener la categoría y crear un nombre de visualización adecuado
                    category = category_data.get('category', 'sin_categoria')
                    
                    print(f"📋 Datos de categoría para {filename}: {category} (Confianza: {category_data.get('confidence', 0.0)})")
                    
                    # Convertir la categoría a formato de visualización con emoji
                    category_emojis = {
                        'pendientes': '👂',
                        'anillos': '💍',
                        'collares': '📿',
                        'pulseras': '⌚',
                        'colgantes': '🧿',
                        'colgantes y collares': '🔗',
                        'sin_categoria': '❓'
                    }
                    
                    emoji = category_emojis.get(category, '🔹')
                    
                    # Usar directamente category_display del JSON si existe
                    if category_data.get('category_display'):
                        category_display = category_data.get('category_display')
                        # Asegurarse de que tenga emoji
                        if not any(emoji in category_display for emoji in category_emojis.values()):
                            category_display = f"{emoji} {category_display}"
                    else:
                        # Crear un nombre de visualización a partir de la categoría
                        category_display = category.replace('_', ' ').title()
                        category_display = f"{emoji} {category_display}"
                    
                    # Determinar el nivel de confianza basado en el valor numérico
                    confidence = category_data.get('confidence', 0.0)
                    confidence_percent = int(confidence * 100)
                    
                    # Añadir el porcentaje al display
                    if '%' not in category_display:
                        category_display = f"{category_display} ({confidence_percent}%)"
                        
                    if confidence >= 0.85:
                        confidence_level = 'alta'
                    elif confidence >= 0.6:
                        confidence_level = 'media'
                    else:
                        confidence_level = 'baja'
                    
                    # Asegurarse de que la clase CSS existe
                    css_class = f"category-{category.replace(' y ', '-').replace(' ', '-')}"
                    if category == 'sin_categoria':
                        css_class = 'category-unknown'
                    
                    # Actualizar información con datos de categoría
                    file_info.update({
                        'category': category,
                        'category_display': category_display,
                        'css_class': css_class,
                        'jewelry_confidence': confidence,
                        'confidence_level': confidence_level,
                        'timestamp': category_data.get('timestamp', '')
                    })
                    
                    print(f"✅ Categoría asignada: {file_info['category_display']}")
                    
                except Exception as e:
                    import traceback
                    print(f"❌ Error leyendo categoría para {filename}: {str(e)}")
                    traceback.print_exc()
            else:
                print(f"⚠️ No se encontró archivo JSON de categoría para {filename}")
            
            files.append(file_info)
    
    # Función para extraer el número del nombre del archivo
    def extract_rect_number(filename):
        match = re.search(r'rect_(\d+)', filename)
        return int(match.group(1)) if match else float('inf')
    
    # Ordenar por número de rectángulo
    files.sort(key=lambda x: extract_rect_number(x['name']))
    
    return files

def process_rectangles_web_version(input_dir, codes_dir, images_dir, discards_dir):
    """
    Versión para web CON CATEGORÍAS DE JOYERÍA
    Adaptada para funcionar como en main.py pero SIN SUFIJOS en los archivos descartados
    """
    # Importamos las funciones necesarias pero implementamos nuestra propia versión del procesamiento
    from improved_classify_rectangles_ocr_fixed import enhanced_rectangle_analysis, clean_output_directories
    
    send_progress("🎯 Usando clasificador personalizado (sin sufijos en descartes)...")
    
    try:
        # Limpieza previa de directorios
        send_progress("🧹 Limpiando directorios de salida...")
        clean_output_dirs(codes_dir, images_dir, discards_dir)
        
        # Obtener todas las imágenes
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
        image_paths = []
        
        for ext in image_extensions:
            image_paths.extend(list(Path(input_dir).glob(f'*{ext}')))
            image_paths.extend(list(Path(input_dir).glob(f'*{ext.upper()}')))
        
        if not image_paths:
            send_progress("❌ No se encontraron imágenes para procesar")
            return
        
        # Ordenar por número de rectángulo
        def extract_rect_number(path):
            match = re.search(r'rect_(\d+)', str(path))
            return int(match.group(1)) if match else float('inf')
        
        image_paths = sorted(image_paths, key=extract_rect_number)
        
        send_progress(f"🔍 Procesando {len(image_paths)} rectángulos...")
        
        # Contadores
        text_count = 0
        image_count = 0
        discard_count = 0
        
        # Procesar cada imagen
        for i, image_path in enumerate(image_paths, 1):
            file_name = os.path.basename(str(image_path))
            send_progress(f"📋 [{i}/{len(image_paths)}] Analizando {file_name}...")
            
            # Usar el análisis existente
            analysis = enhanced_rectangle_analysis(str(image_path))
            
            if analysis['should_discard']:
                # Guardar en descartes SIN SUFIJOS como solicitado
                discard_count += 1
                discard_destination = os.path.join(discards_dir, file_name)
                shutil.copy2(image_path, discard_destination)
                
                # Crear archivo de texto con detalles del descarte (opcional, sin _unknown)
                base_name = os.path.splitext(file_name)[0]
                txt_filename = f"{base_name}_info.txt"
                txt_destination = os.path.join(discards_dir, txt_filename)
                
                with open(txt_destination, 'w', encoding='utf-8') as f:
                    f.write(f"ARCHIVO DESCARTADO: {file_name}\n")
                    f.write(f"FECHA: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"RAZÓN: {analysis['discard_reason']}\n")
                
                send_progress(f"  🗑️ Descartado: {analysis['discard_reason']}")
                
            elif analysis['category'] == 'code':
                # Copiar a directorio de códigos
                destination = os.path.join(codes_dir, file_name)
                shutil.copy2(image_path, destination)
                text_count += 1
                send_progress(f"  📝 Código guardado")
                
            elif analysis['category'] == 'image':
                # Copiar a directorio de imágenes
                destination = os.path.join(images_dir, file_name)
                shutil.copy2(image_path, destination)
                image_count += 1
                send_progress(f"  🖼️ Imagen guardada")
            
            else:
                # Caso inesperado - descartar SIN SUFIJOS
                discard_count += 1
                discard_destination = os.path.join(discards_dir, file_name)
                shutil.copy2(image_path, discard_destination)
                send_progress(f"  ❓ Descartado: categoría desconocida")
        
        send_progress(f"✅ Procesamiento completado:")
        send_progress(f"   📝 {text_count} códigos")
        send_progress(f"   🖼️ {image_count} imágenes")
        send_progress(f"   🗑️ {discard_count} descartes")
        
        # Generar archivos JSON de categoría para cada imagen, como en main.py
        try:
            from enhanced_classifier_with_categories import EnhancedJewelryClassifier
            classifier = EnhancedJewelryClassifier()
            
            image_files = [f for f in os.listdir(images_dir) 
                          if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            
            send_progress(f"📊 Generando archivos JSON de categoría para {len(image_files)} imágenes...")
            
            for i, img_file in enumerate(image_files):
                img_path = os.path.join(images_dir, img_file)
                base_name = os.path.splitext(img_file)[0]
                category_json_path = os.path.join(images_dir, f"{base_name}_category.json")
                
                # Solo crear el archivo JSON si no existe ya
                if not os.path.exists(category_json_path):
                    try:
                        # Analizar la imagen para obtener categoría
                        analysis = classifier.enhanced_rectangle_analysis_with_categories(img_path)
                        
                        # Obtener la categoría y modificar el display para no mostrar porcentajes
                        category = analysis.get('jewelry_category', 'sin_categoria')
                        category_emojis = {
                            'pendientes': '👂',
                            'anillos': '💍',
                            'collares': '📿',
                            'pulseras': '⌚',
                            'colgantes': '🧿',
                            'colgantes y collares': '🔗',
                            'sin_categoria': '❓'
                        }
                        emoji = category_emojis.get(category, '🔹')
                        
                        # Crear display simple sin porcentaje
                        category_title = category.replace('_', ' ').title()
                        category_display = f"{emoji} {category_title}"
                        
                        # Crear archivo JSON con información de categoría
                        category_info = {
                            'filename': img_file,
                            'category': category,
                            'category_display': category_display,
                            'css_class': analysis.get('jewelry_css_class', 'category-unknown'),
                            'confidence': float(analysis.get('jewelry_confidence', 0.0)),
                            'confidence_level': 'alta' if analysis.get('jewelry_confidence', 0) >= 0.8 else 'media' if analysis.get('jewelry_confidence', 0) >= 0.6 else 'baja',
                            'features': analysis.get('features', {}),
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        # Función mejorada para convertir tipos NumPy a tipos JSON compatibles
                        def convert_numpy_to_python_types(obj):
                            import numpy as np
                            if isinstance(obj, np.ndarray):
                                if obj.size == 1:
                                    return obj.item()  # Extraer valor escalar de arrays de 1 elemento
                                else:
                                    return obj.tolist()  # Convertir arrays a listas
                            elif isinstance(obj, (np.integer, np.int64, np.int32)):
                                return int(obj)
                            elif isinstance(obj, (np.floating, np.float64, np.float32)):
                                return float(obj)
                            elif isinstance(obj, np.bool_):
                                return bool(obj)
                            elif isinstance(obj, dict):
                                return {k: convert_numpy_to_python_types(v) for k, v in obj.items()}
                            elif isinstance(obj, (list, tuple)):
                                return [convert_numpy_to_python_types(item) for item in obj]
                            elif obj is None:
                                return None
                            else:
                                return obj
                        
                        # Limpiar características problemáticas ANTES de la conversión
                        features = category_info.get('features', {})
                        clean_features = {}
                        for key, value in features.items():
                            try:
                                # Manejar arrays NumPy problemáticos
                                if hasattr(value, '__module__') and value.__module__ and 'numpy' in str(value.__module__):
                                    if hasattr(value, 'size') and value.size == 1:
                                        clean_features[key] = value.item()  # Extraer valor escalar
                                    elif hasattr(value, 'tolist'):
                                        clean_features[key] = value.tolist()  # Convertir a lista
                                    else:
                                        clean_features[key] = convert_numpy_to_python_types(value)
                                elif value is None or value == "":
                                    clean_features[key] = False  # Valor por defecto para campos vacíos
                                else:
                                    clean_features[key] = value
                            except Exception as conv_error:
                                send_progress(f"  ⚠️ Error procesando característica {key}: {conv_error}")
                                clean_features[key] = False
                        
                        # Actualizar las características limpias
                        category_info['features'] = clean_features
                        
                        # Convertir todos los valores a tipos compatibles con JSON
                        category_info = convert_numpy_to_python_types(category_info)
                        
                        # Validar que el JSON sea correcto antes de guardarlo
                        try:
                            import json
                            # Validar la serialización (prueba de conversión)
                            json_test = json.dumps(category_info, ensure_ascii=False)
                            
                            # Guardar información de categoría
                            with open(category_json_path, 'w', encoding='utf-8') as f:
                                json.dump(category_info, f, indent=2, ensure_ascii=False)
                            
                        except Exception as json_error:
                            send_progress(f"  ⚠️ Error en formato JSON para {img_file}: {str(json_error)}")
                            # Guardar una versión simplificada sin características problemáticas
                            simple_info = {
                                'filename': img_file,
                                'category': category,
                                'category_display': category_display,
                                'confidence': float(analysis.get('jewelry_confidence', 0.0)),
                                'timestamp': datetime.now().isoformat()
                            }
                            with open(category_json_path, 'w', encoding='utf-8') as f:
                                json.dump(simple_info, f, indent=2, ensure_ascii=False)
                        
                        send_progress(f"  ✅ Categoría generada para {img_file}: {category_info['category_display']}")
                    except Exception as e:
                        import traceback
                        send_progress(f"  ❌ Error generando categoría para {img_file}: {str(e)}")
                        traceback.print_exc()
            
            send_progress("✅ Procesamiento de categorías completado")
            return
        except Exception as e:
            send_progress(f"⚠️ Error en análisis de categorías: {e}")
            send_progress("🔄 Continuando sin categorías...")
    
    except Exception as e:
        send_progress(f"❌ Error en procesamiento: {str(e)}")
        # Fallback al sistema original si algo falla
        from improved_classify_rectangles_ocr_fixed import enhanced_rectangle_analysis, clean_output_directories
    
    send_progress("🧹 Limpiando directorios de salida...")
    clean_output_directories(codes_dir, images_dir, discards_dir)
    
    # Obtener todas las imágenes
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
    image_paths = []
    
    for ext in image_extensions:
        image_paths.extend(list(Path(input_dir).glob(f'*{ext}')))
        image_paths.extend(list(Path(input_dir).glob(f'*{ext.upper()}')))
    
    if not image_paths:
        send_progress("❌ No se encontraron imágenes para procesar")
        return
    
    # Ordenar por número de rectángulo
    def extract_rect_number(path):
        match = re.search(r'rect_(\d+)', path.name)
        return int(match.group(1)) if match else float('inf')
    
    image_paths = sorted(image_paths, key=extract_rect_number)
    
    send_progress(f"🔍 Procesando {len(image_paths)} rectángulos (sistema clásico)...")
    
    # Contadores
    text_count = 0
    image_count = 0
    discard_count = 0
    
    # Procesar cada imagen
    for i, image_path in enumerate(image_paths, 1):
        file_name = os.path.basename(str(image_path))
        send_progress(f"📋 [{i}/{len(image_paths)}] Analizando {file_name}...")
        
        # Usar el análisis existente
        analysis = enhanced_rectangle_analysis(str(image_path))
        
        if analysis['should_discard']:
            # Guardar en descartes SIN SUFIJOS
            discard_count += 1
            discard_destination = os.path.join(discards_dir, file_name)
            shutil.copy2(image_path, discard_destination)
            send_progress(f"  🗑️ Descartado: {analysis['discard_reason']}")
            
        elif analysis['category'] == 'code':
            # Copiar a directorio de códigos
            destination = os.path.join(codes_dir, file_name)
            shutil.copy2(image_path, destination)
            text_count += 1
            send_progress(f"  📝 Código guardado")
            
        elif analysis['category'] == 'image':
            # Copiar a directorio de imágenes (sin categoría en sistema clásico)
            destination = os.path.join(images_dir, file_name)
            shutil.copy2(image_path, destination)
            image_count += 1
            send_progress(f"  🖼️ Imagen guardada")
        
        else:
            # Caso inesperado - descartar
            discard_count += 1
            discard_destination = os.path.join(discards_dir, file_name)
            shutil.copy2(image_path, discard_destination)
            send_progress(f"  ❓ Descartado: categoría desconocida")
    
    send_progress(f"✅ Procesamiento completado:")
    send_progress(f"   📝 {text_count} códigos")
    send_progress(f"   🖼️ {image_count} imágenes")
    send_progress(f"   🗑️ {discard_count} descartes")

def process_image_automated():
    """Procesa automáticamente la imagen en source_images (SIN mover a images_old hasta subir a MongoDB)"""
    try:
        # Verificar si hay imagen en source_images
        image_path = get_image_from_sources()
        if not image_path:
            return {'error': 'No hay imagen en source_images para procesar'}
        
        filename = os.path.basename(image_path)
        send_progress(f"🚀 Iniciando procesamiento automático de: {filename}")
        
        # Resto del procesamiento igual que antes
        send_progress("🧹 Limpiando directorios de trabajo...")
        clean_output_dirs("codes_output", "images_output", "discards_output", "rectangles_output")
        
        start_time = time.time()
        
        # Paso 1: Extraer rectángulos
        send_progress("🔍 Detectando rectángulos en la imagen...", 1, 3)
        extract_rectangles(
            image_path=image_path,
            output_dir="rectangles_output",
            debug_path="debug_contours.png"
        )
        
        # Verificar rectángulos extraídos
        rect_files = [f for f in os.listdir("rectangles_output") if f.endswith('.png')]
        send_progress(f"✅ Detectados {len(rect_files)} rectángulos")
        
        if len(rect_files) == 0:
            send_progress("❌ No se detectaron rectángulos en la imagen")
            return {'error': 'No se detectaron rectángulos en la imagen'}
        
        # Paso 2: Procesar rectángulos CON CATEGORÍAS
        send_progress("🤖 Clasificando rectángulos con OCR y categorías...", 2, 3)
        process_rectangles_web_version(
            input_dir="rectangles_output",
            codes_dir="codes_output",
            images_dir="images_output",
            discards_dir="discards_output"
        )
        
        # Obtener estadísticas CON CATEGORÍAS
        codes_count = len(get_directory_contents("codes_output"))
        images_count = len(get_directory_contents_with_categories("images_output"))
        discards_count = len(get_directory_contents("discards_output"))
        
        send_progress(f"📊 Resultado: {codes_count} códigos, {images_count} imágenes, {discards_count} descartes", 3, 3)
        
        processing_time = time.time() - start_time
        needs_manual_review = codes_count != images_count or discards_count > 0
        
        if needs_manual_review:
            send_progress("⚠️ Se requiere revisión manual - los números no coinciden")
        else:
            send_progress("✅ Procesamiento completado exitosamente")
        
        # IMPORTANTE: NO mover imagen a images_old aquí
        # La imagen permanece en source_images hasta confirmar subida a MongoDB
        send_progress("📋 Imagen permanece en source_images hasta confirmar subida a MongoDB")
        
        # Obtener estado del sistema
        system_status = get_system_status()
        
        return {
            'success': True,
            'processing_time': round(processing_time, 2),
            'codes_count': codes_count,
            'images_count': images_count,
            'discards_count': discards_count,
            'needs_manual_review': needs_manual_review,
            'processed_image': filename,
            'system_status': system_status,
            'awaiting_upload': True,  # Nuevo campo para indicar que espera subida
            'enhanced_categories': ENHANCED_CATEGORIES_AVAILABLE,
            'message': f'Procesada {filename}: {codes_count} códigos, {images_count} imágenes, {discards_count} descartes. Esperando subida a MongoDB.'
        }
        
    except Exception as e:
        import traceback
        send_progress(f"❌ Error: {str(e)}")
        print("ERROR COMPLETO:")
        traceback.print_exc()
        return {'error': f'Error procesando imagen: {str(e)}'}

def process_image_with_progress_legacy(filepath, filename):
    """Procesa imagen usando EL PROCESO MODIFICADO PARA WEB (versión legacy para uploads manuales)"""
    try:
        send_progress("🧹 Limpiando directorios de trabajo...")
        clean_output_dirs("codes_output", "images_output", "discards_output", "rectangles_output")
        
        send_progress(f"📁 Procesando imagen: {filename}")
        start_time = time.time()
        
        # Paso 1: Extraer rectángulos
        send_progress("🔍 Detectando rectángulos en la imagen...", 1, 3)
        extract_rectangles(
            image_path=filepath,
            output_dir="rectangles_output",
            debug_path="debug_contours.png"
        )
        
        # Verificar rectángulos extraídos
        rect_files = [f for f in os.listdir("rectangles_output") if f.endswith('.png')]
        send_progress(f"✅ Detectados {len(rect_files)} rectángulos")
        
        if len(rect_files) == 0:
            send_progress("❌ No se detectaron rectángulos en la imagen")
            return {'error': 'No se detectaron rectángulos en la imagen'}
        
        # Paso 2: Procesar rectángulos - VERSIÓN MODIFICADA PARA WEB CON CATEGORÍAS
        send_progress("🤖 Clasificando rectángulos con OCR y categorías...", 2, 3)
        process_rectangles_web_version(
            input_dir="rectangles_output",
            codes_dir="codes_output",
            images_dir="images_output",
            discards_dir="discards_output"
        )
        
        # Obtener estadísticas
        codes_count = len(get_directory_contents("codes_output"))
        images_count = len(get_directory_contents_with_categories("images_output"))
        discards_count = len(get_directory_contents("discards_output"))
        
        send_progress(f"📊 Resultado: {codes_count} códigos, {images_count} imágenes, {discards_count} descartes", 3, 3)
        
        processing_time = time.time() - start_time
        needs_manual_review = codes_count != images_count or discards_count > 0
        
        if needs_manual_review:
            send_progress("⚠️ Se requiere revisión manual - los números no coinciden")
        else:
            send_progress("✅ Procesamiento completado exitosamente")
        
        return {
            'success': True,
            'processing_time': round(processing_time, 2),
            'codes_count': codes_count,
            'images_count': images_count,
            'discards_count': discards_count,
            'needs_manual_review': needs_manual_review,
            'enhanced_categories': ENHANCED_CATEGORIES_AVAILABLE,
            'message': f'Procesamiento completado. {codes_count} códigos, {images_count} imágenes, {discards_count} descartes.'
        }
        
    except Exception as e:
        import traceback
        send_progress(f"❌ Error: {str(e)}")
        print("ERROR COMPLETO:")
        traceback.print_exc()
        return {'error': f'Error procesando imagen: {str(e)}'}

@app.route('/')
def index():
    """Página principal - Procesamiento automático"""
    return render_template('index_auto.html')

@app.route('/manual')
def manual():
    """Página de procesamiento manual (legacy)"""
    return render_template('index.html')

@app.route('/image_source/<filename>')
def serve_image_source(filename):
    """Sirve imágenes desde source_images"""
    try:
        filepath = os.path.join('source_images', filename)
        
        if os.path.exists(filepath):
            return send_file(filepath)
        else:
            return jsonify({'error': 'Imagen no encontrada'}), 404
            
    except Exception as e:
        return jsonify({'error': f'Error sirviendo imagen: {str(e)}'}), 500

@app.route('/progress')
def progress():
    """Stream de progreso usando Server-Sent Events"""
    def generate():
        while True:
            try:
                message = progress_queue.get(timeout=1)
                yield f"data: {json.dumps(message)}\n\n"
            except queue.Empty:
                yield f"data: {json.dumps({'ping': True})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream',
                   headers={'Cache-Control': 'no-cache',
                           'Connection': 'keep-alive'})

@app.route('/process_auto')
def process_auto():
    """Procesa automáticamente la imagen en images_sources"""
    try:
        # Limpiar cola de progreso
        while not progress_queue.empty():
            progress_queue.get()
            
        def process_thread():
            result = process_image_automated()
            send_progress("🏁 Proceso automático completado", step="final")
            progress_queue.put({'result': result})
        
        thread = threading.Thread(target=process_thread)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Procesamiento automático iniciado'})
        
    except Exception as e:
        return jsonify({'error': f'Error: {str(e)}'}), 500

@app.route('/system_status')
def system_status():
    """Obtiene el estado del sistema"""
    try:
        status = get_system_status()
        status['enhanced_categories'] = ENHANCED_CATEGORIES_AVAILABLE
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': f'Error obteniendo estado: {str(e)}'}), 500

@app.route('/setup_next_image')
def setup_next_image():
    """Mueve la siguiente imagen de source a images_sources"""
    try:
        success = move_next_image_to_sources()
        if success:
            status = get_system_status()
            return jsonify({
                'success': True, 
                'message': 'Siguiente imagen movida a images_sources',
                'status': status
            })
        else:
            return jsonify({
                'success': False, 
                'message': 'No hay más imágenes en source'
            })
    except Exception as e:
        return jsonify({'error': f'Error: {str(e)}'}), 500

@app.route('/processing_status')
def processing_status():
    """Verifica el estado del procesamiento actual"""
    try:
        # Verificar si hay imagen en source_images
        current_image_path = get_image_from_sources()
        
        # Verificar si hay archivos procesados pendientes de subir
        codes_count = len(get_directory_contents("codes_output"))
        images_count = len(get_directory_contents_with_categories("images_output"))
        discards_count = len(get_directory_contents("discards_output"))
        
        status = {
            'has_current_image': current_image_path is not None,
            'current_image': os.path.basename(current_image_path) if current_image_path else None,
            'has_processed_data': codes_count > 0 or images_count > 0,
            'codes_count': codes_count,
            'images_count': images_count,
            'discards_count': discards_count,
            'awaiting_upload': codes_count > 0 or images_count > 0,
            'enhanced_categories': ENHANCED_CATEGORIES_AVAILABLE,
            'system_status': get_system_status()
        }
        
        return jsonify(status)
        
    except Exception as e:
        return jsonify({'error': f'Error obteniendo estado: {str(e)}'}), 500

@app.route('/force_archive_image', methods=['POST'])
def force_archive_image():
    """Mueve manualmente la imagen actual a images_old (usar con precaución)"""
    try:
        current_image_path = get_image_from_sources()
        
        if not current_image_path:
            return jsonify({'error': 'No hay imagen en source_images para archivar'}), 400
        
        filename = os.path.basename(current_image_path)
        
        # Mover imagen a images_old
        if move_processed_image_to_old(current_image_path):
            # Preparar siguiente imagen
            has_next = move_next_image_to_sources()
            
            return jsonify({
                'success': True,
                'message': f'Imagen {filename} movida manualmente a images_old',
                'archived_image': filename,
                'has_next': has_next,
                'system_status': get_system_status()
            })
        else:
            return jsonify({'error': 'Error moviendo imagen a images_old'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Error archivando imagen: {str(e)}'}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    """Inicia el procesamiento de imagen en un hilo separado"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No se seleccionó archivo'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No se seleccionó archivo'}), 400
        
        if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            # Limpiar cola de progreso
            while not progress_queue.empty():
                progress_queue.get()
            
            # Guardar archivo
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Procesar en hilo separado
            def process_thread():
                result = process_image_with_progress_legacy(filepath, filename)
                send_progress("🏁 Proceso completado", step="final")
                progress_queue.put({'result': result})
            
            thread = threading.Thread(target=process_thread)
            thread.daemon = True
            thread.start()
            
            return jsonify({'success': True, 'message': 'Procesamiento iniciado'})
        
        return jsonify({'error': 'Tipo de archivo no válido'}), 400
        
    except Exception as e:
        return jsonify({'error': f'Error: {str(e)}'}), 500

@app.route('/get_contents')
def get_contents():
    """Obtiene el contenido de todos los directorios CON CATEGORÍAS"""
    try:
        return jsonify({
            'codes': get_directory_contents("codes_output"),
            'images': get_directory_contents_with_categories("images_output"),  # CON CATEGORÍAS
            'discards': get_directory_contents("discards_output"),
            'enhanced_categories': ENHANCED_CATEGORIES_AVAILABLE  # Indicar si tiene categorías
        })
    except Exception as e:
        return jsonify({'error': f'Error obteniendo contenidos: {str(e)}'}), 500

@app.route('/get_category_stats')
def get_category_stats():
    """Obtiene estadísticas de categorías de joyería"""
    try:
        images_with_categories = get_directory_contents_with_categories("images_output")
        
        # Contar por categoría
        category_counts = {}
        total_images = len(images_with_categories)
        
        for image in images_with_categories:
            category = image.get('category', 'sin_categoria')
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Calcular estadísticas
        stats = {
            'total_images': total_images,
            'categories': {},
            'enhanced_categories_available': ENHANCED_CATEGORIES_AVAILABLE
        }
        
        # Información detallada por categoría
        category_info = {
            'anillos': {'display': '💍 Anillos', 'color': '#667eea'},
            'colgantes y collares': {'display': '🔗 Colgantes y Collares', 'color': '#f5576c'},
            'pulseras': {'display': '⌚ Pulseras', 'color': '#00f2fe'},
            'pendientes': {'display': '👂 Pendientes', 'color': '#38f9d7'},
            'sin_categoria': {'display': '❓ Sin Categoría', 'color': '#999999'}
        }
        
        for category, count in category_counts.items():
            percentage = (count / total_images * 100) if total_images > 0 else 0
            info = category_info.get(category, {'display': category, 'color': '#cccccc'})
            
            stats['categories'][category] = {
                'count': count,
                'percentage': round(percentage, 1),
                'display': info['display'],
                'color': info['color']
            }
        
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': f'Error obteniendo estadísticas: {str(e)}'}), 500

@app.route('/move_file', methods=['POST'])
def move_file():
    """Mueve un archivo entre directorios"""
    try:
        data = request.get_json()
        filename = data.get('filename')
        source_dir = data.get('source_dir')
        target_dir = data.get('target_dir')
        
        if not all([filename, source_dir, target_dir]):
            return jsonify({'error': 'Parámetros faltantes'}), 400
        
        dir_mapping = {
            'codes': 'codes_output',
            'images': 'images_output',
            'discards': 'discards_output'
        }
        
        source_path = os.path.join(dir_mapping.get(source_dir, source_dir), filename)
        target_path = os.path.join(dir_mapping.get(target_dir, target_dir), filename)
        
        if not os.path.exists(source_path):
            return jsonify({'error': 'Archivo fuente no encontrado'}), 404
        
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        shutil.move(source_path, target_path)
        
        # Si se mueve desde imágenes, también mover el archivo JSON de categoría si existe
        if source_dir == 'images':
            base_name = os.path.splitext(filename)[0]
            json_filename = f"{base_name}_category.json"
            source_json = os.path.join(dir_mapping.get(source_dir), json_filename)
            target_json = os.path.join(dir_mapping.get(target_dir), json_filename)
            
            if os.path.exists(source_json):
                try:
                    shutil.move(source_json, target_json)
                except:
                    pass  # No es crítico si falla
        
        return jsonify({'success': True, 'message': f'Archivo movido de {source_dir} a {target_dir}'})
        
    except Exception as e:
        return jsonify({'error': f'Error moviendo archivo: {str(e)}'}), 500

@app.route('/change_category', methods=['POST'])
def change_category():
    """Cambia la categoría de un archivo de imagen"""
    try:
        data = request.get_json()
        filename = data.get('filename')
        new_category = data.get('new_category')
        
        if not filename or not new_category:
            return jsonify({'error': 'Parámetros faltantes: filename y new_category son requeridos'}), 400
        
        # Validar categorías permitidas
        valid_categories = ['anillos', 'pendientes', 'collares', 'pulseras', 'otros']
        if new_category not in valid_categories:
            return jsonify({'error': f'Categoría no válida. Permitidas: {", ".join(valid_categories)}'}), 400
        
        # Construir ruta del archivo de imagen
        image_path = os.path.join('images_output', filename)
        if not os.path.exists(image_path):
            return jsonify({'error': 'Archivo de imagen no encontrado'}), 404
        
        # Construir ruta del archivo JSON de categoría
        base_name = os.path.splitext(filename)[0]
        json_filename = f"{base_name}_category.json"
        json_path = os.path.join('images_output', json_filename)
        
        # Mapeo de categorías a emojis
        category_emojis = {
            'anillos': '💍',
            'pendientes': '👂',
            'collares': '📿',
            'pulseras': '🔗',
            'otros': '✨'
        }
        
        category_names = {
            'anillos': 'Anillos',
            'pendientes': 'Pendientes',
            'collares': 'Collares y Colgantes',
            'pulseras': 'Pulseras',
            'otros': 'Otros'
        }
        
        # Crear o actualizar archivo JSON de categoría
        category_data = {
            "category": new_category,
            "category_name": category_names[new_category],
            "emoji": category_emojis[new_category],
            "confidence": 1.0,  # Máxima confianza para categorías manuales
            "source": "manual_override",
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(category_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            return jsonify({'error': f'Error guardando categoría: {str(e)}'}), 500
        
        # Construir nombre de categoría para mostrar
        new_category_display = f"{category_emojis[new_category]} {category_names[new_category]}"
        
        return jsonify({
            'success': True,
            'message': f'Categoría cambiada a {new_category_display}',
            'filename': filename,
            'new_category': new_category,
            'new_category_display': new_category_display,
            'confidence': 1.0
        })
        
    except Exception as e:
        return jsonify({'error': f'Error cambiando categoría: {str(e)}'}), 500

@app.route('/process_final', methods=['POST'])
def process_final():
    """Procesa los archivos finales y los sube a MongoDB"""
    try:
        # Limpiar cola de progreso
        while not progress_queue.empty():
            progress_queue.get()
            
        def final_process_thread():
            try:
                send_progress("🔗 Conectando a MongoDB...")
                client = return_mongo_client()
                
                send_progress("🤝 Emparejando códigos con imágenes y subiendo a MongoDB...")
                
                # Obtener datos procesados
                codes_count = len(get_directory_contents("codes_output"))
                images_count = len(get_directory_contents_with_categories("images_output"))
                
                # Llamar a la función de emparejado y subida
                pair_and_upload_codes_images_by_order(
                    codes_dir="codes_output",
                    images_dir="images_output", 
                    mongo_client=client,
                    image_id="web_upload"
                )
                
                send_progress(f"✅ Proceso completado: {codes_count} códigos y {images_count} imágenes subidos a MongoDB")
                
                # DESPUÉS de subir exitosamente, mover la imagen original a images_old
                current_image_path = get_image_from_sources()
                if current_image_path:
                    if move_processed_image_to_old(current_image_path):
                        send_progress("📁 Imagen original movida a images_old")
                        
                        # Preparar la siguiente imagen automáticamente
                        if move_next_image_to_sources():
                            send_progress("📸 Siguiente imagen preparada automáticamente")
                            next_status = 'ready_for_next'
                        else:
                            send_progress("✅ No hay más imágenes en cola")
                            next_status = 'all_completed'
                    else:
                        send_progress("⚠️ Error moviendo imagen original, pero subida a MongoDB exitosa")
                        next_status = 'completed_with_warning'
                else:
                    send_progress("⚠️ No se encontró imagen original para mover")
                    next_status = 'completed_with_warning'
                
                # Limpiar directorios de trabajo después de subir
                clean_output_dirs("codes_output", "images_output", "discards_output", "rectangles_output")
                send_progress("🧹 Directorios de trabajo limpiados")
                
                result = {
                    'success': True,
                    'message': f'Proceso completado. {codes_count} códigos y {images_count} imágenes procesados y subidos a MongoDB.',
                    'codes_count': codes_count,
                    'images_count': images_count,
                    'next_status': next_status,
                    'system_status': get_system_status()
                }
                progress_queue.put({'final_result': result})
                
            except Exception as e:
                send_progress(f"❌ Error en proceso final: {str(e)}")
                result = {
                    'success': False,
                    'error': f'Error en proceso final: {str(e)}'
                }
                progress_queue.put({'final_result': result})
        
        thread = threading.Thread(target=final_process_thread)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Proceso final iniciado'})
        
    except Exception as e:
        return jsonify({'error': f'Error en proceso final: {str(e)}'}), 500

@app.route('/reprocess_categories', methods=['POST'])
def reprocess_categories():
    """Re-procesa las categorías de las imágenes actuales"""
    try:
        # Limpiar cola de progreso
        while not progress_queue.empty():
            progress_queue.get()
            
        def reprocess_thread():
            try:
                send_progress("🔄 Iniciando re-procesamiento de categorías...")
                
                # Verificar que hay imágenes para re-procesar
                images_files = get_directory_contents_with_categories("images_output")
                if not images_files:
                    send_progress("❌ No hay imágenes para re-procesar")
                    result = {
                        'success': False,
                        'error': 'No hay imágenes en images_output para re-procesar'
                    }
                    progress_queue.put({'reprocess_result': result})
                    return
                
                send_progress(f"🔍 Re-procesando categorías de {len(images_files)} imágenes...")
                
                # Importar y usar el sistema de categorías
                from enhanced_classifier_with_categories import categorize_jewelry_enhanced
                
                for i, image_file in enumerate(images_files, 1):
                    filename = image_file['name']
                    image_path = os.path.join("images_output", filename)
                    
                    send_progress(f"📋 [{i}/{len(images_files)}] Categorizando {filename}...")
                    
                    try:
                        # Analizar categoría
                        category_result = categorize_jewelry_enhanced(image_path)
                        
                        # Guardar archivo JSON de categoría
                        base_name = os.path.splitext(filename)[0]
                        json_filename = f"{base_name}_category.json"
                        json_path = os.path.join("images_output", json_filename)
                        
                        with open(json_path, 'w', encoding='utf-8') as f:
                            json.dump(category_result, f, ensure_ascii=False, indent=2)
                        
                        send_progress(f"  ✅ {category_result['category_display']}")
                        
                    except Exception as e:
                        send_progress(f"  ⚠️ Error categorizando {filename}: {str(e)}")
                
                send_progress("✅ Re-procesamiento de categorías completado")
                
                result = {
                    'success': True,
                    'message': f'Re-procesamiento completado para {len(images_files)} imágenes',
                    'images_count': len(images_files)
                }
                progress_queue.put({'reprocess_result': result})
                
            except Exception as e:
                send_progress(f"❌ Error en re-procesamiento: {str(e)}")
                result = {
                    'success': False,
                    'error': f'Error en re-procesamiento: {str(e)}'
                }
                progress_queue.put({'reprocess_result': result})
        
        thread = threading.Thread(target=reprocess_thread)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Re-procesamiento de categorías iniciado'})
        
    except Exception as e:
        return jsonify({'error': f'Error iniciando re-procesamiento: {str(e)}'}), 500

@app.route('/delete_file', methods=['POST'])
def delete_file():
    """Elimina un archivo del sistema"""
    try:
        data = request.get_json()
        path = data.get('path')
        
        if not path:
            return jsonify({'error': 'Ruta de archivo requerida'}), 400
        
        # Verificar que el archivo está en un directorio permitido
        allowed_dirs = ['codes_output', 'images_output', 'discards_output', 'uploads']
        if not any(path.startswith(dir) for dir in allowed_dirs):
            return jsonify({'error': 'Directorio no permitido'}), 403
        
        if os.path.exists(path):
            os.remove(path)
            
            # Si es una imagen, también eliminar el archivo JSON de categoría si existe
            if path.startswith('images_output') and path.endswith(('.png', '.jpg', '.jpeg')):
                base_name = os.path.splitext(os.path.basename(path))[0]
                json_path = os.path.join('images_output', f"{base_name}_category.json")
                if os.path.exists(json_path):
                    try:
                        os.remove(json_path)
                    except:
                        pass  # No es crítico si falla
            
            return jsonify({'success': True, 'message': 'Archivo eliminado correctamente'})
        else:
            return jsonify({'error': 'Archivo no encontrado'}), 404
            
    except Exception as e:
        return jsonify({'error': f'Error eliminando archivo: {str(e)}'}), 500

@app.route('/image/<directory>/<filename>')
def serve_image(directory, filename):
    """Sirve imágenes desde los directorios de salida"""
    try:
        dir_mapping = {
            'codes': 'codes_output',
            'images': 'images_output',
            'discards': 'discards_output'
        }
        
        actual_dir = dir_mapping.get(directory, directory)
        filepath = os.path.join(actual_dir, filename)
        
        if os.path.exists(filepath):
            return send_file(filepath)
        else:
            return jsonify({'error': 'Imagen no encontrada'}), 404
            
    except Exception as e:
        return jsonify({'error': f'Error sirviendo imagen: {str(e)}'}), 500

if __name__ == '__main__':
    print("🚀 Sistema de Procesamiento Automático de Imágenes:")
    print("   ✅ Procesamiento automatizado desde /source")
    print("   ✅ Gestión automática de archivos")
    print("   ✅ Zoom de imágenes mejorado")
    print("   ✅ Interfaz moderna y responsiva")
    print("   ✅ Categorización automática de joyería")
    print("   ✅ Sistema de cambio manual de categorías")
    print("\n📁 Estructura de directorios:")
    print("   source/ → images_sources/ → images_old/")
    print("\n🌐 URLs disponibles:")
    print("   http://localhost:5000 - Procesamiento automático")
    print("   http://localhost:5000/manual - Procesamiento manual (legacy)")
    print("🌍 Iniciando servidor en http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
