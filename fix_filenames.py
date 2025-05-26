#!/usr/bin/env python3
"""
Script para limpiar nombres de archivos y eliminar sufijos innecesarios
"""

import os
import re
import shutil

def fix_filenames_in_directory(directory_path):
    """
    Renombra archivos eliminando sufijos comunes como _discard, _code, _image, etc.
    """
    if not os.path.exists(directory_path):
        print(f"❌ Directorio no existe: {directory_path}")
        return
    
    print(f"🔍 Verificando archivos en: {directory_path}")
    files = os.listdir(directory_path)
    image_files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    if not image_files:
        print(f"  ℹ️  No hay archivos de imagen")
        return
    
    print(f"  📁 Encontrados {len(image_files)} archivos de imagen")
    
    renamed_count = 0
    
    for filename in image_files:
        original_path = os.path.join(directory_path, filename)
        
        # Buscar patrones de sufijos comunes
        patterns_to_remove = [
            r'_discard',
            r'_discarded', 
            r'_code',
            r'_codes',
            r'_image',
            r'_images',
            r'_text',
            r'_rejected',
            r'_reject',
            r'_waste',
            r'_trash'
        ]
        
        new_filename = filename
        has_suffix = False
        
        for pattern in patterns_to_remove:
            if re.search(pattern, filename, re.IGNORECASE):
                new_filename = re.sub(pattern, '', filename, flags=re.IGNORECASE)
                has_suffix = True
                break
        
        # También remover números duplicados como rect_1_1.png -> rect_1.png
        new_filename = re.sub(r'_(\d+)_\1', r'_\1', new_filename)
        
        if has_suffix or new_filename != filename:
            new_path = os.path.join(directory_path, new_filename)
            
            # Verificar que el nuevo nombre no exista ya
            if os.path.exists(new_path):
                print(f"  ⚠️  No se puede renombrar {filename} -> {new_filename} (ya existe)")
                continue
            
            try:
                os.rename(original_path, new_path)
                print(f"  ✅ Renombrado: {filename} -> {new_filename}")
                renamed_count += 1
            except Exception as e:
                print(f"  ❌ Error renombrando {filename}: {e}")
        else:
            print(f"  ✓  OK: {filename}")
    
    if renamed_count > 0:
        print(f"  🎉 {renamed_count} archivos renombrados")
    else:
        print(f"  ✓  Todos los nombres están correctos")
    
    return renamed_count

def main():
    """Función principal"""
    print("🚀 Iniciando limpieza de nombres de archivos...")
    print("=" * 50)
    
    # Directorios a verificar
    directories = [
        'codes_output',
        'images_output', 
        'discards_output',
        'rectangles_output'
    ]
    
    total_renamed = 0
    
    for directory in directories:
        renamed = fix_filenames_in_directory(directory)
        total_renamed += renamed
        print()
    
    print("=" * 50)
    if total_renamed > 0:
        print(f"🎯 Total de archivos renombrados: {total_renamed}")
        print("✅ Limpieza completada - los archivos ahora tienen nombres limpios")
    else:
        print("✅ Todos los archivos ya tenían nombres correctos")
    
    # Verificar el estado final
    print("\n📋 Estado final:")
    for directory in directories:
        if os.path.exists(directory):
            files = [f for f in os.listdir(directory) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            print(f"  {directory}: {len(files)} archivos")
            for f in files[:3]:  # Mostrar primeros 3 como ejemplo
                print(f"    - {f}")
            if len(files) > 3:
                print(f"    ... y {len(files) - 3} más")

if __name__ == "__main__":
    main()
