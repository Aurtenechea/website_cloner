import requests
from bs4 import BeautifulSoup
import os

COOKIES_FILE = r"C:\mis_sitios_descargados\cookies.txt"
BASE_DESTINO = r"C:\mis_sitios_descargados"
URLS = [
    "https://cresciente.net/cursos/lecto-escritura-musical-i/lecciones/subdivision-2/",
    "https://cresciente.net/cursos/lecto-escritura-musical-i/lecciones/dictados-3/",
]

cookies = {}
with open(COOKIES_FILE) as f:
    for line in f:
        if line.startswith("#") or line.strip() == "":
            continue
        partes = line.strip().split("\t")
        if len(partes) >= 7:
            cookies[partes[5]] = partes[6]

session = requests.Session()
session.cookies.update(cookies)

extensiones = (".pdf", ".mscz", ".mxl", ".xml", ".mp3", ".zip")

for url in URLS:
    partes_url = url.rstrip("/").split("/")
    curso = partes_url[-3]
    leccion = partes_url[-1]
    carpeta_leccion = os.path.join(BASE_DESTINO, curso, leccion)
    carpeta_materiales = os.path.join(carpeta_leccion, "materiales")
    os.makedirs(carpeta_leccion, exist_ok=True)
    os.makedirs(carpeta_materiales, exist_ok=True)

    print(f"\nProcesando: {leccion}")
    r = session.get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    archivos_a_bajar = []

    # Links <a>
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if any(href.lower().endswith(ext) for ext in extensiones):
            archivos_a_bajar.append(("a", a, "href", href))

    # Etiquetas <audio>
    for audio in soup.find_all("audio", src=True):
        archivos_a_bajar.append(("audio", audio, "src", audio["src"]))

    # Etiquetas <source>
    for source in soup.find_all("source", src=True):
        archivos_a_bajar.append(("source", source, "src", source["src"]))

    for tipo, tag, atributo, href in archivos_a_bajar:
        nombre = href.split("/")[-1]
        print(f"  Descargando: {nombre}")
        archivo = session.get(href)
        ruta_local = os.path.join(carpeta_materiales, nombre)
        with open(ruta_local, "wb") as f:
            f.write(archivo.content)
        tag[atributo] = os.path.join("materiales", nombre)
        print(f"  Guardado: {nombre}")

    with open(os.path.join(carpeta_leccion, "index.html"), "w", encoding="utf-8") as f:
        f.write(str(soup))
    print("  HTML guardado")

print("\nListo!")
