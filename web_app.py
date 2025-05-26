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

def process_rectangles_web_version(input_dir, codes_dir, images_dir, discards_dir):
    """
    Versión para web que guarda descartes SIN SUFIJOS
    Usa el mismo algoritmo que el archivo original pero modificado para la web
    """
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
            # CAMBIO: Guardar en descartes SIN SUFIJOS - solo nombre original
            discard_count += 1
            discard_destination = os.path.join(discards_dir, file_name)  # Sin sufijos!
            shutil.copy2(image_path, discard_destination)
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
            # Caso inesperado - descartar
            discard_count += 1
            discard_destination = os.path.join(discards_dir, file_name)  # Sin sufijos!
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
        
        # Paso 2: Procesar rectángulos
        send_progress("🤖 Clasificando rectángulos con OCR...", 2, 3)
        process_rectangles_web_version(
            input_dir="rectangles_output",
            codes_dir="codes_output",
            images_dir="images_output",
            discards_dir="discards_output"
        )
        
        # Obtener estadísticas
        codes_count = len(get_directory_contents("codes_output"))
        images_count = len(get_directory_contents("images_output"))
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
        
        # Paso 2: Procesar rectángulos - VERSIÓN MODIFICADA PARA WEB
        send_progress("🤖 Clasificando rectángulos con OCR...", 2, 3)
        process_rectangles_web_version(
            input_dir="rectangles_output",
            codes_dir="codes_output",
            images_dir="images_output",
            discards_dir="discards_output"
        )
        
        # Obtener estadísticas
        codes_count = len(get_directory_contents("codes_output"))
        images_count = len(get_directory_contents("images_output"))
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
        images_count = len(get_directory_contents("images_output"))
        discards_count = len(get_directory_contents("discards_output"))
        
        status = {
            'has_current_image': current_image_path is not None,
            'current_image': os.path.basename(current_image_path) if current_image_path else None,
            'has_processed_data': codes_count > 0 or images_count > 0,
            'codes_count': codes_count,
            'images_count': images_count,
            'discards_count': discards_count,
            'awaiting_upload': codes_count > 0 or images_count > 0,
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
    """Obtiene el contenido de todos los directorios"""
    try:
        return jsonify({
            'codes': get_directory_contents("codes_output"),
            'images': get_directory_contents("images_output"),
            'discards': get_directory_contents("discards_output")
        })
    except Exception as e:
        return jsonify({'error': f'Error obteniendo contenidos: {str(e)}'}), 500

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
        
        return jsonify({'success': True, 'message': f'Archivo movido de {source_dir} a {target_dir}'})
        
    except Exception as e:
        return jsonify({'error': f'Error moviendo archivo: {str(e)}'}), 500

@app.route('/process_final')
def process_final():
    """Procesa los archivos finales, los sube a MongoDB y SOLO entonces mueve la imagen a images_old"""
    try:
        # Limpiar cola de progreso
        while not progress_queue.empty():
            progress_queue.get()
            
        def final_process_thread():
            try:
                # Obtener la imagen actual antes de procesar
                current_image_path = get_image_from_sources()
                current_image_name = os.path.basename(current_image_path) if current_image_path else "desconocida"
                
                send_progress("🔗 Conectando a MongoDB...")
                client = return_mongo_client()
                
                send_progress("🤝 Emparejando códigos con imágenes y subiendo a MongoDB...")
                
                # Intentar subir a MongoDB
                pair_and_upload_codes_images_by_order(
                    codes_dir="codes_output",
                    images_dir="images_output",
                    mongo_client=client,
                    image_id="web_upload"
                )
                
                codes_count = len(get_directory_contents("codes_output"))
                images_count = len(get_directory_contents("images_output"))
                
                send_progress(f"✅ Subida a MongoDB exitosa: {codes_count} códigos y {images_count} imágenes")
                
                # SOLO AHORA mover la imagen a images_old tras subida exitosa
                send_progress("📁 Subida confirmada - moviendo imagen a images_old...")
                
                if current_image_path and move_processed_image_to_old(current_image_path):
                    send_progress(f"✅ Imagen {current_image_name} movida a images_old")
                    
                    # Preparar siguiente imagen
                    send_progress("🔄 Preparando siguiente imagen...")
                    has_next = move_next_image_to_sources()
                    
                    if has_next:
                        send_progress("🔄 Siguiente imagen lista para procesamiento")
                        next_status = "ready_for_next"
                    else:
                        send_progress("🎉 ¡Todas las imágenes han sido procesadas!")
                        next_status = "all_completed"
                else:
                    send_progress("⚠️ Error moviendo imagen a images_old")
                    next_status = "move_error"
                
                # Obtener estado actualizado del sistema
                system_status = get_system_status()
                
                result = {
                    'success': True,
                    'codes_count': codes_count,
                    'images_count': images_count,
                    'processed_image': current_image_name,
                    'next_status': next_status,
                    'system_status': system_status,
                    'message': f'Proceso completado. {codes_count} códigos y {images_count} imágenes subidos a MongoDB. Imagen {current_image_name} archivada.'
                }
                progress_queue.put({'final_result': result})
                
            except Exception as e:
                # Si falla la subida a MongoDB, la imagen permanece en images_sources
                import traceback
                error_msg = f"Error en subida a MongoDB: {str(e)}"
                send_progress(f"❌ {error_msg}")
                send_progress("📋 Imagen permanece en source_images por seguridad")
                print("ERROR COMPLETO EN PROCESS_FINAL:")
                traceback.print_exc()
                
                result = {
                    'success': False,
                    'error': error_msg,
                    'message': 'Error en subida a MongoDB. La imagen permanece en source_images para no perder datos.'
                }
                progress_queue.put({'final_result': result})
        
        thread = threading.Thread(target=final_process_thread)
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Proceso final iniciado - subida a MongoDB y archivado'})
        
    except Exception as e:
        return jsonify({'error': f'Error en proceso final: {str(e)}'}), 500

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
    print("🚀 Sistema de Procesamiento Automático de Imágenes RESTAURADO:")
    print("   ✅ Procesamiento automatizado desde /source")
    print("   ✅ Gestión automática de archivos")
    print("   ✅ Zoom de imágenes mejorado")
    print("   ✅ Interfaz moderna y responsiva")
    print("   🔒 Imágenes protegidas hasta confirmación de MongoDB")
    print("\n📁 Flujo ORIGINAL de directorios:")
    print("   source/ → source_images/ → [PROCESAMIENTO] → [SUBIDA MONGODB] → images_old/")
    print("\n🛡️ SEGURIDAD: Las imágenes NO se mueven a images_old hasta confirmar subida exitosa")
    print("\n🌐 URLs disponibles:")
    print("   http://localhost:5000 - Procesamiento automático")
    print("   http://localhost:5000/manual - Procesamiento manual (legacy)")
    print("   http://localhost:5000/processing_status - Estado del procesamiento")
    print("🌍 Iniciando servidor en http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
