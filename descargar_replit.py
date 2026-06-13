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
FALLIDAS_FILE = BASE_DIR / "fallidas.txt"   # URLs que fallaron, listas para reintentar
DELAY         = 2
MAX_INTENTOS_VIDEO = 3
# Prefiere MP4 directo antes que HLS (evita problemas de fragmentos con Vimeo)
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
# REGISTRO DE FALLIDAS
# ══════════════════════════════════════════════════════════════════════════════

def guardar_fallidas(fallidas: list):
    """
    Guarda en fallidas.txt las URLs que fallaron con su error.
    El archivo se sobreescribe en cada corrida — siempre refleja el último run.
    Si no hubo fallidas, borra el archivo (o no lo crea).
    """
    if not fallidas:
        if FALLIDAS_FILE.exists():
            FALLIDAS_FILE.unlink()
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lineas = [
        f"# fallidas.txt — generado el {timestamp}",
        f"# {len(fallidas)} URL(s) fallaron en el último run.",
        f"# Para reintentar: copiá estas URLs a links.txt y volvé a correr descargar_replit.py",
        "",
    ]
    for num, url, error in fallidas:
        lineas.append(f"# Error en lección #{num}: {error}")
        lineas.append(url)
        lineas.append("")

    FALLIDAS_FILE.write_text("\n".join(lineas), encoding="utf-8")
    log(f"\n  [fallidas] Registro guardado en {FALLIDAS_FILE.name}")
    log(f"  → Copiá esas URLs a links.txt para reintentar.")


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
    Busca URLs de YouTube en iframes, atributos data-* y HTML crudo completo.
    Devuelve lista de URLs https://www.youtube.com/watch?v=VIDEO_ID sin duplicados.
    """
    ids_encontrados = []

    for iframe in soup.find_all("iframe"):
        src = iframe.get("src") or iframe.get("data-src") or ""
        for pattern in YOUTUBE_PATTERNS:
            m = re.search(pattern, src)
            if m:
                ids_encontrados.append(m.group(1))

    for tag in soup.find_all(True):
        for attr, val in tag.attrs.items():
            if isinstance(val, str):
                for pattern in YOUTUBE_PATTERNS:
                    m = re.search(pattern, val)
                    if m:
                        ids_encontrados.append(m.group(1))

    for pattern in YOUTUBE_PATTERNS:
        for m in re.finditer(pattern, html_raw):
            ids_encontrados.append(m.group(1))

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
    Descarga el HTML, extrae adjuntos, reescribe rutas y guarda index.html.
    Devuelve (soup, html_raw) para reutilizar en la descarga de video.
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

def _es_parcial_ytdlp(path: Path) -> bool:
    """
    Devuelve True si el archivo es un fragmento temporal de yt-dlp.
    Detecta cualquier nombre que termine en .fNNN o .fNNN.ext:
      nombre.f398          → stream sin mergear
      nombre.f398.mp4      → merge incompleto que quedó con el código en el nombre
      nombre.part          → descarga interrumpida
    """
    return (
        bool(re.search(r'\.f\d+(\.[^.]+)?$', path.name))
        or path.suffix == ".part"
    )


def _limpiar_parciales(output_template: str):
    """Borra archivos .part y .fNNN que haya dejado una descarga interrumpida."""
    import glob as _glob
    patron = output_template.replace("%(ext)s", "*")
    for ruta in _glob.glob(patron) + _glob.glob(patron + ".part"):
        p = Path(ruta)
        if _es_parcial_ytdlp(p):
            try:
                p.unlink()
                log(f"  [limpieza] borrado parcial: {p.name}")
            except Exception:
                pass


def _correr_ytdlp(url_video: str, output_template: str, label: str) -> bool:
    """
    Corre yt-dlp sobre una URL. Reintenta hasta MAX_INTENTOS_VIDEO veces
    desde cero si falla por error de red, para que el video quede completo.
    """
    for intento in range(1, MAX_INTENTOS_VIDEO + 1):
        if intento > 1:
            log(f"  [video] reintentando ({intento}/{MAX_INTENTOS_VIDEO}) → {label}")
            time.sleep(5)
        else:
            log(f"  [video] descargando {label} → {url_video}")

        _limpiar_parciales(output_template)

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
                    "--no-part",
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
    1. Busca YouTube en el HTML → descarga por video ID.
    2. Si no hay YouTube → yt-dlp sobre la URL de la lección (Vimeo, nativo, etc.).
    Devuelve lista de (archivo_local: Path, url_fuente: str).
    """
    videos_dir = BASE_DIR / curso_slug / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    descargados = []

    yt_urls = extraer_urls_youtube(soup, html_raw) if soup is not None else []

    if yt_urls:
        log(f"  [youtube] {len(yt_urls)} video(s) encontrado(s) en el HTML")
        for idx, yt_url in enumerate(yt_urls):
            sufijo    = f"_yt{idx+1}" if len(yt_urls) > 1 else ""
            plantilla = str(videos_dir / f"{nombre_video}{sufijo}.%(ext)s")
            existentes = [p for p in videos_dir.glob(f"{nombre_video}{sufijo}.*")
                          if not _es_parcial_ytdlp(p)]
            if existentes:
                log(f"  [video ya existe] {existentes[0].name}")
                descargados.append((existentes[0], yt_url))
                continue
            _limpiar_parciales(plantilla)
            if _correr_ytdlp(yt_url, plantilla, f"YouTube #{idx+1}"):
                encontrados = [p for p in videos_dir.glob(f"{nombre_video}{sufijo}.*")
                               if not _es_parcial_ytdlp(p)]
                if encontrados:
                    descargados.append((encontrados[0], yt_url))
        return descargados

    log(f"  [video] Sin YouTube — intentando URL de lección directamente")
    existentes = [p for p in videos_dir.glob(f"{nombre_video}.*")
                  if not _es_parcial_ytdlp(p)]
    if existentes:
        log(f"  [video ya existe] {existentes[0].name}")
        return [(existentes[0], url_leccion)]

    plantilla = str(videos_dir / f"{nombre_video}.%(ext)s")
    if _correr_ytdlp(url_leccion, plantilla, "lección completa"):
        encontrados = [p for p in videos_dir.glob(f"{nombre_video}.*")
                       if not _es_parcial_ytdlp(p)]
        if encontrados:
            descargados.append((encontrados[0], url_leccion))
    return descargados


# ══════════════════════════════════════════════════════════════════════════════
# 6. REESCRITURA DE VIDEOS EN EL HTML LOCAL
# ══════════════════════════════════════════════════════════════════════════════

def _ext_mime(ext: str) -> str:
    return {
        ".mp4": "video/mp4", ".webm": "video/webm",
        ".mkv": "video/x-matroska", ".mov": "video/quicktime", ".m4v": "video/mp4",
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
    Reemplaza iframes de YouTube/Vimeo y tags <video> remotos por <video> locales.
    """
    if not videos_descargados:
        return
    html_path = leccion_dir / "index.html"
    if not html_path.exists():
        return

    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    modificado = False

    for archivo_local, url_fuente in videos_descargados:
        ruta_rel = f"../videos/{archivo_local.name}"
        ext      = archivo_local.suffix

        # YouTube: buscar por video ID
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

        # Vimeo
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src") or iframe.get("data-src") or ""
            if "vimeo.com" in src:
                iframe.replace_with(BeautifulSoup(_video_tag(ruta_rel, ext), "html.parser"))
                log(f"  [html] iframe Vimeo reemplazado → {ruta_rel}")
                modificado = True
                break

        # Tags <video>/<source> con URLs remotas
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
        log(f"  [html] No se encontraron iframes de video para reemplazar")


# ══════════════════════════════════════════════════════════════════════════════
# 7. PROCESAMIENTO DE UNA LECCIÓN
# ══════════════════════════════════════════════════════════════════════════════

def _video_pendiente(leccion_dir: Path, curso_slug: str) -> bool:
    """
    Devuelve True si index.html existe pero hay videos sin descargar:
    - iframes de YouTube/Vimeo que no fueron reemplazados, o
    - <source>/<video> con src="../videos/FILENAME" cuyo archivo no existe en disco.
    """
    html_path = leccion_dir / "index.html"
    if not html_path.exists():
        return False

    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")

    for iframe in soup.find_all("iframe"):
        src = iframe.get("src") or iframe.get("data-src") or ""
        if "youtube.com" in src or "youtu.be" in src or "vimeo.com" in src:
            return True

    videos_dir = BASE_DIR / curso_slug / "videos"
    for tag in soup.find_all(["source", "video"]):
        src = tag.get("src") or ""
        if src.startswith("../videos/"):
            nombre_archivo = src[len("../videos/"):]
            archivo = videos_dir / nombre_archivo
            # Pendiente si el archivo no existe O es un fragmento temporal (.fNNN)
            if not archivo.exists() or _es_parcial_ytdlp(archivo):
                return True

    return False


def procesar_leccion(session: requests.Session, url: str) -> bool:
    """
    Devuelve True si la lección fue procesada (nueva o video completado),
    False si ya estaba completamente descargada.
    """
    curso_slug, leccion_slug, nombre_video = segmentos_url(url)
    leccion_dir = BASE_DIR / curso_slug / leccion_slug

    # ── Chequeo previo: ¿ya está descargada? ──────────────────────────────────
    if (leccion_dir / "index.html").exists():
        if not _video_pendiente(leccion_dir, curso_slug):
            log(f"\n{'─'*60}")
            log(f"[ya descargada] {leccion_slug}  ({url})")
            log(f"  → Saltando. Borrá la carpeta si querés volver a descargarla:")
            log(f"     {leccion_dir}")
            return False

        # HTML existe pero falta el video — completar solo la descarga de video
        log(f"\n{'─'*60}")
        log(f"[completando video] {leccion_slug}  ({url})")
        log(f"  → index.html existe pero el video no está. Descargando...")
        raw_path = leccion_dir / "index_raw.html"
        if raw_path.exists():
            html_raw = raw_path.read_text(encoding="utf-8")
            soup = BeautifulSoup(html_raw, "html.parser")
            log(f"  → Usando index_raw.html guardado (sin re-descargar el HTML)")
        else:
            log(f"  → index_raw.html no encontrado, re-descargando el HTML...")
            soup, html_raw = procesar_html_y_adjuntos(session, url, leccion_dir)
        videos_descargados = descargar_video(soup, html_raw, url, curso_slug, nombre_video)
        reescribir_videos_en_html(leccion_dir, videos_descargados)
        return True

    leccion_dir.mkdir(parents=True, exist_ok=True)

    log(f"\n{'─'*60}")
    log(f"URL     : {url}")
    log(f"Curso   : {curso_slug}")
    log(f"Lección : {leccion_slug}")
    log(f"Carpeta : {leccion_dir}")

    soup, html_raw = procesar_html_y_adjuntos(session, url, leccion_dir)
    videos_descargados = descargar_video(soup, html_raw, url, curso_slug, nombre_video)
    reescribir_videos_en_html(leccion_dir, videos_descargados)
    return True


# ══════════════════════════════════════════════════════════════════════════════
# 8. MAIN
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

    fallidas    = []  # (num, url, mensaje_error)
    ya_bajas    = []  # urls que ya estaban descargadas

    for i, url in enumerate(urls):
        try:
            procesada = procesar_leccion(session, url)
            if not procesada:
                ya_bajas.append(url)
        except Exception as e:
            msg = str(e)
            log(f"\n  [ERROR inesperado — lección {i+1}/{len(urls)}] {url}")
            log(f"  → {msg}")
            fallidas.append((i + 1, url, msg))
            log(f"  Continuando con la siguiente lección...")

        if i < len(urls) - 1:
            time.sleep(DELAY)

    # ── Resumen final ──────────────────────────────────────────────────────────
    nuevas = len(urls) - len(fallidas) - len(ya_bajas)
    log(f"\n{'═'*60}")
    log(f"  Nuevas descargadas : {nuevas}/{len(urls)}")
    if ya_bajas:
        log(f"  Ya descargadas     : {len(ya_bajas)} (saltadas)")
    if fallidas:
        log(f"  Con error          : {len(fallidas)}")
        for num, u, err in fallidas:
            log(f"    #{num}: {u}")
            log(f"         {err}")
        guardar_fallidas(fallidas)
    else:
        if FALLIDAS_FILE.exists():
            FALLIDAS_FILE.unlink()
            log(f"  (fallidas.txt eliminado — todo OK)")

    log(f"  Carpetas en: {BASE_DIR}")
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
