from pymongo import MongoClient
import dotenv
import os
# Cargar variables de entorno desde el archivo .env

def return_mongo_client():
    # Cargar variables de entorno desde el archivo .env
    dotenv.load_dotenv()

    # Crear un cliente de MongoDB
    client = MongoClient(os.getenv("MONGODB_URI"))
    return client