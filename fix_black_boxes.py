import cv2
import numpy as np
import os
from connect_mongodb import return_mongo_client
from bson.objectid import ObjectId

DB_NAME = 'images_db'
COLLECTION_NAME = 'codes_images'


def fill_black_boxes_with_white(image):
    N = 3  # Número de píxeles de borde a forzar a blanco
    h, w = image.shape[:2]
    # Superior
    image[:N, :, ...] = 255
    # Inferior
    image[-N:, :, ...] = 255
    # Izquierda
    image[:, :N, ...] = 255
    # Derecha
    image[:, -N:, ...] = 255
    return image


def process_and_update_images():
    client = return_mongo_client()
    collection = client[DB_NAME][COLLECTION_NAME]
    docs = list(collection.find({}))
    print(f"Procesando {len(docs)} imágenes...")
    output_dir = "output_fixed"
    os.makedirs(output_dir, exist_ok=True)
    saved_one = False
    for doc in docs:
        img_bytes = doc.get('image_bytes')
        if not img_bytes:
            continue
        # Leer imagen desde bytes
        img_array = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            print(f"No se pudo decodificar la imagen con _id={doc['_id']}")
            continue
        # Procesar imagen
        img_fixed = fill_black_boxes_with_white(img)
        # Guardar la primera imagen procesada en disco
        if not saved_one:
            out_path = os.path.join(output_dir, f"{doc['_id']}.jpeg")
            cv2.imwrite(out_path, img_fixed)
            print(f"Imagen procesada guardada en {out_path}")
            saved_one = True
        # Codificar de nuevo a bytes
        _, img_encoded = cv2.imencode('.jpeg', img_fixed)
        new_bytes = img_encoded.tobytes()
        # Actualizar en la base de datos
        collection.update_one({'_id': doc['_id']}, {'$set': {'image_bytes': new_bytes}})
        print(f"Imagen {doc['_id']} procesada y actualizada.")
    print("Proceso completado.")


if __name__ == "__main__":
    process_and_update_images()
