"""
generar_visor_curso.py
======================
Lee el index.html de la carpeta raíz de cada curso y genera visor_curso.html,
la página principal del curso con:
  - Video introductorio
  - Descripción del curso
  - Lista completa de lecciones con separadores de módulo
  - Comentarios de la página del curso
  - Botón volver al menú principal (visor_menu.html)

Nomenclatura:
  visor_menu.html   → menú raíz (se genera por separado)
  visor_curso.html  → este archivo, uno por curso
  visor.html        → cada lección (generado por generar_visor.py)
"""

import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup

# ── Configuración ──────────────────────────────────────────────────────────────
CURSOS_DIR   = Path(r"D:\nacho\cursos_descargados")
# CURSOS_DIR = Path(r"C:\cursos_descargados")

DOMINIO_BASE = "cresciente.net"
EXCLUIR_DIRS = {"cursos-online-musica"}
# ──────────────────────────────────────────────────────────────────────────────

PREFIJO_RE = re.compile(r'^\d+_')


def slug_de_url(url: str) -> str:
    from urllib.parse import unquote
    partes = url.rstrip("/").split("/")
    try:
        idx = partes.index("lecciones")
        return unquote(partes[idx + 1])
    except (ValueError, IndexError):
        return ""


def carpeta_para_slug(slug: str, curso_dir: Path) -> Path | None:
    sufijo = f"lecciones_{slug}"
    for carpeta in curso_dir.iterdir():
        if not carpeta.is_dir():
            continue
        nombre_sin_prefijo = PREFIJO_RE.sub("", carpeta.name)
        if nombre_sin_prefijo == sufijo or carpeta.name == sufijo:
            return carpeta
    return None


def extraer_titulo(soup: BeautifulSoup) -> str:
    title = soup.find("title")
    if title:
        texto = title.text.strip()
        for sep in [" – ", " - ", " | "]:
            if sep in texto:
                return texto.split(sep)[0].strip()
        return texto
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else "Curso"


def extraer_descripcion(soup: BeautifulSoup) -> str:
    """Extrae la descripción del curso preservando párrafos."""
    desc = (
        soup.find(class_="ld-tab-content ld-visible")
        or soup.find(class_="ld-tab-content")
        or soup.find(class_="bb-learndash-content-wrap")
    )
    if not desc:
        return ""
    import copy
    desc = copy.copy(desc)
    for el in desc.find_all(class_=["ld-item-list", "learndash-wrapper", "ld-tabs"]):
        el.decompose()
    # Construir HTML limpio con párrafos
    parrafos = []
    for el in desc.find_all(["p", "ul", "ol", "h2", "h3", "h4"]):
        texto = el.get_text(strip=True)
        if texto and len(texto) > 3:
            parrafos.append(f"<p>{texto}</p>")
    resultado = "\n".join(parrafos)
    return resultado if len(resultado) > 20 else ""


def extraer_video(soup: BeautifulSoup) -> str:
    """Retorna el HTML del video local si existe."""
    video = soup.find("video")
    if video:
        return str(video)
    return ""


def extraer_lecciones(soup: BeautifulSoup, curso_dir: Path) -> list[dict]:
    """Extrae la lista de lecciones con separadores desde la página principal del curso."""
    # En la página del curso los items están en ld-item-list-items como divs directos
    items_wrap = soup.find(class_="ld-item-list-items")
    if not items_wrap:
        return []

    items = []
    for child in items_wrap.children:
        if not hasattr(child, "name") or not child.name:
            continue
        cls = " ".join(child.get("class", []))

        # Separador de sección
        if "ld-item-list-section-heading" in cls:
            items.append({"type": "seccion", "texto": child.get_text(strip=True)})
            continue

        # Lección
        if "ld-item-list-item" not in cls:
            continue

        a = child.find("a", href=True)
        if not a:
            continue
        href = a.get("href", "")
        titulo_el = child.find(class_="ld-lesson-title") or child.find(class_="ld-item-title")
        texto = titulo_el.get_text(strip=True) if titulo_el else a.get_text(strip=True)

        if not texto or "/lecciones/" not in href:
            continue

        slug = slug_de_url(href)
        if not slug:
            continue

        carpeta = carpeta_para_slug(slug, curso_dir)
        if carpeta:
            visor = carpeta / "visor.html"
            items.append({
                "type": "leccion",
                "texto": texto,
                "href": f"{carpeta.name}/visor.html",
                "descargada": visor.exists(),
            })
        else:
            items.append({
                "type": "leccion",
                "texto": texto,
                "href": None,
                "descargada": False,
            })

    return items


def extraer_comentarios_curso(soup: BeautifulSoup) -> list[dict]:
    """Extrae comentarios de la página del curso."""
    comentarios = []
    for wrap in soup.find_all(class_="comment-content-wrap"):
        texto_completo = wrap.get_text(separator="\n", strip=True)
        lineas = [l for l in texto_completo.split("\n") if l.strip()]
        if len(lineas) < 2:
            continue
        autor = lineas[0]
        # Segunda línea suele ser la fecha (empieza con número o mes)
        fecha = ""
        cuerpo_start = 1
        if len(lineas) > 2 and re.match(r'^\d', lineas[1]):
            fecha = lineas[1]
            cuerpo_start = 2
        cuerpo = " ".join(lineas[cuerpo_start:]).strip()
        if not cuerpo or cuerpo.lower() in {"respuesta", "reply"}:
            continue
        # ¿Es admin/profe?
        es_admin = "francisco" in autor.lower() or "administrador" in autor.lower()
        comentarios.append({
            "autor": autor,
            "fecha": fecha,
            "cuerpo": cuerpo,
            "es_admin": es_admin,
        })
    return comentarios


CSS = """
:root {
  --bg: #1a1a2e;
  --sidebar-bg: #16213e;
  --card-bg: #0f3460;
  --accent: #e94560;
  --accent2: #f5a623;
  --text: #e0e0e0;
  --text-muted: #9090a0;
  --border: #2a2a4a;
  --font: 'Segoe UI', system-ui, sans-serif;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: var(--font);
  background: var(--bg);
  color: var(--text);
  display: flex;
  min-height: 100vh;
  font-size: 16px;
  line-height: 1.6;
}

/* ── Sidebar izquierdo ── */
#sidebar {
  width: 280px;
  min-width: 240px;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
}

#sidebar-header {
  padding: 16px 16px 14px;
  border-bottom: 1px solid var(--border);
}

#sidebar-header .label {
  font-size: 0.68rem;
  color: var(--accent2);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 4px;
}

#sidebar-header .titulo-curso {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text);
  line-height: 1.3;
}

#nav-lecciones {
  flex: 1;
  padding: 10px 0;
  overflow-y: auto;
}

.seccion-titulo {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--accent2);
  padding: 10px 16px 4px;
}

.leccion-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  font-size: 0.86rem;
  color: var(--text-muted);
  text-decoration: none;
  border-left: 3px solid transparent;
  transition: all 0.15s;
}

.leccion-link:hover {
  background: rgba(233,69,96,0.08);
  color: var(--text);
  border-left-color: var(--accent);
}

.leccion-link.no-desc {
  opacity: 0.4;
  cursor: default;
  pointer-events: none;
}

.leccion-num {
  font-size: 0.7rem;
  color: var(--text-muted);
  min-width: 22px;
  text-align: right;
  flex-shrink: 0;
}

#sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}

.btn-menu {
  display: block;
  padding: 8px 12px;
  border-radius: 6px;
  text-decoration: none;
  font-size: 0.82rem;
  font-weight: 500;
  text-align: center;
  background: rgba(233,69,96,0.10);
  color: var(--accent);
  border: 1px solid rgba(233,69,96,0.3);
  transition: background 0.15s;
}
.btn-menu:hover { background: rgba(233,69,96,0.20); }

/* ── Contenido principal ── */
#main {
  flex: 1;
  overflow-y: auto;
  min-width: 0;
}

#curso-top {
  padding: 28px 40px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--sidebar-bg);
}

#curso-top h1 {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 12px;
  line-height: 1.2;
}

.stats {
  display: flex;
  gap: 20px;
  margin-top: 14px;
  flex-wrap: wrap;
}

.stat {
  font-size: 0.82rem;
  color: var(--text-muted);
}

.stat strong {
  color: var(--accent2);
  font-size: 1.05rem;
}

.descripcion {
  color: var(--text-muted);
  font-size: 0.92rem;
  line-height: 1.7;
}

.descripcion p { margin-bottom: 8px; }

#video-wrap {
  padding: 28px 40px 0;
  max-width: 940px;
}

#video-wrap video {
  width: 100%;
  border-radius: 8px;
  background: #000;
}

#contenido-main {
  padding: 24px 40px 40px;
}

/* Comentarios */
#comentarios-curso {
  margin-top: 32px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}

#comentarios-curso h2 {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  margin-bottom: 14px;
}

.comentario-curso {
  padding: 12px 16px;
  border-radius: 6px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-left: 3px solid var(--border);
  margin-bottom: 10px;
}

.comentario-curso.es-admin {
  border-left-color: var(--accent2);
  background: rgba(245,166,35,0.05);
}

.comentario-header {
  display: flex;
  gap: 10px;
  align-items: baseline;
  margin-bottom: 5px;
}

.comentario-autor {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text);
}

.comentario-curso.es-admin .comentario-autor { color: var(--accent2); }

.comentario-fecha { font-size: 0.75rem; color: var(--text-muted); }

.comentario-cuerpo {
  font-size: 0.88rem;
  color: var(--text);
  line-height: 1.5;
}

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

@media (max-width: 700px) {
  body { flex-direction: column; }
  #sidebar { width: 100%; height: auto; position: static; }
  #curso-top, #video-wrap, #contenido-main { padding: 16px 20px; }
}
"""


def generar_visor_curso(curso_dir: Path) -> bool:
    index_path = curso_dir / "index.html"
    if not index_path.exists():
        return False

    with open(index_path, encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    titulo      = extraer_titulo(soup)
    descripcion = extraer_descripcion(soup)
    video_html  = extraer_video(soup)
    lecciones   = extraer_lecciones(soup, curso_dir)
    comentarios = extraer_comentarios_curso(soup)

    # Estadísticas
    total_lecciones   = sum(1 for it in lecciones if it["type"] == "leccion")
    descargadas       = sum(1 for it in lecciones if it["type"] == "leccion" and it["descargada"])
    total_secciones   = sum(1 for it in lecciones if it["type"] == "seccion")

    stats_html = f"""
    <div class="stats">
      <div class="stat"><strong>{total_lecciones}</strong> lecciones</div>
      <div class="stat"><strong>{descargadas}</strong> descargadas</div>
      {"<div class='stat'><strong>" + str(total_secciones) + "</strong> módulos</div>" if total_secciones else ""}
    </div>"""



    # ── Comentarios ──
    coms_html = ""
    if comentarios:
        items_com = ""
        for c in comentarios:
            admin_cls = " es-admin" if c["es_admin"] else ""
            items_com += (
                f'<div class="comentario-curso{admin_cls}">'
                f'<div class="comentario-header">'
                f'<span class="comentario-autor">{c["autor"]}</span>'
                f'<span class="comentario-fecha">{c["fecha"]}</span>'
                f'</div>'
                f'<div class="comentario-cuerpo">{c["cuerpo"]}</div>'
                f'</div>'
            )
        coms_html = f'<div id="comentarios-curso"><h2>Comentarios ({len(comentarios)})</h2>{items_com}</div>'



    # ── Sidebar lecciones ──────────────────────────────────────────────────
    num = 0
    sidebar_items_html = ""
    for item in lecciones:
        if item["type"] == "seccion":
            sidebar_items_html += f'<div class="seccion-titulo">{item["texto"]}</div>\n'
        else:
            num += 1
            if item["href"] and item["descargada"]:
                sidebar_items_html += (
                    f'<a href="{item["href"]}" class="leccion-link">'
                    f'<span class="leccion-num">{num}</span>{item["texto"]}</a>\n'
                )
            else:
                sidebar_items_html += (
                    f'<span class="leccion-link no-desc">'
                    f'<span class="leccion-num">{num}</span>{item["texto"]}</span>\n'
                )

    descripcion_html = f'<div class="descripcion">{descripcion}</div>' if descripcion else ""
    video_section    = f'<div id="video-wrap">{video_html}</div>' if video_html else ""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{titulo}</title>
<style>{CSS}</style>
</head>
<body>

<nav id="sidebar">
  <div id="sidebar-header">
    <div class="label">Curso</div>
    <div class="titulo-curso">{titulo}</div>
  </div>
  <div id="nav-lecciones">
    {sidebar_items_html}
  </div>
  <div id="sidebar-footer">
    <a href="../visor_menu.html" class="btn-menu">🏠 Menú principal</a>
  </div>
</nav>

<div id="main">
  <div id="curso-top">
    <h1>{titulo}</h1>
    {descripcion_html}
    <div class="stats">
      <div class="stat"><strong>{total_lecciones}</strong> lecciones</div>
      <div class="stat"><strong>{descargadas}</strong> descargadas</div>
      {"<div class=\'stat\'><strong>" + str(total_secciones) + "</strong> módulos</div>" if total_secciones else ""}
    </div>
  </div>
  {video_section}
  <div id="contenido-main">
    {coms_html}
  </div>
</div>

</body>
</html>"""
    visor_path = curso_dir / "visor_curso.html"
    with open(visor_path, "w", encoding="utf-8") as f:
        f.write(html)

    return True


def main():
    if not CURSOS_DIR.exists():
        print(f"[error] No se encontró: {CURSOS_DIR}")
        sys.exit(1)

    print(f"\n{'═'*60}")
    print(f"  Generador de visor_curso.html")
    print(f"  Cursos en: {CURSOS_DIR}")
    print(f"{'═'*60}")

    ok = 0
    sin_index = 0

    for curso_dir in sorted(CURSOS_DIR.iterdir()):
        if not curso_dir.is_dir():
            continue
        if curso_dir.name in EXCLUIR_DIRS:
            print(f"\n  ⏭  {curso_dir.name}  (excluido)")
            continue
        # Solo procesar carpetas que tengan index.html (página de curso descargada)
        if not (curso_dir / "index.html").exists():
            continue

        resultado = generar_visor_curso(curso_dir)
        if resultado:
            ok += 1
            print(f"  ✓  {curso_dir.name}")
        else:
            sin_index += 1
            print(f"  ✗  {curso_dir.name}  (sin index.html)")

    print(f"\n{'═'*60}")
    print(f"  📊 RESUMEN")
    print(f"{'═'*60}")
    print(f"  visor_curso.html creados: {ok}")
    if sin_index:
        print(f"  Sin index.html          : {sin_index}")
    print(f"{'═'*60}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR FATAL] {e}")
        raise
    finally:
        input("\nPresioná Enter para cerrar...")
