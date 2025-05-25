#!/usr/bin/env python3
# filepath: /home/slendy/PythonProjects/ImagesManagement/improved_process_rectangles.py

import cv2
import numpy as np
import os
import shutil
from pathlib import Path
import sys
from MachineLearning.classify_image import ImageCategoryClassifier

def clean_output_directories(codes_dir, images_dir):
    """Limpia las carpetas de salida para comenzar desde cero."""
    print("Limpiando directorios de salida...")
    
    for directory in [codes_dir, images_dir]:
        if os.path.exists(directory):
            shutil.rmtree(directory)
        os.makedirs(directory, exist_ok=True)
    
    print("Directorios de salida limpios y listos para nuevos archivos.")

def process_rectangles_improved(input_dir, codes_dir, images_dir):
    """
    Versión mejorada que usa el clasificador ML para decidir automáticamente
    si cada rectángulo es un código, una imagen de producto, o debe descartarse.
    
    Args:
        input_dir: Directorio con las imágenes de rectángulos
        codes_dir: Directorio donde se guardarán los rectángulos de texto
        images_dir: Directorio donde se guardarán los rectángulos de imágenes
    """
    # Limpiar las carpetas de salida
    clean_output_directories(codes_dir, images_dir)
    
    # Inicializar clasificador ML
    print("🤖 Inicializando clasificador ML...")
    classifier = ImageCategoryClassifier()
    
    # Obtener todas las imágenes
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
    image_paths = []
    
    for ext in image_extensions:
        image_paths.extend(list(Path(input_dir).glob(f'*{ext}')))
        image_paths.extend(list(Path(input_dir).glob(f'*{ext.upper()}')))
    
    if not image_paths:
        print(f"No se encontraron imágenes en {input_dir}")
        return
    
    # Ordenar por número de rectángulo
    def extract_rect_number(path):
        import re
        match = re.search(r'rect_(\d+)', path.name)
        return int(match.group(1)) if match else float('inf')
    
    image_paths = sorted(image_paths, key=extract_rect_number)
    
    print(f"Procesando {len(image_paths)} rectángulos con clasificador ML...")
    
    # Contadores
    text_count = 0
    image_count = 0
    discard_count = 0
    
    # Procesar cada imagen
    for image_path in image_paths:
        file_name = os.path.basename(str(image_path))
        print(f"Analizando: {file_name}")
        
        # Clasificar con ML
        result = classifier.classify_image(str(image_path))
        category = result['final_category']
        confidence = result['confidence']
        
        print(f"  📊 ML: {category} (confianza: {confidence:.2f})")
        
        # Procesar según clasificación
        if category == 'blank_image':
            # Descartar imagen en blanco
            discard_count += 1
            print(f"  ⚪ Descartado (imagen en blanco)")
            
        elif category == 'product_code':
            # Copiar a directorio de códigos
            destination = os.path.join(codes_dir, file_name)
            shutil.copy2(image_path, destination)
            text_count += 1
            extracted_code = result.get('product_code', result['ocr_result']['extracted_text'])
            print(f"  📝 → Código: '{extracted_code}'")
            
        elif category == 'image_category':
            # Copiar a directorio de imágenes
            destination = os.path.join(images_dir, file_name)
            shutil.copy2(image_path, destination)
            image_count += 1
            print(f"  🖼️ → Imagen de producto")
            
        else:  # error
            # En caso de error, descartar
            discard_count += 1
            error_msg = result.get('error', 'Error desconocido')
            print(f"  ❌ Error: {error_msg} - Descartado")
    
    # Mostrar resumen
    print("\nResumen de clasificación final:")
    print(f"  - Rectángulos de texto: {text_count}")
    print(f"  - Rectángulos de imagen: {image_count}")
    print(f"  - Descartados: {discard_count}")
    print(f"  - Total procesado: {len(image_paths)}")
    
    # Verificar balance final
    if text_count == image_count:
        print(f"\n✅ Clasificación equilibrada: {text_count} códigos y {image_count} imágenes")
    else:
        print(f"\n⚖️ Balance: {text_count} códigos vs {image_count} imágenes")
        print("Nota: El clasificador ML prioriza la precisión sobre el balance perfecto")
if __name__ == "__main__":
    # Obtener parámetros de línea de comandos o usar valores predeterminados
    if len(sys.argv) > 3:
        input_dir = sys.argv[1]
        codes_dir = sys.argv[2]
        images_dir = sys.argv[3]
    else:
        # Valores predeterminados
        input_dir = "/home/slendy/PythonProjects/ImagesManagement/rectangles_output"
        codes_dir = "/home/slendy/PythonProjects/ImagesManagement/codes_output"
        images_dir = "/home/slendy/PythonProjects/ImagesManagement/images_output"
    
    # Ejecutar el procesamiento
    process_rectangles_improved(input_dir, codes_dir, images_dir)
