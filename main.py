import cv2
import os
import pytesseract
import numpy as np
from connect_mongodb import return_mongo_client
from pymongo.errors import DuplicateKeyError
import shutil
from fix_black_boxes_improved import fill_black_boxes_with_white, remove_black_borders
import json
import datetime
import time
import pytz
import os
import pytesseract
import numpy as np
from connect_mongodb import return_mongo_client
from pymongo.errors import DuplicateKeyError
import shutil
from fix_black_boxes_improved import fill_black_boxes_with_white
import json
import datetime
import time
import pytz

def extract_rectangles(image_path, output_dir, debug_path=None):
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: No se pudo cargar la imagen {image_path}")
        return
        
    # 1. Guardar una copia de la imagen original
    original_img = image.copy()
    
    # 2. Preprocesar la imagen para mejorar la detección de bordes
    # Convertir a escala de grises y aplicar suavizado
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 2.1 Aplicar ecualización de histograma para mejorar el contraste
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)
    
    # 2.2 Reducir ruido con suavizado Gaussiano conservador
    gray = cv2.GaussianBlur(gray, (3, 3), 0)  # Kernel más pequeño para preservar detalles
    
    # 3. Métodos múltiples de detección de bordes para capturar diferentes características
    # 3.1 Canny - bueno para bordes definidos
    edges_canny = cv2.Canny(gray, 30, 150)  # Umbrales más bajos para detectar más bordes
    
    # 3.2 Diferencia de gaussianos - bueno para detalles más finos
    gray_blur1 = cv2.GaussianBlur(gray, (3, 3), 0)
    gray_blur2 = cv2.GaussianBlur(gray, (15, 15), 0)
    edges_dog = cv2.subtract(gray_blur1, gray_blur2)
    _, edges_dog = cv2.threshold(edges_dog, 20, 255, cv2.THRESH_BINARY)
    
    # 3.3 Umbralización adaptativa - buena para textos y detalles pequeños
    edges_adaptive = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )
    
    # 4. Combinar los diferentes métodos de detección de bordes
    edges = cv2.bitwise_or(edges_canny, edges_dog)
    edges = cv2.bitwise_or(edges, edges_adaptive)
    
    # 5. Cerrar pequeños huecos en los bordes
    kernel = np.ones((3,3), np.uint8)  # Kernel más pequeño para no perder detalles
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=1)
    
    # 6. Encontrar contornos usando los bordes detectados
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 7. Filtrar y seleccionar los contornos que más probablemente sean objetivos de interés
    rects = []
    img_h, img_w = image.shape[:2]
    min_area = 0.0005 * img_h * img_w  # Área mínima como porcentaje del tamaño de la imagen
    max_area = 0.5 * img_h * img_w      # Área máxima
    
    # 8. Estrategia mejorada para extraer rectángulos
    for cnt in contours:
        area = cv2.contourArea(cnt)
        
        # Ignorar contornos muy pequeños o muy grandes
        if area < min_area or area > max_area:
            continue
            
        # Determinar si es un rectángulo usando aproximación poligonal
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        
        # Los rectángulos tienen 4 vértices, pero también consideramos casi-rectángulos
        # que pueden tener entre 4 y 6 vértices debido a imperfecciones en la detección
        if 4 <= len(approx) <= 6:
            x, y, w, h = cv2.boundingRect(cnt)
            
            # Calcular proporción de aspecto
            aspect_ratio = float(w) / h if h > 0 else 0
            
            # Criterios para considerar un rectángulo relevante:
            # 1. Tiene una forma rectangular apropiada (ni muy alargado ni muy achatado)
            is_good_aspect = 0.2 < aspect_ratio < 5.0
            
            # 2. Tiene un tamaño razonable
            is_reasonable_size = (w > 30 and h > 30)  # Tamaño mínimo absoluto
            
            if is_good_aspect and is_reasonable_size:
                rects.append((x, y, w, h))
    
    # Si no se encontraron suficientes rectángulos con el método anterior,
    # intentar una estrategia alternativa específica para imágenes de colgantes
    if len(rects) < 2:
        # Especialmente para imágenes de colgantes, donde los rectángulos 
        # pueden no estar bien definidos, usamos umbralización
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Cerrar huecos para obtener regiones conexas
        kernel = np.ones((5,5), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
        
        # Encontrar contornos grandes que podrían ser los objetos principales
        contours2, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours2:
            area = cv2.contourArea(cnt)
            if area < min_area or area > max_area:
                continue
                
            x, y, w, h = cv2.boundingRect(cnt)
            
            # Para colgantes, aceptamos diferentes proporciones
            aspect_ratio = float(w) / h if h > 0 else 0
            
            # Los colgantes pueden ser más alargados
            is_pendant_aspect = 0.1 < aspect_ratio < 10.0
            is_reasonable_size = (w > 30 and h > 30)
            
            if is_pendant_aspect and is_reasonable_size:
                rects.append((x, y, w, h))

    # 9. Descartar rectángulos demasiado superpuestos (mejorado)
    filtered_rects = []
    for r1 in sorted(rects, key=lambda r: r[2] * r[3], reverse=True):
        should_append = True
        x1, y1, w1, h1 = r1
        for x2, y2, w2, h2 in filtered_rects:
            # Calcular área de superposición
            overlap_x = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
            overlap_y = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
            overlap_area = overlap_x * overlap_y
            r1_area = w1 * h1
            r2_area = w2 * h2
            smaller_area = min(r1_area, r2_area)
            
            # Si hay más de 60% de superposición con respecto al área más pequeña
            # consideramos que son el mismo objeto y nos quedamos con el mayor
            if overlap_area > 0.6 * smaller_area:
                should_append = False
                break
                
        if should_append:
            filtered_rects.append(r1)

    # 10. Extraer y guardar cada rectángulo con un margen adecuado
    print(f"Contornos detectados: {len(contours)} | Rectángulos filtrados: {len(filtered_rects)}")
    
    # Marcar rectángulos en la imagen de debug
    debug_img = original_img.copy()
    
    rect_count = 0
    for x, y, w, h in filtered_rects:
        # Marcar el rectángulo para depuración
        cv2.rectangle(debug_img, (x, y), (x+w, y+h), (0, 255, 0), 2)
        
        # Añadir un margen para asegurar que no se corte contenido importante
        margin_percent = 0.1  # 10% de margen
        mw = int(w * margin_percent)
        mh = int(h * margin_percent)
        
        # Asegurar un margen mínimo de 8 píxeles
        mw = max(mw, 8)
        mh = max(mh, 8)
        
        # Calcular coordenadas con margen, respetando los límites de la imagen
        x1, y1 = max(x-mw, 0), max(y-mh, 0)
        x2, y2 = min(x+w+mw, image.shape[1]), min(y+h+mh, image.shape[0])
        
        # Extraer el rectángulo con margen
        rect = image[y1:y2, x1:x2]
        
        # Verificar que el recorte tiene un tamaño razonable
        if rect.shape[0] > 20 and rect.shape[1] > 20:  # Mínimo 20x20 pixeles
            cv2.imwrite(os.path.join(output_dir, f'rect_{rect_count}.png'), rect)
            rect_count += 1
    
    print(f"{rect_count} rectángulos internos extraídos en {output_dir}")

    # Guardar imagen de depuración si se solicita
    if debug_path:
        cv2.imwrite(debug_path, debug_img)
        print(f"Imagen de depuración guardada en {debug_path}")

def is_mostly_white(img, threshold=0.98):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    white_pixels = np.sum(gray > 240)
    total_pixels = gray.size
    return (white_pixels / total_pixels) > threshold

def is_code_text(text):
    import re
    # Limpiar el texto manteniendo caracteres relevantes
    clean = text.replace('\n', '').replace(' ', '')
    
    # Eliminar caracteres no alfanuméricos que puedan interferir en el reconocimiento
    # pero mantener 'C', 'c', y 'TTS' que son relevantes para los códigos
    clean = re.sub(r'[^A-Za-z0-9CcT]', '', clean)
    
    # 1. Prioridad alta: códigos de 10 dígitos exactos para colgantes
    # Ser menos estricto y buscar cualquier secuencia de 10 dígitos en el texto
    match = re.search(r'(\d{10})', clean)
    if match:
        code = match.group(1)
        print(f"¡Código de colgante detectado (10 dígitos)!: {code}")
        return code
    
    # 2. Anillos: C/c seguido de 8-12 dígitos
    match = re.search(r'([Cc]\d{8,12})', clean)
    if match:
        return match.group(1)
    
    # 3. Pulseras: TTS seguido de cualquier combinación de letras y dígitos
    match = re.search(r'(TTS[A-Za-z0-9]+)', clean, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # 4. Otros: secuencias más cortas si tienen el formato adecuado
    # Códigos de cualquier longitud entre 8 y 12 dígitos
    match = re.search(r'(\d{8,12})', clean)
    if match:
        return match.group(1)
    
    # 5. Última instancia: secuencias que parecen ser códigos parciales
    # (para casos de reconocimiento imperfecto)
    # Buscar cualquier secuencia de al menos 6 dígitos
    match = re.search(r'(\d{6,})', clean)
    if match:
        # Advertir sobre posible código parcial
        partial_code = match.group(1)
        print(f"Posible código parcial detectado: {partial_code}")
        if len(partial_code) >= 8:  # Si es lo suficientemente largo
            return partial_code
    
    return None

def preprocess_for_ocr(img):
    """
    Preprocesa una imagen para mejorar la detección de texto mediante OCR.
    Especialmente optimizado para detectar códigos numéricos en imágenes de joyería.
    """
    # Si la imagen es muy pequeña, ampliarla más
    h, w = img.shape[:2]
    scale_factor = 2.5 if (h < 100 or w < 100) else 2.0
    
    # Redimensionar con interpolación cúbica para mejor calidad
    img = cv2.resize(img, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
    
    # Convertir a escala de grises
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Determinar si el texto es oscuro sobre fondo claro o viceversa
    is_dark_text = np.mean(gray) > 127
    
    # Aplicar filtro bilateral para reducir ruido preservando bordes
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    
    # Mejorar el contraste con CLAHE (más efectivo que equalizeHist)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)
    
    # Si el texto es oscuro sobre fondo claro, invertir para facilitar OCR
    if is_dark_text:
        gray = 255 - gray
    
    # Aplicar umbralización adaptativa para mejor separación texto/fondo
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 15, 10
    )
    
    # Intentar otra umbralización para códigos de 10 dígitos de colgantes
    # que pueden tener características diferentes
    _, otsu_thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Combinar los dos métodos de umbralización para capturar diferentes características
    combined_thresh = cv2.bitwise_or(thresh, otsu_thresh)
    
    # Operación morfológica para cerrar pequeños huecos en caracteres
    kernel = np.ones((2, 2), np.uint8)
    combined_thresh = cv2.morphologyEx(combined_thresh, cv2.MORPH_CLOSE, kernel)
    
    # Filtro mediano para eliminar ruido mientras se preservan los bordes
    final_thresh = cv2.medianBlur(combined_thresh, 3)
    
    return final_thresh

def classify_and_save_rectangles(input_dir, codes_dir, images_dir, code_map, preprocessed_dir=None, image_id=None):
    if not os.path.exists(codes_dir):
        os.makedirs(codes_dir)
    if not os.path.exists(images_dir):
        os.makedirs(images_dir)
    if preprocessed_dir and not os.path.exists(preprocessed_dir):
        os.makedirs(preprocessed_dir)
    for fname in os.listdir(input_dir):
        if not fname.endswith('.png'):
            continue
        img_path = os.path.join(input_dir, fname)
        img = cv2.imread(img_path)
        
        # Verificar que la imagen se haya cargado correctamente
        if img is None:
            print(f"Error: No se pudo cargar la imagen {img_path}")
            continue
            
        # Ignorar recortes que son casi completamente blancos
        if is_mostly_white(img, threshold=0.98):
            continue  
        
        # Primera pasada: eliminar bordes negros
        img = fill_black_boxes_with_white(img)
        
        # Preprocesar para OCR
        pre_img = preprocess_for_ocr(img)
        
        # Guardar el preprocesado para depuración
        if preprocessed_dir:
            cv2.imwrite(os.path.join(preprocessed_dir, fname), pre_img)
            
        # Reconocer texto con OCR
        text = pytesseract.image_to_string(
            pre_img,
            config='--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
        ).strip()
        text = text.replace('\n', '').replace(' ', '')
        print(f"{fname}: '{text}'")  # Para depuración
        
        code = is_code_text(text)
        if code:
            # Evitar códigos duplicados en el diccionario (solo guardar el primero)
            if code in code_map.values():
                continue
                
            # Segunda pasada de limpieza más agresiva si parece un código
            # Intenta recortar solo el contenido principal si es posible
            try:
                cleaned_img = remove_black_borders(img)
                # Si el recorte fue exitoso y no es demasiado pequeño
                if cleaned_img is not None and cleaned_img.shape[0] > 30 and cleaned_img.shape[1] > 30:
                    img = cleaned_img
                # De lo contrario, usar el resultado de fill_black_boxes_with_white
            except:
                pass  # Si falla, continuar con la imagen actual
                
            cv2.imwrite(os.path.join(codes_dir, fname), img)
            unique_key = f"{image_id}_{fname}" if image_id else fname
            code_map[unique_key] = code
        elif not is_mostly_white(img, threshold=0.90):
            # Para imágenes, usar limpieza agresiva
            try:
                cleaned_img = remove_black_borders(img)
                # Si el recorte fue exitoso y no es demasiado pequeño
                if cleaned_img is not None and cleaned_img.shape[0] > 30 and cleaned_img.shape[1] > 30:
                    img = cleaned_img
            except:
                pass  # Si falla, continuar con la imagen actual
                
            cv2.imwrite(os.path.join(images_dir, fname), img)
            
    return code_map

def pair_and_upload_codes_images(rectangles_dir, mongo_client, db_name='images_db', collection_name='codes_images'):
    import re
    from pymongo import MongoClient
    # Obtener lista de archivos y sus posiciones verticales
    files = [f for f in os.listdir(rectangles_dir) if f.endswith('.png')]
    files_with_pos = []
    for fname in files:
        img_path = os.path.join(rectangles_dir, fname)
        img = cv2.imread(img_path)
        # Obtener posición vertical (y) del recorte
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        coords = cv2.findNonZero(255-gray)
        y_pos = coords[:,:,1].min() if coords is not None else 0
        files_with_pos.append((fname, y_pos))
    # Ordenar por posición vertical
    files_with_pos.sort(key=lambda x: x[1])
    # Filtrar recortes vacíos
    non_empty = []
    for fname, y in files_with_pos:
        img = cv2.imread(os.path.join(rectangles_dir, fname))
        if not is_mostly_white(img, threshold=0.98):
            non_empty.append((fname, y))
    # Emparejar: código, imagen, saltando espacios en blanco
    i = 0
    pairs = []
    while i < len(non_empty)-1:
        code_img = cv2.imread(os.path.join(rectangles_dir, non_empty[i][0]))
        code_text = pytesseract.image_to_string(code_img).strip()
        # Si hay texto, buscar la siguiente imagen
        if code_text:
            # Buscar la siguiente no vacía (imagen)
            for j in range(i+1, len(non_empty)):
                img_img = cv2.imread(os.path.join(rectangles_dir, non_empty[j][0]))
                if not pytesseract.image_to_string(img_img).strip():
                    # Subir a MongoDB
                    with open(os.path.join(rectangles_dir, non_empty[j][0]), 'rb') as fimg:
                        img_bytes = fimg.read()
                    doc = {
                        'code': code_text,
                        'image_filename': non_empty[j][0],
                        'image_bytes': img_bytes
                    }
                    mongo_client[db_name][collection_name].insert_one(doc)
                    pairs.append((code_text, non_empty[j][0]))
                    i = j
                    break
        i += 1
    print(f"Subidos {len(pairs)} pares código-imagen a MongoDB.")

def get_category_from_code(code, original_filename=None):
    # Verificar si la imagen proviene de source_images (es un colgante)
    if original_filename and original_filename.startswith(('db728dce', 'f0c54273')):
        return 'colgantes'
    # Por defecto, todos los demás recortes se consideran anillos
    return 'anillos'


def pair_and_upload_codes_images_by_order(
    codes_dir, images_dir, mongo_client, code_map,
    db_name='images_db', collection_name='codes_images', image_id=None
):
    import re
    def extract_number(fname):
        m = re.search(r'rect_(\d+)\.png', fname)
        return int(m.group(1)) if m else -1

    codes = [f for f in os.listdir(codes_dir) if f.endswith('.png')]
    images = [f for f in os.listdir(images_dir) if f.endswith('.png')]
    codes = sorted(codes, key=extract_number)
    images = sorted(images, key=extract_number)

    collection = mongo_client[db_name][collection_name]
    collection.create_index('code', unique=True)

    n = max(len(codes), len(images))
    for i in range(n):
        code = None
        code_key = None
        code_fname = codes[i] if i < len(codes) else None
        image_fname = images[i] if i < len(images) else None

        if code_fname:
            for key in code_map:
                if key.endswith('_' + code_fname):
                    code_key = key
                    break
            if code_key:
                code = code_map[code_key]

        # Leer imagen si existe
        img_bytes = None
        if image_fname:
            image_img_path = os.path.join(images_dir, image_fname)
            with open(image_img_path, 'rb') as fimg:
                img_bytes = fimg.read()

        # Lógica de categoría y código
        # Si no hay código o imagen, saltar esta iteración
        if not code and not img_bytes:
            continue
            
        # Si tenemos código nulo pero tenemos imagen, asignar un código temporal
        if not code and img_bytes:
            code = f"no_code_{i}"
            
        # Verificar si la imagen proviene de source_images (colgantes)
        source_files = os.listdir("source_images")
        is_from_source = image_id and any(src_file.startswith(os.path.splitext(image_id)[0]) for src_file in source_files)
        
        # Comprobar si el código ya existe en MongoDB para evitar duplicados
        existing_doc = None
        if code:
            existing_doc = collection.find_one({'code': code})

        # Si el código ya existe y tiene una imagen, saltar
        if existing_doc and existing_doc.get('image_bytes') and not code.startswith("no_code_"):
            print(f"Omitiendo código duplicado: {code}")
            continue
            
        if is_from_source:
            # Las imágenes de source_images son colgantes
            category = 'colgantes'
        elif code and code.isdigit() and len(code) == 10:
            # Códigos de 10 dígitos corresponden a colgantes
            category = 'colgantes'
        elif code and img_bytes:
            original_filename = code_key.split('_')[0] if code_key else None
            category = get_category_from_code(code, original_filename)
        else:
            category = 'Pendiente de Validar'

        # Usar fecha local actual en zona horaria Europe/Madrid y quitar tzinfo
        tz = pytz.timezone('Europe/Madrid')
        now = datetime.datetime.now(tz).replace(tzinfo=None)
        doc = {
            'code': code,
            'image_bytes': img_bytes,
            'category': category,
            'updated_at': now
        }
        # Usar $setOnInsert para la fecha de creación
        result = collection.update_one(
            {'code': doc['code']},
            {'$set': {'image_bytes': img_bytes, 'category': category, 'updated_at': now},
             '$setOnInsert': {'created_at': now}},
            upsert=True
        )
        if result.matched_count > 0:
            print(f"Actualizado: El código '{doc['code']}' ya existía. Fecha de actualización modificada.")
        elif result.upserted_id is not None:
            print(f"Insertado: Nuevo código '{doc['code']}' subido.")
    print(f"Subidos/actualizados {n} registros a MongoDB (anillos o pendientes de validar).")

def clean_output_dirs(*dirs):
    for d in dirs:
        if os.path.exists(d):
            for f in os.listdir(d):
                fp = os.path.join(d, f)
                if os.path.isfile(fp):
                    os.remove(fp)
            # Elimina el directorio si está vacío
            if not os.listdir(d):
                os.rmdir(d)

if __name__ == "__main__":
    client = return_mongo_client()
    """ client['images_db']['codes_images'].drop() """
    clean_output_dirs("rectangles_output", "codes_output", "images_output","preprocessed_output")
    print(client.list_database_names())
    source_dir = "source_images"
    images_old_dir = "images_old"
    if not os.path.exists(images_old_dir):
        os.makedirs(images_old_dir)
    for fname in os.listdir(source_dir):
        if not fname.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        start_time = time.time()
        global_code_map = {}  # Limpia el diccionario aquí
        image_path = os.path.join(source_dir, fname)
        print(f"Procesando {image_path}")
        extract_rectangles(
            image_path=image_path,
            output_dir="rectangles_output",
            debug_path="debug_contours.png"
        )
        classify_and_save_rectangles(
            input_dir="rectangles_output",
            codes_dir="codes_output",
            images_dir="images_output",
            code_map=global_code_map,
            preprocessed_dir="preprocessed_output",
            image_id=os.path.splitext(fname)[0]
        )
        pair_and_upload_codes_images_by_order(
            codes_dir="codes_output",
            images_dir="images_output",
            mongo_client=client,
            code_map=global_code_map,
            image_id=os.path.splitext(fname)[0]
        )
        # Mover la imagen procesada a images_old
        shutil.move(image_path, os.path.join(images_old_dir, fname))
        elapsed = time.time() - start_time
        print(f"Tiempo de procesamiento para {fname}: {elapsed:.2f} segundos")
        """ clean_output_dirs("rectangles_output", "codes_output", "images_output", "preprocessed_output") """