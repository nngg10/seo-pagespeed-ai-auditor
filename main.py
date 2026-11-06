"""Punto de entrada: python main.py  ->  http://localhost:8000"""
import uvicorn

from app.config import HOST, PORT

if __name__ == "__main__":
    print(f"Auditor SEO & PageSpeed AI en http://localhost:{PORT}")
    uvicorn.run("app.api:app", host=HOST, port=PORT)
