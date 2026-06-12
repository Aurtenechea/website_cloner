import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urlparse, unquote
import re
import subprocess
import time
import http.cookiejar
from datetime import datetime

# ── Configuración ──────────────────────────────────────────────────────────────
# Modificá esta ruta si usás otra carpeta, pero mantenemos la estructura original
BASE_DIR      = Path(r"C:\mis_sitios_descargados")
COOKIES_FILE  = BASE_DIR / "cookies.txt"
LINKS_FILE    = BASE_DIR / "links.txt"
LOG_FILE      = BASE_DIR / "log.txt"
DELAY         = 2
VIDEO_CALIDAD = "bv*[height<=720]+ba/b[height<=720]"
# ──────────────────────────────────────────────────────────────────────────────

_log_file = None

def log(msg: str = ""):
    print(msg)
    if _log_file:
        _log_file.write(msg + "\n")
        _log_file.flush()

def init_log():
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    global _log_file
    _log_file = open(LOG_FILE, "a", encoding="utf-8")
    log(f"\n{'═'*60}")
    log(f"   Inicio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"{'═'*60}")

def close_log():
    log(f"\n   Fin: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"{'═'*60}\n")
    if _log_file:
        _log_file.close()

# ══════════════════════════════════════════════════════════════════════════════
# 1. COOKIES (MÉTODO MANUAL)
# ══════════════════════════════════════════════════════════════════════════════

def cargar_cookies_en_sesion(session: requests.Session, path: Path):
    if not path.exists():
        log(f"   [ERROR CRÍTICO] No existe el archivo manual: {path}")
        log(f"   Por favor, exportá las cookies en formato Netscape de cresciente.net y guardalas ahí.")
        return False
    
    try:
        cj = http.cookiejar.MozillaCookieJar(str(path))
        cj.load(ignore_discard=True, ignore_expires=True)
        session.cookies.update(cj)
        
        cookies_cargadas = [c.name for c in session.cookies]
        log(f"   [cookies] Se cargaron {len(cookies_cargadas)} cookies desde cookies.txt")
        return True
    except Exception as e:
        log(f"   [error parseando cookies] {e}.")
        return False

# ══════════════════════════════════════════════════════════════════════════════
# 2. HELPERS (REPLICANDO LA LÓGICA DE POWERSHELL)
# ══════════════════════════════════════════════════════════════════════════════

def limpiar_nombre(texto: str) -> str:
    texto = unquote(texto)
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", texto).strip("_ ")

def procesar_url_estilo_powershell(url: str):
    """
    Replica exactamente el comportamiento de la Regex de tu PowerShell:
    $u -match '([^/]+)/([^/]+)/([^/]+)/([^/]+)/?$'
    """
    path = urlparse(url).path.strip("/")
    partes = path.split("/")
    
    # Si tiene menos de 4 segmentos, usamos lo que haya, si no, los últimos 4
    segmentos_interes = partes[-4:] if len(partes) >= 4 else partes
    
    # El nombre base del video combinando los 4 segmentos
    nombre_video = "___".join(segmentos_interes)
    # Removemos el emoji de cámara si existiera codificado
    nombre_video = re.sub(r'%f0%9f%93%b9-', '', nombre_video, flags=re.IGNORECASE)
    nombre_video = limpiar_nombre(nombre_video)
    
    # Para organizar en carpetas locales de forma prolija:
    # curso_slug será el segundo elemento de los 4 (ej: 'mi-curso') o 'curso' por defecto
    curso_slug = segmentos_interes[1] if len(segmentos_interes) >= 2 else "curso"
    # leccion_slug será el último elemento (ej: 'mi-leccion')
    leccion_slug = segmentos_interes[-1] if len(segmentos_interes) >= 1 else "leccion"
    
    return limpiar_nombre(curso_slug), limpiar_nombre(leccion_slug), nombre_video

# ══════════════════════════════════════════════════════════════════════════════
# 3. HTML Y ADJUNTOS
# ══════════════════════════════════════════════════════════════════════════════

def descargar_archivo(session: requests.Session, url: str, destino: Path) -> bool:
    if destino.exists():
        log(f"   [ya existe] {destino.name}")
        return True
    try:
        r = session.get(url, timeout=30, stream=True)
        r.raise_for_status()
        destino.parent.mkdir(parents=True, exist_ok=True)
        with open(destino, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        log(f"   [ok] {destino.name}")
        return True
    except Exception as e:
        log(f"   [error descargando archivo] {url} -> {e}")
        return False

def procesar_html_y_adjuntos(session: requests.Session, url: str, leccion_dir: Path):
    materiales = leccion_dir / "materiales"
    materiales.mkdir(parents=True, exist_ok=True)

    log(f"   Descargando HTML...")
    try:
        r = session.get(url, timeout=30)
        log(f"   [http {r.status_code}] {url}")
        r.raise_for_status()
    except Exception as e:
        log(f"   [error al obtener HTML] {e}")
        return

    raw_path = leccion_dir / "index_raw.html"
    raw_path.write_text(r.text, encoding="utf-8")
    
    soup = BeautifulSoup(r.text, "html.parser")
    titulo = soup.find("title")
    titulo_texto = titulo.text.strip() if titulo else "(sin título)"
    log(f"   [título página] {titulo_texto}")

    if any(k in titulo_texto.lower() for k in ["login", "iniciar", "acceso", "denied", "error"]):
        log("   [ALERTA CRÍTICA] ¡Página de Login o Error detectada! Revisá tus cookies.")

    # Descarga de adjuntos estándar
    extensiones_descargables = {
        ".pdf", ".mp3", ".wav", ".ogg", ".flac",
        ".mscz", ".mxl", ".xml", ".zip", ".rar",
        ".jpg", ".jpeg", ".png", ".gif", ".webp",
        ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    }
    selectores = [("a[href]", "href"), ("audio[src]", "src"), ("source[src]", "src"), ("img[src]", "src")]

    encontrados = 0
    for selector, atributo in selectores:
        for tag in soup.select(selector):
            href = tag.get(atributo, "").strip()
            if not href or href.startswith(("javascript:", "mailto:", "#")):
                continue

            from urllib.parse import urljoin
            href_abs = urljoin(url, href)
            sufijo = Path(urlparse(href_abs).path).suffix.lower()

            if sufijo in extensiones_descargables:
                encontrados += 1
                nombre_archivo = Path(urlparse(href_abs).path).name
                destino = materiales / nombre_archivo

                if descargar_archivo(session, href_abs, destino):
                    tag[atributo] = f"materiales/{nombre_archivo}"

    log(f"   [adjuntos procesados] {encontrados}")
    html_path = leccion_dir / "index.html"
    html_path.write_text(soup.prettify(), encoding="utf-8")

# ══════════════════════════════════════════════════════════════════════════════
# 4. DESCARGA DE VIDEO (ESTILO POWERSHELL CON COOKIES MANUALES)
# ══════════════════════════════════════════════════════════════════════════════

def descargar_video_powershell_style(url_leccion: str, curso_slug: str, nombre_video: str):
    videos_dir = BASE_DIR / curso_slug / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    # Buscamos si ya existe el archivo sin importar la extensión (.mp4, .mkv, etc.)
    existentes = list(videos_dir.glob(f"{nombre_video}.*"))
    if existentes:
        log(f"   [video ya existe] {existentes[0].name}")
        return

    # Estructura de salida idéntica a tu comando original
    output_template = str(videos_dir / f"{nombre_video}.%(ext)s")
    log(f"   [video] Iniciando yt-dlp para la lección...")

    try:
        # Ejecutamos yt-dlp pasándole las cookies manuales del archivo txt
        result = subprocess.run(
            [
                "yt-dlp",
                url_leccion,  # Le pasamos la URL de la lección directamente igual que en tu PowerShell
                "-f", VIDEO_CALIDAD,
                "--output", output_template,
                "--cookies", str(COOKIES_FILE), # Usa tus cookies manuales para autenticarse en el sitio
            ],
            capture_output=True,
            text=True,
        )
        
        if result.returncode == 0:
            log(f"   [video ok] Guardado como: {nombre_video}")
        else:
            log(f"   [error video] yt-dlp falló (Código {result.returncode})")
            log(f"   [yt-dlp stderr]\n{result.stderr[-400:]}")
    except FileNotFoundError:
        log("   [error] yt-dlp no encontrado en el sistema.")
    except Exception as e:
        log(f"   [error inesperado en video] {e}")

# ══════════════════════════════════════════════════════════════════════════════
# 5. MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    init_log()
    log(f"Log activo en: {LOG_FILE}")

    if not LINKS_FILE.exists():
        log(f"[error] Falta el archivo {LINKS_FILE.name}")
        LINKS_FILE.write_text("# Pegá tus URLs acá\n", encoding="utf-8")
        return

    urls = [
        line.strip()
        for line in LINKS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    if not urls:
        log("Agregá URLs en links.txt para continuar.")
        return

    log(f"Lecciones cargadas para procesar: {len(urls)}")

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    })
    
    # Cargamos tus cookies manuales del TXT
    if not cargar_cookies_en_sesion(session, COOKIES_FILE):
        close_log()
        return

    # Bucle de procesamiento
    for i, url in enumerate(urls):
        # Extraemos nombres calcados a tu script de PowerShell
        curso_slug, leccion_slug, nombre_video = procesar_url_estilo_powershell(url)
        
        leccion_dir = BASE_DIR / curso_slug / leccion_slug
        leccion_dir.mkdir(parents=True, exist_ok=True)

        log(f"\n{'─'*60}")
        log(f"Procesando: {url}")
        log(f"Nombre Video Base: {nombre_video}")

        # 1. Bajamos el HTML y los adjuntos usando la sesión logueada de requests
        procesar_html_y_adjuntos(session, url, leccion_dir)
        
        # 2. Bajamos el video pasándole la URL de la lección y las cookies a yt-dlp
        descargar_video_powershell_style(url, curso_slug, nombre_video)

        if i < len(urls) - 1:
            log(f"Esperando {DELAY} segundos...")
            time.sleep(DELAY)

    log(f"\n{'═'*60}")
    log("¡Proceso finalizado!")
    close_log()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR FATAL] {e}")
    finally:
        input("\nPresioná Enter para cerrar la consola...")