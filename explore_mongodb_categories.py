#!/usr/bin/env python3
"""
Script para explorar las categorías existentes en MongoDB y crear un clasificador automático
"""

from connect_mongodb import return_mongo_client
import json
from collections import Counter

def explore_categories():
    """Explora las categorías existentes en la base de datos"""
    client = return_mongo_client()
    db = client['images_db']
    collection = db['codes_images']
    
    print("🔍 Explorando categorías existentes en MongoDB...")
    
    # Obtener todos los documentos
    documents = list(collection.find({}))
    print(f"📊 Total de documentos: {len(documents)}")
    
    # Analizar categorías
    categories = []
    category_counter = Counter()
    
    print("\n📋 Análisis de categorías:")
    print("-" * 50)
    
    for doc in documents:
        category = doc.get('category', 'sin_categoria')
        categories.append(category)
        category_counter[category] += 1
        
        # Mostrar algunos ejemplos
        if len([c for c in categories if c == category]) <= 3:
            code = doc.get('code', 'Sin código')
            created = doc.get('created_at', 'Sin fecha')
            print(f"  📝 {code} → {category} (creado: {created})")
    
    print("\n📊 Resumen de categorías:")
    print("-" * 50)
    for category, count in category_counter.most_common():
        percentage = (count / len(documents)) * 100
        print(f"  {category}: {count} documentos ({percentage:.1f}%)")
    
    print(f"\n🎯 Categorías únicas encontradas: {len(category_counter)}")
    print(f"📝 Categorías disponibles: {list(category_counter.keys())}")
    
    # Analizar códigos para encontrar patrones
    print("\n🔍 Análisis de patrones en códigos:")
    print("-" * 50)
    
    code_patterns = {}
    for doc in documents:
        code = doc.get('code', '')
        category = doc.get('category', 'sin_categoria')
        
        # Analizar patrones de códigos
        if code:
            # Patrones comunes
            if code.startswith('TODZ'):
                pattern = 'TODZ_pattern'
            elif code.isdigit():
                if len(code) >= 9:
                    pattern = 'numeric_long'
                else:
                    pattern = 'numeric_short'
            elif any(char.isalpha() for char in code) and any(char.isdigit() for char in code):
                pattern = 'alphanumeric'
            else:
                pattern = 'other'
            
            if pattern not in code_patterns:
                code_patterns[pattern] = {}
            
            if category not in code_patterns[pattern]:
                code_patterns[pattern][category] = []
            
            code_patterns[pattern][category].append(code)
    
    # Mostrar patrones
    for pattern, categories in code_patterns.items():
        print(f"\n  🔸 Patrón {pattern}:")
        for cat, codes in categories.items():
            example_codes = codes[:3]  # Mostrar primeros 3 ejemplos
            print(f"    → {cat}: {len(codes)} códigos (ej: {', '.join(example_codes)})")
    
    # Crear reglas de categorización automática
    create_categorization_rules(code_patterns, category_counter)
    
    return category_counter, code_patterns

def create_categorization_rules(code_patterns, category_counter):
    """Crea reglas automáticas de categorización basadas en los patrones encontrados"""
    print("\n🤖 Generando reglas de categorización automática:")
    print("-" * 50)
    
    rules = {}
    
    # Analizar cada patrón para encontrar la categoría más común
    for pattern, categories in code_patterns.items():
        # Encontrar la categoría más común para este patrón
        pattern_counter = Counter()
        for cat, codes in categories.items():
            pattern_counter[cat] += len(codes)
        
        if pattern_counter:
            most_common_category = pattern_counter.most_common(1)[0]
            category, count = most_common_category
            total_in_pattern = sum(pattern_counter.values())
            confidence = (count / total_in_pattern) * 100
            
            rules[pattern] = {
                'category': category,
                'confidence': confidence,
                'sample_count': total_in_pattern
            }
            
            print(f"  🔸 {pattern} → {category} (confianza: {confidence:.1f}%, muestras: {total_in_pattern})")
    
    # Guardar reglas en archivo JSON
    rules_file = "categorization_rules.json"
    with open(rules_file, 'w', encoding='utf-8') as f:
        json.dump({
            'rules': rules,
            'category_stats': dict(category_counter),
            'total_samples': sum(category_counter.values()),
            'generated_at': str(Counter())  # Timestamp placeholder
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Reglas guardadas en: {rules_file}")
    
    return rules

def test_categorization_rules(code_sample):
    """Prueba las reglas de categorización con un código de ejemplo"""
    try:
        with open("categorization_rules.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
        rules = data['rules']
    except FileNotFoundError:
        print("❌ No se encontraron reglas de categorización. Ejecuta explore_categories() primero.")
        return None
    
    print(f"\n🧪 Probando categorización para código: '{code_sample}'")
    
    # Determinar patrón del código
    if code_sample.startswith('TODZ'):
        pattern = 'TODZ_pattern'
    elif code_sample.isdigit():
        if len(code_sample) >= 9:
            pattern = 'numeric_long'
        else:
            pattern = 'numeric_short'
    elif any(char.isalpha() for char in code_sample) and any(char.isdigit() for char in code_sample):
        pattern = 'alphanumeric'
    else:
        pattern = 'other'
    
    print(f"  🔍 Patrón detectado: {pattern}")
    
    if pattern in rules:
        rule = rules[pattern]
        category = rule['category']
        confidence = rule['confidence']
        print(f"  🎯 Categoría predicha: {category} (confianza: {confidence:.1f}%)")
        return category, confidence
    else:
        print(f"  ❓ No se encontró regla para el patrón '{pattern}'")
        return None, 0

if __name__ == "__main__":
    print("🚀 Explorador de Categorías MongoDB")
    print("=" * 50)
    
    # Explorar categorías existentes
    categories, patterns = explore_categories()
    
    # Probar con algunos códigos de ejemplo
    test_codes = ["TODZ1026", "018114700", "c1004290512", "123456"]
    
    print("\n🧪 Probando reglas de categorización:")
    print("-" * 50)
    
    for code in test_codes:
        test_categorization_rules(code)
