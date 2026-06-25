import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote
import re
import subprocess
import time
from datetime import datetime
import glob


class SinAccesoError(Exception):
    """Se lanza cuando el servidor redirige a otra página (lección sin acceso)."""

# ── Configuración ──────────────────────────────────────────────────────────────
# DESTINO = r"C:\cursos_descargados"
DESTINO = r"D:\nacho\cursos_descargados"


SCRIPT_DIR = Path(__file__).parent
CURSOS_DIR = Path(DESTINO) if DESTINO.strip() else SCRIPT_DIR

COOKIES_FILE = SCRIPT_DIR / "cookies.txt"

# ── ARCHIVOS DE LINKS (hardcodeados) ────────────────────────────────────────
# Comenta/descomenta las líneas para elegir qué archivos procesar.
LINKS_FILES = [

    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_cc1_e_contrapunto_por_especies.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_2022_intensivo_armonia_aplicada_a_la_guitarra_2.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_armonia_aplicada_a_la_guitarra_1_guitarra_funcional.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_armonia_modal_aplicada_a_la_composicion.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_armonia_modal_que_es_y_como_usarla_en_tus_composiciones_06_2.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_armonia_moderna_1_las_bases.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_armonia_moderna_2_de_la_armonia_modal_al_cromatismo_funcional_05_21.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_audioperceptiva_i.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_c1c_voz_y_cuerpo.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_cc_armonia_aplicada_al_piano.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_cc0_a_sistema_de_estudio_y_organizacion.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_ciclo_0_primeros_pasos_en_la_composicion_musical_v3_0.txt"),
    
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_ciclo_2_ampliando_el_lenguaje.txt"),
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_de_la_teoria_al_diapason_entendiendo_la_guitarra_09_25.txt"),
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_experimentos_creativos.txt"),
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_introduccion_a_la_produccion_musical.txt"),
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_lecto_escritura_musical_i.txt"),
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_musescore.txt"),
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_s_como_analizar_una_cancion.txt"),
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_s_composicion_y_escritura_para_bateria.txt"),
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_s_crear_musica_con_conceptos_simples_02_25.txt"),

    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_ciclo_1_fundamentos_del_oficio_v3_0.txt"),
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_seminario_el_fagot_historia_posibilidades_y_nuevas_perspectivas.txt"),
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_seminario_introduccion_a_la_armonia_del_jazz_y_sus_ramificaciones.txt"),
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_seminario_introduccion_al_arreglo_musical.txt"),
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_seminario_partitura.txt"),
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_seminario_planificacion_en_una_pieza_musical.txt"),
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_seminario_rock_estilo_composicion_y_arreglo.txt"),
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_teoria_musical_basica_en_50_lecciones.txt"),
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_teoria_musical_basica_en_capsulas.txt"),
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_termina_tus_canciones_02_26.txt"),

]

LOG_FILE = SCRIPT_DIR / "log.txt"
FALLIDAS_FILE = SCRIPT_DIR / "fallidas.txt"
DELAY = 2
MAX_INTENTOS_VIDEO = 3
# VIDEO_CALIDAD = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best"
VIDEO_CALIDAD = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]/best"
# ── Patrones de YouTube ──────────────────────────────────────────────────────
YOUTUBE_PATTERNS = [
    r'youtube\.com/embed/([A-Za-z0-9_-]{11})',
    r'youtube\.com/watch\?v=([A-Za-z0-9_-]{11})',
    r'youtu\.be/([A-Za-z0-9_-]{11})',
    r'youtube\.com/v/([A-Za-z0-9_-]{11})',
]

VIDEO_IFRAME_DOMINIOS = (
    "vimeo.com", "mediadelivery.net", "iframe.mediadelivery.net", "bunnycdn.com",
    "b-cdn.net", "wistia.com", "fast.wistia.net", "loom.com", "kaltura.com",
    "sproutvideo.com", "vidyard.com", "dailymotion.com",
    "jwplatform.com", "jwplayer.com", "brightcove.net", "brightcove.com",
    "api.video",
)
# ──────────────────────────────────────────────────────────────────────────────

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


def guardar_fallidas(fallidas: list):
    if not fallidas:
        if FALLIDAS_FILE.exists():
            FALLIDAS_FILE.unlink()
        return
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lineas = [f"# fallidas.txt — generado el {timestamp}", f"# {len(fallidas)} URL(s) fallaron.", ""]
    for num, url, error in fallidas:
        lineas.append(f"# Error en lección #{num}: {error}")
        lineas.append(url)
        lineas.append("")
    FALLIDAS_FILE.write_text("\n".join(lineas), encoding="utf-8")
    log(f"\n  [fallidas] Registro guardado en {FALLIDAS_FILE.name}")


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
    parsed = urlparse(url_prueba)
    url_home = f"{parsed.scheme}://{parsed.netloc}/"
    log(f"\n  [login] Verificando sesión en: {url_home}")
    try:
        r = session.get(url_home, timeout=30, allow_redirects=True)
        m = re.search(r'<body[^>]+class="([^"]*)"', r.text)
        if m and "logged-in" in m.group(1).split():
            log(f"  [login] OK — sesión activa (body.logged-in detectado)")
            return True
        if 'id="loginform"' in r.text or 'name="log"' in r.text:
            log(f"  [login] FALLÓ — se encontró el formulario de login de WordPress")
            return False
        log(f"  [advertencia login] No se detectó 'logged-in' en el body.")
        return True
    except Exception as e:
        log(f"  [login] Error al verificar: {e}")
        return False


def limpiar_nombre(texto: str) -> str:
    texto = unquote(texto)
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", texto).strip("_ ")


def segmentos_url(url: str):
    partes = urlparse(url).path.strip("/").split("/")
    curso_slug = "curso"
    leccion_slug = "_".join(partes[-2:]) if len(partes) >= 2 else partes[-1]
    for i, p in enumerate(partes):
        if p in ("courses", "cursos") and i + 1 < len(partes):
            curso_slug = partes[i + 1]
            break
    nombre_video = "___".join(partes[:4]) if len(partes) >= 4 else "___".join(partes)
    nombre_video = re.sub(r'%f0%9f%93%b9-', '', nombre_video, flags=re.IGNORECASE)
    nombre_video = limpiar_nombre(nombre_video)
    return limpiar_nombre(curso_slug), limpiar_nombre(leccion_slug), nombre_video


def extraer_urls_youtube(soup: BeautifulSoup, html_raw: str) -> list[str]:
    """Extrae solo URLs de YouTube que están dentro de iframes (no texto)."""
    ids = []
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src") or iframe.get("data-src") or ""
        for pat in YOUTUBE_PATTERNS:
            m = re.search(pat, src)
            if m:
                ids.append(m.group(1))
    # Eliminamos duplicados
    vistos = set()
    urls = []
    for vid in ids:
        if vid not in vistos:
            vistos.add(vid)
            urls.append(f"https://www.youtube.com/watch?v={vid}")
    return urls


def extraer_urls_videos_embebidos(soup: BeautifulSoup, html_raw: str) -> list[str]:
    encontrados = []
    for iframe in soup.find_all("iframe"):
        src = (iframe.get("src") or iframe.get("data-src") or iframe.get("data-lazy-src") or "").strip()
        if src.startswith("//"):
            src = "https:" + src
        if any(d in src for d in VIDEO_IFRAME_DOMINIOS):
            encontrados.append(src)
    for source in soup.find_all("source"):
        src = (source.get("src") or source.get("data-src") or "").strip()
        if src.startswith("//"):
            src = "https:" + src
        if any(d in src for d in VIDEO_IFRAME_DOMINIOS) or src.startswith("http") or ".m3u8" in src:
            encontrados.append(src)
    for video in soup.find_all("video"):
        src = (video.get("src") or video.get("data-src") or "").strip()
        if src.startswith("//"):
            src = "https:" + src
        if any(d in src for d in VIDEO_IFRAME_DOMINIOS) or src.startswith("http") or ".m3u8" in src:
            encontrados.append(src)
    vistos = set()
    urls = []
    for url in encontrados:
        if url and url not in vistos:
            vistos.add(url)
            urls.append(url)
    return urls


def obtener_iframes_video_originales(soup: BeautifulSoup) -> list[dict]:
    """Extrae todos los iframes de video del HTML original y devuelve URLs únicas."""
    resultados = []
    vistos = set()
    for iframe in soup.find_all("iframe"):
        src = (iframe.get("src") or iframe.get("data-src") or iframe.get("data-lazy-src") or "").strip()
        if not src:
            continue
        if src.startswith("//"):
            src = "https:" + src

        # Detectar tipo
        tipo = None
        vid_id = None

        # Vimeo
        vimeo_match = re.search(r'vimeo\.com/(?:video/)?(\d+)', src)
        if vimeo_match:
            tipo = "vimeo"
            vid_id = vimeo_match.group(1)
        # YouTube
        else:
            for pat in YOUTUBE_PATTERNS:
                m = re.search(pat, src)
                if m:
                    tipo = "youtube"
                    vid_id = m.group(1)
                    break

        if tipo and vid_id:
            if tipo == "youtube":
                url_std = f"https://www.youtube.com/watch?v={vid_id}"
            elif tipo == "vimeo":
                url_std = f"https://vimeo.com/video/{vid_id}"
            else:
                url_std = src
        else:
            # Si no es YouTube ni Vimeo, pero está en VIDEO_IFRAME_DOMINIOS, lo guardamos tal cual
            if any(d in src for d in VIDEO_IFRAME_DOMINIOS):
                url_std = src
            else:
                continue

        if url_std not in vistos:
            vistos.add(url_std)
            resultados.append({
                "url": url_std,
                "tipo": tipo or "otro",
                "id": vid_id,
                "src_original": src
            })
    return resultados


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


def is_google_drive_url(url: str) -> bool:
    return any(domain in url for domain in ("drive.google.com", "docs.google.com"))


def registrar_drive_link(curso_slug: str, leccion_slug: str, url: str, leccion_dir: Path):
    leccion_dir.mkdir(parents=True, exist_ok=True)
    lesson_file = leccion_dir / "drive_links.txt"
    root_file = CURSOS_DIR / "drive_links.txt"
    if lesson_file.exists():
        existentes = {line.strip() for line in lesson_file.read_text(encoding="utf-8").splitlines() if line.strip()}
    else:
        existentes = set()
    if url not in existentes:
        with lesson_file.open("a", encoding="utf-8") as f:
            if lesson_file.stat().st_size == 0:
                f.write(f"# Drive links para {curso_slug} / {leccion_slug}\n")
            f.write(url + "\n")
        log(f"  [drive] link guardado en {lesson_file.relative_to(CURSOS_DIR)}")
    entry = f"{curso_slug} / {leccion_slug} : {url}"
    if root_file.exists():
        existentes_root = {line.strip() for line in root_file.read_text(encoding="utf-8").splitlines() if line.strip()}
    else:
        existentes_root = set()
    if entry not in existentes_root:
        with root_file.open("a", encoding="utf-8") as f:
            if root_file.stat().st_size == 0:
                f.write("# Drive links de cursos\n")
            f.write(entry + "\n")
        log(f"  [drive] link agregado a {root_file.name}")


def procesar_html_y_adjuntos(session: requests.Session, url: str, leccion_dir: Path):
    log(f"  Descargando HTML...")
    try:
        r = session.get(url, timeout=30, allow_redirects=True)
        log(f"  [http {r.status_code}] {url}")
        r.raise_for_status()
    except Exception as e:
        log(f"  [error al obtener HTML] {e}")
        return None, ""

    path_pedido = urlparse(url).path.rstrip("/")
    path_final = urlparse(r.url).path.rstrip("/")
    dominio_pedido = urlparse(url).netloc
    dominio_final = urlparse(r.url).netloc
    if path_final != path_pedido:
        if dominio_final != dominio_pedido:
            log(f"  [sin acceso] Redirigido a otro dominio: {r.url}")
            raise SinAccesoError(f"redirigido a otro dominio: {r.url}")
        if path_pedido.startswith(path_final + "/") or path_final in ("/", ""):
            log(f"  [sin acceso] Redirigido a página superior: {r.url}")
            raise SinAccesoError(f"redirigido a página superior: {r.url}")
        log(f"  [advertencia] URL redirigida a {r.url} — procesando igual")

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

    selectores = [("a[href]", "href"), ("audio[src]", "src"), ("source[src]", "src"), ("img[src]", "src")]
    for selector, atributo in selectores:
        tags = soup.select(selector)
        log(f"  [selector '{selector}'] {len(tags)} tags encontrados")
        for tag in tags:
            href = tag.get(atributo, "").strip()
            if not href or href.startswith(("javascript:", "mailto:", "#")):
                continue
            href_abs = urljoin(url, href)
            if is_google_drive_url(href_abs):
                registrar_drive_link(curso_slug=leccion_dir.parent.name, leccion_slug=leccion_dir.name, url=href_abs, leccion_dir=leccion_dir)
                continue
            sufijo = Path(urlparse(href_abs).path).suffix.lower()
            if sufijo not in extensiones_descargables:
                continue
            nombre_archivo = Path(urlparse(href_abs).path).name
            destino = materiales / nombre_archivo
            if descargar_archivo(session, href_abs, destino):
                tag[atributo] = f"materiales/{nombre_archivo}"

    html_path = leccion_dir / "index.html"
    html_path.write_text(soup.prettify(), encoding="utf-8")
    log(f"  [html guardado] {html_path.name}")
    return soup, html_raw


def _es_parcial_ytdlp(path: Path) -> bool:
    return bool(re.search(r'(?:\.f\d+(?:\.[^.]+)?$|\.fhls-[^/\\]+(?:\.[^.]+)?$|\.part$|-Frag\d+(?:\.[^.]+)?$)', path.name)) or path.suffix == ".part"


def _limpiar_parciales(output_template: str):
    patron = output_template.replace("%(ext)s", "*")
    for ruta in glob.glob(patron) + glob.glob(patron + ".part"):
        p = Path(ruta)
        if _es_parcial_ytdlp(p):
            try:
                p.unlink()
                log(f"  [limpieza] borrado parcial: {p.name}")
            except Exception:
                pass


def _correr_ytdlp(url_video: str, output_template: str, label: str, allow_playlist: bool = True, referer: str = None) -> bool:
    for intento in range(1, MAX_INTENTOS_VIDEO + 1):
        if intento > 1:
            log(f"  [video] reintentando ({intento}/{MAX_INTENTOS_VIDEO}) → {label}")
            time.sleep(5)
        else:
            log(f"  [video] descargando {label} → {url_video}")
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
                log(f"  [video ok] {label}")
                return True
            else:
                log(f"  [error video] código {result.returncode} — intento {intento}/{MAX_INTENTOS_VIDEO}")
                log(f"  [yt-dlp stderr]\n{result.stderr[-800:]}")
                if "Unsupported URL" in result.stderr:
                    log(f"  [sin video] La lección no tiene video descargable — se considera completa")
                    return None
                if "not found" in result.stderr.lower():
                    break
        except FileNotFoundError:
            log("  [error] yt-dlp no encontrado. Instalalo con: pip install yt-dlp")
            return False
        except Exception as e:
            log(f"  [error inesperado en video] {e}")
    log(f"  [video fallido] No se pudo descargar después de {MAX_INTENTOS_VIDEO} intentos: {label}")
    return False


# ===== DESCARGA DE VIDEOS MODIFICADA: SIEMPRE PROCESA YOUTUBE =====

def descargar_video(soup, html_raw: str, url_leccion: str, curso_slug: str, nombre_video: str) -> list:
    videos_dir = CURSOS_DIR / curso_slug / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    descargados = []

    # 1. Videos embebidos (Vimeo, Bunny, etc.) – estos son los principales
    urls_embebidas = extraer_urls_videos_embebidos(soup, html_raw) if soup is not None else []
    if urls_embebidas:
        log(f"  [video embebido] {len(urls_embebidas)} video(s) encontrado(s) en el HTML")
        for idx, video_url in enumerate(urls_embebidas):
            sufijo = f"_v{idx+1}" if len(urls_embebidas) > 1 else ""
            plantilla = str(videos_dir / f"{nombre_video}{sufijo}.%(ext)s")
            existentes = [p for p in videos_dir.glob(f"{nombre_video}{sufijo}.*") if not _es_parcial_ytdlp(p)]
            if existentes:
                log(f"  [video ya existe] {existentes[0].name}")
                descargados.append((existentes[0], video_url))
                continue
            _limpiar_parciales(plantilla)
            resultado = _correr_ytdlp(video_url, plantilla, f"video embebido #{idx+1}", allow_playlist=False, referer=url_leccion)
            if resultado is False:
                continue
            if resultado is None:
                continue
            encontrados = [p for p in videos_dir.glob(f"{nombre_video}{sufijo}.*") if not _es_parcial_ytdlp(p)]
            if encontrados:
                descargados.append((encontrados[0], video_url))

    # 2. YouTube – SIEMPRE se procesa, independientemente de si hay embebidos o no
    yt_urls = extraer_urls_youtube(soup, html_raw) if soup is not None else []
    if yt_urls:
        log(f"  [youtube] {len(yt_urls)} video(s) encontrado(s) en iframes")
        for idx, yt_url in enumerate(yt_urls):
            # Usamos sufijo _yt1, _yt2, ... para diferenciar de los embebidos
            sufijo = f"_yt{idx+1}"
            plantilla = str(videos_dir / f"{nombre_video}{sufijo}.%(ext)s")
            existentes = [p for p in videos_dir.glob(f"{nombre_video}{sufijo}.*") if not _es_parcial_ytdlp(p)]
            if existentes:
                log(f"  [video ya existe] {existentes[0].name}")
                descargados.append((existentes[0], yt_url))
                continue
            _limpiar_parciales(plantilla)
            resultado = _correr_ytdlp(yt_url, plantilla, f"YouTube #{idx+1}")
            if resultado is False:
                continue
            if resultado is None:
                continue
            encontrados = [p for p in videos_dir.glob(f"{nombre_video}{sufijo}.*") if not _es_parcial_ytdlp(p)]
            if encontrados:
                descargados.append((encontrados[0], yt_url))

    # 3. Fallback a URL de lección (solo si no se descargó nada)
    if not descargados:
        log(f"  [video] Sin YouTube ni embebidos detectados — intentando URL de lección directamente")
        existentes = sorted([p for p in videos_dir.glob(f"{nombre_video}*.*") if not _es_parcial_ytdlp(p)])
        if existentes:
            log(f"  [video ya existe] {existentes[0].name}")
            return [(p, url_leccion) for p in existentes]

        plantilla = str(videos_dir / f"{nombre_video}-%(playlist_index)03d.%(ext)s")
        resultado = _correr_ytdlp(url_leccion, plantilla, "lección completa")
        if resultado is False:
            return None
        if resultado is None:
            return []
        if resultado:
            encontrados = sorted([p for p in videos_dir.glob(f"{nombre_video}*.*") if not _es_parcial_ytdlp(p)])
            for encontrado in encontrados:
                descargados.append((encontrado, url_leccion))

    if not descargados:
        return None  # No se descargó ningún video

    return descargados


def _ext_mime(ext: str) -> str:
    return {
        ".mp4": "video/mp4", ".webm": "video/webm",
        ".mkv": "video/x-matroska", ".mov": "video/quicktime", ".m4v": "video/mp4",
    }.get(ext.lower(), "video/mp4")


def _video_tag(ruta_relativa: str, ext: str) -> str:
    mime = _ext_mime(ext)
    return (f'<video controls style="width:100%;max-width:960px;display:block;margin:1em 0" preload="auto">'
            f'<source src="{ruta_relativa}" type="{mime}">'
            f'Tu navegador no soporta video HTML5.</video>')


# ===== NUEVA FUNCIÓN PARA NORMALIZAR URLS =====
def _normalizar_url(url: str) -> str:
    """Elimina query y fragment de una URL para comparación."""
    parsed = urlparse(url)
    return parsed.scheme + "://" + parsed.netloc + parsed.path


# ===== FUNCIÓN PARA CONTAR IFRAMES REMOTOS =====
def contar_iframes_video_remotos(html_path: Path) -> int:
    """Cuenta cuántos iframes de video (dominios conocidos) hay en el HTML."""
    try:
        soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "html.parser")
        count = 0
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src") or iframe.get("data-src") or ""
            if src.startswith("//"):
                src = "https:" + src
            if any(d in src for d in VIDEO_IFRAME_DOMINIOS):
                count += 1
        return count
    except Exception:
        return 0


# ===== FUNCIÓN REESCRIBIR VIDEOS MODIFICADA =====
def reescribir_videos_en_html(leccion_dir: Path, videos_descargados: list, soup: BeautifulSoup = None):
    """
    Reescribe el HTML para reemplazar iframes de video por etiquetas <video> locales.
    Si se proporciona soup, se usa ese soup (debe provenir del HTML original).
    Si no, se carga desde index.html (pero se recomienda pasar siempre soup).
    """
    if not videos_descargados:
        return
    html_path = leccion_dir / "index.html"
    if soup is None:
        # Si no se proporciona soup, cargar desde index.html (fallback)
        if not html_path.exists():
            return
        soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    else:
        # Trabajamos sobre una copia del soup para no modificar el original si no queremos
        soup = BeautifulSoup(str(soup), "html.parser")  # copia profunda

    modificado = False

    for archivo_local, url_fuente in videos_descargados:
        ruta_rel = f"../videos/{archivo_local.name}"
        ext = archivo_local.suffix

        # Extraer vid_id de YouTube
        vid_id = None
        for pat in YOUTUBE_PATTERNS:
            m = re.search(pat, url_fuente)
            if m:
                vid_id = m.group(1)
                break

        # Extraer ID de Vimeo (número)
        vimeo_id = None
        vimeo_match = re.search(r'vimeo\.com/(?:video/)?(\d+)', url_fuente)
        if vimeo_match:
            vimeo_id = vimeo_match.group(1)

        if vid_id:
            # Reemplazar cualquier iframe que contenga este vid_id
            for iframe in soup.find_all("iframe"):
                src = iframe.get("src") or iframe.get("data-src") or ""
                if vid_id in src:
                    iframe.replace_with(BeautifulSoup(_video_tag(ruta_rel, ext), "html.parser"))
                    log(f"  [html] iframe YouTube reemplazado → {ruta_rel}")
                    modificado = True
        elif vimeo_id:
            # Reemplazar iframes de Vimeo por el ID
            for iframe in soup.find_all("iframe"):
                src = iframe.get("src") or iframe.get("data-src") or ""
                if f"vimeo.com/video/{vimeo_id}" in src or f"player.vimeo.com/video/{vimeo_id}" in src:
                    iframe.replace_with(BeautifulSoup(_video_tag(ruta_rel, ext), "html.parser"))
                    log(f"  [html] iframe Vimeo reemplazado → {ruta_rel}")
                    modificado = True
        else:
            # Buscar por coincidencia de URL en iframes (para otros servicios)
            url_normalizada = _normalizar_url(url_fuente)
            for iframe in soup.find_all("iframe"):
                src = iframe.get("src") or iframe.get("data-src") or ""
                if src and _normalizar_url(src) == url_normalizada:
                    iframe.replace_with(BeautifulSoup(_video_tag(ruta_rel, ext), "html.parser"))
                    log(f"  [html] iframe de video reemplazado por coincidencia normalizada → {ruta_rel}")
                    modificado = True
                    break  # Una vez reemplazado, salir del bucle para no reemplazar más de una vez

        # Reemplazar <video> y <source> remotos
        for video_tag in soup.find_all("video"):
            src_video = video_tag.get("src") or ""
            sources = video_tag.find_all("source")
            es_remoto = (src_video.startswith("http") or src_video.startswith("blob:") or
                         any((s.get("src") or "").startswith("http") or
                             any(d in (s.get("src") or "") for d in ("b-cdn.net", "mediadelivery.net")) or
                             (s.get("type") or "") == "application/vnd.apple.mpegURL" for s in sources))
            if es_remoto:
                video_tag.replace_with(BeautifulSoup(_video_tag(ruta_rel, ext), "html.parser"))
                log(f"  [html] <video> remoto reemplazado → {ruta_rel}")
                modificado = True

        for tag in soup.find_all("source"):
            src = tag.get("src") or ""
            if src.startswith("http") or ".m3u8" in src or any(d in src for d in ("b-cdn.net", "mediadelivery.net")):
                parent = tag.parent
                if parent and parent.name == "video":
                    parent.replace_with(BeautifulSoup(_video_tag(ruta_rel, ext), "html.parser"))
                    log(f"  [html] <video> HLS remoto reemplazado → {ruta_rel}")
                    modificado = True
                else:
                    tag["src"] = ruta_rel
                    log(f"  [html] <source> remoto reemplazado → {ruta_rel}")
                    modificado = True

    if modificado:
        html_path.write_text(soup.prettify(), encoding="utf-8")
        log(f"  [html] index.html actualizado con videos locales")
    else:
        log(f"  [html] No se encontraron iframes de video para reemplazar")


def _video_pendiente(leccion_dir: Path, curso_slug: str) -> bool:
    html_path = leccion_dir / "index.html"
    if not html_path.exists():
        return False
    # Verificar si hay iframes remotos
    if contar_iframes_video_remotos(html_path) > 0:
        return True
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src") or iframe.get("data-src") or ""
        if "youtube.com" in src or "youtu.be" in src or any(d in src for d in VIDEO_IFRAME_DOMINIOS):
            return True
    videos_dir = CURSOS_DIR / curso_slug / "videos"
    for tag in soup.find_all(["source", "video"]):
        src = tag.get("src") or ""
        if src.startswith("../videos/"):
            nombre_archivo = src[len("../videos/"):]
            archivo = videos_dir / nombre_archivo
            if not archivo.exists() or _es_parcial_ytdlp(archivo):
                return True
    return False


def resolver_leccion_dir(curso_slug: str, leccion_slug: str) -> Path:
    import re as _re
    curso_dir = CURSOS_DIR / curso_slug
    ruta_exacta = curso_dir / leccion_slug
    if ruta_exacta.exists():
        return ruta_exacta
    if curso_dir.exists():
        def _normalizar(s: str) -> str:
            s = s.lower()
            s = _re.sub(r'[\s_\-\.]+', '-', s)
            return s.strip('-')
        for carpeta in curso_dir.iterdir():
            if not carpeta.is_dir():
                continue
            nombre = carpeta.name
            nombre_sin_prefijo = _re.sub(r'^[0-9]+(?:[_\-\. ]+)?', '', nombre)
            if nombre_sin_prefijo == leccion_slug:
                return carpeta
            if _normalizar(nombre_sin_prefijo) == _normalizar(leccion_slug):
                return carpeta
    return ruta_exacta


def _marcar_completa(centinela: Path, url: str):
    centinela.write_text(f"descarga_completa\nfecha : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nurl   : {url}\n", encoding="utf-8")


# ===== FUNCIONES DE REPARACIÓN =====

def obtener_sufijo(nombre: str) -> str | None:
    """Devuelve '_vN' si existe, o None."""
    m = re.search(r'(_v\d+)(?=\.mp4$)', nombre)
    return m.group(1) if m else None


def reparar_videos(leccion_dir: Path, videos_dir: Path, soup: BeautifulSoup, html_raw: str, url_leccion: str, curso_slug: str, nombre_video: str) -> list:
    """
    Analiza el estado actual de los videos locales y los iframes originales,
    y toma acciones para dejar todo correcto:
    - Si hay un solo video y un solo archivo sin sufijo -> OK
    - Si hay múltiples videos y un solo archivo sin sufijo -> eliminar y descargar todos
    - Si hay archivos con sufijos pero faltan algunos -> descargar faltantes
    - Si hay archivos con sufijos sobrantes -> eliminar
    - Si hay mezcla de con/sin sufijo (y múltiples videos) -> eliminar todos y descargar de nuevo
    Retorna la lista de (archivo_local, url_origen) para reescribir el HTML.
    """
    # Obtener iframes originales (URLs únicas)
    iframes_originales = obtener_iframes_video_originales(soup)
    urls_unicas = list(set([iframe['url'] for iframe in iframes_originales]))
    num_urls = len(urls_unicas)

    if num_urls == 0:
        log(f"  [reparación] No hay videos en el HTML original.")
        return []

    # Obtener archivos locales existentes (solo .mp4)
    archivos_locales = [p for p in videos_dir.glob(f"{nombre_video}*.mp4") if not _es_parcial_ytdlp(p)]
    con_sufijo = []
    sin_sufijo = []
    for p in archivos_locales:
        suf = obtener_sufijo(p.name)
        if suf:
            con_sufijo.append((p, suf))
        else:
            sin_sufijo.append(p)

    log(f"  [reparación] URLs únicas: {num_urls}, archivos locales: {len(archivos_locales)} (con sufijo: {len(con_sufijo)}, sin sufijo: {len(sin_sufijo)})")

    # ---- Caso 1: Un solo video y un solo archivo sin sufijo ----
    if num_urls == 1 and len(sin_sufijo) == 1 and len(con_sufijo) == 0:
        log(f"  [reparación] Caso OK: un video y un archivo sin sufijo.")
        archivo = sin_sufijo[0]
        return [(archivo, urls_unicas[0])]

    # ---- Caso 2: Múltiples videos y un solo archivo sin sufijo ----
    if num_urls > 1 and len(sin_sufijo) == 1 and len(con_sufijo) == 0:
        log(f"  [reparación] Eliminando archivo sin sufijo y descargando todos los videos.")
        sin_sufijo[0].unlink()
        videos_descargados = descargar_video(soup, html_raw, url_leccion, curso_slug, nombre_video)
        if videos_descargados is None:
            return []
        return videos_descargados

    # ---- Caso 3: Archivos con sufijos ----
    if con_sufijo:
        numeros_existentes = set()
        for p, suf in con_sufijo:
            num = int(suf[2:])  # _v1 -> 1
            numeros_existentes.add(num)
        numeros_esperados = set(range(1, num_urls + 1))

        faltantes = numeros_esperados - numeros_existentes
        sobrantes = numeros_existentes - numeros_esperados

        # Eliminar sobrantes
        for p, suf in con_sufijo:
            num = int(suf[2:])
            if num in sobrantes:
                p.unlink()
                log(f"  [reparación] Eliminado sobrante: {p.name}")

        # Si hay faltantes, descargar esos videos específicos
        if faltantes:
            log(f"  [reparación] Faltan videos con sufijos: {', '.join(f'_v{n}' for n in sorted(faltantes))}")
            for n in faltantes:
                idx = n - 1
                if idx < len(urls_unicas):
                    url_faltante = urls_unicas[idx]
                    sufijo = f"_v{n}"
                    plantilla = str(videos_dir / f"{nombre_video}{sufijo}.%(ext)s")
                    if any(p for p in videos_dir.glob(f"{nombre_video}{sufijo}.*") if not _es_parcial_ytdlp(p)):
                        log(f"  [reparación] {sufijo} ya existe, saltando.")
                        continue
                    _limpiar_parciales(plantilla)
                    resultado = _correr_ytdlp(url_faltante, plantilla, f"faltante {sufijo}", allow_playlist=False, referer=url_leccion)
                    if resultado is True:
                        encontrados = [p for p in videos_dir.glob(f"{nombre_video}{sufijo}.*") if not _es_parcial_ytdlp(p)]
                        if encontrados:
                            # Añadir a la lista de descargados
                            pass
                    # Si falla, se registrará en el log.

        # Reconstruir la lista de archivos descargados
        videos_descargados = descargar_video(soup, html_raw, url_leccion, curso_slug, nombre_video)
        if videos_descargados is None:
            return []
        return videos_descargados

    # ---- Caso 4: Mezcla o múltiples sin sufijo ----
    if (len(sin_sufijo) > 0 and num_urls > 1) or (con_sufijo and sin_sufijo and num_urls > 1):
        log(f"  [reparación] Mezcla de archivos (con/sin sufijo) o múltiples sin sufijo. Eliminando todos y descargando de nuevo.")
        for p in archivos_locales:
            p.unlink()
        videos_descargados = descargar_video(soup, html_raw, url_leccion, curso_slug, nombre_video)
        if videos_descargados is None:
            return []
        return videos_descargados

    # ---- Fallback ----
    log(f"  [reparación] Caso no contemplado, descargando todos los videos.")
    videos_descargados = descargar_video(soup, html_raw, url_leccion, curso_slug, nombre_video)
    if videos_descargados is None:
        return []
    return videos_descargados


def limpiar_videos_huerfanos(leccion_dir: Path, videos_dir: Path, prefijo: str):
    """
    Elimina archivos de video que existen en videos_dir con el prefijo dado,
    pero que NO están referenciados en el HTML final.
    """
    html_path = leccion_dir / "index.html"
    if not html_path.exists():
        return

    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
    except Exception:
        return

    referencias = set(re.findall(r'<source src="\.\./videos/([^"]+)"', html_content))
    referencias.update(re.findall(r'<video[^>]+src="\.\./videos/([^"]+)"', html_content))

    archivos_existentes = [p for p in videos_dir.glob(f"{prefijo}*.mp4") if not _es_parcial_ytdlp(p)]
    eliminados = 0

    for archivo in archivos_existentes:
        if archivo.name not in referencias:
            try:
                archivo.unlink()
                log(f"  [limpieza] Archivo huérfano eliminado: {archivo.name}")
                eliminados += 1
            except Exception as e:
                log(f"  [limpieza] Error al eliminar {archivo.name}: {e}")

    if eliminados:
        log(f"  [limpieza] Se eliminaron {eliminados} archivos huérfanos.")


# ===== FUNCIÓN PRINCIPAL DE PROCESAMIENTO CON REPARACIÓN =====

def procesar_leccion(session: requests.Session, url: str) -> bool:
    curso_slug, leccion_slug, nombre_video = segmentos_url(url)
    leccion_dir = resolver_leccion_dir(curso_slug, leccion_slug)
    centinela = leccion_dir / "_descarga_completa.txt"
    videos_dir = CURSOS_DIR / curso_slug / "videos"

    # Función interna para el flujo de descarga/reparación
    def _reprocesar(soup, html_raw):
        # REPARAR VIDEOS
        videos_descargados = reparar_videos(leccion_dir, videos_dir, soup, html_raw, url, curso_slug, nombre_video)

        # Si no hay videos descargados y no hay videos en el HTML, marcar como completa sin video
        if videos_descargados is None:
            # No se pudo descargar ningún video (error)
            return False
        if not videos_descargados:
            # No hay videos en el HTML
            _marcar_completa(centinela, url)
            return True

        # Reescribir HTML con los videos descargados (usamos el soup original)
        reescribir_videos_en_html(leccion_dir, videos_descargados, soup)

        # Limpiar huérfanos
        limpiar_videos_huerfanos(leccion_dir, videos_dir, nombre_video)

        # Verificar que no queden iframes remotos
        iframes_restantes = contar_iframes_video_remotos(leccion_dir / "index.html")
        if iframes_restantes > 0:
            log(f"  [advertencia] Quedan {iframes_restantes} iframes remotos sin reemplazar.")
            # NO MARCAR COMO COMPLETA
            return False

        # Marcar completa
        _marcar_completa(centinela, url)
        return True

    # -------- FLUJO PRINCIPAL --------

    # Caso 1: Ya está completa y no hay pendientes
    if centinela.exists() and not _video_pendiente(leccion_dir, curso_slug):
        log(f"\n{'─'*60}")
        log(f"[ya descargada] {leccion_slug}  ({url})")
        log(f"  → Saltando. Borrá la carpeta si querés volver a descargarla:")
        log(f"     {leccion_dir}")
        return False

    # Caso 2: Centinela existe pero hay pendientes (reprocesar)
    if centinela.exists():
        log(f"\n{'─'*60}")
        log(f"[reprocesando incompleto] {leccion_slug}  ({url})")
        log(f"  → Centinela encontrado pero hay videos pendientes o falta index.html. Reintentando...")
        raw_path = leccion_dir / "index_raw.html"
        if raw_path.exists():
            html_raw = raw_path.read_text(encoding="utf-8")
            soup = BeautifulSoup(html_raw, "html.parser")
            log(f"  → Usando index_raw.html guardado (sin re-descargar el HTML)")
        else:
            log(f"  → index_raw.html no encontrado, re-descargando el HTML...")
            soup, html_raw = procesar_html_y_adjuntos(session, url, leccion_dir)
        if soup is None:
            raise Exception("No se pudo descargar el HTML de la lección")
        return _reprocesar(soup, html_raw)

    # Caso 3: No hay centinela pero existe index.html (descarga incompleta)
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
        if soup is None:
            raise Exception("No se pudo descargar el HTML de la lección")
        return _reprocesar(soup, html_raw)

    # Caso 4: Lección nueva (sin index.html ni centinela)
    log(f"\n{'─'*60}")
    log(f"URL     : {url}")
    log(f"Curso   : {curso_slug}")
    log(f"Lección : {leccion_slug}")
    log(f"Carpeta : {leccion_dir}")

    soup, html_raw = procesar_html_y_adjuntos(session, url, leccion_dir)
    if soup is None:
        raise Exception("No se pudo descargar el HTML de la lección")
    return _reprocesar(soup, html_raw)


# ===== RESTO DEL CÓDIGO (procesar_archivo_links, main) =====

def procesar_archivo_links(links_file: Path) -> dict:
    """
    Procesa un único archivo de links y devuelve estadísticas.
    """
    log(f"\n{'─'*60}")
    log(f"📁 Procesando: {links_file.name}")
    log(f"{'─'*60}")

    if not links_file.exists():
        log(f"  ❌ Archivo no encontrado: {links_file}")
        return {"error": True, "archivo": links_file}

    urls = [
        line.strip()
        for line in links_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    if not urls:
        log("  ⚠️ El archivo está vacío.")
        return {"error": True, "archivo": links_file, "vacío": True}

    log(f"  📄 Lecciones encontradas: {len(urls)}")

    cookies = cargar_cookies(COOKIES_FILE)
    session = requests.Session()
    session.cookies.update(cookies)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    })

    if not verificar_login(session, urls[0]):
        log(f"  ❌ Login fallido. Revisá las cookies.")
        return {"error": True, "archivo": links_file, "login_fail": True}

    fallidas = []
    ya_bajas = []
    sin_acceso = []

    for i, url in enumerate(urls, start=1):
        try:
            log(f"\n  [{i}/{len(urls)}] Procesando: {url}")
            procesada = procesar_leccion(session, url)
            if not procesada:
                ya_bajas.append(url)
        except SinAccesoError as e:
            log(f"\n  [SIN ACCESO — lección {i}/{len(urls)}] {url}")
            log(f"  → {e}")
            sin_acceso.append((i, url, str(e)))
        except Exception as e:
            msg = str(e)
            log(f"\n  [ERROR inesperado — lección {i}/{len(urls)}] {url}")
            log(f"  → {msg}")
            fallidas.append((i, url, msg))

        if i < len(urls):
            time.sleep(DELAY)

    nuevas = len(urls) - len(fallidas) - len(ya_bajas) - len(sin_acceso)

    log(f"\n  {'─'*40}")
    log(f"  Resumen de {links_file.name}:")
    log(f"    Nuevas descargadas : {nuevas}/{len(urls)}")
    if ya_bajas:
        log(f"    Ya descargadas     : {len(ya_bajas)} (saltadas)")
    if sin_acceso:
        log(f"    Sin acceso         : {len(sin_acceso)}")
    if fallidas:
        log(f"    Con error          : {len(fallidas)}")

    return {
        "error": False,
        "archivo": links_file,
        "total": len(urls),
        "nuevas": nuevas,
        "ya_bajas": ya_bajas,
        "sin_acceso": sin_acceso,
        "fallidas": fallidas,
    }


def main():
    init_log()
    log(f"Log guardado en: {LOG_FILE}")

    resultados = []
    for links_file in LINKS_FILES:
        if not links_file:
            continue
        resultado = procesar_archivo_links(links_file)
        resultados.append(resultado)

    log(f"\n{'═'*60}")
    log(f"  📊 RESUMEN GLOBAL")
    log(f"{'═'*60}")

    total_archivos = 0
    total_lecciones = 0
    total_nuevas = 0
    total_ya_bajas = 0
    total_sin_acceso = 0
    total_fallidas = 0
    todas_fallidas = []

    for r in resultados:
        if r.get("error"):
            if r.get("login_fail"):
                log(f"  ❌ Login fallido en {r['archivo'].name}")
            elif r.get("vacío"):
                log(f"  ⚠️ {r['archivo'].name} está vacío")
            else:
                log(f"  ❌ Error en {r['archivo'].name}")
            continue

        log(f"\n  📁 {r['archivo'].name}")
        log(f"     Total lecciones: {r['total']}")
        log(f"     ✅ Nuevas descargadas: {r['nuevas']}")
        log(f"     ⏭️  Ya descargadas: {len(r['ya_bajas'])}")
        log(f"     🚫 Sin acceso: {len(r['sin_acceso'])}")
        log(f"     ❌ Fallidas: {len(r['fallidas'])}")

        total_archivos += 1
        total_lecciones += r['total']
        total_nuevas += r['nuevas']
        total_ya_bajas += len(r['ya_bajas'])
        total_sin_acceso += len(r['sin_acceso'])
        total_fallidas += len(r['fallidas'])
        todas_fallidas.extend(r.get('fallidas', []))

    log(f"\n{'─'*60}")
    log(f"  🌟 TOTAL GLOBAL:")
    log(f"     Archivos procesados: {total_archivos}")
    log(f"     Lecciones totales: {total_lecciones}")
    log(f"     ✅ Nuevas descargadas: {total_nuevas}")
    log(f"     ⏭️  Ya descargadas: {total_ya_bajas}")
    log(f"     🚫 Sin acceso: {total_sin_acceso}")
    log(f"     ❌ Fallidas: {total_fallidas}")
    log(f"{'═'*60}")

    guardar_fallidas(todas_fallidas)

    close_log()
    log(f"\n  Log completo en: {LOG_FILE}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        error_msg = f"\n[ERROR FATAL] {e}"
        print(error_msg)
        if _log_file:
            _log_file.write(error_msg + "\n")
            _log_file.flush()
    finally:
        # El log ya se cerró en main(), no intentamos escribir más en él
        pass