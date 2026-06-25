"""
creador_de_index_cursos.py
==========================
Para cada curso de la lista, descarga la página principal desde la web
y guarda dos archivos en la raíz de la carpeta del curso:
  - index_raw.html  → HTML original sin modificar
  - index.html      → HTML con iframes de video reemplazados por <video> locales

NO genera index_indice.html ni index_sidebar.html.
El visor_curso.html se genera por separado con generar_visor_curso.py.
"""

import re
import subprocess
import glob
import time
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime

# ── Configuración ─────────────────────────────────────────────────────────────
CURSOS_DIR   = Path(r"D:\nacho\cursos_descargados")
COOKIES_FILE = Path(r"C:\mis_sitios_descargados\cookies.txt")

# Lista de URLs de cursos a procesar (una por curso)
CURSOS_URLS = [
"https://cresciente.net/cursos/2022-intensivo-armonia-aplicada-a-la-guitarra-2/",
"https://cresciente.net/cursos/armonia-aplicada-a-la-guitarra-1-guitarra-funcional/",
"https://cresciente.net/cursos/armonia-modal-aplicada-a-la-composicion/",
"https://cresciente.net/cursos/armonia-modal-que-es-y-como-usarla-en-tus-composiciones-06-2/",
"https://cresciente.net/cursos/armonia-moderna-1-las-bases/",
"https://cresciente.net/cursos/armonia-moderna-2-de-la-armonia-modal-al-cromatismo-funcional-05-21/",
"https://cresciente.net/cursos/audioperceptiva-i/",
"https://cresciente.net/cursos/c1c-voz-y-cuerpo/",
"https://cresciente.net/cursos/cc-armonia-aplicada-al-piano/",
"https://cresciente.net/cursos/cc0-a-sistema-de-estudio-y-organizacion/",
"https://cresciente.net/cursos/cc1-e-contrapunto-por-especies/",
"https://cresciente.net/cursos/ciclo-0-primeros-pasos-en-la-composicion-musical-v3-0/",
"https://cresciente.net/cursos/ciclo-1-fundamentos-del-oficio-v3-0/",
"https://cresciente.net/cursos/ciclo-2-ampliando-el-lenguaje/",
"https://cresciente.net/cursos/de-la-teoria-al-diapason-entendiendo-la-guitarra-09-25/",
"https://cresciente.net/cursos/experimentos-creativos/",
"https://cresciente.net/cursos/introduccion-a-la-produccion-musical/",
"https://cresciente.net/cursos/lecto-escritura-musical-i/",
"https://cresciente.net/cursos/musescore/",
"https://cresciente.net/cursos/s-como-analizar-una-cancion/",
"https://cresciente.net/cursos/s-composicion-y-escritura-para-bateria/",
"https://cresciente.net/cursos/s-crear-musica-con-conceptos-simples-02-25/",
"https://cresciente.net/cursos/seminario-el-fagot-historia-posibilidades-y-nuevas-perspectivas/",
"https://cresciente.net/cursos/seminario-introduccion-a-la-armonia-del-jazz-y-sus-ramificaciones/",
"https://cresciente.net/cursos/seminario-introduccion-al-arreglo-musical/",
"https://cresciente.net/cursos/seminario-partitura/",
"https://cresciente.net/cursos/seminario-planificacion-en-una-pieza-musical/",
"https://cresciente.net/cursos/seminario-rock-estilo-composicion-y-arreglo/",
"https://cresciente.net/cursos/teoria-musical-basica-en-50-lecciones/",
"https://cresciente.net/cursos/teoria-musical-basica-en-capsulas/",
"https://cresciente.net/cursos/termina-tus-canciones-02-26/"
]

# Calidad de video para yt-dlp
VIDEO_CALIDAD    = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]/best"
MAX_INTENTOS     = 3
VIDEO_DOMINIOS   = (
    "vimeo.com", "mediadelivery.net", "iframe.mediadelivery.net", "bunnycdn.com",
    "b-cdn.net", "wistia.com", "fast.wistia.net", "loom.com", "kaltura.com",
    "sproutvideo.com", "vidyard.com", "dailymotion.com",
    "jwplatform.com", "jwplayer.com", "brightcove.net", "brightcove.com",
    "api.video", "youtube.com", "youtu.be",
)
# ──────────────────────────────────────────────────────────────────────────────

import requests

def slug_desde_url(url: str) -> str:
    partes = urlparse(url).path.strip("/").split("/")
    for i, p in enumerate(partes):
        if p in ("cursos", "courses", "curso") and i + 1 < len(partes):
            return partes[i + 1]
    return partes[-1] if partes else ""


def cargar_cookies(path: Path) -> dict:
    cookies = {}
    if not path.exists():
        print(f"  [advertencia] No se encontró {path}")
        return cookies
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            partes = line.strip().split("\t")
            if len(partes) >= 7:
                cookies[partes[5]] = partes[6]
    print(f"  [cookies] {len(cookies)} cargadas")
    return cookies


def descargar_pagina(url: str, cookies: dict) -> str | None:
    session = requests.Session()
    session.cookies.update(cookies)
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    })
    try:
        r = session.get(url, timeout=30)
        r.raise_for_status()
        print(f"  [http {r.status_code}] {url}")
        return r.text
    except Exception as e:
        print(f"  [error] {e}")
        return None


def _es_parcial(path: Path) -> bool:
    return bool(re.search(
        r'(?:\.f\d+(?:\.[^.]+)?$|\.fhls-[^/\\]+(?:\.[^.]+)?$|\.part$|-Frag\d+(?:\.[^.]+)?$)',
        path.name
    )) or path.suffix == ".part"


def _limpiar_parciales(template: str):
    patron = template.replace("%(ext)s", "*")
    for ruta in glob.glob(patron) + glob.glob(patron + ".part"):
        p = Path(ruta)
        if _es_parcial(p):
            try:
                p.unlink()
            except Exception:
                pass


def descargar_video(url_video: str, template: str, label: str, referer: str) -> bool | None:
    for intento in range(1, MAX_INTENTOS + 1):
        if intento > 1:
            print(f"  [video] reintento {intento}/{MAX_INTENTOS}")
            time.sleep(5)
        else:
            print(f"  [video] descargando: {url_video[:80]}")
        _limpiar_parciales(template)
        try:
            cmd = [
                "yt-dlp", url_video,
                "-f", VIDEO_CALIDAD,
                "--output", template,
                "--cookies", str(COOKIES_FILE),
                "--merge-output-format", "mp4",
                "--referer", referer,
                "--no-playlist",
                "--fragment-retries", "5",
                "--retries", "5",
                "--socket-timeout", "30",
                "--no-part",
            ]
            result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                print(f"  [video ok] {label}")
                return True
            if "Unsupported URL" in result.stderr:
                print(f"  [sin video] URL no soportada")
                return None
            print(f"  [error video] código {result.returncode}")
        except FileNotFoundError:
            print("  [error] yt-dlp no encontrado")
            return False
        except Exception as e:
            print(f"  [error] {e}")
    return False


def video_tag(ruta_rel: str, ext: str) -> str:
    mime = {
        ".mp4": "video/mp4", ".webm": "video/webm",
        ".mkv": "video/x-matroska", ".mov": "video/quicktime",
    }.get(ext.lower(), "video/mp4")
    return (
        f'<video controls style="width:100%;max-width:960px;display:block;margin:1em 0" preload="auto">'
        f'<source src="{ruta_rel}" type="{mime}">'
        f'Tu navegador no soporta video HTML5.</video>'
    )


def procesar_videos(soup: BeautifulSoup, curso_slug: str, curso_dir: Path, url_curso: str) -> BeautifulSoup:
    videos_dir = curso_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    iframes = soup.find_all("iframe")
    urls_video = []
    for iframe in iframes:
        src = (iframe.get("src") or iframe.get("data-src") or "").strip()
        if src.startswith("//"):
            src = "https:" + src
        if any(d in src for d in VIDEO_DOMINIOS):
            urls_video.append((iframe, src))

    if not urls_video:
        print("  [video] No se encontraron videos en la portada")
        return soup

    print(f"  [video] {len(urls_video)} video(s) encontrado(s)")

    for idx, (iframe, video_url) in enumerate(urls_video):
        sufijo = f"_portada_{idx+1}" if len(urls_video) > 1 else "_portada"
        template = str(videos_dir / f"{curso_slug}{sufijo}.%(ext)s")

        # ¿Ya existe?
        existentes = [p for p in videos_dir.glob(f"{curso_slug}{sufijo}.*") if not _es_parcial(p)]
        if existentes:
            archivo = existentes[0]
            print(f"  [video ya existe] {archivo.name}")
        else:
            resultado = descargar_video(video_url, template, f"portada #{idx+1}", referer=url_curso)
            if resultado is not True:
                continue
            existentes = [p for p in videos_dir.glob(f"{curso_slug}{sufijo}.*") if not _es_parcial(p)]
            if not existentes:
                continue
            archivo = existentes[0]

        ruta_rel = f"videos/{archivo.name}"
        iframe.replace_with(BeautifulSoup(video_tag(ruta_rel, archivo.suffix), "html.parser"))
        print(f"  [html] iframe → {ruta_rel}")

    return soup


def procesar_curso(url_curso: str, cookies: dict) -> bool:
    curso_slug = slug_desde_url(url_curso)
    curso_dir  = CURSOS_DIR / curso_slug

    print(f"\n{'─'*60}")
    print(f"  Curso: {curso_slug}")
    print(f"  URL  : {url_curso}")
    print(f"{'─'*60}")

    if not curso_dir.exists():
        print(f"  [error] Carpeta no encontrada: {curso_dir}")
        return False

    # Descargar HTML
    html_raw = descargar_pagina(url_curso, cookies)
    if not html_raw:
        return False

    # Guardar index_raw.html (original sin tocar)
    raw_path = curso_dir / "index_raw.html"
    raw_path.write_text(html_raw, encoding="utf-8")
    print(f"  [guardado] index_raw.html")

    # Procesar videos y guardar index.html
    soup = BeautifulSoup(html_raw, "html.parser")
    soup = procesar_videos(soup, curso_slug, curso_dir, url_curso)

    index_path = curso_dir / "index.html"
    index_path.write_text(soup.prettify(), encoding="utf-8")
    print(f"  [guardado] index.html")

    return True


def main():
    print(f"\n{'═'*60}")
    print(f"  Descargador de páginas principales de cursos")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*60}")
    print(f"  Cursos a procesar: {len(CURSOS_URLS)}")

    if not CURSOS_DIR.exists():
        print(f"\n[error] No se encontró: {CURSOS_DIR}")
        return

    cookies = cargar_cookies(COOKIES_FILE)
    ok = 0
    errores = 0

    for url in CURSOS_URLS:
        url = url.strip()
        if not url or url.startswith("#"):
            continue
        if procesar_curso(url, cookies):
            ok += 1
        else:
            errores += 1

    print(f"\n{'═'*60}")
    print(f"  📊 RESUMEN")
    print(f"{'═'*60}")
    print(f"  OK     : {ok}")
    print(f"  Errores: {errores}")
    print(f"{'═'*60}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR FATAL] {e}")
        raise
    finally:
        input("\nPresioná Enter para cerrar...")
