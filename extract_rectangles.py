import cv2
import os
import numpy as np

def extract_rectangles(image_path, output_dir, debug_path=None):
    """
    Detecta rectángulos en una imagen y guarda cada uno como una imagen independiente.
    EXACTAMENTE el mismo método que en test_rectangles.py
    
    Args:
        image_path: Ruta a la imagen original
        output_dir: Directorio donde se guardarán los rectángulos extraídos
        debug_path: Ruta opcional para guardar una imagen con los rectángulos marcados
    """
    # Leer la imagen
    image = cv2.imread(str(image_path))
    if image is None:
        print(f"No se pudo cargar la imagen: {image_path}")
        return
    
    # Crear una copia para visualización
    output_image = image.copy()
    
    # Convertir a escala de grises
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Aplicar umbral para obtener una imagen binaria
    _, threshold = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    
    # Encontrar contornos
    contours, _ = cv2.findContours(threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Crear directorio de salida si no existe
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Filtrar contornos para encontrar rectángulos
    rectangles = []
    for contour in contours:
        # Calcular el perímetro del contorno
        perimeter = cv2.arcLength(contour, True)
        
        # Aproximar el contorno a un polígono
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        
        # Calcular el área
        area = cv2.contourArea(contour)
        
        # Filtrar por área mínima y número de vértices (4 para rectángulos)
        if len(approx) == 4 and area > 1000:  # Umbral de área según test_rectangles.py
            rectangles.append(approx)
    
    print(f"Detectados {len(rectangles)} rectángulos en {image_path}")
    
    # Procesar cada rectángulo
    rect_count = 0
    for rect in rectangles:
        # Dibujar el contorno en la imagen de salida (para visualización)
        cv2.drawContours(output_image, [rect], 0, (0, 255, 0), 2)
        
        # Extraer las coordenadas del rectángulo
        x, y, w, h = cv2.boundingRect(rect)
        
        # Recortar el rectángulo de la imagen original
        cropped = image[y:y+h, x:x+w]
        
        # Guardar el rectángulo recortado con nombre simple
        output_path = os.path.join(output_dir, f'rect_{rect_count}.png')
        cv2.imwrite(output_path, cropped)
        rect_count += 1
    
    print(f"{rect_count} celdas extraídas y guardadas en {output_dir}")
    
    # Guardar la imagen con los rectángulos marcados
    if debug_path:
        cv2.imwrite(debug_path, output_image)
        print(f"Imagen de depuración guardada en {debug_path}")

# Limpiar directorios de salida
def clean_output_dirs(*dirs):
    for d in dirs:
        if os.path.exists(d):
            for f in os.listdir(d):
                fp = os.path.join(d, f)
                if os.path.isfile(fp):
                    os.remove(fp)

# Ejecutar el código
if __name__ == "__main__":
    clean_output_dirs("rectangles_output")
    image_path = "source_images/db728dce-7b8c-4f8b-9f41-08c8851e7c3f.jpeg"
    extract_rectangles(
        image_path=image_path,
        output_dir="rectangles_output",
        debug_path="debug_contours.png"
    )
