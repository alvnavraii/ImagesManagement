import cv2
import os
import pytesseract
import numpy as np
from connect_mongodb import return_mongo_client
from pymongo.errors import DuplicateKeyError
import shutil
from fix_black_boxes import fill_black_boxes_with_white
import json
import datetime
import time

def extract_rectangles(image_path, output_dir, debug_path=None):
    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Mejorar contraste
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)
    # Umbral adaptativo
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY_INV, 15, 8)
    # Encontrar contornos con jerarquía
    contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Filtrar contornos: ignorar el contorno externo y buscar rectángulos internos
    rects = []
    areas = [cv2.contourArea(cnt) for cnt in contours]
    max_area = max(areas) if areas else 0
    for i, cnt in enumerate(contours):
        area = cv2.contourArea(cnt)
        approx = cv2.approxPolyDP(cnt, 0.02 * cv2.arcLength(cnt, True), True)
        # Solo rectángulos internos, no el más grande (externo)
        if len(approx) == 4 and 500 < area < 0.95 * max_area:
            # Además, debe tener un padre (no ser el contorno externo)
            if hierarchy[0][i][3] != -1:
                rects.append(approx)

    rect_count = 0
    for approx in rects:
        x, y, w, h = cv2.boundingRect(approx)
        # Margen para evitar bordes
        pad = 2
        x1, y1, x2, y2 = max(x-pad,0), max(y-pad,0), min(x+w+pad,image.shape[1]), min(y+h+pad,image.shape[0])
        rect = image[y1:y2, x1:x2]
        cv2.imwrite(os.path.join(output_dir, f'rect_{rect_count}.png'), rect)
        rect_count += 1
    print(f"{rect_count} rectángulos internos extraídos en {output_dir}")

    # Imagen de depuración
    if debug_path:
        debug_img = image.copy()
        cv2.drawContours(debug_img, rects, -1, (0, 255, 0), 2)
        cv2.imwrite(debug_path, debug_img)

def is_mostly_white(img, threshold=0.98):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    white_pixels = np.sum(gray > 240)
    total_pixels = gray.size
    return (white_pixels / total_pixels) > threshold

def is_code_text(text):
    import re
    # No eliminar la 'C' o 'c' inicial ni otros caracteres relevantes
    clean = text.replace('\n', '').replace(' ', '')
    # Anillos: C/c seguido de 8-12 dígitos
    match = re.search(r'([Cc][0-9]{8,12})', clean)
    if match:
        return match.group(1)
    # Pulseras: TTS seguido de cualquier combinación de letras y dígitos
    match = re.search(r'(TTS[A-Za-z0-9]+)', clean, re.IGNORECASE)
    if match:
        return match.group(1)
    # Pulseras: solo 10-12 dígitos
    match = re.search(r'([0-9]{10,12})', clean)
    if match:
        return match.group(1)
    # Anillos: solo 8-9 dígitos
    match = re.search(r'([0-9]{8,9})', clean)
    if match:
        return match.group(1)
    return None

def preprocess_for_ocr(img):
    # Aumentar tamaño
    img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Invertir si el texto es oscuro sobre fondo claro
    if np.mean(gray) > 127:
        gray = 255 - gray
    gray = cv2.equalizeHist(gray)
    _, thresh = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY)
    thresh = cv2.medianBlur(thresh, 3)
    return thresh

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
        if is_mostly_white(img, threshold=0.98):
            continue  # Ignora recortes vacíos
        pre_img = preprocess_for_ocr(img)
        # Guarda el preprocesado para depuración
        if preprocessed_dir:
            cv2.imwrite(os.path.join(preprocessed_dir, fname), pre_img)
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
            img = fill_black_boxes_with_white(img)
            cv2.imwrite(os.path.join(codes_dir, fname), img)
            unique_key = f"{image_id}_{fname}" if image_id else fname
            code_map[unique_key] = code
        elif not is_mostly_white(img, threshold=0.90):
            img = fill_black_boxes_with_white(img)
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

def get_category_from_code(code):
    # Todos los recortes se consideran anillos
    return 'anillos'

def pair_and_upload_codes_images_by_order(
    codes_dir, images_dir, mongo_client, code_map,
    db_name='images_db', collection_name='codes_images'
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
        if code and img_bytes:
            category = 'anillos'
            code_value = code
        else:
            category = 'Pendiente de Validar'
            code_value = code if code else f"no_code_{i}"

        now = datetime.datetime.utcnow()
        doc = {
            'code': code_value,
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
            code_map=global_code_map
        )
        # Mover la imagen procesada a images_old
        #shutil.move(image_path, os.path.join(images_old_dir, fname))
        elapsed = time.time() - start_time
        print(f"Tiempo de procesamiento para {fname}: {elapsed:.2f} segundos")
        """ clean_output_dirs("rectangles_output", "codes_output", "images_output", "preprocessed_output") """