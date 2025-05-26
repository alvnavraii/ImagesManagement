from flask import Flask, render_template, request, jsonify, send_file
import os
import shutil
import time
import json
import traceback
import logging
from werkzeug.utils import secure_filename
import cv2

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Crear directorios necesarios
for directory in ['uploads', 'codes_output', 'images_output', 'discards_output', 'rectangles_output']:
    if not os.path.exists(directory):
        os.makedirs(directory)

def clean_output_dirs(*dirs):
    """Limpia los directorios de salida"""
    for d in dirs:
        if os.path.exists(d):
            for f in os.listdir(d):
                fp = os.path.join(d, f)
                if os.path.isfile(fp):
                    os.remove(fp)

def get_directory_contents(directory):
    """Obtiene el contenido de un directorio con metadatos"""
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
    return files

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Procesa la imagen subida"""
    try:
        logger.info("Iniciando procesamiento de imagen")
        
        if 'file' not in request.files:
            return jsonify({'error': 'No se seleccionó archivo'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No se seleccionó archivo'}), 400
        
        if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            # Limpiar directorios de salida
            logger.info("Limpiando directorios de salida")
            clean_output_dirs("codes_output", "images_output", "discards_output", "rectangles_output")
            
            # Guardar archivo subido
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            logger.info(f"Archivo guardado en: {filepath}")
            
            start_time = time.time()
            
            # Verificar que el archivo se guardó correctamente
            if not os.path.exists(filepath):
                return jsonify({'error': 'Error guardando archivo'}), 500
            
            # Procesar imagen - Paso 1: Extraer rectángulos
            logger.info("Iniciando extracción de rectángulos")
            try:
                from extract_rectangles import extract_rectangles
                extract_rectangles(
                    image_path=filepath,
                    output_dir="rectangles_output",
                    debug_path="debug_contours.png"
                )
                logger.info("Extracción de rectángulos completada")
            except Exception as e:
                logger.error(f"Error en extract_rectangles: {str(e)}")
                return jsonify({'error': f'Error extrayendo rectángulos: {str(e)}'}), 500
            
            # Verificar que se extrajeron rectángulos
            rect_files = [f for f in os.listdir("rectangles_output") if f.endswith('.png')]
            logger.info(f"Rectángulos extraídos: {len(rect_files)}")
            
            if len(rect_files) == 0:
                return jsonify({'error': 'No se detectaron rectángulos en la imagen'}), 400
            
            # Procesar imagen - Paso 2: Clasificar rectángulos
            logger.info("Iniciando clasificación de rectángulos")
            try:
                from improved_classify_rectangles_ocr_fixed import process_rectangles_improved as process_rectangles
                process_rectangles(
                    input_dir="rectangles_output",
                    codes_dir="codes_output",
                    images_dir="images_output",
                    discards_dir="discards_output"
                )
                logger.info("Clasificación de rectángulos completada")
            except Exception as e:
                logger.error(f"Error en process_rectangles: {str(e)}")
                return jsonify({'error': f'Error clasificando rectángulos: {str(e)}'}), 500
            
            # Obtener estadísticas
            codes_count = len(get_directory_contents("codes_output"))
            images_count = len(get_directory_contents("images_output"))
            discards_count = len(get_directory_contents("discards_output"))
            
            processing_time = time.time() - start_time
            
            logger.info(f"Procesamiento completado: {codes_count} códigos, {images_count} imágenes, {discards_count} descartes")
            
            # Verificar si hay discrepancias
            needs_manual_review = codes_count != images_count or discards_count > 0
            
            result = {
                'success': True,
                'processing_time': round(processing_time, 2),
                'codes_count': codes_count,
                'images_count': images_count,
                'discards_count': discards_count,
                'needs_manual_review': needs_manual_review,
                'message': f'Procesamiento completado. {codes_count} códigos, {images_count} imágenes, {discards_count} descartes.'
            }
            
            if needs_manual_review:
                result['message'] += ' Se requiere revisión manual.'
            
            return jsonify(result)
        
        return jsonify({'error': 'Tipo de archivo no válido'}), 400
        
    except Exception as e:
        logger.error(f"Error general en upload_file: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Error procesando imagen: {str(e)}'}), 500

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
        logger.error(f"Error en get_contents: {str(e)}")
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
        
        # Mapear nombres de directorios
        dir_mapping = {
            'codes': 'codes_output',
            'images': 'images_output',
            'discards': 'discards_output'
        }
        
        source_path = os.path.join(dir_mapping.get(source_dir, source_dir), filename)
        target_path = os.path.join(dir_mapping.get(target_dir, target_dir), filename)
        
        if not os.path.exists(source_path):
            return jsonify({'error': 'Archivo fuente no encontrado'}), 404
        
        # Crear directorio destino si no existe
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        # Mover archivo
        shutil.move(source_path, target_path)
        logger.info(f"Archivo movido: {filename} de {source_dir} a {target_dir}")
        
        return jsonify({'success': True, 'message': f'Archivo movido de {source_dir} a {target_dir}'})
        
    except Exception as e:
        logger.error(f"Error en move_file: {str(e)}")
        return jsonify({'error': f'Error moviendo archivo: {str(e)}'}), 500

@app.route('/process_final')
def process_final():
    """Procesa los archivos finales y los sube a MongoDB"""
    try:
        logger.info("Iniciando proceso final")
        
        # Verificar conexión a MongoDB
        try:
            from connect_mongodb import return_mongo_client
            client = return_mongo_client()
            logger.info("Conexión a MongoDB establecida")
        except Exception as e:
            logger.error(f"Error conectando a MongoDB: {str(e)}")
            return jsonify({'error': f'Error conectando a MongoDB: {str(e)}'}), 500
        
        # Importar la función de emparejamiento
        try:
            from main import pair_and_upload_codes_images_by_order
            logger.info("Función de emparejamiento importada")
        except Exception as e:
            logger.error(f"Error importando función: {str(e)}")
            return jsonify({'error': f'Error importando función: {str(e)}'}), 500
        
        # Ejecutar el proceso de emparejamiento y subida
        pair_and_upload_codes_images_by_order(
            codes_dir="codes_output",
            images_dir="images_output",
            mongo_client=client,
            image_id="web_upload"
        )
        
        # Obtener estadísticas finales
        codes_count = len(get_directory_contents("codes_output"))
        images_count = len(get_directory_contents("images_output"))
        
        logger.info(f"Proceso final completado: {codes_count} códigos, {images_count} imágenes")
        
        return jsonify({
            'success': True,
            'message': f'Proceso completado. {codes_count} códigos y {images_count} imágenes procesados y subidos a MongoDB.'
        })
        
    except Exception as e:
        logger.error(f"Error en process_final: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'error': f'Error en proceso final: {str(e)}'}), 500

@app.route('/image/<directory>/<filename>')
def serve_image(directory, filename):
    """Sirve imágenes desde los directorios de salida"""
    try:
        # Mapear directorios
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
        logger.error(f"Error sirviendo imagen: {str(e)}")
        return jsonify({'error': f'Error sirviendo imagen: {str(e)}'}), 500

@app.route('/test')
def test():
    """Endpoint de prueba para verificar que la aplicación funciona"""
    return jsonify({
        'status': 'ok',
        'message': 'Aplicación funcionando correctamente',
        'directories': {
            'codes_output': os.path.exists('codes_output'),
            'images_output': os.path.exists('images_output'),
            'discards_output': os.path.exists('discards_output'),
            'rectangles_output': os.path.exists('rectangles_output')
        }
    })

if __name__ == '__main__':
    print("🚀 Iniciando aplicación web...")
    print("📍 URL: http://localhost:5000")
    print("🧪 Test: http://localhost:5000/test")
    app.run(debug=True, host='0.0.0.0', port=5000)
