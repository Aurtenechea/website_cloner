import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urlparse, urljoin, unquote
from datetime import datetime

# ── Configuración ──────────────────────────────────────────────────────────────
CURSOS_DIR   = Path(r"D:\nacho\cursos_descargados")
# CURSOS_DIR   = Path(r"C:\cursos_descargados")
COOKIES_FILE = Path(r"C:\mis_sitios_descargados\cookies.txt")

# ── LISTA DE ARCHIVOS DE LINKS (comentar/descomentar) ──────────────────────
LINKS_FILES = [
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
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_cc1_e_contrapunto_por_especies.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_ciclo_0_primeros_pasos_en_la_composicion_musical_v3_0.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_ciclo_1_fundamentos_del_oficio_v3_0.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_ciclo_2_ampliando_el_lenguaje.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_de_la_teoria_al_diapason_entendiendo_la_guitarra_09_25.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_experimentos_creativos.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_introduccion_a_la_produccion_musical.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_lecto_escritura_musical_i.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_musescore.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_s_como_analizar_una_cancion.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_s_composicion_y_escritura_para_bateria.txt"),
    Path(r"C:\mis_sitios_descargados\links_todos\links_curso_s_crear_musica_con_conceptos_simples_02_25.txt"),
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
# ──────────────────────────────────────────────────────────────────────────────

PREFIJO_RE = re.compile(r'^\d+_')


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
    return cookies


def limpiar_nombre(texto: str) -> str:
    texto = unquote(texto)
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", texto).strip("_ ")


def segmentos_url(url: str) -> tuple[str, str]:
    partes = urlparse(url).path.strip("/").split("/")
    curso_slug   = "curso"
    leccion_slug = "_".join(partes[-2:]) if len(partes) >= 2 else partes[-1]
    for i, p in enumerate(partes):
        if p in ("courses", "cursos") and i + 1 < len(partes):
            curso_slug = partes[i + 1]
            break
    return limpiar_nombre(curso_slug), limpiar_nombre(leccion_slug)


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


def sin_prefijo(nombre: str) -> str:
    return PREFIJO_RE.sub('', nombre)


def obtener_urls_curso(url_curso: str) -> list[str]:
    """
    Descarga el listado de lecciones del curso entrando al sidebar
    de la primera lección, igual que indice.py pero sin guardar archivo.
    """
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

    dominio_base = urlparse(url_curso).netloc
    partes_path  = urlparse(url_curso).path.strip("/").split("/")
    curso_slug   = ""
    for i, p in enumerate(partes_path):
        if p in ("courses", "cursos", "curso") and i + 1 < len(partes_path):
            curso_slug = partes_path[i + 1]
            break
    if not curso_slug and partes_path:
        curso_slug = partes_path[-1]

    print(f"  [curso] Slug: {curso_slug}")
    print(f"  [índice] Descargando: {url_curso}")
    try:
        r = session.get(url_curso, timeout=30)
        print(f"  [http {r.status_code}]")
        r.raise_for_status()
    except Exception as e:
        print(f"  [error] {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    # Encontrar primera lección en el índice
    primera_leccion = None
    for a in soup.find_all("a", href=True):
        href = urljoin(url_curso, a["href"].strip())
        if es_url_leccion(href, dominio_base, curso_slug):
            primera_leccion = href
            break

    if not primera_leccion:
        print(f"  [error] No se encontró ninguna lección en el índice")
        return []

    print(f"  [sidebar] Entrando a primera lección: {primera_leccion}")
    try:
        r2 = session.get(primera_leccion, timeout=30)
        print(f"  [http {r2.status_code}]")
        soup2 = BeautifulSoup(r2.text, "html.parser")
        sidebar = soup2.find(class_="lms-lessions-list") or soup2.find(class_="bb-lessons-list")
        if not sidebar:
            print(f"  [error] No se encontró el sidebar de lecciones")
            return []

        urls = []
        vistas = set()
        for a in sidebar.find_all("a", href=True):
            href = urljoin(url_curso, a["href"].strip()).split("?")[0].split("#")[0]
            if not href.endswith("/"):
                href += "/"
            if href not in vistas and es_url_leccion(href, dominio_base, curso_slug):
                urls.append(href)
                vistas.add(href)

        print(f"  [sidebar] {len(urls)} lecciones encontradas")
        return urls

    except Exception as e:
        print(f"  [error] {e}")
        return []


def main():
    print(f"\n{'═'*60}")
    print(f"  Ordenador de cursos (múltiples)")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*60}")
    print(f"  Cursos en : {CURSOS_DIR}")
    print(f"  Archivos de links: {len(LINKS_FILES)}")

    if not CURSOS_DIR.exists():
        print(f"\n[error] No se encontró la carpeta de cursos: {CURSOS_DIR}")
        return

    # ── Lista para acumular las lecciones faltantes ──────────────────────────
    faltantes_global = []

    # Estadísticas globales
    total_renombradas = 0
    total_ya_ok       = 0
    total_faltantes   = 0
    total_conflictos  = 0
    cursos_procesados = 0

    for links_file in LINKS_FILES:
        if not links_file.exists():
            print(f"\n[aviso] Archivo no encontrado: {links_file} - Saltando")
            continue

        # Leer la primera URL no comentada del archivo (índice del curso)
        with open(links_file, encoding="utf-8") as f:
            url_curso = None
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    url_curso = line
                    break
        if not url_curso:
            print(f"\n[aviso] No se encontró ninguna URL en {links_file.name} - Saltando")
            continue

        print(f"\n{'─'*60}")
        print(f"  Procesando: {links_file.name}")
        print(f"  URL del curso: {url_curso}")
        print(f"{'─'*60}")

        # ── Obtener URLs del curso ────────────────────────────────────────────
        print(f"\n  Obteniendo listado de lecciones...")
        urls = obtener_urls_curso(url_curso)

        if not urls:
            print(f"\n[error] No se pudieron obtener las lecciones para {url_curso}. Saltando.")
            continue

        print(f"\n  Lecciones encontradas: {len(urls)}")

        # ── Agrupar por curso (normalmente solo uno) ─────────────────────────
        por_curso: dict[str, list[tuple[int, str]]] = {}
        for i, url in enumerate(urls):
            curso_slug, leccion_slug = segmentos_url(url)
            por_curso.setdefault(curso_slug, []).append((i + 1, leccion_slug))

        # ── Renombrar carpetas ────────────────────────────────────────────────
        for curso_slug, lecciones in por_curso.items():
            curso_dir = CURSOS_DIR / curso_slug
            if not curso_dir.exists():
                print(f"[aviso] Carpeta de curso no encontrada: {curso_dir} - Saltando")
                continue

            cursos_procesados += 1
            print(f"\n  Curso: {curso_slug}  ({len(lecciones)} lecciones)")

            # Mantener al menos 3 dígitos para compatibilidad con nombres previos (ej: 002)
            digitos = max(3, len(str(len(lecciones))))

            carpetas_existentes: dict[str, Path] = {}
            for carpeta in curso_dir.iterdir():
                if carpeta.is_dir():
                    nombre_limpio = sin_prefijo(carpeta.name)
                    carpetas_existentes[nombre_limpio] = carpeta

            temporales: list[tuple[Path, Path]] = []

            for orden, leccion_slug in lecciones:
                prefijo      = str(orden).zfill(digitos)
                nombre_nuevo = f"{prefijo}_{leccion_slug}"
                destino      = curso_dir / nombre_nuevo

                carpeta_actual = carpetas_existentes.get(leccion_slug)

                if carpeta_actual is None:
                    print(f"  [faltante] #{orden:>{digitos}} {leccion_slug}")
                    total_faltantes += 1
                    # ── GUARDAR EN EL REPORTE ──────────────────────────────
                    faltantes_global.append(
                        f"Curso: {curso_slug} | Lección #{orden} | {leccion_slug} | (URL origen: {url_curso})"
                    )
                    continue

                if carpeta_actual.name == nombre_nuevo:
                    print(f"  [ya ok]    {nombre_nuevo}")
                    total_ya_ok += 1
                    continue

                temporal = curso_dir / f"__tmp_{orden}_{leccion_slug}"
                try:
                    carpeta_actual.rename(temporal)
                    temporales.append((temporal, destino))
                    carpetas_existentes[leccion_slug] = temporal
                except Exception as e:
                    print(f"  [error]    No se pudo renombrar '{carpeta_actual.name}': {e}")
                    total_conflictos += 1

            for temporal, destino in temporales:
                try:
                    temporal.rename(destino)
                    print(f"  [ok]       {destino.name}")
                    total_renombradas += 1
                except Exception as e:
                    print(f"  [error]    '{temporal.name}' -> '{destino.name}': {e}")
                    total_conflictos += 1

    # ── GUARDAR REPORTE DE FALTANTES EN ARCHIVO ──────────────────────────────
    report_dir = Path(r"C:\mis_sitios_descargados\links_todos")
    report_dir.mkdir(parents=True, exist_ok=True)
    # El archivo se llama igual que el script: ordenar_cursos7.txt
    report_file = report_dir / (Path(__file__).stem + ".txt")

    if faltantes_global:
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(f"REPORTE DE LECCIONES FALTANTES\n")
            f.write(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'═'*60}\n\n")
            for linea in faltantes_global:
                f.write(linea + "\n")
            f.write(f"\nTotal de lecciones faltantes: {len(faltantes_global)}\n")
        print(f"\n[reporte] ✅ Guardado en: {report_file}")
    else:
        # Si no hay faltantes, borramos el archivo si existía de antes
        if report_file.exists():
            report_file.unlink()
            print(f"\n[reporte] 🗑️ No hay faltantes, se eliminó {report_file} (versión anterior)")
        else:
            print(f"\n[reporte] ✅ No hay lecciones faltantes. No se generó archivo.")

    # ── Resumen global ──────────────────────────────────────────────────────
    print(f"\n{'═'*60}")
    print(f"  📊 RESUMEN GLOBAL")
    print(f"{'═'*60}")
    print(f"  Cursos procesados : {cursos_procesados}")
    print(f"  Renombradas       : {total_renombradas}")
    print(f"  Ya correctas      : {total_ya_ok}")
    if total_faltantes:
        print(f"  Faltantes         : {total_faltantes}  (aún no descargadas)")
    if total_conflictos:
        print(f"  Con error         : {total_conflictos}")
    print(f"{'═'*60}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR FATAL] {e}")
        raise
    finally:
        input("\nPresioná Enter para cerrar...")