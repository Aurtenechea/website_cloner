import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin, urlparse
from datetime import datetime
import re

# ── Configuración ──────────────────────────────────────────────────────────────
BASE_DIR     = Path(r"C:\mis_sitios_descargados")
COOKIES_FILE = BASE_DIR / "cookies.txt"
LINKS_FILE   = BASE_DIR / "links_autocreado.txt"

# Pegá acá la URL de la página de índice del curso
URL_INDICE = "https://cresciente.net/cursos/cc1-e-contrapunto-por-especies/"
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
    parsed = urlparse(url)
    if dominio_base not in parsed.netloc:
        return False
    path = parsed.path.lower().rstrip("/")
    slug = curso_slug.lower()
    if slug not in path:
        return False
    idx = path.find(slug)
    resto = path[idx + len(slug):]
    return len(resto.strip("/")) > 0


def extraer_nonce_y_params(soup: BeautifulSoup, html_raw: str, course_id: str) -> dict | None:
    """
    Extrae el pager_nonce y demás parámetros necesarios para la API AJAX de LearnDash.
    LearnDash los inyecta en el HTML como atributos data-* o en variables JS.
    """
    # Estrategia 1: atributos data-nonce o data-pager-nonce en el HTML
    for tag in soup.find_all(True):
        nonce = tag.get("data-nonce") or tag.get("data-pager-nonce")
        if nonce:
            print(f"  [nonce] Encontrado en atributo data-* de <{tag.name}>: {nonce}")
            return {"nonce": nonce}

    # Estrategia 2: buscar en variables JS inline (ldVars, learndash_course_data, etc.)
    patrones_js = [
        r'["\']pager_nonce["\']\s*:\s*["\']([a-f0-9]+)["\']',
        r'pager_nonce\s*=\s*["\']([a-f0-9]+)["\']',
        r'nonce["\']?\s*:\s*["\']([a-f0-9]{10})["\']',
    ]
    for script in soup.find_all("script"):
        texto = script.string or ""
        for pat in patrones_js:
            m = re.search(pat, texto)
            if m:
                print(f"  [nonce] Encontrado en <script> inline: {m.group(1)}")
                return {"nonce": m.group(1)}

    # Estrategia 3: buscar en el HTML crudo directamente
    for pat in patrones_js:
        m = re.search(pat, html_raw)
        if m:
            print(f"  [nonce] Encontrado en HTML crudo: {m.group(1)}")
            return {"nonce": m.group(1)}

    print("  [advertencia] No se encontró pager_nonce en el HTML")
    return None


def pedir_pagina_ajax(
    session: requests.Session,
    ajax_url: str,
    course_id: str,
    user_id: str,
    nonce: str,
    pagina: int,
    num_por_pagina: int,
    total_paginas: int,
    total_items: int,
) -> BeautifulSoup | None:
    """
    Hace la request AJAX a admin-ajax.php para obtener una página del índice de lecciones.
    """
    params = {
        "action":                          "ld30_ajax_pager",
        "ld-courseinfo-lesson-page":       str(pagina),
        "pager_nonce":                     nonce,
        "pager_results[paged]":            str(pagina),
        "pager_results[total_items]":      str(total_items),
        "pager_results[total_pages]":      str(total_paginas),
        "context":                         "course_content_shortcode",
        "course_id":                       course_id,
        "shortcode_instance[course_id]":   course_id,
        "shortcode_instance[post_id]":     course_id,
        "shortcode_instance[group_id]":    "0",
        "shortcode_instance[paged]":       str(pagina),
        "shortcode_instance[num]":         str(num_por_pagina),
        "shortcode_instance[wrapper]":     "false",
        "shortcode_instance[user_id]":     user_id,
    }

    print(f"  [ajax] Pidiendo página {pagina}/{total_paginas}...")
    try:
        r = session.get(ajax_url, params=params, timeout=30)
        print(f"  [http {r.status_code}] {r.url[:120]}...")
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  [error ajax] {e}")
        return None

    # La respuesta JSON de LearnDash tiene el HTML en data["data"]["html"] o data["html"]
    html_fragment = None
    if isinstance(data, dict):
        html_fragment = (
            data.get("data", {}).get("markup")
            or data.get("data", {}).get("html")
            or data.get("markup")
            or data.get("html")
            or data.get("content")
        )
        if not html_fragment:
            print(f"  [ajax] Claves en respuesta: {list(data.keys())}")

    if not html_fragment and isinstance(data, str):
        html_fragment = data

    if not html_fragment:
        print(f"  [advertencia] La respuesta AJAX no tiene HTML reconocible")
        print(f"  [debug] Respuesta completa: {str(data)[:500]}")
        return None

    return BeautifulSoup(html_fragment, "html.parser")


def extraer_links_de_soup(soup: BeautifulSoup, url_indice: str, dominio_base: str, curso_slug: str, vistas: set) -> list:
    encontrados = []
    for a in soup.find_all("a", href=True):
        href = urljoin(url_indice, a["href"].strip())
        if href not in vistas and es_url_leccion(href, dominio_base, curso_slug):
            encontrados.append(href)
            vistas.add(href)
    return encontrados


def extraer_links_lecciones(url_indice: str) -> list[str]:
    cookies = cargar_cookies(COOKIES_FILE)

    session = requests.Session()
    session.cookies.update(cookies)
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
        "Referer": url_indice,
    })

    print(f"\nObteniendo índice del curso: {url_indice}")
    try:
        r = session.get(url_indice, timeout=30)
        print(f"  [http {r.status_code}]")
        r.raise_for_status()
    except Exception as e:
        print(f"  [error] No se pudo obtener la página: {e}")
        return []

    html_raw = r.text
    soup = BeautifulSoup(html_raw, "html.parser")

    titulo = soup.find("title")
    print(f"  [título] {titulo.text.strip() if titulo else '(sin título)'}")

    titulo_lower = (titulo.text.strip() if titulo else "").lower()
    if any(w in titulo_lower for w in ("login", "iniciar", "acceso", "sign in")):
        print("  [advertencia] La página parece ser un login — las cookies pueden haber expirado")

    dominio_base = urlparse(url_indice).netloc
    ajax_url     = f"{urlparse(url_indice).scheme}://{dominio_base}/wp-admin/admin-ajax.php"

    # ── Extraer slug del curso ────────────────────────────────────────────────
    partes_path = urlparse(url_indice).path.strip("/").split("/")
    curso_slug = ""
    for i, p in enumerate(partes_path):
        if p in ("courses", "cursos", "curso") and i + 1 < len(partes_path):
            curso_slug = partes_path[i + 1]
            break
    if not curso_slug and partes_path:
        curso_slug = partes_path[-1]
    print(f"  [curso slug detectado] '{curso_slug}'")

    # ── Extraer parámetros del paginador LearnDash desde el HTML ─────────────
    course_id      = ""
    user_id        = "0"
    nonce          = ""
    num_por_pagina = 60
    total_paginas  = 1
    total_items    = 0

    # Buscar el elemento del paginador — LearnDash lo pone con data-* attributes
    pager = soup.find(attrs={"data-pager-nonce": True}) or soup.find(attrs={"data-nonce": True})

    # Buscar en atributos data-shortcode-instance u otros contenedores del paginador
    for tag in soup.find_all(True):
        if tag.get("data-pager-nonce"):
            nonce = tag["data-pager-nonce"]
        if tag.get("data-nonce"):
            nonce = nonce or tag["data-nonce"]
        if tag.get("data-course-id"):
            course_id = tag["data-course-id"]
        if tag.get("data-user-id"):
            user_id = tag["data-user-id"]
        if tag.get("data-total-pages"):
            total_paginas = int(tag["data-total-pages"])
        if tag.get("data-total-items"):
            total_items = int(tag["data-total-items"])
        if tag.get("data-num"):
            num_por_pagina = int(tag["data-num"])

    # Si no encontró en data-*, buscar en JS inline
    if not nonce:
        result = extraer_nonce_y_params(soup, html_raw, course_id)
        if result:
            nonce = result["nonce"]

    # Buscar course_id en el HTML si no lo encontró
    if not course_id:
        m = re.search(r'course_id["\']?\s*[:=]\s*["\']?(\d+)', html_raw)
        if m:
            course_id = m.group(1)
            print(f"  [course_id] Encontrado en HTML: {course_id}")

    # Buscar user_id en el HTML si no lo encontró
    if user_id == "0":
        m = re.search(r'user_id["\']?\s*[:=]\s*["\']?(\d+)', html_raw)
        if m:
            user_id = m.group(1)
            print(f"  [user_id] Encontrado en HTML: {user_id}")

    # Buscar total_pages en el HTML — LearnDash lo puede meter de muchas formas
    if total_paginas == 1:
        patrones_total_pages = [
            r'"total_pages"\s*:\s*(\d+)',
            r"'total_pages'\s*:\s*(\d+)",
            r'total_pages["\']?\s*[:=]\s*["\']?(\d+)',
            r'pager_results\[total_pages\]=(\d+)',
            r'total_pages=(\d+)',
        ]
        for pat in patrones_total_pages:
            m = re.search(pat, html_raw)
            if m:
                total_paginas = int(m.group(1))
                print(f"  [total_pages] Encontrado con patrón '{pat}': {total_paginas}")
                break

    if total_items == 0:
        patrones_total_items = [
            r'"total_items"\s*:\s*(\d+)',
            r"'total_items'\s*:\s*(\d+)",
            r'total_items["\']?\s*[:=]\s*["\']?(\d+)',
            r'pager_results\[total_items\]=(\d+)',
        ]
        for pat in patrones_total_items:
            m = re.search(pat, html_raw)
            if m:
                total_items = int(m.group(1))
                break

    # Si num_por_pagina es 60 pero hay 122 items y 1 página detectada,
    # calculamos total_paginas a partir de items (mejor que quedarse en 1)
    if total_paginas == 1 and total_items > num_por_pagina:
        import math
        total_paginas = math.ceil(total_items / num_por_pagina)
        print(f"  [total_pages] Calculado desde total_items ({total_items} / {num_por_pagina}): {total_paginas}")

    print(f"  [paginador] course_id={course_id} | user_id={user_id} | nonce={nonce or '(no encontrado)'}")
    print(f"  [paginador] total_páginas={total_paginas} | items={total_items} | por_página={num_por_pagina}")

    # ── Recolectar links de todas las páginas ─────────────────────────────────
    lecciones_encontradas = []
    vistas = set()

    # Página 1: ya la tenemos en el HTML inicial
    print(f"\n  [página 1] Extrayendo del HTML inicial...")
    links_p1 = extraer_links_de_soup(soup, url_indice, dominio_base, curso_slug, vistas)
    lecciones_encontradas.extend(links_p1)
    print(f"  → {len(links_p1)} lecciones en página 1")

    # Páginas 2 en adelante: via AJAX
    # Modo A: si sabemos cuántas páginas hay, las pedimos todas
    # Modo B (fallback): iteramos hasta que una página devuelva 0 lecciones
    MAX_PAGINAS_FALLBACK = 20  # techo de seguridad para el modo fallback

    if not nonce:
        print(f"\n  [error] No se encontró pager_nonce — no se pueden pedir páginas adicionales.")
        print(f"  → Revisá que estés autenticado y que las cookies sean válidas.")
    else:
        pagina = 2
        paginas_sin_resultado = 0

        while True:
            # Condición de corte en modo A (total_pages conocido)
            if total_paginas > 1 and pagina > total_paginas:
                break
            # Condición de corte en modo B (fallback sin total_pages)
            if total_paginas == 1 and pagina > MAX_PAGINAS_FALLBACK:
                print(f"  [fallback] Llegamos al límite de {MAX_PAGINAS_FALLBACK} páginas — deteniendo.")
                break
            if paginas_sin_resultado >= 2:
                print(f"  [fallback] Dos páginas consecutivas sin lecciones — fin de la paginación.")
                break

            soup_pag = pedir_pagina_ajax(
                session, ajax_url, course_id, user_id, nonce,
                pagina, num_por_pagina, total_paginas, total_items
            )
            if soup_pag is None:
                print(f"  [error] No se pudo obtener página {pagina} — se omite")
                paginas_sin_resultado += 1
                pagina += 1
                continue

            links = extraer_links_de_soup(soup_pag, url_indice, dominio_base, curso_slug, vistas)
            lecciones_encontradas.extend(links)
            print(f"  → {len(links)} lecciones en página {pagina}")

            if len(links) == 0:
                paginas_sin_resultado += 1
            else:
                paginas_sin_resultado = 0

            pagina += 1

    # ── Fallback: si no encontró nada, buscar en todo el HTML ────────────────
    if not lecciones_encontradas:
        print(f"\n  [fallback] Buscando en todos los <a> del HTML inicial...")
        for a in soup.find_all("a", href=True):
            href = urljoin(url_indice, a["href"].strip())
            if href not in vistas and es_url_leccion(href, dominio_base, curso_slug):
                lecciones_encontradas.append(href)
                vistas.add(href)

    # ── Debug si sigue sin resultados ─────────────────────────────────────────
    if not lecciones_encontradas:
        print(f"\n  [debug] No se encontraron lecciones con el slug '{curso_slug}'.")
        print(f"  [debug] Links del dominio en la página:")
        for a in soup.find_all("a", href=True):
            href = urljoin(url_indice, a["href"].strip())
            if dominio_base in urlparse(href).netloc:
                print(f"    {href}")
    else:
        print(f"\n  [resultado] {len(lecciones_encontradas)} lecciones encontradas en total:")
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