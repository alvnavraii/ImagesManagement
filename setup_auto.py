#!/usr/bin/env python3
"""
Script de configuración inicial para el Sistema de Procesamiento Automático
"""

import os
import shutil
from pathlib import Path

def create_directories():
    """Crea todos los directorios necesarios"""
    directories = [
        'source',
        'images_sources', 
        'images_old',
        'codes_output',
        'images_output',
        'discards_output',
        'rectangles_output',
        'uploads'
    ]
    
    print("📁 Creando directorios...")
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"  ✅ Creado: {directory}/")
        else:
            print(f"  ✓  Existe: {directory}/")

def check_dependencies():
    """Verifica que las dependencias estén instaladas"""
    print("\n🔍 Verificando dependencias...")
    
    required_modules = [
        'flask',
        'cv2',
        'PIL',
        'pymongo'
    ]
    
    missing = []
    for module in required_modules:
        try:
            if module == 'cv2':
                import cv2
            elif module == 'PIL':
                from PIL import Image
            elif module == 'flask':
                import flask
            elif module == 'pymongo':
                import pymongo
            print(f"  ✅ {module}")
        except ImportError:
            print(f"  ❌ {module} - FALTA")
            missing.append(module)
    
    if missing:
        print(f"\n⚠️  Dependencias faltantes: {', '.join(missing)}")
        print("Instalar con: pip install " + " ".join(missing))
        return False
    
    print("✅ Todas las dependencias están instaladas")
    return True

def setup_sample_images():
    """Configuración de imágenes de ejemplo"""
    print("\n🖼️  Configuración de imágenes...")
    
    source_dir = Path('source')
    source_images_dir = Path('source_images')
    
    if source_images_dir.exists():
        # Copiar imágenes de ejemplo de source_images a source
        images = list(source_images_dir.glob('*.jpg')) + list(source_images_dir.glob('*.png'))
        
        if images:
            print(f"  📋 Encontradas {len(images)} imágenes en source_images/")
            
            response = input("  ¿Copiar a source/ para procesamiento? (s/n): ").lower()
            if response == 's':
                for img in images:
                    dest = source_dir / img.name
                    if not dest.exists():
                        shutil.copy2(img, dest)
                        print(f"    ✅ Copiada: {img.name}")
                    else:
                        print(f"    ✓  Existe: {img.name}")
                print(f"  🎉 {len(images)} imágenes listas en source/")
            else:
                print("  ⏭️  Saltando copia de imágenes")
        else:
            print("  ℹ️  No hay imágenes en source_images/")
    else:
        print("  ℹ️  Directorio source_images/ no encontrado")
    
    # Verificar estado de source
    source_images = list(source_dir.glob('*.jpg')) + list(source_dir.glob('*.png'))
    print(f"  📊 Estado final: {len(source_images)} imágenes en source/")

def show_next_steps():
    """Muestra los siguientes pasos"""
    print("\n🚀 ¡Configuración completada!")
    print("\n📋 Siguientes pasos:")
    print("1. Iniciar servidor: python web_app.py")
    print("2. Abrir navegador: http://localhost:5000")
    print("3. Click en '⏭️ Preparar Siguiente' para mover primera imagen")
    print("4. Click en '▶️ Procesar Automático' para comenzar")
    
    print("\n📚 Documentación:")
    print("- README_AUTO.md - Guía completa del sistema")
    print("- http://localhost:5000/manual - Interfaz manual (legacy)")

def main():
    """Función principal"""
    print("🔧 CONFIGURACIÓN INICIAL - Sistema de Procesamiento Automático")
    print("=" * 60)
    
    # Verificar dependencias
    if not check_dependencies():
        print("\n❌ Configuración abortada - instalar dependencias primero")
        return
    
    # Crear directorios
    create_directories()
    
    # Configurar imágenes
    setup_sample_images()
    
    # Mostrar siguientes pasos
    show_next_steps()
    
    print("\n" + "=" * 60)
    print("✅ Sistema listo para usar!")

if __name__ == "__main__":
    main()
