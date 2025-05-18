from pymongo import MongoClient
import dotenv
import os
import pathlib

def return_mongo_client():
    # Buscar el archivo .env en la ruta actual y directorios superiores
    # Esto asegura que lo encontrará incluso si el script se ejecuta desde otro directorio
    dotenv_path = pathlib.Path(__file__).parent / '.env'
    
    if dotenv_path.exists():
        print(f"Archivo .env encontrado en: {dotenv_path}")
        dotenv.load_dotenv(dotenv_path=dotenv_path)
    else:
        print(f"ADVERTENCIA: Archivo .env no encontrado en: {dotenv_path}")
        print("Buscando en la ruta por defecto...")
        dotenv.load_dotenv()
    
    # Imprimir la URI para depuración
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        print("ADVERTENCIA: MONGODB_URI no encontrada en .env, usando conexión local predeterminada")
        mongo_uri = "mongodb://localhost:27017/"
    else:
        # Corregir el problema con los caracteres escapados
        mongo_uri = mongo_uri.replace('\\x3a', ':')
        print(f"Conectando a MongoDB con URI corregida: {mongo_uri}")
    
    # Crear un cliente de MongoDB
    client = MongoClient(mongo_uri)
    return client