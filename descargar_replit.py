import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote
import re
import subprocess
import time
from datetime import datetime


class SinAccesoError(Exception):
    """Se lanza cuando el servidor redirige a otra página (lección sin acceso)."""

# ── Configuración ──────────────────────────────────────────────────────────────
# Carpeta donde se guardan los cursos descargados.
# Si se deja vacío (""), se usa la misma carpeta donde está este script.
# DESTINO = r""
#DESTINO = r"D:\nacho\cursos_descargados"
DESTINO = r"C:\cursos_descargados"

SCRIPT_DIR    = Path(__file__).parent                              # siempre la carpeta del script
CURSOS_DIR    = Path(DESTINO) if DESTINO.strip() else SCRIPT_DIR  # donde van los cursos

COOKIES_FILE  = SCRIPT_DIR / "cookies.txt"
LINKS_FILE    = SCRIPT_DIR / "links_curso_cc_armonia_aplicada_al_piano.txt"
LOG_FILE      = SCRIPT_DIR / "log.txt"
FALLIDAS_FILE = SCRIPT_DIR / "fallidas.txt"
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
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    CURSOS_DIR.mkdir(parents=True, exist_ok=True)
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


def verificar_login(session: requests.Session, url_prueba: str) -> bool:
    """
    Verifica la sesión yendo a la home del sitio y buscando la clase
    'logged-in' en el <body> — WordPress la agrega siempre al estar autenticado,
    sin importar si la página en sí es accesible o no.
    """
    parsed   = urlparse(url_prueba)
    url_home = f"{parsed.scheme}://{parsed.netloc}/"
    log(f"\n  [login] Verificando sesión en: {url_home}")
    try:
        r = session.get(url_home, timeout=30, allow_redirects=True)

        # WordPress agrega 'logged-in' a las clases del <body> cuando hay sesión activa
        m = re.search(r'<body[^>]+class="([^"]*)"', r.text)
        if m and "logged-in" in m.group(1).split():
            log(f"  [login] OK — sesión activa (body.logged-in detectado)")
            return True

        # Si hay form de login en la página, definitivamente no estamos logueados
        if 'id="loginform"' in r.text or 'name="log"' in r.text:
            log(f"  [login] FALLÓ — se encontró el formulario de login de WordPress")
            return False

        # No se pudo confirmar ni descartar — advertir pero no bloquear
        log(f"  [advertencia login] No se detectó 'logged-in' en el body.")
        log(f"  → Si las descargas dan páginas incorrectas, revisá las cookies.")
        return True

    except Exception as e:
        log(f"  [login] Error al verificar: {e}")
        return False


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
    Las carpetas se crean recién DESPUÉS de verificar que tenemos acceso.
    """
    log(f"  Descargando HTML...")
    try:
        r = session.get(url, timeout=30, allow_redirects=True)
        log(f"  [http {r.status_code}] {url}")
        r.raise_for_status()
    except Exception as e:
        log(f"  [error al obtener HTML] {e}")
        return None, ""

    # Chequeo de acceso ANTES de crear carpetas
    path_pedido    = urlparse(url).path.rstrip("/")
    path_final     = urlparse(r.url).path.rstrip("/")
    dominio_pedido = urlparse(url).netloc
    dominio_final  = urlparse(r.url).netloc

    if path_final != path_pedido:
        if dominio_final != dominio_pedido:
            log(f"  [sin acceso] Redirigido a otro dominio: {r.url}")
            raise SinAccesoError(f"redirigido a otro dominio: {r.url}")
        if path_pedido.startswith(path_final + "/") or path_final in ("/", ""):
            log(f"  [sin acceso] Redirigido a página superior: {r.url}")
            raise SinAccesoError(f"redirigido a página superior: {r.url}")
        log(f"  [advertencia] URL redirigida a {r.url} — procesando igual")

    # Acceso confirmado — recién ahora creamos las carpetas
    materiales = leccion_dir / "materiales"
    leccion_dir.mkdir(parents=True, exist_ok=True)
    materiales.mkdir(parents=True, exist_ok=True)

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
                stdout=None,              # progreso visible en consola en tiempo real
                stderr=subprocess.PIPE,   # capturamos stderr solo para detectar errores
                text=True,
            )
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
    videos_dir = CURSOS_DIR / curso_slug / "videos"
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

        # Vimeo / Bunny.net (mediadelivery.net) y cualquier otro iframe de video conocido
        IFRAME_VIDEO_DOMINIOS = (
            "vimeo.com",
            "mediadelivery.net", "iframe.mediadelivery.net", "bunnycdn.com",  # Bunny.net
            "wistia.com", "fast.wistia.net",          # Wistia
            "loom.com",                                # Loom
            "kaltura.com",                             # Kaltura
            "sproutvideo.com",                         # SproutVideo
            "vidyard.com",                             # Vidyard
            "dailymotion.com",                         # Dailymotion
            "jwplatform.com", "jwplayer.com",          # JW Player
            "brightcove.net", "brightcove.com",        # Brightcove
            "api.video",                               # api.video
        )
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src") or iframe.get("data-src") or ""
            if any(d in src for d in IFRAME_VIDEO_DOMINIOS):
                iframe.replace_with(BeautifulSoup(_video_tag(ruta_rel, ext), "html.parser"))
                log(f"  [html] iframe de video reemplazado ({src[:60]}...) → {ruta_rel}")
                modificado = True
                break

        # Tags <video>/<source> con URLs remotas (incluyendo Bunny.net/HLS)
        DOMINIOS_REMOTOS = ("b-cdn.net", "mediadelivery.net", "vz-", "vimeo.com", "youtube.com")
        for video_tag in soup.find_all("video"):
            # Considerar remoto si: src empieza con http, es blob:, o algún <source> hijo es remoto/HLS
            src_video = video_tag.get("src") or ""
            sources   = video_tag.find_all("source")
            es_remoto = (
                src_video.startswith("http") or
                src_video.startswith("blob:") or
                any(
                    (s.get("src") or "").startswith("http") or
                    any(d in (s.get("src") or "") for d in DOMINIOS_REMOTOS) or
                    (s.get("type") or "") == "application/vnd.apple.mpegURL"
                    for s in sources
                )
            )
            if es_remoto:
                video_tag.replace_with(BeautifulSoup(_video_tag(ruta_rel, ext), "html.parser"))
                log(f"  [html] <video> remoto (posiblemente HLS/Bunny) reemplazado → {ruta_rel}")
                modificado = True
                break
        else:
            # Fallback: source sueltos fuera de <video>
            for tag in soup.find_all("source"):
                src = tag.get("src") or ""
                if src.startswith("http") or any(d in src for d in DOMINIOS_REMOTOS):
                    tag["src"] = ruta_rel
                    log(f"  [html] <source> remoto reemplazado → {ruta_rel}")
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

    videos_dir = CURSOS_DIR / curso_slug / "videos"
    for tag in soup.find_all(["source", "video"]):
        src = tag.get("src") or ""
        if src.startswith("../videos/"):
            nombre_archivo = src[len("../videos/"):]
            archivo = videos_dir / nombre_archivo
            # Pendiente si el archivo no existe O es un fragmento temporal (.fNNN)
            if not archivo.exists() or _es_parcial_ytdlp(archivo):
                return True

    return False


def resolver_leccion_dir(curso_slug: str, leccion_slug: str) -> Path:
    """
    Devuelve la Path real de la carpeta de la leccion, tolerando prefijos numericos.
    Para cada carpeta en curso_dir, quita el prefijo "NNN_" si existe y compara
    el resultado exactamente con leccion_slug. Asi "001_ejercicio" matchea "ejercicio"
    pero "021_primer-ejercicio" no matchea "ejercicio".
    Si no encuentra ninguna, devuelve la ruta sin prefijo (se creara al descargar).
    """
    import re as _re
    curso_dir   = CURSOS_DIR / curso_slug
    ruta_exacta = curso_dir / leccion_slug
    if ruta_exacta.exists():
        return ruta_exacta

    if curso_dir.exists():
        for carpeta in curso_dir.iterdir():
            if not carpeta.is_dir():
                continue
            # Quitarle el prefijo numerico si lo tiene y comparar exactamente
            nombre_sin_prefijo = _re.sub(r"^\d{2,}_", "", carpeta.name)
            if nombre_sin_prefijo == leccion_slug:
                return carpeta

    return ruta_exacta


def _marcar_completa(centinela: Path, url: str):
    """Crea el archivo centinela que indica que la leccion se descargo completamente."""
    from datetime import datetime
    centinela.write_text(
        f"descarga_completa\n"
        f"fecha : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"url   : {url}\n",
        encoding="utf-8"
    )


def procesar_leccion(session: requests.Session, url: str) -> bool:
    """
    Devuelve True si la lección fue procesada (nueva o video completado),
    False si ya estaba completamente descargada.
    """
    curso_slug, leccion_slug, nombre_video = segmentos_url(url)
    leccion_dir = resolver_leccion_dir(curso_slug, leccion_slug)

    # ── Chequeo previo: ¿ya está descargada? ──────────────────────────────────
    centinela = leccion_dir / "_descarga_completa.txt"
    if centinela.exists():
        log(f"\n{'─'*60}")
        log(f"[ya descargada] {leccion_slug}  ({url})")
        log(f"  → Saltando. Borrá la carpeta si querés volver a descargarla:")
        log(f"     {leccion_dir}")
        return False

    # No hay centinela — puede ser lección nueva o descarga incompleta
    if (leccion_dir / "index.html").exists():
        log(f"\n{'─'*60}")
        log(f"[descarga incompleta] {leccion_slug}  ({url})")
        log(f"  → Falta el centinela _descarga_completa.txt. Reintentando...")
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
        _marcar_completa(centinela, url)
        return True

    log(f"\n{'─'*60}")
    log(f"URL     : {url}")
    log(f"Curso   : {curso_slug}")
    log(f"Lección : {leccion_slug}")
    log(f"Carpeta : {leccion_dir}")

    soup, html_raw = procesar_html_y_adjuntos(session, url, leccion_dir)
    videos_descargados = descargar_video(soup, html_raw, url, curso_slug, nombre_video)
    reescribir_videos_en_html(leccion_dir, videos_descargados)
    _marcar_completa(centinela, url)
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

    if not verificar_login(session, urls[0]):
        log(f"\n{'═'*60}")
        log(f"  *** LOGIN FALLIDO ***")
        log(f"  Las cookies no son válidas o la sesión expiró.")
        log(f"  Exportá las cookies nuevamente desde el navegador y reemplazá cookies.txt.")
        log(f"  No se descargó nada.")
        log(f"{'═'*60}")
        close_log()
        return

    fallidas    = []  # (num, url, mensaje_error)
    ya_bajas    = []  # urls que ya estaban descargadas
    sin_acceso  = []  # urls a las que el servidor no nos dejó entrar

    for i, url in enumerate(urls):
        try:
            procesada = procesar_leccion(session, url)
            if not procesada:
                ya_bajas.append(url)
        except SinAccesoError as e:
            log(f"\n  [SIN ACCESO — lección {i+1}/{len(urls)}] {url}")
            log(f"  → {e}")
            log(f"  Continuando con la siguiente lección...")
            sin_acceso.append((i + 1, url, str(e)))
        except Exception as e:
            msg = str(e)
            log(f"\n  [ERROR inesperado — lección {i+1}/{len(urls)}] {url}")
            log(f"  → {msg}")
            fallidas.append((i + 1, url, msg))
            log(f"  Continuando con la siguiente lección...")

        if i < len(urls) - 1:
            time.sleep(DELAY)

    # ── Resumen final ──────────────────────────────────────────────────────────
    nuevas = len(urls) - len(fallidas) - len(ya_bajas) - len(sin_acceso)
    log(f"\n{'═'*60}")
    log(f"  Nuevas descargadas : {nuevas}/{len(urls)}")
    if ya_bajas:
        log(f"  Ya descargadas     : {len(ya_bajas)} (saltadas)")
    if sin_acceso:
        log(f"\n  ┌─ SIN ACCESO ({len(sin_acceso)} lección/es) ──────────────────────")
        for num, u, err in sin_acceso:
            log(f"  │  #{num}: {u}")
            log(f"  │       → {err}")
        log(f"  └─ No se crearon carpetas para estas lecciones.")
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

    log(f"  Programa en: {SCRIPT_DIR}")
    log(f"  Cursos en  : {CURSOS_DIR}")
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