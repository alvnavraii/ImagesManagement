#!/usr/bin/env python3
"""
Script de inicio para la aplicación web de gestión de imágenes
"""
import os
import sys
import subprocess

def check_dependencies():
    """Verifica que todas las dependencias estén instaladas"""
    try:
        import flask
        import cv2
        import pytesseract
        import pymongo
        print("✅ Todas las dependencias están instaladas")
        return True
    except ImportError as e:
        print(f"❌ Dependencia faltante: {e}")
        print("Ejecuta: pip install -r requirements.txt")
        return False

def check_mongodb():
    """Verifica la conexión a MongoDB"""
    try:
        from connect_mongodb import return_mongo_client
        client = return_mongo_client()
        client.admin.command('ping')
        print("✅ Conexión a MongoDB exitosa")
        return True
    except Exception as e:
        print(f"❌ Error conectando a MongoDB: {e}")
        print("Asegúrate de que MongoDB esté ejecutándose")
        return False

def main():
    print("🚀 Iniciando aplicación web de gestión de imágenes...")
    print("=" * 50)
    
    # Verificar dependencias
    if not check_dependencies():
        sys.exit(1)
    
    # Verificar MongoDB
    if not check_mongodb():
        print("⚠️  Continuando sin verificar MongoDB (se puede configurar después)")
    
    # Crear directorios necesarios
    directories = ['uploads', 'codes_output', 'images_output', 'discards_output', 'rectangles_output', 'templates']
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"📁 Creado directorio: {directory}")
    
    print("\n🌐 Iniciando servidor web...")
    print("📍 URL: http://localhost:5000")
    print("🛑 Para detener: Ctrl+C")
    print("=" * 50)
    
    # Ejecutar la aplicación Flask
    try:
        from web_app import app
        app.run(debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n👋 Aplicación detenida")
    except Exception as e:
        print(f"\n❌ Error ejecutando aplicación: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
