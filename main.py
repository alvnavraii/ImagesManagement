import cv2
import os
from connect_mongodb import return_mongo_client
import shutil
import datetime
import time
import pytz
from extract_rectangles import extract_rectangles
# Usar la versión mejorada del procesamiento de rectángulos
from improved_classify_rectangles_ocr_fixed import process_rectangles_improved as process_rectangles

# Eliminadas las funciones is_mostly_white, is_code_text, preprocess_for_ocr y classify_and_save_rectangles
# Ahora estas funcionalidades se importan desde classify_rectangles.py

# La antigua función pair_and_upload_codes_images ha sido eliminada
# ya que ha sido reemplazada por la versión mejorada pair_and_upload_codes_images_by_order

# La función get_category_from_code fue eliminada y su funcionalidad
# incorporada directamente en pair_and_upload_codes_images_by_order


def pair_and_upload_codes_images_by_order(
    codes_dir, images_dir, mongo_client, 
    db_name='images_db', collection_name='codes_images', image_id=None
):
    """
    Empareja códigos e imágenes basándose en los nombres de archivo y los sube a MongoDB.
    Versión simplificada que asume que codes_dir contiene solo códigos e images_dir solo imágenes.
    
    Args:
        codes_dir: Directorio que contiene las imágenes de códigos
        images_dir: Directorio que contiene las imágenes de productos
        mongo_client: Cliente MongoDB
        db_name: Nombre de la base de datos
        collection_name: Nombre de la colección
        image_id: Identificador opcional de la imagen original
    """
    import re
    import pytesseract
    
    # Función auxiliar para extraer el número del nombre del archivo
    def extract_number(fname):
        m = re.search(r'rect_(\d+)\.png', fname)
        return int(m.group(1)) if m else -1

    # Obtener y ordenar los archivos de código e imágenes por su número de rectángulo
    code_files = sorted([f for f in os.listdir(codes_dir) if f.endswith('.png')], key=extract_number)
    image_files = sorted([f for f in os.listdir(images_dir) if f.endswith('.png')], key=extract_number)
    
    print(f"Encontrados {len(code_files)} códigos y {len(image_files)} imágenes para emparejar")
    
    # Acceder a la colección y crear índice si es necesario
    collection = mongo_client[db_name][collection_name]
    collection.create_index('code', unique=True)
    
    # Para los registros insertados/actualizados
    inserted_count = 0
    updated_count = 0
    
    # Procesar cada código
    for code_file in code_files:
        # Leer la imagen del código
        code_img_path = os.path.join(codes_dir, code_file)
        code_img = cv2.imread(code_img_path)
        
        # Verificar que la imagen se haya cargado correctamente
        if code_img is None:
            print(f"Error: No se pudo cargar la imagen {code_img_path}, omitiendo...")
            continue
            
        try:
            # Extraer el texto del código usando OCR
            code_text = pytesseract.image_to_string(
                code_img,
                config='--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
            ).strip()
        except Exception as e:
            print(f"Error al procesar {code_file}: {str(e)}")
            continue
        
        # Limpiar el texto
        code_text = code_text.replace('\n', '').replace(' ', '')
        
        # Verificar que tenemos un código válido
        if not code_text:
            print(f"No se pudo extraer texto del archivo {code_file}, omitiendo...")
            continue
            
        print(f"Código extraído: '{code_text}' de {code_file}")
        
        # Determinar la categoría basada en el código
        category = 'pendientes'  # Por defecto es colgantes
        """ if code_text.isdigit() and len(code_text) == 10:
            category = 'colgantes'  # Códigos de 10 dígitos son colgantes
        else:
            # Verificar si proviene de una fuente conocida de colgantes
            if image_id and image_id.startswith(('db728dce', 'f0c54273')):
                category = 'colgantes'
            else:
                category = 'anillos'  # Por defecto es anillos
         """
        # Buscar la imagen correspondiente por número de rectángulo
        rect_num = extract_number(code_file)
        matching_image = None
        
        # Buscar una imagen con el mismo número de rectángulo
        for img_file in image_files:
            if extract_number(img_file) == rect_num:
                matching_image = img_file
                break
        
        # Si no encontramos una correspondencia exacta, usar la primera disponible
        if not matching_image and image_files:
            matching_image = image_files[0]
            image_files.remove(matching_image)  # Eliminar para no reutilizar
            print(f"No se encontró correspondencia exacta para {code_file}. Usando {matching_image}")
        elif not matching_image:
            print(f"No se encontró ninguna imagen disponible para emparejar con {code_file}, omitiendo...")
            continue
        
        # Si tenemos una imagen para este código
        img_bytes = None
        if matching_image:
            image_path = os.path.join(images_dir, matching_image)
            with open(image_path, 'rb') as img_file:
                img_bytes = img_file.read()
        
        # Comprobar si el código ya existe en MongoDB
        existing_doc = collection.find_one({'code': code_text})
        
        # Preparar timestamp
        tz = pytz.timezone('Europe/Madrid')
        now = datetime.datetime.now(tz).replace(tzinfo=None)
        
        # Preparar documento para insertar/actualizar
        doc = {
            'code': code_text,
            'category': category,
            'updated_at': now
        }
        
        # Añadir la imagen solo si la tenemos
        if img_bytes:
            doc['image_bytes'] = img_bytes
        
        # Insertar o actualizar en MongoDB
        result = collection.update_one(
            {'code': code_text},
            {
                '$set': doc,
                '$setOnInsert': {'created_at': now}
            },
            upsert=True
        )
        
        # Registrar resultado
        if result.matched_count > 0:
            print(f"Actualizado: Código '{code_text}' ({category})")
            updated_count += 1
        elif result.upserted_id is not None:
            print(f"Insertado: Nuevo código '{code_text}' ({category})")
            inserted_count += 1
    
    print(f"\nProceso completado:")
    print(f"  - {inserted_count} nuevos registros insertados")
    print(f"  - {updated_count} registros actualizados")
    print(f"  - {len(code_files)} códigos procesados en total")

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
    clean_output_dirs("colgantes y collares", "codes_output", "images_output", "discards_output", "preprocessed_output", "rectangles_output")
    print(client.list_database_names())
    source_dir = "source_images"
    images_old_dir = "images_old"
    if not os.path.exists(images_old_dir):
        os.makedirs(images_old_dir)
    for fname in os.listdir(source_dir):
        if not fname.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        start_time = time.time()
        image_path = os.path.join(source_dir, fname)
        print(f"Procesando {image_path}")
        extract_rectangles(
            image_path=image_path,
            output_dir="rectangles_output",
            debug_path="debug_contours.png"
        ) 
        # Usar la función process_rectangles del módulo classify_rectangles.py
        process_rectangles(
            input_dir="rectangles_output",
            codes_dir="codes_output",
            images_dir="images_output",
            discards_dir="discards_output"
        ) 
        
         # Emparejar códigos e imágenes y subir a MongoDB
        pair_and_upload_codes_images_by_order(
            codes_dir="codes_output",
            images_dir="images_output",
            mongo_client=client,
            image_id=os.path.splitext(fname)[0]
        ) 
       
        # Mover la imagen procesada a images_old
        shutil.move(image_path, os.path.join(images_old_dir, fname))
        elapsed = time.time() - start_time
        print(f"Tiempo de procesamiento para {fname}: {elapsed:.2f} segundos")
        """ clean_output_dirs("rectangles_output", "codes_output", "images_output", "preprocessed_output") """