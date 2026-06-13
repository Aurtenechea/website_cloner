import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin, urlparse
from datetime import datetime

# ── Configuración ──────────────────────────────────────────────────────────────
BASE_DIR     = Path(r"C:\mis_sitios_descargados")
COOKIES_FILE = BASE_DIR / "cookies.txt"
LINKS_FILE   = BASE_DIR / "links_autocreado.txt"

# Pegá acá la URL de la página de índice del curso
URL_INDICE = "https://cresciente.net/cursos/primeros-pasos-en-la-composicion-musical-ciclo-introductorio/"
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


def es_url_leccion(url: str, dominio_base: str, curso_slug: str) -> bool:
    """
    Considera como lección cualquier URL del mismo dominio que:
      - Contenga el slug del curso en la ruta, Y
      - Tenga al menos un segmento más después del slug del curso
        (es decir, no sea la URL del índice del curso mismo)
    Esto cubre tanto /lessons/ como /lecciones/ como rutas directas.
    """
    parsed = urlparse(url)
    if dominio_base not in parsed.netloc:
        return False

    path = parsed.path.lower().rstrip("/")
    slug  = curso_slug.lower()

    if slug not in path:
        return False

    # Debe haber algo después del slug del curso
    idx = path.find(slug)
    resto = path[idx + len(slug):]
    return len(resto.strip("/")) > 0


def extraer_links_lecciones(url_indice: str) -> list[str]:
    cookies = cargar_cookies(COOKIES_FILE)

    session = requests.Session()
    session.cookies.update(cookies)
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    })

    print(f"\nObteniendo índice del curso: {url_indice}")
    try:
        r = session.get(url_indice, timeout=30)
        print(f"  [http {r.status_code}]")
        r.raise_for_status()
    except Exception as e:
        print(f"  [error] No se pudo obtener la página: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    titulo = soup.find("title")
    print(f"  [título] {titulo.text.strip() if titulo else '(sin título)'}")

    # Si el título parece una página de login, avisamos
    titulo_lower = (titulo.text.strip() if titulo else "").lower()
    if any(w in titulo_lower for w in ("login", "iniciar", "acceso", "sign in")):
        print("  [advertencia] La página devuelta parece ser un login — las cookies pueden haber expirado")

    dominio_base = urlparse(url_indice).netloc

    # Extraer el slug del curso desde la URL del índice
    # Ejemplo: /courses/teoria-musical/ → slug = "teoria-musical"
    partes_path = urlparse(url_indice).path.strip("/").split("/")
    curso_slug = ""
    for i, p in enumerate(partes_path):
        if p in ("courses", "cursos", "curso") and i + 1 < len(partes_path):
            curso_slug = partes_path[i + 1]
            break
    if not curso_slug and partes_path:
        curso_slug = partes_path[-1]  # fallback: último segmento

    print(f"  [curso slug detectado] '{curso_slug}'")

    lecciones_encontradas = []
    vistas = set()

    # ── Estrategia 1: buscar en contenedores específicos de LearnDash ──────────
    contenedores_ld = soup.select(
        ".ld-item-list-items, "
        ".learndash-course-index, "
        ".course-content, "
        ".ld-lesson-list, "
        ".ld-topic-list, "
        ".sfwd-lessons, "
        ".course_progress, "
        "[id*='learndash'], "
        "[class*='learndash'], "
        "[class*='sfwd']"
    )

    if contenedores_ld:
        print(f"  [LearnDash] {len(contenedores_ld)} contenedor(es) específico(s) encontrado(s)")
        for contenedor in contenedores_ld:
            for a in contenedor.find_all("a", href=True):
                href = urljoin(url_indice, a["href"].strip())
                if href not in vistas and es_url_leccion(href, dominio_base, curso_slug):
                    lecciones_encontradas.append(href)
                    vistas.add(href)
    else:
        print("  [LearnDash] Sin contenedores específicos — buscando en todo el HTML")

    # ── Estrategia 2: si no encontró nada, buscar en todos los <a> ────────────
    if not lecciones_encontradas:
        todos_links = soup.find_all("a", href=True)
        print(f"  [fallback] Revisando {len(todos_links)} links en la página...")
        for a in todos_links:
            href = urljoin(url_indice, a["href"].strip())
            if href not in vistas and es_url_leccion(href, dominio_base, curso_slug):
                lecciones_encontradas.append(href)
                vistas.add(href)

    # ── Debug: mostrar todos los links del dominio si sigue sin resultados ────
    if not lecciones_encontradas:
        print(f"\n  [debug] No se encontraron lecciones con el slug '{curso_slug}'.")
        print(f"  [debug] Links del dominio encontrados en la página:")
        for a in soup.find_all("a", href=True):
            href = urljoin(url_indice, a["href"].strip())
            if dominio_base in urlparse(href).netloc:
                print(f"    {href}")
        print(f"\n  → Revisá los links de arriba para ajustar URL_INDICE o el slug del curso.")
    else:
        print(f"\n  [resultado] {len(lecciones_encontradas)} lecciones encontradas:")
        for url in lecciones_encontradas:
            print(f"    {url}")

    return lecciones_encontradas


def guardar_en_links_txt(urls: list[str]):
    if not urls:
        print("\nNo hay lecciones para guardar.")
        return

    existentes = set()
    if LINKS_FILE.exists():
        for line in LINKS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                existentes.add(line)

    nuevas = [u for u in urls if u not in existentes]

    if not nuevas:
        print(f"\nTodos los links ya estaban en {LINKS_FILE.name} — nada nuevo que agregar.")
        return

    with open(LINKS_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n# Agregado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} desde índice\n")
        for url in nuevas:
            f.write(url + "\n")

    print(f"\n  [ok] {len(nuevas)} lecciones nuevas agregadas a {LINKS_FILE.name}")
    if existentes:
        print(f"  [info] {len(urls) - len(nuevas)} ya existían y se omitieron")
    print(f"\nAhora podés correr descargar.py para bajar todas las lecciones.")


def main():
    if "NOMBRE-DEL-CURSO" in URL_INDICE:
        print("⚠  Editá la variable URL_INDICE en el script con la URL real del curso.")
        return

    urls = extraer_links_lecciones(URL_INDICE)
    guardar_en_links_txt(urls)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR FATAL] {e}")
    finally:
        input("\nPresioná Enter para cerrar...")
