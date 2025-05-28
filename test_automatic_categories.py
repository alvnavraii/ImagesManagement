#!/usr/bin/env python3
"""
Script de prueba para verificar la detección automática de categorías de joyería
"""

import os
import sys
import shutil
import time
from pathlib import Path

# Agregar el directorio actual al path para importar módulos
sys.path.append('/home/slendy/PythonProjects/ImagesManagement')

from extract_rectangles import extract_rectangles
from improved_classify_rectangles_ocr_fixed import process_rectangles_improved
from connect_mongodb import return_mongo_client
from main import pair_and_upload_codes_images_by_order

def clean_test_directories():
    """Limpiar directorios de prueba"""
    test_dirs = [
        "test_rectangles_output",
        "test_codes_output", 
        "test_images_output",
        "test_discards_output"
    ]
    
    for test_dir in test_dirs:
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
        os.makedirs(test_dir, exist_ok=True)
    
    print("✅ Directorios de prueba limpiados")

def test_category_detection_pipeline():
    """
    Probar todo el pipeline de detección automática de categorías
    """
    print("🧪 INICIANDO PRUEBA DE DETECCIÓN AUTOMÁTICA DE CATEGORÍAS")
    print("=" * 70)
    
    # Limpiar directorios
    clean_test_directories()
    
    # Usar la imagen de ejemplo disponible
    source_image = "/home/slendy/PythonProjects/ImagesManagement/source_images/6b0f9a03-8ac8-4170-a448-79d236c53c10.jpeg"
    
    if not os.path.exists(source_image):
        print(f"❌ Error: No se encontró la imagen de prueba: {source_image}")
        return
    
    print(f"📷 Procesando imagen de prueba: {os.path.basename(source_image)}")
    
    try:
        # Paso 1: Extraer rectángulos
        print(f"\n🔲 Paso 1: Extrayendo rectángulos...")
        start_time = time.time()
        
        extract_rectangles(
            image_path=source_image,
            output_dir="test_rectangles_output",
            debug_path="test_debug_contours.png"
        )
        
        rectangles_time = time.time() - start_time
        print(f"   ⏱️ Tiempo de extracción: {rectangles_time:.2f} segundos")
        
        # Verificar que se extrajeron rectángulos
        rectangles = [f for f in os.listdir("test_rectangles_output") if f.endswith('.png')]
        print(f"   📦 Rectángulos extraídos: {len(rectangles)}")
        
        if not rectangles:
            print("❌ No se extrajeron rectángulos. Terminando prueba.")
            return
        
        # Paso 2: Procesar rectángulos con detección automática de categorías
        print(f"\n🔍 Paso 2: Procesando rectángulos con detección automática...")
        start_time = time.time()
        
        process_rectangles_improved(
            input_dir="test_rectangles_output",
            codes_dir="test_codes_output",
            images_dir="test_images_output", 
            discards_dir="test_discards_output"
        )
        
        processing_time = time.time() - start_time
        print(f"   ⏱️ Tiempo de procesamiento: {processing_time:.2f} segundos")
        
        # Verificar resultados
        codes = [f for f in os.listdir("test_codes_output") if f.endswith('.png')]
        images = [f for f in os.listdir("test_images_output") if f.endswith('.png')]
        discards = [f for f in os.listdir("test_discards_output") if f.endswith('.png')]
        
        print(f"   📝 Códigos clasificados: {len(codes)}")
        print(f"   🖼️ Imágenes clasificadas: {len(images)}")
        print(f"   🗑️ Rectángulos descartados: {len(discards)}")
        
        # Verificar archivos JSON de categorías
        category_jsons = [f for f in os.listdir("test_images_output") if f.endswith('_category.json')]
        print(f"   🏷️ Archivos de categoría generados: {len(category_jsons)}")
        
        # Mostrar detalles de las categorías detectadas
        if category_jsons:
            print(f"\n📋 CATEGORÍAS DETECTADAS:")
            import json
            for json_file in category_jsons:
                json_path = os.path.join("test_images_output", json_file)
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        category_data = json.load(f)
                    
                    print(f"   📄 {json_file}:")
                    print(f"      🏷️ Categoría: {category_data.get('category_display', category_data.get('category', 'N/A'))}")
                    print(f"      📊 Confianza: {category_data.get('confidence', 0):.2f}")
                    print(f"      🔍 Método: {category_data.get('analysis_method', 'N/A')}")
                    if category_data.get('explanation'):
                        print(f"      💡 Explicación: {category_data['explanation'].replace(chr(10), ' ')}")
                        
                except Exception as e:
                    print(f"   ❌ Error leyendo {json_file}: {e}")
        
        # Paso 3: Probar subida a MongoDB con categorías automáticas (simulado)
        print(f"\n💾 Paso 3: Simulando subida a MongoDB con categorías...")
        
        try:
            # Conectar a MongoDB
            mongo_client = return_mongo_client()
            print(f"   ✅ Conexión MongoDB establecida")
            
            # Llamar función de emparejamiento y subida (en modo prueba)
            print(f"   🔄 Procesando emparejamiento códigos-imágenes...")
            
            # Esta función ya está actualizada para usar las categorías automáticas
            pair_and_upload_codes_images_by_order(
                codes_dir="test_codes_output",
                images_dir="test_images_output",
                mongo_client=mongo_client,
                image_id=f"test_{int(time.time())}"
            )
            
            print(f"   ✅ Subida a MongoDB completada")
            
        except Exception as e:
            print(f"   ⚠️ Error en MongoDB (no crítico para prueba): {e}")
        
        # Resumen final
        total_time = rectangles_time + processing_time
        print(f"\n📊 RESUMEN DE LA PRUEBA:")
        print(f"   ⏱️ Tiempo total: {total_time:.2f} segundos")
        print(f"   📦 Rectángulos procesados: {len(rectangles)}")
        print(f"   📝 Códigos encontrados: {len(codes)}")
        print(f"   🖼️ Imágenes categorizadas: {len(images)}")
        print(f"   🏷️ Categorías automáticas: {len(category_jsons)}")
        print(f"   🗑️ Elementos descartados: {len(discards)}")
        
        # Verificar si la integración funcionó
        if category_jsons and images:
            print(f"\n✅ ÉXITO: La detección automática de categorías está funcionando correctamente")
            print(f"   🎯 Se generaron {len(category_jsons)} archivos de categoría para {len(images)} imágenes")
        else:
            print(f"\n⚠️ ADVERTENCIA: No se generaron archivos de categoría")
            print(f"   🔍 Verificar que las imágenes no estén siendo descartadas incorrectamente")
        
    except Exception as e:
        print(f"❌ Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print(f"\n🧹 Prueba completada. Los archivos de prueba están en:")
        print(f"   📁 test_rectangles_output/ - Rectángulos extraídos")
        print(f"   📁 test_codes_output/ - Códigos clasificados")  
        print(f"   📁 test_images_output/ - Imágenes categorizadas")
        print(f"   📁 test_discards_output/ - Elementos descartados")

if __name__ == "__main__":
    test_category_detection_pipeline()
