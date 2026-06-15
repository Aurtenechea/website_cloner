import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin, urlparse
from datetime import datetime

# ── Configuración ──────────────────────────────────────────────────────────────
BASE_DIR     = Path(r"C:\mis_sitios_descargados")
COOKIES_FILE = BASE_DIR / "cookies.txt"
OUTPUT_FILE  = BASE_DIR / "links_todos_cursos.txt"

# URL de la página que lista todos los cursos
URL_CATALOGO = "https://cresciente.net/cursos-online-musica/"
# ──────────────────────────────────────────────────────────────────────────────


def cargar_cookies(path: Path) -> dict:
    cookies = {}
    if not path.exists():
        print(f"  [advertencia] No se encontró {path}")
        return cookies
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or line.strip() == "":
                continue
            partes = line.strip().split("\t")
            if len(partes) >= 7:
                cookies[partes[5]] = partes[6]
    print(f"  [cookies] {len(cookies)} cookies cargadas")

    wp_cookies = [k for k in cookies if k.startswith("wordpress_logged_in")]
    if wp_cookies:
        print(f"  [cookies] Sesión WP activa: {', '.join(wp_cookies)}")
    else:
        print(f"  [advertencia] No se encontró wordpress_logged_in_* — puede que no estés autenticado")

    return cookies


def extraer_links_cursos(url_catalogo: str) -> list[str]:
    """
    Descarga la página de catálogo de cursos y extrae todos los links a cursos.
    Busca todos los <a> que tengan href con '/cursos/' en la URL.
    """
    cookies = cargar_cookies(COOKIES_FILE)

    session = requests.Session()
    session.cookies.update(cookies)
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    })

    print(f"\nObteniendo catálogo de cursos: {url_catalogo}")
    try:
        r = session.get(url_catalogo, timeout=30)
        print(f"  [http {r.status_code}]")
        r.raise_for_status()
    except Exception as e:
        print(f"  [error] No se pudo obtener la página: {e}")
        return []

    html_raw = r.text
    soup = BeautifulSoup(html_raw, "html.parser")

    titulo = soup.find("title")
    print(f"  [título] {titulo.text.strip() if titulo else '(sin título)'}")

    # Extraer todos los links que apunten a /cursos/ pero NO a /lecciones/
    links_encontrados = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href:
            continue
        
        # Convertir a URL absoluta
        href_abs = urljoin(url_catalogo, href)
        
        # Verificar que sea un link a un curso en el mismo dominio
        parsed = urlparse(href_abs)
        path = parsed.path.lower()
        
        # Debe tener /cursos/ pero NO debe tener /lecciones/
        if "/cursos/" in path and "/lecciones/" not in path:
            # Limpiar trailing slash para evitar duplicados (ej: curso/ vs curso)
            href_limpio = href_abs.rstrip("/")
            # Evitar duplicados
            if href_limpio not in links_encontrados:
                links_encontrados.add(href_limpio)

    # Ordenar y convertir a lista
    links_ordenados = sorted(list(links_encontrados))
    
    print(f"  [encontrados] {len(links_ordenados)} links de cursos")
    
    return links_ordenados


def guardar_links(links: list[str], archivo: Path):
    """Guarda los links en un archivo de texto, uno por línea."""
    if not links:
        print(f"  [advertencia] No hay links para guardar")
        return
    
    try:
        with open(archivo, "w", encoding="utf-8") as f:
            f.write(f"# Links de todos los cursos de Cresciente\n")
            f.write(f"# Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total: {len(links)} cursos\n")
            f.write("#\n")
            for link in links:
                f.write(link + "\n")
        
        print(f"  [guardado] {len(links)} links en {archivo.name}")
    except Exception as e:
        print(f"  [error] No se pudo guardar los links: {e}")


def main():
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    
    links = extraer_links_cursos(URL_CATALOGO)
    
    if links:
        guardar_links(links, OUTPUT_FILE)
        print(f"\n✓ Completado. Links guardados en: {OUTPUT_FILE}")
    else:
        print(f"\n✗ No se encontraron links de cursos.")


if __name__ == "__main__":
    main()
