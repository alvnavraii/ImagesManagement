#!/usr/bin/env python3
"""
Clasificador mejorado que incluye detección de categorías de joyería
Integra el nuevo predictor de categorías con el sistema existente
"""

import cv2
import numpy as np
import os
import shutil
from pathlib import Path
import sys
import re
from datetime import datetime

# Importar el nuevo predictor de categorías
try:
    from MachineLearning.jewelry_category_predictor import JewelryCategoryPredictor
    CATEGORY_PREDICTOR_AVAILABLE = True
    print("✅ Predictor de categorías de joyería cargado")
except ImportError as e:
    print(f"⚠️ Predictor de categorías no disponible: {e}")
    CATEGORY_PREDICTOR_AVAILABLE = False

# Importar funciones existentes
from improved_classify_rectangles_ocr_fixed import (
    is_measurements_or_weight_only_enhanced,
    clean_output_directories
)

class EnhancedJewelryClassifier:
    """
    Clasificador mejorado que incluye categorías específicas de joyería
    """
    
    def __init__(self):
        """Inicializar el clasificador"""
        self.category_predictor = None
        
        if CATEGORY_PREDICTOR_AVAILABLE:
            try:
                self.category_predictor = JewelryCategoryPredictor()
                print("✅ Clasificador de joyería con categorías inicializado")
            except Exception as e:
                print(f"⚠️ Error inicializando predictor: {e}")
                self.category_predictor = None
        
        # Importar clasificador ML existente
        try:
            from MachineLearning.classify_image import ImageCategoryClassifier
            self.ml_classifier = ImageCategoryClassifier()
            print("✅ Clasificador ML base cargado")
        except ImportError as e:
            print(f"⚠️ Clasificador ML base no disponible: {e}")
            self.ml_classifier = None
    
    def enhanced_rectangle_analysis_with_categories(self, image_path: str) -> dict:
        """
        Análisis mejorado que incluye categorías de joyería
        
        Args:
            image_path: Ruta a la imagen a analizar
            
        Returns:
            dict: Resultado completo con categoría si es imagen de producto
        """
        result = {
            'image_path': image_path,
            'should_discard': False,
            'discard_reason': None,
            'category': None,
            'jewelry_category': None,
            'jewelry_category_display': None,
            'jewelry_css_class': None,
            'confidence': 0.0,
            'jewelry_confidence': 0.0,
            'analysis_steps': [],
            'features': {}
        }
        
        print(f"🔍 Analizando con categorías: {os.path.basename(image_path)}")
        
        # Paso 1: Usar el clasificador ML existente para extraer texto
        result['analysis_steps'].append('ml_classification')
        extracted_text = ""
        
        try:
            if self.ml_classifier:
                ml_result = self.ml_classifier.classify_image(image_path)
                
                # Si el ML ya lo descarta, respetamos esa decisión
                if ml_result['final_category'] == 'blank_image':
                    result['should_discard'] = True
                    result['discard_reason'] = f"ML: {ml_result.get('description', 'Imagen en blanco')}"
                    result['confidence'] = ml_result.get('confidence', 0.9)
                    print(f"  ❌ ML descarta: {result['discard_reason']}")
                    return result
                
                # Extraer texto del resultado ML
                if ml_result.get('ocr_result') and ml_result['ocr_result'].get('extracted_text'):
                    extracted_text = ml_result['ocr_result']['extracted_text'].strip()
                    
        except Exception as e:
            print(f"  ⚠️ Error en clasificador ML: {e}")
            extracted_text = ""
        
        # Paso 2: Análisis de medidas/pesos (MEJORADO)
        if extracted_text:
            result['analysis_steps'].append('enhanced_measurement_analysis')
            measurement_check = is_measurements_or_weight_only_enhanced(extracted_text)
            
            if measurement_check['is_only_measurement']:
                result['should_discard'] = True
                result['discard_reason'] = f"DESCARTADO - {measurement_check['type']}: '{measurement_check['original_text']}'"
                
                # Si es una corrección OCR, indicarlo
                if 'corrected_text' in measurement_check and measurement_check['original_text'] != measurement_check['corrected_text']:
                    result['discard_reason'] += f" (corrección OCR: '{measurement_check['corrected_text']}')"
                
                result['confidence'] = 0.98
                result['measurement_details'] = measurement_check
                print(f"  ❌ {result['discard_reason']}")
                return result
            else:
                print(f"  ✅ Texto válido: '{extracted_text}' - {measurement_check['reason']}")
        
        # Paso 3: Determinar si es código o imagen
        if extracted_text:
            # Determinar si es código o imagen usando lógica del ML
            if self.ml_classifier and hasattr(self.ml_classifier, 'classify_image'):
                try:
                    if ml_result.get('final_category') == 'product_code':
                        result['category'] = 'code'
                        print(f"  📝 Clasificado como CÓDIGO: '{extracted_text}'")
                    else:
                        result['category'] = 'image'
                        print(f"  🖼️ Clasificado como IMAGEN con texto: '{extracted_text}'")
                except:
                    result['category'] = 'image'
            else:
                # Fallback: clasificar basado en características del texto
                result['category'] = 'code' if self._is_likely_product_code(extracted_text) else 'image'
        else:
            result['category'] = 'image'  # Sin texto = imagen
            print(f"  🖼️ Clasificado como IMAGEN (sin texto)")
        
        # Paso 4: NUEVO - Si es imagen, predecir categoría de joyería
        if result['category'] == 'image' and self.category_predictor:
            result['analysis_steps'].append('jewelry_category_prediction')
            
            try:
                print(f"  🔮 Prediciendo categoría de joyería...")
                category_result = self.category_predictor.predict_jewelry_category(image_path)
                
                result['jewelry_category'] = category_result['category']
                result['jewelry_category_display'] = category_result['category_display']
                result['jewelry_css_class'] = category_result['css_class']
                result['jewelry_confidence'] = category_result['confidence']
                result['features'] = category_result.get('features', {})
                
                print(f"     🎯 Categoría detectada: {category_result['category_display']}")
                print(f"     📊 Confianza: {category_result['confidence']:.3f} ({category_result['confidence_level']})")
                
            except Exception as e:
                print(f"  ⚠️ Error prediciendo categoría: {e}")
                result['jewelry_category'] = 'sin_categoria'
                result['jewelry_category_display'] = '❓ Sin Categoría'
                result['jewelry_css_class'] = 'category-unknown'
                result['jewelry_confidence'] = 0.0
        
        # Establecer confianza general
        if result['category'] == 'image' and result.get('jewelry_confidence'):
            # Para imágenes, usar la confianza de la categoría de joyería
            result['confidence'] = min(0.8, 0.5 + result['jewelry_confidence'] / 2)
        else:
            result['confidence'] = 0.8
        
        print(f"  ✅ VÁLIDO - Categoría: {result['category']}")
        if result.get('jewelry_category'):
            print(f"      🏷️ Joyería: {result['jewelry_category_display']}")
        
        return result
    
    def _is_likely_product_code(self, text: str) -> bool:
        """
        Determina si un texto parece un código de producto
        Fallback para cuando no hay ML classifier
        """
        if not text or len(text.strip()) < 4:
            return False
        
        text = text.strip()
        
        # Patrones típicos de códigos de producto
        # 1. Empieza con 'c' seguido de números
        if text.lower().startswith('c') and len(text) > 5 and text[1:].isdigit():
            return True
        
        # 2. Solo números largos
        if text.isdigit() and len(text) >= 6:
            return True
        
        # 3. Patrón alfanumérico típico
        digits = sum(c.isdigit() for c in text)
        letters = sum(c.isalpha() for c in text)
        
        if len(text) >= 6 and digits >= 3 and letters >= 1:
            return True
        
        return False

def process_rectangles_with_categories(input_dir, codes_dir, images_dir, discards_dir):
    """
    Versión mejorada que incluye categorías de joyería para imágenes
    
    Args:
        input_dir: Directorio con las imágenes de rectángulos
        codes_dir: Directorio donde se guardarán los rectángulos de texto
        images_dir: Directorio donde se guardarán los rectángulos de imágenes
        discards_dir: Directorio donde se guardarán los rectángulos descartados
    """
    # Limpiar las carpetas de salida
    clean_output_directories(codes_dir, images_dir, discards_dir)
    
    # Crear clasificador mejorado
    classifier = EnhancedJewelryClassifier()
    
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
        match = re.search(r'rect_(\d+)', path.name)
        return int(match.group(1)) if match else float('inf')
    
    image_paths = sorted(image_paths, key=extract_rect_number)
    
    print(f"🔍 PROCESAMIENTO CON CATEGORÍAS - {len(image_paths)} rectángulos")
    print("   🎯 Detecta categorías: Anillos, Colgantes, Pulseras, Pendientes")
    print("=" * 70)
    
    # Contadores
    text_count = 0
    image_count = 0
    discard_count = 0
    category_stats = {}
    
    # Procesar cada imagen
    for i, image_path in enumerate(image_paths, 1):
        file_name = os.path.basename(str(image_path))
        print(f"\n📊 [{i}/{len(image_paths)}] {file_name}")
        
        # Análisis mejorado con categorías
        analysis = classifier.enhanced_rectangle_analysis_with_categories(str(image_path))
        
        if analysis['should_discard']:
            # Guardar en descartes
            discard_count += 1
            discard_destination = os.path.join(discards_dir, file_name)
            shutil.copy2(image_path, discard_destination)
            
            # Crear archivo de información del descarte
            info_filename = f"{os.path.splitext(file_name)[0]}_discard_info.json"
            info_path = os.path.join(discards_dir, info_filename)
            
            discard_info = {
                'filename': file_name,
                'reason': analysis['discard_reason'],
                'confidence': analysis['confidence'],
                'timestamp': datetime.now().isoformat(),
                'analysis_steps': analysis['analysis_steps']
            }
            
            import json
            with open(info_path, 'w', encoding='utf-8') as f:
                json.dump(discard_info, f, indent=2, ensure_ascii=False)
            
            print(f"  🗑️ DESCARTADO: {analysis['discard_reason']}")
            
        elif analysis['category'] == 'code':
            # Guardar como código
            code_destination = os.path.join(codes_dir, file_name)
            shutil.copy2(image_path, code_destination)
            text_count += 1
            print(f"  📝 → CÓDIGO guardado")
            
        elif analysis['category'] == 'image':
            # Guardar como imagen CON información de categoría
            image_destination = os.path.join(images_dir, file_name)
            shutil.copy2(image_path, image_destination)
            image_count += 1
            
            # Crear archivo JSON con información de categoría
            category_info_filename = f"{os.path.splitext(file_name)[0]}_category.json"
            category_info_path = os.path.join(images_dir, category_info_filename)
            
            category_info = {
                'filename': file_name,
                'category': analysis.get('jewelry_category', 'sin_categoria'),
                'category_display': analysis.get('jewelry_category_display', '❓ Sin Categoría'),
                'css_class': analysis.get('jewelry_css_class', 'category-unknown'),
                'confidence': analysis.get('jewelry_confidence', 0.0),
                'confidence_level': 'alta' if analysis.get('jewelry_confidence', 0) >= 0.8 else 'media' if analysis.get('jewelry_confidence', 0) >= 0.6 else 'baja',
                'features': analysis.get('features', {}),
                'timestamp': datetime.now().isoformat()
            }
            
            # Guardar información de categoría
            import json
            with open(category_info_path, 'w', encoding='utf-8') as f:
                json.dump(category_info, f, indent=2, ensure_ascii=False)
            
            # Actualizar estadísticas
            category = analysis.get('jewelry_category', 'sin_categoria')
            category_stats[category] = category_stats.get(category, 0) + 1
            
            print(f"  🖼️ → IMAGEN guardada")
            if analysis.get('jewelry_category'):
                print(f"      🏷️ Categoría: {analysis['jewelry_category_display']}")
    
    # Mostrar resumen
    print("\n" + "=" * 70)
    print("📊 RESUMEN CON CATEGORÍAS DE JOYERÍA")
    print("=" * 70)
    print(f"  📝 Códigos:    {text_count}")
    print(f"  🖼️ Imágenes:   {image_count}")
    print(f"  🗑️ Descartes:  {discard_count}")
    print(f"  📦 Total:      {len(image_paths)}")
    
    if category_stats:
        print(f"\n🏷️ CATEGORÍAS DE JOYERÍA DETECTADAS:")
        category_display = {
            'anillos': '💍 Anillos',
            'colgantes y collares': '🔗 Colgantes y Collares',
            'pulseras': '⌚ Pulseras', 
            'pendientes': '👂 Pendientes',
            'sin_categoria': '❓ Sin Categoría'
        }
        
        for category, count in sorted(category_stats.items(), key=lambda x: x[1], reverse=True):
            display_name = category_display.get(category, category)
            percentage = (count / image_count * 100) if image_count > 0 else 0
            print(f"  • {display_name}: {count} imágenes ({percentage:.1f}%)")
    
    # Verificar balance
    if text_count == image_count:
        print(f"\n✅ BALANCE PERFECTO: {text_count} códigos ↔ {image_count} imágenes")
    else:
        diff = abs(text_count - image_count)
        print(f"\n⚖️ BALANCE: {text_count} códigos vs {image_count} imágenes (diferencia: {diff})")
    
    print(f"\n📁 Archivos guardados en:")
    print(f"  📝 Códigos: {codes_dir}")
    print(f"  🖼️ Imágenes: {images_dir} (con archivos JSON de categorías)")
    print(f"  🗑️ Descartes: {discards_dir}")
    
    print(f"\n🎯 FUNCIONALIDADES NUEVAS:")
    print(f"  ✅ Categorización automática de imágenes de joyería")
    print(f"  ✅ Archivos JSON con información detallada de categorías")
    print(f"  ✅ Estadísticas por tipo de joyería")
    print(f"  ✅ Preparado para mostrar tarjetas en la interfaz web")

if __name__ == "__main__":
    # Valores predeterminados
    input_dir = "/home/slendy/PythonProjects/ImagesManagement/rectangles_output"
    codes_dir = "/home/slendy/PythonProjects/ImagesManagement/codes_output"
    images_dir = "/home/slendy/PythonProjects/ImagesManagement/images_output"
    discards_dir = "/home/slendy/PythonProjects/ImagesManagement/discards_output"
    
    print("🚀 PROCESADOR CON CATEGORÍAS DE JOYERÍA")
    print("   ✅ Clasifica automáticamente: Anillos, Colgantes, Pulseras, Pendientes")
    print("   ✅ Genera archivos JSON con información detallada")
    print("   ✅ Compatible con interfaz web mejorada")
    print("=" * 70)
    
    # Ejecutar procesamiento
    process_rectangles_with_categories(input_dir, codes_dir, images_dir, discards_dir)
