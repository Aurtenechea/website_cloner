import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import re
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urlparse, unquote
from datetime import datetime

# ── Configuración ──────────────────────────────────────────────────────────────
# CURSOS_DIR = Path(r"C:\cursos_descargados")
CURSOS_DIR = Path(r"D:\nacho\cursos_descargados")

# ── ARCHIVOS DE LINKS (hardcodeados) ────────────────────────────────────────
# Comenta/descomenta las líneas para elegir qué archivos procesar.
LINKS_FILES = [
    # Path(r"C:\mis_sitios_descargados\links_todos\links_curso_cc1_e_contrapunto_por_especies.txt"),
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
    
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_ciclo_2_ampliando_el_lenguaje.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_de_la_teoria_al_diapason_entendiendo_la_guitarra_09_25.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_experimentos_creativos.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_introduccion_a_la_produccion_musical.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_lecto_escritura_musical_i.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_musescore.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_s_como_analizar_una_cancion.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_s_composicion_y_escritura_para_bateria.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_s_crear_musica_con_conceptos_simples_02_25.txt"),

    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_ciclo_1_fundamentos_del_oficio_v3_0.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_seminario_el_fagot_historia_posibilidades_y_nuevas_perspectivas.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_seminario_introduccion_a_la_armonia_del_jazz_y_sus_ramificaciones.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_seminario_introduccion_al_arreglo_musical.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_seminario_partitura.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_seminario_planificacion_en_una_pieza_musical.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_seminario_rock_estilo_composicion_y_arreglo.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_teoria_musical_basica_en_50_lecciones.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_teoria_musical_basica_en_capsulas.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_termina_tus_canciones_02_26.txt"),
]

REPORTE_FILE = Path(r"C:\mis_sitios_descargados\reporte_cursos.txt")
# ──────────────────────────────────────────────────────────────────────────────

DOMINIOS_VIDEO = (
    "vimeo.com", "mediadelivery.net", "iframe.mediadelivery.net", "bunnycdn.com",
    "wistia.com", "fast.wistia.net", "loom.com", "kaltura.com",
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


def limpiar_nombre(texto: str) -> str:
    texto = unquote(texto)
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", texto).strip("_ ")


def slug_curso_desde_url(url: str) -> str:
    partes = urlparse(url).path.strip("/").split("/")
    for i, p in enumerate(partes):
        if p in ("courses", "cursos", "curso") and i + 1 < len(partes):
            return partes[i + 1]
    return partes[-1] if partes else ""


def slug_leccion_desde_url(url: str) -> str:
    """
    Genera el slug de la lección usando exactamente la misma lógica que
    el script de descarga (descargar_replit_fix8.py): une los últimos 2 segmentos
    de la URL con guión bajo.
    """
    partes = urlparse(url).path.strip("/").split("/")
    if len(partes) >= 2:
        leccion_slug = "_".join(partes[-2:])
    else:
        leccion_slug = partes[-1] if partes else ""
    return limpiar_nombre(leccion_slug)


def buscar_carpeta_leccion(curso_dir: Path, lec_slug: str) -> Path | None:
    posibles = {lec_slug, f"lecciones_{lec_slug}"}
    for posible in posibles:
        ruta = curso_dir / posible
        if ruta.exists():
            return ruta
    for carpeta in curso_dir.iterdir():
        if not carpeta.is_dir():
            continue
        nombre_sin_prefijo = re.sub(r"^\d{2,}_", "", carpeta.name)
        if nombre_sin_prefijo in posibles:
            return carpeta
    return None


def videos_locales_en_html(html_path: Path) -> list[str]:
    try:
        soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "html.parser")
        videos = []
        for video in soup.find_all("video"):
            for attr in [video.get("src") or ""]:
                for prefix in ("../videos/", "videos/"):
                    if attr.startswith(prefix):
                        videos.append(attr[len(prefix):])
            for source in video.find_all("source"):
                s = source.get("src") or ""
                for prefix in ("../videos/", "videos/"):
                    if s.startswith(prefix):
                        videos.append(s[len(prefix):])
        return videos
    except Exception:
        return []


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
            if any(d in src for d in DOMINIOS_VIDEO):
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


def contar_iframes_video_en_soup(soup: BeautifulSoup) -> int:
    """Cuenta cuántos iframes de video (dominios conocidos) hay en el soup."""
    count = 0
    for iframe in soup.find_all("iframe"):
        src = (iframe.get("src") or iframe.get("data-src") or iframe.get("data-lazy-src") or "").strip()
        if src.startswith("//"):
            src = "https:" + src
        if any(d in src for d in DOMINIOS_VIDEO):
            count += 1
    return count


def iframes_remotos_en_html(html_path: Path) -> int:
    try:
        soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "html.parser")
        contenido = None
        for clase in ["ld-tab-content", "learndash_content_wrap", "entry-content"]:
            contenido = soup.find(class_=clase)
            if contenido:
                break
        if not contenido:
            wrapper = soup.find(class_="learndash-wrapper")
            if wrapper:
                contenido = wrapper
        if not contenido:
            body = soup.find("body")
            if body:
                contenido = BeautifulSoup(str(body), "html.parser")
                for comentarios in contenido.find_all(class_="ld-focus-comments"):
                    comentarios.decompose()
                for comentarios in contenido.find_all(class_="ld-focus-comments__comments"):
                    comentarios.decompose()
                for comentarios in contenido.find_all(id="ld-comments"):
                    comentarios.decompose()
        if not contenido:
            contenido = soup
        return contar_iframes_video_en_soup(contenido)
    except Exception:
        return 0


def obtener_archivos_locales(videos_dir: Path, prefijo: str) -> list[Path]:
    """Devuelve lista de archivos .mp4 que coinciden con el prefijo."""
    if not videos_dir.exists():
        return []
    return [p for p in videos_dir.glob(f"{prefijo}*.mp4") if p.is_file()]


def obtener_sufijo(nombre: str) -> str | None:
    """Devuelve '_vN' si existe, o None."""
    m = re.search(r'(_v\d+)(?=\.mp4$)', nombre)
    return m.group(1) if m else None


def chequear_leccion(leccion_dir: Path, videos_dir: Path, prefijo: str) -> dict:
    resultado = {
        "completa": False,
        "sin_video": False,
        "videos_ok": [],
        "videos_faltantes": [],
        "error": None,
        "detalles": {}
    }

    index_html = leccion_dir / "index.html"
    raw_html = leccion_dir / "index_raw.html"
    centinela = leccion_dir / "_descarga_completa.txt"

    if not index_html.exists():
        resultado["error"] = "Sin index.html"
        return resultado

    # 1. Verificar iframes remotos en el HTML procesado
    iframes = iframes_remotos_en_html(index_html)
    if iframes > 0:
        resultado["error"] = f"{iframes} iframe(s) de video sin reemplazar"
        return resultado

    # 2. Obtener información del HTML original
    if raw_html.exists():
        try:
            raw_soup = BeautifulSoup(raw_html.read_text(encoding="utf-8", errors="replace"), "html.parser")
            iframes_originales = obtener_iframes_video_originales(raw_soup)
            urls_unicas = list(set([iframe['url'] for iframe in iframes_originales]))
        except Exception:
            urls_unicas = []
    else:
        urls_unicas = []

    resultado["detalles"]["urls_unicas"] = len(urls_unicas)

    # 3. Extraer referencias a videos locales en index.html
    local_refs = []
    try:
        soup = BeautifulSoup(index_html.read_text(encoding="utf-8", errors="replace"), "html.parser")
        for video in soup.find_all("video"):
            for source in video.find_all("source"):
                src = source.get("src") or ""
                if src.startswith("../videos/"):
                    local_refs.append(src[len("../videos/"):])
            src_video = video.get("src") or ""
            if src_video.startswith("../videos/"):
                local_refs.append(src_video[len("../videos/"):])
    except Exception:
        local_refs = []
    resultado["detalles"]["local_refs"] = local_refs

    # 4. Verificar existencia de archivos de video
    videos_ref = videos_locales_en_html(index_html)
    if not videos_ref:
        resultado["sin_video"] = True
        resultado["completa"] = True
        return resultado

    for nombre in videos_ref:
        video_path = videos_dir / nombre
        if video_path.exists() and video_path.stat().st_size > 0:
            resultado["videos_ok"].append(nombre)
        else:
            resultado["videos_faltantes"].append(nombre)

    # 5. Validar estructura de nombres de archivo (con/sin sufijo)
    if urls_unicas:
        num_urls = len(urls_unicas)
        archivos_locales = obtener_archivos_locales(videos_dir, prefijo)

        # Clasificar
        con_sufijo = []
        sin_sufijo = []
        for p in archivos_locales:
            suf = obtener_sufijo(p.name)
            if suf:
                con_sufijo.append((p, suf))
            else:
                sin_sufijo.append(p)

        # Caso especial: 1 video y 1 archivo sin sufijo -> OK
        if num_urls == 1 and len(sin_sufijo) == 1 and len(con_sufijo) == 0:
            # Coincidencia perfecta
            pass
        elif num_urls > 1 and len(sin_sufijo) == 1 and len(con_sufijo) == 0:
            resultado["error"] = "Video único sin sufijo pero hay múltiples videos en el HTML (se necesita reparación)"
            return resultado
        elif con_sufijo:
            # Verificar que cubren exactamente 1..num_urls
            numeros = set()
            for p, suf in con_sufijo:
                num = int(suf[2:])  # _v1 -> 1
                numeros.add(num)
            esperados = set(range(1, num_urls + 1))
            if numeros != esperados:
                faltan = esperados - numeros
                sobran = numeros - esperados
                if faltan:
                    resultado["error"] = f"Faltan videos con sufijos: {', '.join(f'_v{n}' for n in sorted(faltan))}"
                    return resultado
                if sobran:
                    resultado["error"] = f"Sobran videos con sufijos: {', '.join(f'_v{n}' for n in sorted(sobran))}"
                    return resultado
        else:
            # Si no hay con_sufijo y num_urls > 1, pero sin_sufijo no es 1, puede ser múltiple sin sufijo
            if num_urls > 1 and len(sin_sufijo) > 1:
                # No podemos saber cuál es cuál -> error
                resultado["error"] = f"Múltiples archivos sin sufijo ({len(sin_sufijo)}) para {num_urls} videos. No se puede mapear."
                return resultado
            # Si num_urls == 1 y no hay archivos locales, eso ya se captura en videos_faltantes

    # 6. Decidir si está completa
    resultado["completa"] = centinela.exists() and len(resultado["videos_faltantes"]) == 0
    return resultado


def procesar_archivo_links(links_file: Path) -> dict:
    """Procesa un archivo de links y devuelve estadísticas."""
    print(f"\n{'─'*70}")
    print(f"📁 Procesando: {links_file.name}")
    print(f"{'─'*70}")

    if not links_file.exists():
        print(f"  ❌ Archivo no encontrado: {links_file}")
        return {"error": True}

    urls = [
        line.strip()
        for line in links_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    if not urls:
        print(f"  ⚠️ El archivo está vacío.")
        return {"error": True, "vacío": True}

    print(f"  📄 Lecciones encontradas: {len(urls)}")

    # Agrupar por curso
    por_curso: dict[str, list[str]] = {}
    for url in urls:
        curso_slug = slug_curso_desde_url(url)
        por_curso.setdefault(curso_slug, []).append(url)

    total_ok = 0
    total_faltantes = 0
    total_incompletas = 0
    total_lecciones = 0
    resultados_curso = {}

    for curso_slug, lecciones_url in por_curso.items():
        curso_dir = CURSOS_DIR / curso_slug
        videos_dir = curso_dir / "videos"
        total_lecciones += len(lecciones_url)

        print(f"\n  📚 Curso: {curso_slug} ({len(lecciones_url)} lecciones)")

        if not curso_dir.exists():
            print(f"    ❌ Carpeta no encontrada — no descargado")
            total_faltantes += len(lecciones_url)
            continue

        lec_ok = []
        lec_faltantes = []
        lec_incompletas = []

        for idx, url in enumerate(lecciones_url, start=1):
            numero = str(idx).zfill(3)
            lec_slug = slug_leccion_desde_url(url)
            leccion_dir = buscar_carpeta_leccion(curso_dir, lec_slug)

            # Mostrar progreso en la misma línea
            sys.stdout.write(f"\r    [{numero}/{len(lecciones_url)}] Chequeando: {lec_slug[:50]}{'...' if len(lec_slug)>50 else ''}   ")
            sys.stdout.flush()

            if leccion_dir is None:
                lec_faltantes.append((numero, lec_slug, url))
                continue

            # Obtener prefijo para archivos de video (usamos el mismo que genera descargar)
            # Para simplificar, lo extraemos del nombre de la carpeta (quitando prefijo numérico)
            prefijo_video = lec_slug  # usamos el slug
            # Alternativamente, podríamos obtenerlo de la URL, pero es más simple así

            resultado = chequear_leccion(leccion_dir, videos_dir, prefijo_video)

            if resultado["error"]:
                lec_incompletas.append((numero, lec_slug, resultado["error"], leccion_dir.name))
            elif resultado["completa"] or resultado["sin_video"]:
                lec_ok.append((numero, lec_slug))
            elif resultado["videos_faltantes"]:
                motivo = f"Videos faltantes: {', '.join(resultado['videos_faltantes'])}"
                lec_incompletas.append((numero, lec_slug, motivo, leccion_dir.name))
            else:
                lec_incompletas.append((numero, lec_slug, "Sin centinela", leccion_dir.name))

        # Salto de línea después del progreso
        print()

        n_ok = len(lec_ok)
        n_fal = len(lec_faltantes)
        n_inc = len(lec_incompletas)
        total_ok += n_ok
        total_faltantes += n_fal
        total_incompletas += n_inc

        resumen = f"    ✅ {n_ok} ok | ❌ {n_fal} no descargadas | ⚠️ {n_inc} con problemas"
        print(resumen)

        # Guardar resultados detallados
        resultados_curso[curso_slug] = {
            "lec_ok": lec_ok,
            "lec_faltantes": lec_faltantes,
            "lec_incompletas": lec_incompletas,
            "n_ok": n_ok,
            "n_fal": n_fal,
            "n_inc": n_inc,
        }

    return {
        "error": False,
        "archivo": links_file,
        "total_lecciones": total_lecciones,
        "total_ok": total_ok,
        "total_faltantes": total_faltantes,
        "total_incompletas": total_incompletas,
        "por_curso": resultados_curso,
    }


def main():
    print(f"\n{'═'*70}")
    print(f"  🧾 CHEQUEADOR DE LECCIONES")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*70}")
    print(f"  Cursos en: {CURSOS_DIR}")
    print(f"  Archivos de links configurados: {len([f for f in LINKS_FILES if f])}")

    # Procesar cada archivo de links
    reportes = []
    for links_file in LINKS_FILES:
        if not links_file:
            continue
        resultado = procesar_archivo_links(links_file)
        reportes.append(resultado)

    # ── Resumen global ──────────────────────────────────────────────────────
    print(f"\n{'═'*70}")
    print(f"  📊 RESUMEN GLOBAL")
    print(f"{'═'*70}")

    total_ok_global = 0
    total_fal_global = 0
    total_inc_global = 0
    total_lec_global = 0

    for r in reportes:
        if r.get("error"):
            print(f"  ❌ Error procesando: {r.get('archivo', 'desconocido')}")
            continue
        if r.get("vacío"):
            continue
        print(f"\n  📁 {r['archivo'].name}")
        print(f"     Total lecciones: {r['total_lecciones']}")
        print(f"     ✅ OK          : {r['total_ok']}")
        print(f"     ❌ No descargadas: {r['total_faltantes']}")
        print(f"     ⚠️ Con problemas: {r['total_incompletas']}")
        total_ok_global += r["total_ok"]
        total_fal_global += r["total_faltantes"]
        total_inc_global += r["total_incompletas"]
        total_lec_global += r["total_lecciones"]

    print(f"\n{'─'*70}")
    print(f"  🌟 TOTAL GLOBAL:")
    print(f"     Lecciones    : {total_lec_global}")
    print(f"     ✅ OK        : {total_ok_global}")
    print(f"     ❌ No descargadas: {total_fal_global}")
    print(f"     ⚠️ Con problemas: {total_inc_global}")
    print(f"{'═'*70}")

    # Generar reporte en archivo
    with open(REPORTE_FILE, "w", encoding="utf-8") as f:
        f.write(f"REPORTE DE LECCIONES — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"═" * 70 + "\n\n")
        for r in reportes:
            if r.get("error") or r.get("vacío"):
                continue
            f.write(f"Archivo: {r['archivo'].name}\n")
            f.write(f"  Total: {r['total_lecciones']} | OK: {r['total_ok']} | Faltan: {r['total_faltantes']} | Inc: {r['total_incompletas']}\n\n")
            for curso, datos in r["por_curso"].items():
                f.write(f"  Curso: {curso}\n")
                f.write(f"    OK ({datos['n_ok']}):\n")
                for num, slug in datos["lec_ok"]:
                    f.write(f"      ✓ [{num}] {slug}\n")
                if datos["lec_faltantes"]:
                    f.write(f"    NO DESCARGADAS ({datos['n_fal']}):\n")
                    for num, slug, url in datos["lec_faltantes"]:
                        f.write(f"      ✗ [{num}] {slug}\n")
                        f.write(f"        {url}\n")
                if datos["lec_incompletas"]:
                    f.write(f"    CON PROBLEMAS ({datos['n_inc']}):\n")
                    for num, slug, motivo, carpeta in datos["lec_incompletas"]:
                        f.write(f"      ⚠ [{num}] {slug}\n")
                        f.write(f"        Carpeta: {carpeta}\n")
                        f.write(f"        Motivo: {motivo}\n")
            f.write("\n")

    print(f"\n  📄 Reporte guardado en: {REPORTE_FILE}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR FATAL] {e}")
        raise
    finally:
        input("\nPresioná Enter para cerrar...")