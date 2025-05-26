#!/usr/bin/env python3
"""
VERSIÓN MEJORADA para el problema de confusión OCR entre '11' y 'll'
Específicamente orientada a manejar casos como '6. llg' que deberían ser '6.11g'
ACTUALIZADA: Descarta más agresivamente unidades de medida problemáticas
"""

import cv2
import numpy as np
import os
import shutil
from pathlib import Path
import sys
import re
from datetime import datetime
from MachineLearning.classify_image import ImageCategoryClassifier

def clean_output_directories(codes_dir, images_dir, discards_dir):
    """Limpia las carpetas de salida para comenzar desde cero."""
    print("Limpiando directorios de salida...")
    
    for directory in [codes_dir, images_dir, discards_dir]:
        if os.path.exists(directory):
            shutil.rmtree(directory)
        os.makedirs(directory, exist_ok=True)
    
    print("Directorios de salida limpios y listos para nuevos archivos.")

def is_measurements_or_weight_only_enhanced(text: str) -> dict:
    """
    VERSIÓN MEJORADA: Detecta medidas/pesos incluyendo confusiones OCR como 'll' en lugar de '11'
    ACTUALIZADA: Descarta más agresivamente unidades problemáticas
    
    Args:
        text: Texto extraído del rectángulo
        
    Returns:
        dict: {
            'is_only_measurement': bool,
            'type': str,
            'reason': str,
            'matched_pattern': str,
            'original_text': str,
            'cleaned_text': str,
            'corrected_text': str (opcional)
        }
    """
    if not text or len(text.strip()) == 0:
        return {
            'is_only_measurement': False,
            'type': 'empty',
            'reason': 'Texto vacío',
            'matched_pattern': None
        }
    
    # LIMPIEZA AGRESIVA para manejar variaciones de OCR
    text_original = text.strip()
    print(f"   📝 Texto original: '{text_original}'")
    
    # Paso 1: Aplicar correcciones específicas para errores OCR comunes
    # Corregir confusión de 'll' por '11'
    corrected_text = text_original
    if 'll' in corrected_text.lower():
        ocr_fixed = corrected_text.lower().replace('ll', '11')
        print(f"   🔄 Corrección OCR: '{corrected_text}' → '{ocr_fixed}' (ll → 11)")
        corrected_text = ocr_fixed
    
    # Paso 2: Normalización y limpieza estándar
    text_clean = corrected_text.upper()
    text_clean = re.sub(r'(\d)\s+([A-Z])', r'\1\2', text_clean)
    text_clean = re.sub(r'(\d)\s*\.\s*(\d)', r'\1.\2', text_clean)  # "6. 11" → "6.11"
    text_clean = re.sub(r'\s+', '', text_clean)  # Eliminar espacios restantes
    text_clean = text_clean.replace(',', '.')    # "6,11g" → "6.11g"
    
    print(f"   🧹 Texto limpio final: '{text_clean}'")
    
    # NUEVA SECCIÓN: Descarte ultra-agresivo para problemas específicos
    problematic_patterns = [
        # === PATRONES PROBLEMÁTICOS ESPECÍFICOS ===
        r'^\d+\.\d+[G|GR|GRAM|GRAMOS|GMS]$',  # Cualquier decimal + unidad de peso
        r'^\d+\.\d+[K|KG|KT|QUILATES]$',      # Cualquier decimal + unidad de peso/material
        r'^\d+\.\d+[C|CM|M|MM|IN|INCH]$',     # Cualquier decimal + unidad de longitud
        r'^\d+\.\d+[L|ML|CL|CC|GAL]$',        # Cualquier decimal + unidad de volumen
        r'^\d+\.\d+[%|€|\$|USD|EUR]$',        # Cualquier decimal + símbolo monetario/porcentaje
        r'^\d+\.\d{1,2}G$',                   # Específicamente para casos como "6.1G", "7.25G"
        r'^\d+\.\d{1,2}KG$',                  # Específicamente para casos como "1.5KG", "0.8KG"
        r'^\d+\.\d{1,2}CM$',                  # Específicamente para casos como "2.5CM", "1.2CM"
        r'^\d+\.\d{1,2}MM$',                  # Específicamente para casos como "5.3MM", "7.8MM"
    ]
    
    # Primero probar los patrones problemáticos específicos (máxima prioridad)
    for pattern in problematic_patterns:
        if re.match(pattern, text_clean):
            print(f"   🚨 DETECTADO patrón problemático: {pattern}")
            return {
                'is_only_measurement': True,
                'type': 'problematic_measurement',
                'reason': 'Patrón problemático de medida con decimal (ej: 6.1g)',
                'matched_pattern': pattern,
                'original_text': text_original,
                'cleaned_text': text_clean,
                'corrected_text': corrected_text
            }
    
    # PATRONES ESPECÍFICOS MEJORADOS PARA DESCARTAR - VERSIÓN AGRESIVA
    discard_patterns = {
        # === PESOS (MEJORADOS Y MÁS AGRESIVOS) ===
        'weight_decimal': [
            r'^\d+\.\d+G$',         # "6.11G", "7.3G", "12.5G", "6.1G"
            r'^\d+\.\d+GR$',        # "6.11GR", "7.3GR", "12.5GR", "6.1GR"
            r'^\d+\.\d+GRAMOS$',    # "6.11GRAMOS", "6.1GRAMOS"
            r'^\d+\.\d+GRAM$',      # "6.11GRAM", "6.1GRAM"
            r'^\d+\.\d+GMS$',       # "6.11GMS", "6.1GMS"
            r'^\d+\.\d+KG$',        # "1.5KG", "0.1KG"
            r'^\d+\.\d+OZ$',        # "0.26OZ", "0.1OZ"
            r'^\d+\.\d+LLG$',       # "6.11LLG" o "6.llG" (error OCR)
            r'^\d+\.\d+LG$',        # "6.11LG" o "6.lG" (error OCR)
            r'^\d+\.\d+LB$',        # "2.5LB", "0.1LB"
            r'^\d+\.\d+LIBRAS$',    # "2.5LIBRAS", "0.1LIBRAS"
            r'^\d+\.\d+POUNDS$',    # "2.5POUNDS", "0.1POUNDS"
        ],
        'weight_integer': [
            r'^\d+G$',              # "3G", "34G", "1G"
            r'^\d+GR$',             # "3GR", "34GR", "1GR"
            r'^\d+GRAMOS$',         # "3GRAMOS", "1GRAMOS"
            r'^\d+GRAM$',           # "3GRAM", "1GRAM"
            r'^\d+GMS$',            # "3GMS", "1GMS"
            r'^\d+KG$',             # "1KG", "0KG"
            r'^\d+OZ$',             # "1OZ", "0OZ"
            r'^\d+LLG$',            # "6LLG" o "6llG" (error OCR)
            r'^\d+LG$',             # "6LG" o "6lG" (error OCR)
            r'^\d+LB$',             # "2LB", "1LB"
            r'^\d+LIBRAS$',         # "2LIBRAS", "1LIBRAS"
            r'^\d+POUNDS$',         # "2POUNDS", "1POUNDS"
        ],
        
        # === MEDIDAS/DIMENSIONES (MEJORADAS Y MÁS AGRESIVAS) ===
        'measurement_decimal': [
            r'^\d+\.\d+CM$',        # "2.5CM", "10.2CM", "0.1CM"
            r'^\d+\.\d+MM$',        # "7.3MM", "15.8MM", "0.1MM"
            r'^\d+\.\d+M$',         # "1.2M", "0.1M"
            r'^\d+\.\d+PULGADAS$',  # "2.5PULGADAS", "0.1PULGADAS"
            r'^\d+\.\d+IN$',        # "2.5IN", "0.1IN"
            r'^\d+\.\d+INCH$',      # "2.5INCH", "0.1INCH"
            r'^\d+\.\d+FT$',        # "2.5FT", "0.1FT"
            r'^\d+\.\d+FEET$',      # "2.5FEET", "0.1FEET"
            r'^\d+\.\d+YD$',        # "2.5YD", "0.1YD"
            r'^\d+\.\d+YARD$',      # "2.5YARD", "0.1YARD"
        ],
        'measurement_integer': [
            r'^\d+CM$',             # "2CM", "22CM", "0CM"
            r'^\d+MM$',             # "5MM", "10MM", "0MM"
            r'^\d+M$',              # "1M", "0M"
            r'^\d+PULGADAS$',       # "5PULGADAS", "0PULGADAS"
            r'^\d+IN$',             # "5IN", "0IN"
            r'^\d+INCH$',           # "5INCH", "0INCH"
            r'^\d+FT$',             # "2FT", "0FT"
            r'^\d+FEET$',           # "2FEET", "0FEET"
            r'^\d+YD$',             # "2YD", "0YD"
            r'^\d+YARD$',           # "2YARD", "0YARD"
        ],
        
        # === NÚMEROS PEQUEÑOS (PROBABLEMENTE TALLAS) ===
        'size_number': [
            r'^\d{1,2}$',           # "6", "7", "42" (números de 1-2 dígitos)
            r'^\d+\.\d+$',          # "6.5", "7.5", "6.1" (tallas decimales)
        ],
        
        # === UNIDADES ESPECÍFICAS ===
        'specific_units': [
            r'^LLG$',               # Solo "LLG" (probablemente error OCR para "11G")
            r'^G$',                 # Solo "G"
            r'^KG$',                # Solo "KG"
            r'^L$',                 # Solo "L"
            r'^ML$',                # Solo "ML"
            r'^CM$',                # Solo "CM"
            r'^MM$',                # Solo "MM"
        ],
    }
    
    # CASOS ESPECIALES para patrones con formato atípico - MÁS AGRESIVOS
    special_cases = [
        # === CONFUSIONES OCR ESPECÍFICAS ===
        r'^\d+\.\s*LLG$',       # "6. LLG", "6.LLG" (probablemente "6.11G")
        r'^\d+\s+LLG$',         # "6 LLG" (probablemente "6 11G")
        r'^\d+\.\s*G$',         # "6. G", "6.G"
        r'^\d+\s+G$',           # "6 G"
        r'^\d+\.\s*KG$',        # "6. KG", "6.KG"
        r'^\d+\s+KG$',          # "6 KG"
        
        # === NÚMEROS CON UN SOLO DÍGITO DECIMAL (MUY PROBLEMÁTICOS) ===
        r'^\d+\.\d$',           # "6.1", "7.5", "8.3" (sin unidad pero formato de medida)
        r'^\d+\.\d[A-Z]*$',     # "6.1G", "7.5K", "8.3CM" etc.
        
        # === PATRONES NUMÉRICOS QUE PARECEN MEDIDAS ===
        r'^\d+\.\s*\d+$',       # "6. 11", "6.11" (sin unidad pero probablemente medida)
        r'^\d+\.\s*LL$',        # "6. LL", "6.LL" (probablemente "6.11")
        r'^\d+\.\s*ll$',        # "6. ll", "6.ll" (minúsculas)
        r'^\d+\.\s*II$',        # "6. II", "6.II" (confusión con números romanos)
        
        # === PATRONES DE UN SOLO DÍGITO DECIMAL MUY ESPECÍFICOS ===
        r'^\d\.\d+[A-Z]*$',     # "6.1g", "7.2kg", "5.8cm" (un dígito antes del punto)
        r'^\d{1,2}\.\d{1,2}[A-Z]*$',  # Hasta 2 dígitos antes y después del punto con unidad
    ]
    
    # Segundo, probar los casos especiales (alta prioridad)
    for pattern in special_cases:
        if re.match(pattern, text_clean) or re.match(pattern, text_original.upper()):
            print(f"   🎯 DETECTADO caso especial: patrón {pattern}")
            return {
                'is_only_measurement': True,
                'type': 'special_case',
                'reason': 'Caso especial de medida/peso con formato atípico o error OCR',
                'matched_pattern': pattern,
                'original_text': text_original,
                'cleaned_text': text_clean,
                'corrected_text': corrected_text
            }
    
    # Tercero, probar los patrones regulares
    for category, patterns in discard_patterns.items():
        for pattern in patterns:
            if re.match(pattern, text_clean):
                print(f"   🎯 DETECTADO como {category}: patrón {pattern}")
                return {
                    'is_only_measurement': True,
                    'type': category,
                    'reason': f'Coincide con patrón de {category}',
                    'matched_pattern': pattern,
                    'original_text': text_original,
                    'cleaned_text': text_clean,
                    'corrected_text': corrected_text
                }
    
    # Caso específico: Detectar "6. llg" como medida por su formato
    if re.search(r'\d+\s*\.\s*ll', text_original.lower()):
        print(f"   🎯 DETECTADO caso específico: formato '6. llg' (error OCR)")
        return {
            'is_only_measurement': True,
            'type': 'ocr_error_weight',
            'reason': 'Formato que corresponde a error OCR en peso (ll en lugar de 11)',
            'matched_pattern': r'\d+\s*\.\s*ll',
            'original_text': text_original,
            'cleaned_text': text_clean,
            'corrected_text': corrected_text
        }
    
    # NUEVO: Verificación adicional para números decimales sospechosos
    if re.match(r'^\d+\.\d{1,2}$', text_clean):  # Números como "6.1", "7.25", etc.
        print(f"   🤔 SOSPECHOSO: Número decimal sin unidad que podría ser medida")
        return {
            'is_only_measurement': True,
            'type': 'suspicious_decimal',
            'reason': 'Número decimal sospechoso sin unidad (probablemente medida)',
            'matched_pattern': r'^\d+\.\d{1,2}$',
            'original_text': text_original,
            'cleaned_text': text_clean,
            'corrected_text': corrected_text
        }
    
    # Si llegamos aquí, NO es solo una medida/peso
    print(f"   ✅ NO es medida/peso - texto válido para clasificación")
    return {
        'is_only_measurement': False,
        'type': 'valid_content',
        'reason': 'No coincide con patrones de medidas/pesos únicamente',
        'matched_pattern': None,
        'original_text': text_original,
        'cleaned_text': text_clean,
        'corrected_text': corrected_text
    }

def enhanced_rectangle_analysis(image_path: str) -> dict:
    """
    Análisis mejorado que combina OCR + detección de medidas/pesos + análisis visual
    """
    result = {
        'image_path': image_path,
        'should_discard': False,
        'discard_reason': None,
        'category': None,
        'confidence': 0.0,
        'analysis_steps': []
    }
    
    print(f"🔍 Analizando: {os.path.basename(image_path)}")
    
    # Paso 1: Usar el clasificador ML existente para extraer texto
    result['analysis_steps'].append('ml_classification')
    try:
        classifier = ImageCategoryClassifier()
        ml_result = classifier.classify_image(image_path)
        
        # Si el ML ya lo descarta, respetamos esa decisión
        if ml_result['final_category'] == 'blank_image':
            result['should_discard'] = True
            result['discard_reason'] = f"ML: {ml_result.get('description', 'Imagen en blanco')}"
            result['confidence'] = ml_result.get('confidence', 0.9)
            print(f"  ❌ ML descarta: {result['discard_reason']}")
            return result
        
        # Extraer texto del resultado ML
        extracted_text = ""
        if ml_result.get('ocr_result') and ml_result['ocr_result'].get('extracted_text'):
            extracted_text = ml_result['ocr_result']['extracted_text'].strip()
            
    except Exception as e:
        print(f"  ⚠️ Error en clasificador ML: {e}")
        extracted_text = ""
    
    # Paso 2: MEJORADO - Análisis de medidas/pesos con corrección OCR MÁS AGRESIVO
    if extracted_text:
        result['analysis_steps'].append('enhanced_measurement_analysis')
        measurement_check = is_measurements_or_weight_only_enhanced(extracted_text)
        
        if measurement_check['is_only_measurement']:
            result['should_discard'] = True
            result['discard_reason'] = f"DESCARTADO - {measurement_check['type']}: '{measurement_check['original_text']}'"
            
            # Si es una corrección OCR, indicarlo en la razón de descarte
            if 'corrected_text' in measurement_check and measurement_check['original_text'] != measurement_check['corrected_text']:
                result['discard_reason'] += f" (corrección OCR: '{measurement_check['corrected_text']}')"
            
            result['confidence'] = 0.98
            result['measurement_details'] = measurement_check
            print(f"  ❌ {result['discard_reason']}")
            print(f"     Patrón detectado: {measurement_check['matched_pattern']}")
            return result
        else:
            print(f"  ✅ Texto válido: '{extracted_text}' - {measurement_check['reason']}")
    
    # Paso 3: Si no hay texto o el texto es válido, usar clasificación ML
    if extracted_text:
        # Determinar si es código o imagen usando lógica del ML actualizado
        if ml_result.get('final_category') == 'product_code':
            result['category'] = 'code'
            print(f"  📝 Clasificado como CÓDIGO: '{extracted_text}'")
        else:
            result['category'] = 'image'
            print(f"  🖼️ Clasificado como IMAGEN con texto: '{extracted_text}'")
    else:
        result['category'] = 'image'  # Sin texto = imagen
        print(f"  🖼️ Clasificado como IMAGEN (sin texto)")
    
    result['confidence'] = 0.8
    print(f"  ✅ VÁLIDO - Categoría final: {result['category']}")
    
    return result

def process_rectangles_improved(input_dir, codes_dir, images_dir, discards_dir):
    """
    Versión mejorada que descarta específicamente rectángulos con solo medidas/pesos
    con mayor robustez ante variaciones de OCR y confusiones entre 'll' y '11'.
    ACTUALIZADA: Más agresiva con unidades problemáticas como "6.1g"
    NUEVA: Crea directorio de descartes para análisis posterior
    
    Args:
        input_dir: Directorio con las imágenes de rectángulos
        codes_dir: Directorio donde se guardarán los rectángulos de texto
        images_dir: Directorio donde se guardarán los rectángulos de imágenes
        discards_dir: Directorio donde se guardarán los rectángulos descartados
    """
    # Limpiar las carpetas de salida
    clean_output_directories(codes_dir, images_dir, discards_dir)
    
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
    
    print(f"🔍 ANÁLISIS ULTRA-MEJORADO - Procesando {len(image_paths)} rectángulos")
    print("   🚨 MODO AGRESIVO: Descarta unidades problemáticas como '6.1g'")
    print("=" * 70)
    
    # Contadores mejorados
    text_count = 0
    image_count = 0
    discard_count = 0
    discard_reasons = {}
    
    # Procesar cada imagen con análisis mejorado
    for i, image_path in enumerate(image_paths, 1):
        file_name = os.path.basename(str(image_path))
        print(f"\n📊 [{i}/{len(image_paths)}] {file_name}")
        
        # Análisis mejorado
        analysis = enhanced_rectangle_analysis(str(image_path))
        
        if analysis['should_discard']:
            # Guardar en directorio de descartes con información detallada
            discard_count += 1
            reason = analysis['discard_reason']
            discard_reasons[reason] = discard_reasons.get(reason, 0) + 1
            
            # Crear nombre de archivo con información del descarte
            base_name = os.path.splitext(file_name)[0]
            ext = os.path.splitext(file_name)[1]
            safe_reason = analysis['measurement_details']['type'] if 'measurement_details' in analysis else 'unknown'
            discard_filename = f"{base_name}_{safe_reason}{ext}"
            
            # Copiar imagen a directorio de descartes
            discard_destination = os.path.join(discards_dir, discard_filename)
            shutil.copy2(image_path, discard_destination)
            
            # Crear archivo de texto con detalles del descarte
            txt_filename = f"{base_name}_{safe_reason}_info.txt"
            txt_destination = os.path.join(discards_dir, txt_filename)
            
            with open(txt_destination, 'w', encoding='utf-8') as f:
                f.write(f"ARCHIVO DESCARTADO: {file_name}\n")
                f.write(f"FECHA: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"RAZÓN: {reason}\n")
                f.write(f"CONFIANZA: {analysis['confidence']:.2f}\n")
                if 'measurement_details' in analysis:
                    details = analysis['measurement_details']
                    f.write(f"\nDETALLES TÉCNICOS:\n")
                    f.write(f"- Tipo: {details['type']}\n")
                    f.write(f"- Texto original: '{details['original_text']}'\n")
                    f.write(f"- Texto limpio: '{details['cleaned_text']}'\n")
                    if 'corrected_text' in details:
                        f.write(f"- Texto corregido: '{details['corrected_text']}'\n")
                    f.write(f"- Patrón detectado: {details['matched_pattern']}\n")
                    f.write(f"- Explicación: {details['reason']}\n")
            
            print(f"  🗑️ DESCARTADO: {reason}")
            print(f"     → Guardado en: {discard_destination}")
            print(f"     → Info en: {txt_destination}")
            
        elif analysis['category'] == 'code':
            # Copiar a directorio de códigos
            destination = os.path.join(codes_dir, file_name)
            shutil.copy2(image_path, destination)
            text_count += 1
            print(f"  📝 → CÓDIGO guardado en: {destination}")
            
        elif analysis['category'] == 'image':
            # Copiar a directorio de imágenes
            destination = os.path.join(images_dir, file_name)
            shutil.copy2(image_path, destination)
            image_count += 1
            print(f"  🖼️ → IMAGEN guardada en: {destination}")
        
        else:
            # Caso inesperado - descartar por seguridad
            discard_count += 1
            discard_reasons['categoria_desconocida'] = discard_reasons.get('categoria_desconocida', 0) + 1
            print(f"  ❓ DESCARTADO: Categoría desconocida")
    
    # Mostrar resumen detallado
    print("\n" + "=" * 70)
    print("📊 RESUMEN FINAL DEL ANÁLISIS ULTRA-MEJORADO")
    print("=" * 70)
    print(f"  📝 Rectángulos de código:  {text_count}")
    print(f"  🖼️ Rectángulos de imagen:  {image_count}")
    print(f"  🗑️ Rectángulos descartados: {discard_count}")
    print(f"  📦 Total procesado:        {len(image_paths)}")
    
    if discard_reasons:
        print(f"\n🔍 RAZONES DE DESCARTE:")
        for reason, count in sorted(discard_reasons.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {reason}: {count} rectángulos")
    
    # Verificar balance
    total_valid = text_count + image_count
    discard_percentage = (discard_count / len(image_paths)) * 100
    
    print(f"\n📈 ESTADÍSTICAS:")
    print(f"  • Rectángulos válidos: {total_valid} ({100-discard_percentage:.1f}%)")
    print(f"  • Rectángulos descartados: {discard_count} ({discard_percentage:.1f}%)")
    
    if text_count == image_count:
        print(f"\n✅ BALANCE PERFECTO: {text_count} códigos ↔ {image_count} imágenes")
    else:
        diff = abs(text_count - image_count)
        print(f"\n⚖️ BALANCE: {text_count} códigos vs {image_count} imágenes (diferencia: {diff})")
    print(f"\n📁 Archivos guardados en:")
    print(f"  📝 Códigos: {codes_dir}")
    print(f"  🖼️ Imágenes: {images_dir}")
    print(f"  🗑️ Descartes: {discards_dir} (con detalles técnicos)")
    
    print(f"\n🎯 MEJORAS APLICADAS:")
    print(f"  ✅ Corrección OCR específica para confusión de 'll' y '11'")
    print(f"  ✅ Detección de casos como '6. llg' que debería ser '6.11g'")
    print(f"  ✅ Soporte para variantes de formato (6. llg, 6.llg, 6 llg)")
    print(f"  ✅ Detección de unidades aisladas (llg, g, kg, etc.)")
    print(f"  ✅ Limpieza agresiva de texto para manejar variaciones de OCR")
    print(f"  🚨 NUEVO: Descarte agresivo de medidas problemáticas como '6.1g'")
    print(f"  🚨 NUEVO: Patrones específicos para decimales con unidades")
    print(f"  🚨 NUEVO: Detección de números decimales sospechosos sin unidad")

if __name__ == "__main__":
    # Obtener parámetros de línea de comandos o usar valores predeterminados
    if len(sys.argv) > 4:
        input_dir = sys.argv[1]
        codes_dir = sys.argv[2]
        images_dir = sys.argv[3]
        discards_dir = sys.argv[4]
    else:
        # Valores predeterminados
        input_dir = "/home/slendy/PythonProjects/ImagesManagement/rectangles_output"
        codes_dir = "/home/slendy/PythonProjects/ImagesManagement/codes_output"
        images_dir = "/home/slendy/PythonProjects/ImagesManagement/images_output"
        discards_dir = "/home/slendy/PythonProjects/ImagesManagement/discards_output"
    
    print("🚀 PROCESADOR DE RECTÁNGULOS - VERSIÓN ULTRA-MEJORADA")
    print("   ✅ Descarta automáticamente medidas, pesos y contenido no relevante")
    print("   ✅ Corrección para la confusión OCR entre 'll' y '11'")
    print("   ✅ Detección específica de '6. llg' como error OCR para '6.11g'")
    print("   🚨 NUEVO: Descarte agresivo de unidades problemáticas como '6.1g'")
    print("=" * 70)
    
    # Ejecutar el procesamiento mejorado
    process_rectangles_improved(input_dir, codes_dir, images_dir, discards_dir)
