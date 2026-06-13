import re
from pathlib import Path
from urllib.parse import urlparse, unquote
from datetime import datetime

# ── Configuración ──────────────────────────────────────────────────────────────
# Debe coincidir con la configuración de descargar_replit.py
CURSOS_DIR = Path(r"D:\nacho\cursos_descargados")
LINKS_FILE = Path(__file__).parent / "links.txt"
# ──────────────────────────────────────────────────────────────────────────────

PREFIJO_RE = re.compile(r'^\d+_')  # detecta prefijos como "001_", "42_", etc.


def limpiar_nombre(texto: str) -> str:
    texto = unquote(texto)
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", texto).strip("_ ")


def segmentos_url(url: str) -> tuple[str, str]:
    """
    Devuelve (curso_slug, leccion_slug) derivados de la URL,
    igual que en descargar_replit.py.
    """
    partes = urlparse(url).path.strip("/").split("/")

    curso_slug   = "curso"
    leccion_slug = "_".join(partes[-2:]) if len(partes) >= 2 else partes[-1]

    for i, p in enumerate(partes):
        if p in ("courses", "cursos") and i + 1 < len(partes):
            curso_slug = partes[i + 1]
            break

    nombre_video = "___".join(partes[:4]) if len(partes) >= 4 else "___".join(partes)
    nombre_video = re.sub(r'%f0%9f%93%b9-', '', nombre_video, flags=re.IGNORECASE)

    return limpiar_nombre(curso_slug), limpiar_nombre(leccion_slug)


def sin_prefijo(nombre: str) -> str:
    """Quita el prefijo numérico si existe: '003_bienvenida' → 'bienvenida'."""
    return PREFIJO_RE.sub('', nombre)


def main():
    print(f"\n{'═'*60}")
    print(f"  Ordenador de cursos")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═'*60}")
    print(f"  Cursos en : {CURSOS_DIR}")
    print(f"  Links de  : {LINKS_FILE}")

    if not LINKS_FILE.exists():
        print(f"\n[error] No se encontró {LINKS_FILE}")
        return

    if not CURSOS_DIR.exists():
        print(f"\n[error] No se encontró la carpeta de cursos: {CURSOS_DIR}")
        return

    # ── Leer URLs en orden ────────────────────────────────────────────────────
    urls = [
        line.strip()
        for line in LINKS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    if not urls:
        print("\nlinks.txt está vacío.")
        return

    print(f"\n  Lecciones en links.txt: {len(urls)}")

    # ── Agrupar por curso ─────────────────────────────────────────────────────
    # { curso_slug: [ (indice_global, leccion_slug), ... ] }
    por_curso: dict[str, list[tuple[int, str]]] = {}
    for i, url in enumerate(urls):
        curso_slug, leccion_slug = segmentos_url(url)
        por_curso.setdefault(curso_slug, []).append((i + 1, leccion_slug))

    print(f"  Cursos detectados     : {len(por_curso)}")
    for slug, lecciones in por_curso.items():
        print(f"    · {slug}  ({len(lecciones)} lecciones)")

    # ── Renombrar carpetas ────────────────────────────────────────────────────
    print()
    total_renombradas = 0
    total_ya_ok       = 0
    total_faltantes   = 0
    total_conflictos  = 0

    for curso_slug, lecciones in por_curso.items():
        curso_dir = CURSOS_DIR / curso_slug
        if not curso_dir.exists():
            print(f"[aviso] Carpeta de curso no encontrada, se saltea: {curso_dir}")
            continue

        print(f"\n{'─'*60}")
        print(f"Curso: {curso_slug}  ({len(lecciones)} lecciones)")

        # Cuántos dígitos necesitamos para este curso
        digitos = len(str(len(lecciones)))

        # Construir mapa actual de carpetas sin prefijo → carpeta real
        # Así podemos encontrar "003_bienvenida" buscando "bienvenida"
        carpetas_existentes: dict[str, Path] = {}
        for carpeta in curso_dir.iterdir():
            if carpeta.is_dir():
                nombre_limpio = sin_prefijo(carpeta.name)
                carpetas_existentes[nombre_limpio] = carpeta

        # Primero renombramos todo a nombres temporales para evitar colisiones
        # (ej: "002_x" quiere el nombre "001_x" que todavía existe)
        temporales: list[tuple[Path, Path]] = []  # (temporal, destino_final)

        for orden, leccion_slug in lecciones:
            prefijo    = str(orden).zfill(digitos)
            nombre_nuevo = f"{prefijo}_{leccion_slug}"
            destino    = curso_dir / nombre_nuevo

            # Buscar la carpeta actual (con o sin prefijo)
            carpeta_actual = carpetas_existentes.get(leccion_slug)

            if carpeta_actual is None:
                print(f"  [faltante] #{orden:>{digitos}} {leccion_slug}")
                total_faltantes += 1
                continue

            if carpeta_actual.name == nombre_nuevo:
                print(f"  [ya ok]    {nombre_nuevo}")
                total_ya_ok += 1
                continue

            # Renombrar a temporal primero
            temporal = curso_dir / f"__tmp_{orden}_{leccion_slug}"
            try:
                carpeta_actual.rename(temporal)
                temporales.append((temporal, destino))
                # Actualizar el mapa por si otra lección usa el mismo slug
                carpetas_existentes[leccion_slug] = temporal
            except Exception as e:
                print(f"  [error]    No se pudo renombrar '{carpeta_actual.name}': {e}")
                total_conflictos += 1

        # Ahora renombramos de temporal a nombre final
        for temporal, destino in temporales:
            try:
                temporal.rename(destino)
                print(f"  [ok]       {destino.name}")
                total_renombradas += 1
            except Exception as e:
                print(f"  [error]    No se pudo renombrar '{temporal.name}' → '{destino.name}': {e}")
                total_conflictos += 1

    # ── Resumen ───────────────────────────────────────────────────────────────
    print(f"\n{'═'*60}")
    print(f"  Renombradas  : {total_renombradas}")
    print(f"  Ya correctas : {total_ya_ok}")
    if total_faltantes:
        print(f"  Faltantes    : {total_faltantes}  (aún no descargadas)")
    if total_conflictos:
        print(f"  Con error    : {total_conflictos}")
    print(f"{'═'*60}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR FATAL] {e}")
        raise
    finally:
        input("\nPresioná Enter para cerrar...")
