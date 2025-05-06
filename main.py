import cv2
import os
import pytesseract
import numpy as np
from connect_mongodb import return_mongo_client
from pymongo.errors import DuplicateKeyError
import shutil

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
    # Elimina espacios y caracteres no alfanuméricos
    clean = re.sub(r'[^A-Za-z0-9]', '', text)
    # Busca una letra y 10 dígitos, o solo 10-11 dígitos
    match = re.search(r'([A-Za-z][0-9]{10})|([0-9]{10,11})', clean)
    if match:
        code = match.group(0)
        # Si solo hay dígitos, puedes asumir que la letra inicial es 'c'
        if re.fullmatch(r'[0-9]{10,11}', code):
            code = 'c' + code[-10:]  # Toma los últimos 10 dígitos y antepone 'c'
        return code
    return None

def classify_and_save_rectangles(input_dir, codes_dir, images_dir):
    if not os.path.exists(codes_dir):
        os.makedirs(codes_dir)
    if not os.path.exists(images_dir):
        os.makedirs(images_dir)
    for fname in os.listdir(input_dir):
        if not fname.endswith('.png'):
            continue
        img_path = os.path.join(input_dir, fname)
        img = cv2.imread(img_path)
        if is_mostly_white(img, threshold=0.98):
            continue  # Ignora recortes vacíos
        text = pytesseract.image_to_string(img).strip()
        print(f"{fname}: '{text}'")  # Imprime el texto detectado para depuración
        code = is_code_text(text)
        if code:
            cv2.imwrite(os.path.join(codes_dir, fname), img)
        elif not is_mostly_white(img, threshold=0.90):  # Más estricto para imágenes
            cv2.imwrite(os.path.join(images_dir, fname), img)

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

def pair_and_upload_codes_images_by_order(codes_dir, images_dir, mongo_client, db_name='images_db', collection_name='codes_images'):
    codes = sorted([f for f in os.listdir(codes_dir) if f.endswith('.png')])
    images = sorted([f for f in os.listdir(images_dir) if f.endswith('.png')])
    n = min(len(codes), len(images))
    collection = mongo_client[db_name][collection_name]
    # Crear índice único en 'code'
    collection.create_index('code', unique=True)
    for i in range(n):
        code_img_path = os.path.join(codes_dir, codes[i])
        image_img_path = os.path.join(images_dir, images[i])
        code_img = cv2.imread(code_img_path)
        code_text = pytesseract.image_to_string(code_img).strip()
        code = is_code_text(code_text)
        with open(image_img_path, 'rb') as fimg:
            img_bytes = fimg.read()
        doc = {
            'code': code,
            'image_bytes': img_bytes,
            'category': 'anillos'
        }
        try:
            collection.insert_one(doc)
        except DuplicateKeyError:
            print(f"Error: El código '{code}' ya existe en la base de datos. No se ha insertado el duplicado.")
    print(f"Subidos {n} pares código-imagen a MongoDB por orden (sin duplicados).")

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
    print(client.list_database_names())
    extract_rectangles(
        image_path="source_images/3bb60701-86c2-410f-a05b-dc0b353f51bf.jpeg",
        output_dir="rectangles_output",
        debug_path="debug_contours.png"
    )
    classify_and_save_rectangles(
        input_dir="rectangles_output",
        codes_dir="codes_output",
        images_dir="images_output"
    )
    pair_and_upload_codes_images_by_order(
        codes_dir="codes_output",
        images_dir="images_output",
        mongo_client=client
    )
    # Limpiar y eliminar directorios tras la subida
    clean_output_dirs("rectangles_output", "codes_output", "images_output")