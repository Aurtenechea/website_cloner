import re
import requests
import subprocess
import glob
import time
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from datetime import datetime
from os.path import relpath

# ── Configuración ────────────────────────────────────────────────────────────
CURSOS_DIR = Path(r"D:\nacho\cursos_descargados")
COOKIES_FILE = Path(r"C:\mis_sitios_descargados\cookies.txt")  # Ajustá la ruta

# Opción 1: Lista manual de slugs de cursos
CURSOS_SLUGS = [
    "ciclo-0-primeros-pasos-en-la-composicion-musical-v3-0",
    # "otro-curso",
]

# Opción 2: Archivo con URLs (una por línea) - si se define, se ignora CURSOS_SLUGS
# CURSOS_URLS_FILE = Path(r"C:\mis_sitios_descargados\links_todos_cursos.txt")

# ── Constantes para videos (igual que en descarga_deepseek7-1.py) ──────────
VIDEO_CALIDAD = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]/best"
MAX_INTENTOS_VIDEO = 3
VIDEO_IFRAME_DOMINIOS = (
    "vimeo.com", "mediadelivery.net", "iframe.mediadelivery.net", "bunnycdn.com",
    "b-cdn.net", "wistia.com", "fast.wistia.net", "loom.com", "kaltura.com",
    "sproutvideo.com", "vidyard.com", "dailymotion.com",
    "jwplatform.com", "jwplayer.com", "brightcove.net", "brightcove.com",
    "api.video", "youtube.com", "youtu.be",
)
YOUTUBE_PATTERNS = [
    r'youtube\.com/embed/([A-Za-z0-9_-]{11})',
    r'youtube\.com/watch\?v=([A-Za-z0-9_-]{11})',
    r'youtu\.be/([A-Za-z0-9_-]{11})',
    r'youtube\.com/v/([A-Za-z0-9_-]{11})',
]

# ── Funciones auxiliares ──────────────────────────────────────────────────
def limpiar_nombre(texto: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", texto).strip("_ ")

def slug_leccion_desde_url(url: str) -> str:
    """Extrae el slug de la lección de una URL del tipo .../lecciones/xxxx/"""
    parsed = urlparse(url)
    path_parts = parsed.path.strip("/").split("/")
    try:
        idx = path_parts.index("lecciones") if "lecciones" in path_parts else -1
        if idx != -1 and idx + 1 < len(path_parts):
            return limpiar_nombre(path_parts[idx + 1])
    except ValueError:
        pass
    return None

def slug_curso_desde_url(url: str) -> str:
    """Extrae el slug del curso de una URL del tipo .../cursos/xxxx/..."""
    parsed = urlparse(url)
    path_parts = parsed.path.strip("/").split("/")
    for i, p in enumerate(path_parts):
        if p in ("cursos", "courses", "curso") and i + 1 < len(path_parts):
            return limpiar_nombre(path_parts[i + 1])
    return limpiar_nombre(path_parts[-1]) if path_parts else ""

def buscar_carpeta_leccion(curso_dir: Path, slug: str) -> Path | None:
    """
    Busca la carpeta local que coincide con el slug, normalizando nombres.
    Maneja carpetas con:
      - Prefijo numérico (ej: 075_)
      - Prefijo 'lecciones_' o sin él
    """
    slug_limpio = re.sub(r'^lecciones_', '', slug)
    for carpeta in curso_dir.iterdir():
        if not carpeta.is_dir():
            continue
        nombre = carpeta.name
        # Eliminar prefijo numérico (ej: 075_)
        nombre = re.sub(r'^\d+_', '', nombre)
        # Eliminar prefijo 'lecciones_' si existe
        nombre = re.sub(r'^lecciones_', '', nombre)
        if nombre == slug_limpio:
            return carpeta
        if nombre == slug:
            return carpeta
    return None

# ── Funciones para cookies y descarga ──────────────────────────────────────
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
    return cookies

def descargar_pagina_curso(url_curso: str) -> BeautifulSoup | None:
    """Descarga la página raíz del curso y devuelve un objeto BeautifulSoup."""
    cookies = cargar_cookies(COOKIES_FILE)
    session = requests.Session()
    session.cookies.update(cookies)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    })
    try:
        r = session.get(url_curso, timeout=30)
        r.raise_for_status()
        print(f"  [descarga] {url_curso} → {r.status_code}")
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"  [error] No se pudo descargar {url_curso}: {e}")
        return None

# ── Funciones para reescritura de enlaces (página principal) ──────────────
def reescribir_enlaces_lecciones(soup: BeautifulSoup, curso_dir: Path, url_curso: str) -> BeautifulSoup:
    """
    Reemplaza:
      - Enlaces a lecciones (contienen '/lecciones/') → carpeta_leccion/index_indice.html
      - Enlace al catálogo general (cursos-online-musica) → ../index_indice.html
    """
    for a in soup.find_all("a", href=True):
        href = a["href"]
        href_abs = urljoin(url_curso, href)

        # 1. Enlaces a lecciones
        if "/lecciones/" in href_abs:
            slug = slug_leccion_desde_url(href_abs)
            if not slug:
                continue
            carpeta = buscar_carpeta_leccion(curso_dir, slug)
            if carpeta:
                nuevo_href = f"{carpeta.name}/index_indice.html"
                a["href"] = nuevo_href
                print(f"    {slug} → {nuevo_href}")
            else:
                print(f"  [aviso] No se encontró carpeta para {slug}")

        # 2. Enlace al catálogo de cursos (cursos-online-musica)
        elif "cursos-online-musica" in href_abs:
            a["href"] = "../index_indice.html"
            print(f"    [catálogo] → ../index_indice.html")

    return soup

# ── Funciones para descarga de videos (copiadas de descarga_deepseek7-1.py) ──
def _es_parcial_ytdlp(path: Path) -> bool:
    return bool(re.search(r'(?:\.f\d+(?:\.[^.]+)?$|\.fhls-[^/\\]+(?:\.[^.]+)?$|\.part$|-Frag\d+(?:\.[^.]+)?$)', path.name)) or path.suffix == ".part"

def _limpiar_parciales(output_template: str):
    patron = output_template.replace("%(ext)s", "*")
    for ruta in glob.glob(patron) + glob.glob(patron + ".part"):
        p = Path(ruta)
        if _es_parcial_ytdlp(p):
            try:
                p.unlink()
                print(f"  [limpieza] borrado parcial: {p.name}")
            except Exception:
                pass

def _correr_ytdlp(url_video: str, output_template: str, label: str, allow_playlist: bool = True, referer: str = None) -> bool | None:
    for intento in range(1, MAX_INTENTOS_VIDEO + 1):
        if intento > 1:
            print(f"  [video] reintentando ({intento}/{MAX_INTENTOS_VIDEO}) → {label}")
            time.sleep(5)
        else:
            print(f"  [video] descargando {label} → {url_video}")
        _limpiar_parciales(output_template)
        try:
            command = [
                "yt-dlp", url_video,
                "-f", VIDEO_CALIDAD,
                "--output", output_template,
                "--cookies", str(COOKIES_FILE),
                "--merge-output-format", "mp4"
            ]
            if referer:
                command.extend(["--referer", referer])
            if not allow_playlist:
                command.append("--no-playlist")
            command.extend([
                "--fragment-retries", "5",
                "--retries", "5",
                "--socket-timeout", "30",
                "--no-part"
            ])
            result = subprocess.run(command, stdout=None, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                print(f"  [video ok] {label}")
                return True
            else:
                print(f"  [error video] código {result.returncode} — intento {intento}/{MAX_INTENTOS_VIDEO}")
                if "Unsupported URL" in result.stderr:
                    print(f"  [sin video] No hay video descargable")
                    return None
        except FileNotFoundError:
            print("  [error] yt-dlp no encontrado. Instalalo con: pip install yt-dlp")
            return False
        except Exception as e:
            print(f"  [error inesperado] {e}")
    return False

def extraer_urls_videos_embebidos(soup: BeautifulSoup, html_raw: str) -> list[str]:
    encontrados = []
    for iframe in soup.find_all("iframe"):
        src = (iframe.get("src") or iframe.get("data-src") or iframe.get("data-lazy-src") or "").strip()
        if src.startswith("//"):
            src = "https:" + src
        if any(d in src for d in VIDEO_IFRAME_DOMINIOS):
            encontrados.append(src)
    vistos = set()
    urls = []
    for url in encontrados:
        if url and url not in vistos:
            vistos.add(url)
            urls.append(url)
    return urls

def _video_tag(ruta_relativa: str, ext: str) -> str:
    mime = {
        ".mp4": "video/mp4", ".webm": "video/webm",
        ".mkv": "video/x-matroska", ".mov": "video/quicktime", ".m4v": "video/mp4",
    }.get(ext.lower(), "video/mp4")
    return (f'<video controls style="width:100%;max-width:960px;display:block;margin:1em 0" preload="auto">'
            f'<source src="{ruta_relativa}" type="{mime}">'
            f'Tu navegador no soporta video HTML5.</video>')

# ── Funciones para procesar la página principal con video ────────────────
def procesar_videos_portada(soup: BeautifulSoup, curso_slug: str, curso_dir: Path, url_curso: str) -> BeautifulSoup:
    """Descarga los videos de la portada y reemplaza iframes por etiquetas <video> locales."""
    videos_dir = curso_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    urls_video = extraer_urls_videos_embebidos(soup, str(soup))
    if not urls_video:
        print("  [video portada] No se encontraron videos en la portada.")
        return soup

    print(f"  [video portada] {len(urls_video)} video(s) encontrado(s)")

    for idx, video_url in enumerate(urls_video):
        sufijo = f"_portada_{idx+1}" if len(urls_video) > 1 else "_portada"
        plantilla = str(videos_dir / f"{curso_slug}{sufijo}.%(ext)s")

        # Verificar si ya existe
        existentes = [p for p in videos_dir.glob(f"{curso_slug}{sufijo}.*") if not _es_parcial_ytdlp(p)]
        if existentes:
            archivo_local = existentes[0]
            ruta_rel = f"videos/{archivo_local.name}"
            print(f"  [video ya existe] {archivo_local.name}")
            # Reemplazar iframe
            for iframe in soup.find_all("iframe"):
                src = iframe.get("src") or ""
                if video_url in src or any(d in src for d in ("vimeo", "youtube", "b-cdn")):
                    iframe.replace_with(BeautifulSoup(_video_tag(ruta_rel, archivo_local.suffix), "html.parser"))
                    print(f"  [html] iframe reemplazado → {ruta_rel}")
            continue

        _limpiar_parciales(plantilla)
        resultado = _correr_ytdlp(video_url, plantilla, f"video portada #{idx+1}", allow_playlist=False, referer=url_curso)
        if resultado is True:
            encontrados = [p for p in videos_dir.glob(f"{curso_slug}{sufijo}.*") if not _es_parcial_ytdlp(p)]
            if encontrados:
                archivo_local = encontrados[0]
                ruta_rel = f"videos/{archivo_local.name}"
                for iframe in soup.find_all("iframe"):
                    src = iframe.get("src") or ""
                    if video_url in src or any(d in src for d in ("vimeo", "youtube", "b-cdn")):
                        iframe.replace_with(BeautifulSoup(_video_tag(ruta_rel, archivo_local.suffix), "html.parser"))
                        print(f"  [html] iframe reemplazado → {ruta_rel}")
        else:
            print(f"  [video portada] No se pudo descargar {video_url}")

    return soup

# ── Funciones para generar índices locales de lecciones ──────────────────
def reescribir_enlaces_sidebar(soup: BeautifulSoup, curso_dir: Path, carpeta_origen: Path) -> BeautifulSoup:
    sidebar = soup.find(class_="lms-topic-sidebar-data") or soup.find(class_="lms-topic-sidebar-wrapper")
    if not sidebar:
        print("  [aviso] No se encontró el sidebar en el HTML, se conserva sin cambios.")
        return soup

    lista = sidebar.find("ol", class_="bb-lessons-list") or sidebar.find(class_="lms-lessions-list")
    if not lista:
        lista = sidebar.find("ol")
    if not lista:
        print("  [aviso] No se encontró la lista de lecciones en el sidebar.")
        return soup

    for a in lista.find_all("a", href=True):
        href = a["href"]
        if "cresciente.net" in href and "/lecciones/" in href:
            slug = slug_leccion_desde_url(href)
            if not slug:
                continue
            carpeta_destino = buscar_carpeta_leccion(curso_dir, slug)
            if not carpeta_destino:
                print(f"  [aviso] No se encontró carpeta local para el slug: {slug}")
                continue
            try:
                rel = relpath(carpeta_destino, carpeta_origen)
                nuevo_href = rel.replace("\\", "/") + "/index_indice.html"
                a["href"] = nuevo_href
                print(f"    {slug} → {nuevo_href}")
            except Exception as e:
                print(f"    [error] al reescribir {slug}: {e}")
    return soup

def reescribir_enlaces_navegacion(soup: BeautifulSoup, curso_dir: Path, carpeta_origen: Path) -> BeautifulSoup:
    nav_container = soup.find(class_="learndash_next_prev_link")
    if not nav_container:
        return soup

    for a in nav_container.find_all("a", href=True):
        href = a["href"]
        if "cresciente.net" in href and "/lecciones/" in href:
            slug = slug_leccion_desde_url(href)
            if not slug:
                continue
            carpeta_destino = buscar_carpeta_leccion(curso_dir, slug)
            if not carpeta_destino:
                print(f"  [aviso] No se encontró carpeta local para navegación: {slug}")
                continue
            try:
                rel = relpath(carpeta_destino, carpeta_origen)
                nuevo_href = rel.replace("\\", "/") + "/index_indice.html"
                a["href"] = nuevo_href
                print(f"    [nav] {slug} → {nuevo_href}")
            except Exception as e:
                print(f"    [error] al reescribir navegación para {slug}: {e}")
    return soup

def reescribir_enlace_volver_curso(soup: BeautifulSoup, url_curso: str) -> BeautifulSoup:
    """Reescribe cualquier enlace que apunte a la raíz del curso para que vaya a ../index_indice.html."""
    parsed_curso = urlparse(url_curso)
    curso_path = parsed_curso.path.rstrip("/")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        href_abs = urljoin(url_curso, href)
        parsed = urlparse(href_abs)
        # Si el enlace apunta a la misma ruta que el curso (sin /lecciones/)
        if parsed.netloc == parsed_curso.netloc and parsed.path.rstrip("/") == curso_path:
            a["href"] = "../index_indice.html"
            print(f"    [volver curso] → ../index_indice.html")
    return soup

def agregar_boton_volver_indice(soup: BeautifulSoup) -> BeautifulSoup:
    """Agrega un botón al sidebar que apunta a ../index_indice.html"""
    sidebar = soup.find(class_="lms-topic-sidebar-data") or soup.find(class_="lms-topic-sidebar-wrapper")
    if not sidebar:
        return soup

    lista = sidebar.find("ol", class_="bb-lessons-list") or sidebar.find(class_="lms-lessions-list")
    if not lista:
        lista = sidebar.find("ol")
    if not lista:
        container = sidebar
    else:
        container = lista

    new_li = BeautifulSoup(
        f'<li style="margin-top:20px; border-top:2px solid #f29d00; padding-top:15px;">'
        f'<a href="../index_indice.html" style="font-weight:bold; color:#f29d00;">🏠 Volver al índice del curso</a>'
        f'</li>',
        "html.parser"
    )
    container.append(new_li)
    return soup

def generar_indice_local_para_leccion(leccion_dir: Path, curso_dir: Path, url_curso: str) -> dict:
    html_path = leccion_dir / "index.html"
    if not html_path.exists():
        return {"error": "No se encontró index.html"}

    try:
        soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    except Exception as e:
        return {"error": f"Error al leer HTML: {e}"}

    # Reescribir enlaces del sidebar, navegación y el botón "Volver al curso"
    soup = reescribir_enlaces_sidebar(soup, curso_dir, leccion_dir)
    soup = reescribir_enlaces_navegacion(soup, curso_dir, leccion_dir)
    soup = reescribir_enlace_volver_curso(soup, url_curso)
    soup = agregar_boton_volver_indice(soup)

    output_path = leccion_dir / "index_indice.html"
    try:
        output_path.write_text(soup.prettify(), encoding="utf-8")
        return {"ok": True, "ruta": str(output_path)}
    except Exception as e:
        return {"error": f"Error al guardar: {e}"}

# ── Índice desde sidebar con video de portada ──────────────────────────────
def generar_indice_sidebar(curso_dir: Path):
    """
    Genera un índice a partir del sidebar de la primera lección.
    Si existe un video en la portada (desde index_indice.html), lo incluye arriba.
    """
    lecciones = list(curso_dir.glob("*_lecciones_*/index.html")) or list(curso_dir.glob("lecciones_*/index.html"))
    if not lecciones:
        print("❌ No se encontraron lecciones para generar el índice desde sidebar.")
        return

    # Obtener el sidebar de la primera lección
    soup = BeautifulSoup(lecciones[0].read_text(encoding="utf-8"), "html.parser")
    sidebar = soup.find(class_="lms-topic-sidebar-data") or soup.find(class_="lms-topic-sidebar-wrapper")
    if not sidebar:
        print("❌ No se encontró el sidebar en la muestra.")
        return

    lista = sidebar.find("ol", class_="bb-lessons-list") or sidebar.find(class_="lms-lessions-list")
    if not lista:
        lista = sidebar.find("ol")
    if not lista:
        print("❌ No se encontró la lista.")
        return

    lista_clon = BeautifulSoup(str(lista), "html.parser")
    for a in lista_clon.find_all("a", href=True):
        href = a["href"]
        if "cresciente.net" in href and "/lecciones/" in href:
            slug = slug_leccion_desde_url(href)
            if slug:
                carpeta = buscar_carpeta_leccion(curso_dir, slug)
                if carpeta:
                    a["href"] = f"{carpeta.name}/index_indice.html"
                else:
                    print(f"  [aviso] No se encontró carpeta para {slug}, se mantiene enlace original.")

    # --- Extraer video de la portada (si existe) desde index_indice.html ---
    video_html = ""
    portada_path = curso_dir / "index_indice.html"
    if portada_path.exists():
        try:
            portada_soup = BeautifulSoup(portada_path.read_text(encoding="utf-8"), "html.parser")
            video_tag = portada_soup.find("video")
            if video_tag:
                video_html = str(video_tag)
                print("  [video portada] se incluirá en el índice sidebar.")
            else:
                print("  [video portada] no se encontró video en la portada.")
        except Exception as e:
            print(f"  [aviso] No se pudo leer index_indice.html para extraer video: {e}")

    # Construir el HTML final
    html_template = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Índice del curso: {curso_dir.name}</title>
    <style>
        body {{ font-family: sans-serif; margin: 20px; background: #f8f8f8; }}
        .container {{ max-width: 800px; margin: auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #f29d00; padding-bottom: 10px; }}
        .video-container {{ margin: 20px 0; text-align: center; }}
        video {{ width: 100%; max-width: 100%; height: auto; }}
        ul {{ list-style: none; padding: 0; }}
        li {{ padding: 8px 0; border-bottom: 1px solid #eee; }}
        li a {{ color: #0066cc; text-decoration: none; }}
        li a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
<div class="container">
    <h1>📚 {curso_dir.name}</h1>
    {f'<div class="video-container">{video_html}</div>' if video_html else ''}
    {str(lista_clon)}
    <p style="margin-top:20px;"><a href="index_indice.html">↩ Volver a la página principal del curso</a></p>
</div>
</body>
</html>
    """
    output_path = curso_dir / "index_sidebar.html"
    output_path.write_text(html_template, encoding="utf-8")
    print(f"✅ Índice sidebar generado en {output_path}")

# ── Función principal ──────────────────────────────────────────────────────
def procesar_curso(curso_slug: str, url_curso: str = None) -> dict:
    curso_dir = CURSOS_DIR / curso_slug
    if not curso_dir.exists():
        return {
            "curso": curso_slug,
            "error": f"Carpeta no encontrada: {curso_dir}",
            "total_lecciones": 0,
            "ok": 0,
            "errores": []
        }

    print(f"\n{'='*60}")
    print(f"📁 Procesando curso: {curso_slug}")
    if url_curso:
        print(f"   URL: {url_curso}")
    print(f"{'='*60}")

    reporte = {
        "curso": curso_slug,
        "total_lecciones": 0,
        "ok": 0,
        "errores": []
    }

    # ── 1. Descargar y reescribir la página principal del curso ──
    if url_curso:
        print("\n🌐 Descargando página principal del curso...")
        soup_curso = descargar_pagina_curso(url_curso)
        if soup_curso:
            # 1a. Procesar videos de la portada
            print("\n🎬 Procesando videos de la portada...")
            soup_curso = procesar_videos_portada(soup_curso, curso_slug, curso_dir, url_curso)
            # 1b. Reescribir enlaces a lecciones y catálogo
            print("\n🔗 Reescribiendo enlaces...")
            soup_curso = reescribir_enlaces_lecciones(soup_curso, curso_dir, url_curso)
            # 1c. Guardar como index_indice.html
            guardar_pagina_curso(soup_curso, curso_dir)
        else:
            print("  [aviso] No se pudo descargar la página del curso, se omite.")
    else:
        print("\n  [aviso] No se proporcionó URL del curso, se omite la descarga de la página principal.")

    # ── 2. Generar índices locales para cada lección ──
    print("\n📄 Generando índices locales para cada lección...")
    lecciones_dir = [d for d in curso_dir.iterdir() if d.is_dir() and (d / "index.html").exists()]
    reporte["total_lecciones"] = len(lecciones_dir)

    for leccion in lecciones_dir:
        print(f"\n📄 Procesando lección: {leccion.name}")
        resultado = generar_indice_local_para_leccion(leccion, curso_dir, url_curso or f"https://cresciente.net/cursos/{curso_slug}/")
        if "error" in resultado:
            reporte["errores"].append((leccion.name, resultado["error"]))
            print(f"  ❌ Error: {resultado['error']}")
        else:
            reporte["ok"] += 1
            print(f"  ✅ index_indice.html generado")

    # ── 3. Generar índice sidebar con video de portada ──
    print("\n📄 Generando índice sidebar (index_sidebar.html) con video de portada...")
    try:
        generar_indice_sidebar(curso_dir)
        reporte["indice_sidebar"] = "OK"
    except Exception as e:
        reporte["indice_sidebar"] = f"ERROR: {e}"

    return reporte

def guardar_pagina_curso(soup: BeautifulSoup, curso_dir: Path) -> bool:
    """Guarda el HTML reescrito como index_indice.html en la raíz del curso."""
    output_path = curso_dir / "index_indice.html"
    try:
        output_path.write_text(soup.prettify(), encoding="utf-8")
        print(f"  [guardado] {output_path}")
        return True
    except Exception as e:
        print(f"  [error] No se pudo guardar: {e}")
        return False

# ── Ejecución principal ──────────────────────────────────────────────────
def main():
    inicio_global = datetime.now()

    # Obtener la lista de cursos a procesar
    cursos_a_procesar = []
    if 'CURSOS_URLS_FILE' in globals() and CURSOS_URLS_FILE and Path(CURSOS_URLS_FILE).exists():
        print(f"📄 Leyendo URLs desde: {CURSOS_URLS_FILE}")
        with open(CURSOS_URLS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    slug = slug_curso_desde_url(line)
                    if slug:
                        cursos_a_procesar.append((slug, line))
                    else:
                        print(f"  [aviso] No se pudo extraer slug de: {line}")
    elif CURSOS_SLUGS:
        cursos_a_procesar = [(slug, None) for slug in CURSOS_SLUGS]
    else:
        print("❌ No se definieron cursos. Configura CURSOS_SLUGS o CURSOS_URLS_FILE.")
        input("Presiona Enter para salir...")
        return

    if not cursos_a_procesar:
        print("❌ La lista de cursos está vacía.")
        input("Presiona Enter para salir...")
        return

    print(f"\n🚀 Procesando {len(cursos_a_procesar)} curso(s):")
    for slug, url in cursos_a_procesar:
        print(f"  - {slug}" + (f" ({url})" if url else ""))

    reportes = []
    for slug, url in cursos_a_procesar:
        if not url:
            url = f"https://cresciente.net/cursos/{slug}/"
        reporte = procesar_curso(slug, url)
        reportes.append(reporte)

    # ── Reporte global ──────────────────────────────────────────────────
    fin_global = datetime.now()
    duracion_global = str(fin_global - inicio_global).split('.')[0]

    print("\n" + "="*70)
    print("  📊 REPORTE GLOBAL DE GENERACIÓN DE ÍNDICES LOCALES")
    print("="*70)

    total_cursos = len(reportes)
    total_lecciones = 0
    total_ok = 0
    total_errores = 0

    for r in reportes:
        if "error" in r:
            print(f"\n  ❌ Curso '{r['curso']}': {r['error']}")
            continue
        print(f"\n  📁 {r['curso']}")
        print(f"     Lecciones totales: {r['total_lecciones']}")
        print(f"     ✅ Generados correctamente: {r['ok']}")
        print(f"     ❌ Errores: {len(r['errores'])}")
        print(f"     📄 Índice sidebar: {r.get('indice_sidebar', 'N/A')}")
        total_lecciones += r['total_lecciones']
        total_ok += r['ok']
        total_errores += len(r['errores'])

    print("\n" + "─"*70)
    print(f"  Resumen global:")
    print(f"     Cursos procesados   : {total_cursos}")
    print(f"     Lecciones totales   : {total_lecciones}")
    print(f"     ✅ Exitosas         : {total_ok}")
    print(f"     ❌ Con error        : {total_errores}")
    print(f"     Duración total      : {duracion_global}")
    print("="*70)

    # Guardar reporte global
    reporte_global_path = CURSOS_DIR / "reporte_indices_global.txt"
    with open(reporte_global_path, "w", encoding="utf-8") as f:
        f.write("REPORTE GLOBAL DE GENERACIÓN DE ÍNDICES LOCALES\n")
        f.write("="*70 + "\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Duración: {duracion_global}\n\n")
        for r in reportes:
            if "error" in r:
                f.write(f"❌ Curso '{r['curso']}': {r['error']}\n")
                continue
            f.write(f"📁 {r['curso']}\n")
            f.write(f"  Lecciones totales: {r['total_lecciones']}\n")
            f.write(f"  ✅ Generados correctamente: {r['ok']}\n")
            f.write(f"  ❌ Errores: {len(r['errores'])}\n")
            if r['errores']:
                f.write("    Detalle:\n")
                for nombre, error in r['errores']:
                    f.write(f"      - {nombre}: {error}\n")
            f.write(f"  📄 Índice sidebar: {r.get('indice_sidebar', 'N/A')}\n\n")
        f.write("─"*70 + "\n")
        f.write(f"Resumen global:\n")
        f.write(f"  Cursos procesados: {total_cursos}\n")
        f.write(f"  Lecciones totales: {total_lecciones}\n")
        f.write(f"  ✅ Exitosas      : {total_ok}\n")
        f.write(f"  ❌ Con error     : {total_errores}\n")
        f.write(f"  Duración total   : {duracion_global}\n")
        f.write("="*70 + "\n")
        f.write(f"Reporte generado: {reporte_global_path}\n")

    print(f"\n📄 Reporte global guardado en: {reporte_global_path}")
    print("\n✅ ¡Todos los cursos procesados!")
    input("\nPresiona Enter para salir...")

if __name__ == "__main__":
    main()