from waitress import serve
from app import create_app

app = create_app()

if __name__ == '__main__':
    print("Serveur WaterLife Congo demarre sur le port 8080")
    print("Accessible depuis ce PC via : http://localhost:8080")
    print("Accessible depuis les autres PC du bureau via l'adresse IP de ce PC")
    serve(app, host='0.0.0.0', port=8080)