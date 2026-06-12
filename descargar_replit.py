import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote
import re
import subprocess
import time
from datetime import datetime

# ── Configuración ──────────────────────────────────────────────────────────────
BASE_DIR      = Path(r"C:\mis_sitios_descargados")
COOKIES_FILE  = BASE_DIR / "cookies.txt"
LINKS_FILE    = BASE_DIR / "links.txt"
LOG_FILE      = BASE_DIR / "log.txt"
DELAY         = 2
# Prefiere MP4 directo antes que HLS cuando esté disponible (evita problemas de fragmentos)
VIDEO_CALIDAD = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best"
# ──────────────────────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════════
# LOG
# ══════════════════════════════════════════════════════════════════════════════

_log_file = None

def log(msg: str = ""):
    print(msg)
    if _log_file:
        _log_file.write(msg + "\n")
        _log_file.flush()

def init_log():
    global _log_file
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    _log_file = open(LOG_FILE, "a", encoding="utf-8")
    log(f"\n{'═'*60}")
    log(f"  Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"{'═'*60}")

def close_log():
    log(f"\n  Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"{'═'*60}\n")
    if _log_file:
        _log_file.close()


# ══════════════════════════════════════════════════════════════════════════════
# 1. COOKIES
# ══════════════════════════════════════════════════════════════════════════════

def cargar_cookies(path: Path) -> dict:
    cookies = {}
    if not path.exists():
        log(f"  [advertencia] No se encontró {path}")
        return cookies

    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or line.strip() == "":
                continue
            partes = line.strip().split("\t")
            if len(partes) >= 7:
                cookies[partes[5]] = partes[6]

    log(f"  [cookies] {len(cookies)} cookies cargadas desde {path.name}")

    # Validar que hay cookie de sesión de WordPress
    wp_cookies = [k for k in cookies if k.startswith("wordpress_logged_in")]
    if wp_cookies:
        log(f"  [cookies] Sesión WP activa: {', '.join(wp_cookies)}")
    else:
        log(f"  [advertencia] No se encontró wordpress_logged_in_* — puede que no estés autenticado")

    return cookies


# ══════════════════════════════════════════════════════════════════════════════
# 2. HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def limpiar_nombre(texto: str) -> str:
    texto = unquote(texto)
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", texto).strip("_ ")


def segmentos_url(url: str):
    partes = urlparse(url).path.strip("/").split("/")

    curso_slug   = "curso"
    leccion_slug = "_".join(partes[-2:]) if len(partes) >= 2 else partes[-1]

    for i, p in enumerate(partes):
        if p in ("courses", "cursos") and i + 1 < len(partes):
            curso_slug = partes[i + 1]
            break

    nombre_video = "___".join(partes[:4]) if len(partes) >= 4 else "___".join(partes)
    nombre_video = re.sub(r'%f0%9f%93%b9-', '', nombre_video, flags=re.IGNORECASE)
    nombre_video = limpiar_nombre(nombre_video)

    return limpiar_nombre(curso_slug), limpiar_nombre(leccion_slug), nombre_video


# ══════════════════════════════════════════════════════════════════════════════
# 3. EXTRACCIÓN DE URLs DE YOUTUBE DESDE EL HTML
# ══════════════════════════════════════════════════════════════════════════════

YOUTUBE_PATTERNS = [
    r'youtube\.com/embed/([A-Za-z0-9_-]{11})',
    r'youtube\.com/watch\?v=([A-Za-z0-9_-]{11})',
    r'youtu\.be/([A-Za-z0-9_-]{11})',
    r'youtube\.com/v/([A-Za-z0-9_-]{11})',
]

def extraer_urls_youtube(soup: BeautifulSoup, html_raw: str) -> list[str]:
    """
    Busca URLs de YouTube en:
      - iframes (src y data-src)
      - atributos data-* de cualquier elemento
      - el texto crudo del HTML (para videos embebidos con JS)
    Devuelve lista de URLs https://www.youtube.com/watch?v=VIDEO_ID sin duplicados.
    """
    ids_encontrados = []

    # 1. Buscar en iframes
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src") or iframe.get("data-src") or ""
        for pattern in YOUTUBE_PATTERNS:
            m = re.search(pattern, src)
            if m:
                ids_encontrados.append(m.group(1))

    # 2. Buscar en atributos data-* de cualquier tag (LearnDash a veces los usa)
    for tag in soup.find_all(True):
        for attr, val in tag.attrs.items():
            if isinstance(val, str):
                for pattern in YOUTUBE_PATTERNS:
                    m = re.search(pattern, val)
                    if m:
                        ids_encontrados.append(m.group(1))

    # 3. Buscar en el HTML crudo completo (cubre casos de JS/JSON embebido)
    for pattern in YOUTUBE_PATTERNS:
        for m in re.finditer(pattern, html_raw):
            ids_encontrados.append(m.group(1))

    # Deduplicar manteniendo orden
    vistos = set()
    urls = []
    for vid_id in ids_encontrados:
        if vid_id not in vistos:
            vistos.add(vid_id)
            urls.append(f"https://www.youtube.com/watch?v={vid_id}")

    return urls


# ══════════════════════════════════════════════════════════════════════════════
# 4. DESCARGA DE ADJUNTOS
# ══════════════════════════════════════════════════════════════════════════════

def descargar_archivo(session: requests.Session, url: str, destino: Path) -> bool:
    if destino.exists():
        log(f"  [ya existe] {destino.name}")
        return True
    try:
        r = session.get(url, timeout=30, stream=True)
        log(f"  [http {r.status_code}] {url}")
        r.raise_for_status()
        destino.parent.mkdir(parents=True, exist_ok=True)
        with open(destino, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        log(f"  [ok] {destino.name}")
        return True
    except Exception as e:
        log(f"  [error descargando archivo] {url}")
        log(f"    → {e}")
        return False


def procesar_html_y_adjuntos(session: requests.Session, url: str, leccion_dir: Path):
    """
    Descarga el HTML de la lección, guarda index_raw.html, extrae adjuntos,
    reescribe rutas y guarda index.html.
    Devuelve el soup y el html crudo para que la función de video los reutilice.
    """
    materiales = leccion_dir / "materiales"
    materiales.mkdir(parents=True, exist_ok=True)

    log(f"  Descargando HTML...")
    try:
        r = session.get(url, timeout=30)
        log(f"  [http {r.status_code}] {url}")
        r.raise_for_status()
    except Exception as e:
        log(f"  [error al obtener HTML] {e}")
        return None, ""

    html_raw = r.text
    raw_path = leccion_dir / "index_raw.html"
    raw_path.write_text(html_raw, encoding="utf-8")
    log(f"  [html crudo guardado] {raw_path.name} ({len(html_raw)} chars)")

    soup = BeautifulSoup(html_raw, "html.parser")

    titulo = soup.find("title")
    log(f"  [título página] {titulo.text.strip() if titulo else '(sin título)'}")

    extensiones_descargables = {
        ".pdf", ".mp3", ".wav", ".ogg", ".flac",
        ".mscz", ".mxl", ".xml", ".zip", ".rar",
        ".jpg", ".jpeg", ".png", ".gif", ".webp",
        ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    }

    selectores = [
        ("a[href]",     "href"),
        ("audio[src]",  "src"),
        ("source[src]", "src"),
        ("img[src]",    "src"),
    ]

    encontrados = 0
    for selector, atributo in selectores:
        tags = soup.select(selector)
        log(f"  [selector '{selector}'] {len(tags)} tags encontrados")
        for tag in tags:
            href = tag.get(atributo, "").strip()
            if not href or href.startswith(("javascript:", "mailto:", "#")):
                continue

            href_abs = urljoin(url, href)
            sufijo   = Path(urlparse(href_abs).path).suffix.lower()

            if sufijo not in extensiones_descargables:
                continue

            encontrados += 1
            nombre_archivo = Path(urlparse(href_abs).path).name
            destino = materiales / nombre_archivo

            if descargar_archivo(session, href_abs, destino):
                tag[atributo] = f"materiales/{nombre_archivo}"

    log(f"  [adjuntos descargables encontrados] {encontrados}")

    html_path = leccion_dir / "index.html"
    html_path.write_text(soup.prettify(), encoding="utf-8")
    log(f"  [html guardado] {html_path.name}")

    return soup, html_raw


# ══════════════════════════════════════════════════════════════════════════════
# 5. DESCARGA DE VIDEO
# ══════════════════════════════════════════════════════════════════════════════

MAX_INTENTOS_VIDEO = 3  # cuántas veces reintentar la descarga si falla

def _correr_ytdlp(url_video: str, output_template: str, label: str):
    """
    Corre yt-dlp sobre una URL concreta.
    Si falla por error de red (fragmentos HLS, timeout, etc.), reintenta
    hasta MAX_INTENTOS_VIDEO veces desde cero — así el video queda completo.
    """
    for intento in range(1, MAX_INTENTOS_VIDEO + 1):
        if intento > 1:
            log(f"  [video] reintentando ({intento}/{MAX_INTENTOS_VIDEO}) → {label}")
            time.sleep(5)
        else:
            log(f"  [video] descargando {label} → {url_video}")

        # Borrar archivo parcial antes de reintentar para empezar limpio
        import glob as _glob
        for parcial in _glob.glob(output_template.replace("%(ext)s", "*") + ".part"):
            try:
                Path(parcial).unlink()
            except Exception:
                pass

        try:
            result = subprocess.run(
                [
                    "yt-dlp",
                    url_video,
                    "-f", VIDEO_CALIDAD,
                    "--output", output_template,
                    "--cookies", str(COOKIES_FILE),
                    "--no-playlist",
                    "--fragment-retries", "5",
                    "--retries", "5",
                    "--socket-timeout", "30",
                    "--no-part",  # no dejar archivos .part incompletos
                ],
                capture_output=True,
                text=True,
            )
            log(f"  [yt-dlp stdout]\n{result.stdout[-1500:]}")
            if result.returncode == 0:
                log(f"  [video ok] {label}")
                return True
            else:
                log(f"  [error video] código {result.returncode} — intento {intento}/{MAX_INTENTOS_VIDEO}")
                log(f"  [yt-dlp stderr]\n{result.stderr[-800:]}")
                # Si el error no es de red, no tiene sentido reintentar
                if "Unsupported URL" in result.stderr or "not found" in result.stderr.lower():
                    break
        except FileNotFoundError:
            log("  [error] yt-dlp no encontrado. Instalalo con: pip install yt-dlp")
            return False
        except Exception as e:
            log(f"  [error inesperado en video] {e}")

    log(f"  [video fallido] No se pudo descargar después de {MAX_INTENTOS_VIDEO} intentos: {label}")
    return False


def descargar_video(soup, html_raw: str, url_leccion: str, curso_slug: str, nombre_video: str) -> list:
    """
    Estrategia:
      1. Busca URLs de YouTube en el HTML (iframe, data-*, texto crudo).
      2. Si encuentra alguna, descarga cada una con yt-dlp.
      3. Si no hay YouTube, intenta yt-dlp sobre la URL de la lección directamente
         (para videos nativos de LearnDash / Vimeo / etc.).
    Devuelve lista de (archivo_local: Path, url_fuente: str) para los videos descargados.
    """
    videos_dir = BASE_DIR / curso_slug / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    descargados = []  # [(Path, str_url_fuente)]

    # ── Buscar videos de YouTube ──────────────────────────────────────────────
    if soup is not None:
        yt_urls = extraer_urls_youtube(soup, html_raw)
    else:
        yt_urls = []

    if yt_urls:
        log(f"  [youtube] {len(yt_urls)} video(s) encontrado(s) en el HTML")
        for idx, yt_url in enumerate(yt_urls):
            sufijo    = f"_yt{idx+1}" if len(yt_urls) > 1 else ""
            plantilla = str(videos_dir / f"{nombre_video}{sufijo}.%(ext)s")

            existentes = list(videos_dir.glob(f"{nombre_video}{sufijo}.*"))
            if existentes:
                log(f"  [video ya existe] {existentes[0].name}")
                descargados.append((existentes[0], yt_url))
                continue

            ok = _correr_ytdlp(yt_url, plantilla, f"YouTube #{idx+1}")
            if ok:
                encontrados = list(videos_dir.glob(f"{nombre_video}{sufijo}.*"))
                if encontrados:
                    descargados.append((encontrados[0], yt_url))
        return descargados

    # ── Sin YouTube: intentar con la URL de la lección (video nativo / Vimeo) ─
    log(f"  [video] No se encontraron iframes de YouTube — intentando URL de lección directamente")
    existentes = list(videos_dir.glob(f"{nombre_video}.*"))
    if existentes:
        log(f"  [video ya existe] {existentes[0].name}")
        return [(existentes[0], url_leccion)]

    plantilla = str(videos_dir / f"{nombre_video}.%(ext)s")
    ok = _correr_ytdlp(url_leccion, plantilla, "lección completa")
    if ok:
        encontrados = list(videos_dir.glob(f"{nombre_video}.*"))
        if encontrados:
            descargados.append((encontrados[0], url_leccion))
    return descargados


# ══════════════════════════════════════════════════════════════════════════════
# 6. REESCRITURA DE VIDEOS EN EL HTML LOCAL
# ══════════════════════════════════════════════════════════════════════════════

def _ext_mime(ext: str) -> str:
    return {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
        ".mov": "video/quicktime",
        ".m4v": "video/mp4",
    }.get(ext.lower(), "video/mp4")


def _video_tag(ruta_relativa: str, ext: str) -> str:
    mime = _ext_mime(ext)
    return (
        f'<video controls style="width:100%;max-width:960px;display:block;margin:1em 0">'
        f'<source src="{ruta_relativa}" type="{mime}">'
        f'Tu navegador no soporta video HTML5.'
        f'</video>'
    )


def reescribir_videos_en_html(leccion_dir: Path, videos_descargados: list):
    """
    Lee index.html, reemplaza cada iframe de YouTube/Vimeo (y tags <video>/<source>
    con URLs remotas) por un <video> local apuntando a ../videos/nombre.ext
    """
    if not videos_descargados:
        return

    html_path = leccion_dir / "index.html"
    if not html_path.exists():
        return

    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    modificado = False

    for archivo_local, url_fuente in videos_descargados:
        # Ruta relativa desde {leccion}/index.html → ../videos/archivo.ext
        ruta_rel = f"../videos/{archivo_local.name}"
        ext      = archivo_local.suffix

        # ── 1. Iframes de YouTube: buscar por video ID ────────────────────────
        m_yt = None
        for pat in YOUTUBE_PATTERNS:
            m_yt = re.search(pat, url_fuente)
            if m_yt:
                break

        if m_yt:
            vid_id = m_yt.group(1)
            for iframe in soup.find_all("iframe"):
                src = iframe.get("src") or iframe.get("data-src") or ""
                if vid_id in src:
                    iframe.replace_with(BeautifulSoup(_video_tag(ruta_rel, ext), "html.parser"))
                    log(f"  [html] iframe YouTube reemplazado → {ruta_rel}")
                    modificado = True
            continue

        # ── 2. Iframes de Vimeo ───────────────────────────────────────────────
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src") or iframe.get("data-src") or ""
            if "vimeo.com" in src:
                iframe.replace_with(BeautifulSoup(_video_tag(ruta_rel, ext), "html.parser"))
                log(f"  [html] iframe Vimeo reemplazado → {ruta_rel}")
                modificado = True
                break

        # ── 3. Tags <video> o <source> con URLs remotas ───────────────────────
        for tag in soup.find_all(["video", "source"]):
            src = tag.get("src") or ""
            if src.startswith("http"):
                tag["src"] = ruta_rel
                log(f"  [html] <{tag.name}> src reemplazado → {ruta_rel}")
                modificado = True

    if modificado:
        html_path.write_text(soup.prettify(), encoding="utf-8")
        log(f"  [html] index.html actualizado con videos locales")
    else:
        log(f"  [html] No se encontraron iframes de video para reemplazar en el HTML")


# ══════════════════════════════════════════════════════════════════════════════
# 7. PROCESAMIENTO DE UNA LECCIÓN
# ══════════════════════════════════════════════════════════════════════════════

def procesar_leccion(session: requests.Session, url: str):
    curso_slug, leccion_slug, nombre_video = segmentos_url(url)

    leccion_dir = BASE_DIR / curso_slug / leccion_slug
    leccion_dir.mkdir(parents=True, exist_ok=True)

    log(f"\n{'─'*60}")
    log(f"URL     : {url}")
    log(f"Curso   : {curso_slug}")
    log(f"Lección : {leccion_slug}")
    log(f"Carpeta : {leccion_dir}")

    soup, html_raw = procesar_html_y_adjuntos(session, url, leccion_dir)
    videos_descargados = descargar_video(soup, html_raw, url, curso_slug, nombre_video)
    reescribir_videos_en_html(leccion_dir, videos_descargados)


# ══════════════════════════════════════════════════════════════════════════════
# 7. MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    init_log()
    log(f"Log guardado en: {LOG_FILE}")

    if not LINKS_FILE.exists():
        log(f"[error] No se encontró {LINKS_FILE}")
        log("Creá el archivo con una URL por línea.")
        return

    urls = [
        line.strip()
        for line in LINKS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    if not urls:
        log("links.txt está vacío. Agregá al menos una URL.")
        return

    log(f"Lecciones a procesar: {len(urls)}")

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

    for i, url in enumerate(urls):
        procesar_leccion(session, url)
        if i < len(urls) - 1:
            time.sleep(DELAY)

    log(f"\n{'═'*60}")
    log(f"¡Listo! Carpetas en: {BASE_DIR}")
    close_log()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        msg = f"\n[ERROR FATAL] {e}"
        print(msg)
        if _log_file:
            _log_file.write(msg + "\n")
            _log_file.flush()
    finally:
        input("\nPresioná Enter para cerrar...")
