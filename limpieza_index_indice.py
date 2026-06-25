import shutil
from pathlib import Path
from datetime import datetime

# ── Configuración ────────────────────────────────────────────────────────────
CURSOS_DIR = Path(r"D:\nacho\cursos_descargados")

# Lista de cursos a limpiar (misma que usaste en el script anterior)
CURSOS_SLUGS = [
    "seminario-partitura",
    "ciclo-1-fundamentos-del-oficio-v3-0",
    "ciclo-2-ampliando-el-lenguaje",
    # Agrega más si es necesario
]

# Opcional: archivo de URLs para extraer slugs (si lo prefieres)
CURSOS_URLS_FILE = None  # Path(r"...\lista_cursos.txt")

# ── Funciones auxiliares ──────────────────────────────────────────────────
def slug_curso_desde_url(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path_parts = parsed.path.strip("/").split("/")
    for i, p in enumerate(path_parts):
        if p in ("cursos", "courses", "curso") and i + 1 < len(path_parts):
            return limpiar_nombre(path_parts[i + 1])
    return limpiar_nombre(path_parts[-1]) if path_parts else ""

def limpiar_nombre(texto: str) -> str:
    import re
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", texto).strip("_ ")

# ── Función principal ──────────────────────────────────────────────────
def limpiar_curso(curso_slug: str) -> dict:
    curso_dir = CURSOS_DIR / curso_slug
    if not curso_dir.exists():
        return {"curso": curso_slug, "error": "Carpeta no encontrada"}

    eliminados = []
    # Buscar todos los archivos index_indice.html en el curso
    for archivo in curso_dir.rglob("index_indice.html"):
        try:
            archivo.unlink()
            eliminados.append(str(archivo.relative_to(CURSOS_DIR)))
        except Exception as e:
            return {"curso": curso_slug, "error": f"Error eliminando {archivo}: {e}"}

    return {"curso": curso_slug, "eliminados": eliminados, "total": len(eliminados)}

# ── Ejecución ──────────────────────────────────────────────────────────────
def main():
    inicio = datetime.now()

    # Obtener lista de cursos
    cursos_a_procesar = []
    if CURSOS_URLS_FILE and Path(CURSOS_URLS_FILE).exists():
        print(f"📄 Leyendo URLs desde: {CURSOS_URLS_FILE}")
        with open(CURSOS_URLS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    slug = slug_curso_desde_url(line)
                    if slug:
                        cursos_a_procesar.append(slug)
    elif CURSOS_SLUGS:
        cursos_a_procesar = CURSOS_SLUGS
    else:
        print("❌ No se definieron cursos. Configura CURSOS_SLUGS o CURSOS_URLS_FILE.")
        input("Presiona Enter para salir...")
        return

    if not cursos_a_procesar:
        print("❌ La lista de cursos está vacía.")
        input("Presiona Enter para salir...")
        return

    print(f"🧹 Eliminando archivos index_indice.html en {len(cursos_a_procesar)} curso(s):")
    for slug in cursos_a_procesar:
        print(f"  - {slug}")

    # Confirmación
    print("\n⚠️  Se eliminarán TODOS los archivos index_indice.html en estos cursos.")
    confirm = input("¿Estás seguro? (escribe 'SI' para continuar): ")
    if confirm != "SI":
        print("Operación cancelada.")
        input("Presiona Enter para salir...")
        return

    resultados = []
    for slug in cursos_a_procesar:
        print(f"\n📁 Procesando: {slug}")
        resultado = limpiar_curso(slug)
        resultados.append(resultado)
        if "error" in resultado:
            print(f"  ❌ Error: {resultado['error']}")
        else:
            print(f"  ✅ Eliminados {resultado['total']} archivos")

    # ── Reporte final ──────────────────────────────────────────────────
    fin = datetime.now()
    duracion = str(fin - inicio).split('.')[0]

    print("\n" + "="*60)
    print("  📊 REPORTE DE LIMPIEZA")
    print("="*60)

    total_eliminados = 0
    for r in resultados:
        if "error" in r:
            print(f"  ❌ {r['curso']}: {r['error']}")
        else:
            print(f"  ✅ {r['curso']}: {r['total']} archivos eliminados")
            total_eliminados += r['total']

    print("\n" + "─"*60)
    print(f"  Total archivos eliminados: {total_eliminados}")
    print(f"  Duración: {duracion}")
    print("="*60)

    # Guardar reporte
    reporte_path = CURSOS_DIR / "reporte_limpieza_indices.txt"
    with open(reporte_path, "w", encoding="utf-8") as f:
        f.write("REPORTE DE LIMPIEZA DE ÍNDICES LOCALES\n")
        f.write("="*60 + "\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Duración: {duracion}\n\n")
        for r in resultados:
            if "error" in r:
                f.write(f"❌ {r['curso']}: {r['error']}\n")
            else:
                f.write(f"✅ {r['curso']}: {r['total']} archivos eliminados\n")
                if r['eliminados']:
                    f.write("  Archivos:\n")
                    for arch in r['eliminados']:
                        f.write(f"    - {arch}\n")
        f.write("="*60 + "\n")
        f.write(f"Total eliminados: {total_eliminados}\n")
        f.write(f"Reporte generado: {reporte_path}\n")

    print(f"\n📄 Reporte guardado en: {reporte_path}")
    print("\n✅ ¡Limpieza completada!")
    input("\nPresiona Enter para salir...")

if __name__ == "__main__":
    main()