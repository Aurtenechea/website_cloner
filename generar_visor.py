"""
generar_visor.py
================
Recorre todos los cursos en CURSOS_DIR, lee el index.html de cada lección
y genera un visor.html limpio, offline, con estilos propios embebidos.

Nomenclatura de archivos generados:
  visor.html        → cada lección
  visor_curso.html  → página principal de un curso  (se creará después)
  visor_menu.html   → menú raíz de todos los cursos (se creará después)

Lógica de resolución de carpetas:
  URL: .../lecciones/sesion-2-2/
  slug de lección: sesion-2-2
  carpeta buscada: cualquiera que termine en _lecciones_sesion-2-2
                   (con o sin prefijo numérico NN_)
  link generado:   ../[carpeta_encontrada]/visor.html
"""

import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup

# ── Configuración ──────────────────────────────────────────────────────────────
CURSOS_DIR = Path(r"D:\nacho\cursos_descargados")
# CURSOS_DIR = Path(r"C:\cursos_descargados")

DOMINIO_BASE = "cresciente.net"

# Carpetas dentro de CURSOS_DIR que NO son cursos
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
    return "Lección"


def extraer_nombre_curso(soup: BeautifulSoup) -> str:
    IGNORAR_TEXTOS = {"volver a curso", "volver al curso", "back to course"}
    for a in soup.find_all("a", href=True):
        texto = a.get_text(strip=True)
        if not texto or texto.lower() in IGNORAR_TEXTOS:
            continue
        if len(texto) > 3 and "/cursos/" in a.get("href", ""):
            if "lecciones" not in a["href"]:
                return texto
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return ""


def extraer_sidebar_items(soup: BeautifulSoup, curso_dir: Path, leccion_actual_dir: Path) -> list[dict]:
    """Lee el sidebar completo con separadores de sección y lecciones."""
    sidebar = (
        soup.find(class_="lms-lessions-list")
        or soup.find(class_="bb-lessons-list")
    )
    if not sidebar:
        return []

    ol = sidebar.find("ol") or sidebar
    items = []

    for li in ol.find_all("li", recursive=False):
        # Separador de sección
        seccion_el = li.find(class_="ld-lesson-section-heading")
        if seccion_el:
            items.append({"type": "seccion", "texto": seccion_el.get_text(strip=True)})

        # Lección
        a = li.find("a", class_="bb-lesson-head")
        if not a:
            continue
        href = a.get("href", "")
        titulo_el = li.find(class_="bb-lesson-title")
        texto = titulo_el.get_text(strip=True) if titulo_el else a.get_text(strip=True)

        if not texto or DOMINIO_BASE not in href or "/lecciones/" not in href:
            continue

        slug = slug_de_url(href)
        if not slug:
            continue

        carpeta = carpeta_para_slug(slug, curso_dir)
        if carpeta:
            rel = Path("..") / carpeta.name / "visor.html"
            es_actual = carpeta == leccion_actual_dir
            items.append({"type": "leccion", "texto": texto, "href": str(rel).replace("\\", "/"), "es_actual": es_actual, "carpeta": carpeta})
        else:
            items.append({"type": "leccion", "texto": texto, "href": None, "es_actual": False, "carpeta": None})

    return items


def extraer_materiales(soup: BeautifulSoup, leccion_dir: Path) -> list[dict]:
    """Extrae materiales de descarga desde el HTML: archivos locales y links a Drive."""
    from urllib.parse import urlparse as _urlparse
    contenedor = soup.find(class_="learndash_content_wrap")
    if not contenedor:
        return []

    EXT_DESCARGA = {".pdf", ".mscz", ".zip", ".docx", ".xlsx", ".mp3", ".pptx"}
    IGNORAR_TEXTOS = {"descarga", "download", "descargar", "respuesta", "cancelar la respuesta", ""}
    mat_dir = leccion_dir / "materiales"
    vistos = set()
    mats = []

    for a in contenedor.find_all("a", href=True):
        href = a["href"]
        texto = a.get_text(strip=True)
        if href in vistos or not href:
            continue
        if texto.lower() in IGNORAR_TEXTOS:
            continue
        vistos.add(href)

        # Google Drive
        if "drive.google.com" in href or "docs.google.com" in href:
            nombre = texto if len(texto) > 3 else "Archivo en Drive"
            mats.append({"nombre": nombre, "href": href, "ext": "DRIVE", "local": False})
            continue

        # Archivo en wp-content/uploads
        if "cresciente.net" in href and "wp-content/uploads" in href:
            ext = Path(_urlparse(href).path).suffix.lower()
            if ext not in EXT_DESCARGA:
                continue
            nombre_archivo = Path(_urlparse(href).path).name
            local_path = mat_dir / nombre_archivo if mat_dir.exists() else None
            nombre_display = texto if len(texto) > 3 and texto.lower() not in IGNORAR_TEXTOS else Path(nombre_archivo).stem.replace("-", " ").replace("_", " ")
            if local_path and local_path.exists():
                mats.append({"nombre": nombre_display, "href": f"materiales/{nombre_archivo}", "ext": ext.lstrip(".").upper(), "local": True})
            else:
                mats.append({"nombre": nombre_display, "href": href, "ext": ext.lstrip(".").upper(), "local": False})

    return mats



def resolver_link_leccion(href: str, leccion_dir: Path, cursos_dir: Path) -> str | None:
    """
    Dado un link a una lección en cresciente.net, intenta resolverlo
    a una ruta relativa local apuntando al visor.html correspondiente.
    Busca en toda la estructura de cursos_dir.
    Retorna la ruta relativa o None si no se encuentra.
    """
    from urllib.parse import urlparse, unquote
    parsed = urlparse(href)
    path = parsed.path.rstrip("/")
    partes = path.strip("/").split("/")

    # Extraer curso-slug y leccion-slug
    try:
        idx_cursos = next(i for i, p in enumerate(partes) if p in ("cursos", "curso"))
        curso_slug = partes[idx_cursos + 1]
        idx_lec = partes.index("lecciones")
        leccion_slug = unquote(partes[idx_lec + 1])
    except (StopIteration, ValueError, IndexError):
        return None

    # Buscar la carpeta del curso
    curso_dir_target = cursos_dir / curso_slug
    if not curso_dir_target.exists():
        return None

    # Buscar la carpeta de la lección
    carpeta = carpeta_para_slug(leccion_slug, curso_dir_target)
    if not carpeta:
        return None

    visor = carpeta / "visor.html"
    if not visor.exists():
        return None

    # Calcular ruta relativa desde leccion_dir hasta el visor
    try:
        rel = visor.relative_to(leccion_dir.parent.parent)
        # leccion_dir está en cursos_dir/curso/leccion/
        # visor está en cursos_dir/curso_target/leccion_target/visor.html
        # ruta relativa: desde leccion_dir subir dos niveles y bajar
        rel = Path("../..") / curso_slug / carpeta.name / "visor.html"
        return str(rel).replace("\\", "/")
    except Exception:
        return None

def extraer_contenido(soup: BeautifulSoup, leccion_dir: Path = None, cursos_dir: Path = None) -> str:
    contenedor = soup.find(class_="learndash_content_wrap")
    if not contenedor:
        contenedor = (
            soup.find(id="learndash-page-content")
            or soup.find(class_="ld-tab-content")
            or soup.find(class_="entry-content")
        )
    if not contenedor:
        return "<p><em>No se encontró contenido en este archivo.</em></p>"

    for tag in contenedor.find_all(["form", "button"]):
        tag.decompose()
    for cls in ["ld-focus-comments", "ld-content-actions", "learndash-wrapper",
                "comment-respond", "comments-area", "ld-comments"]:
        for el in contenedor.find_all(class_=cls):
            el.decompose()
    for el in contenedor.find_all(["p", "div"]):
        texto = el.get_text(strip=True).lower()
        if "debes estar conectado" in texto or "must be logged in" in texto:
            el.decompose()

    # Eliminar texto fallback de video que no debería verse
    for el in contenedor.find_all(string=lambda t: t and "tu navegador no soporta video" in t.lower()):
        el.extract()

    # Agregar clase "partitura" a figures que contienen imágenes de partituras (.webp, materiales)
    for fig in contenedor.find_all("figure"):
        img = fig.find("img")
        if img:
            src = img.get("src", "")
            if "materiales/" in src or src.endswith(".webp") or "partitura" in src.lower():
                existing = fig.get("class", [])
                if "partitura" not in existing:
                    fig["class"] = existing + ["partitura"]

    for a in contenedor.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"):
            continue
        # Intentar resolver links a otras lecciones localmente
        if "/lecciones/" in href and leccion_dir and cursos_dir:
            local = resolver_link_leccion(href, leccion_dir, cursos_dir)
            if local:
                a["href"] = local
                a["class"] = a.get("class", []) + ["link-local"]
                continue
        if "materiales/" not in href:
            a["target"] = "_blank"
            a["class"] = a.get("class", []) + ["link-externo"]

    return str(contenedor)



def extraer_comentarios(soup: BeautifulSoup) -> list[dict]:
    """Extrae comentarios del HTML si existen."""
    seccion = soup.find(class_="ld-focus-comments")
    if not seccion:
        return []
    comentarios = []
    for div in seccion.find_all(class_="comment"):
        # Autor
        autor_el = div.find(class_="ld-comment-author-name")
        autor = autor_el.get_text(strip=True) if autor_el else "Anónimo"
        # Es admin/profe?
        classes = " ".join(div.get("class", []))
        es_admin = "bypostauthor" in classes or "comment-author-admin" in classes
        # Fecha
        fecha_els = div.find(class_="ld-comment-permalink")
        if fecha_els:
            spans = fecha_els.find_all("span")
            fecha = " ".join(s.get_text(strip=True) for s in spans if s.get_text(strip=True))
        else:
            fecha = ""
        # Cuerpo
        cuerpo_el = div.find(class_="ld-comment-body")
        if not cuerpo_el:
            continue
        # Sacar el link de responder
        for a in cuerpo_el.find_all(class_="ld-comment-reply"):
            a.decompose()
        cuerpo = cuerpo_el.get_text(strip=True)
        if not cuerpo:
            continue
        # Profundidad (indentación para respuestas)
        depth = 1
        for cls in div.get("class", []):
            if cls.startswith("depth-"):
                depth = int(cls.split("-")[1])
                break
        comentarios.append({
            "autor": autor,
            "fecha": fecha,
            "cuerpo": cuerpo,
            "es_admin": es_admin,
            "depth": depth,
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

/* ── Sidebar ── */
#sidebar {
  width: 280px;
  min-width: 240px;
  max-width: 320px;
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

#sidebar-header .label-curso {
  font-size: 0.68rem;
  color: var(--accent2);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 4px;
}

#sidebar-header .nombre-curso {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text);
  line-height: 1.3;
  margin-bottom: 10px;
}

#sidebar-header .nombre-leccion {
  font-size: 0.82rem;
  color: var(--text-muted);
  border-top: 1px solid var(--border);
  padding-top: 8px;
  margin-top: 2px;
}

#nav-lecciones {
  flex: 1;
  padding: 10px 0;
  overflow-y: auto;
}

#nav-lecciones .seccion-titulo {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  padding: 8px 16px 4px;
}

#nav-lecciones a,
#nav-lecciones .no-descargada {
  display: block;
  padding: 8px 16px;
  font-size: 0.86rem;
  color: var(--text-muted);
  text-decoration: none;
  border-left: 3px solid transparent;
  transition: all 0.15s;
}

#nav-lecciones a:hover {
  background: rgba(233,69,96,0.08);
  color: var(--text);
  border-left-color: var(--accent);
}

#nav-lecciones a.actual {
  color: var(--text);
  border-left-color: var(--accent);
  background: rgba(233,69,96,0.12);
  font-weight: 600;
}

#nav-lecciones .no-descargada {
  opacity: 0.4;
  font-style: italic;
  cursor: default;
}

#sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.btn-nav {
  display: block;
  padding: 8px 12px;
  border-radius: 6px;
  text-decoration: none;
  font-size: 0.82rem;
  font-weight: 500;
  text-align: center;
  transition: background 0.15s;
}

.btn-curso {
  background: rgba(245,166,35,0.12);
  color: var(--accent2);
  border: 1px solid rgba(245,166,35,0.3);
}
.btn-curso:hover { background: rgba(245,166,35,0.22); }

.btn-menu {
  background: rgba(233,69,96,0.10);
  color: var(--accent);
  border: 1px solid rgba(233,69,96,0.3);
}
.btn-menu:hover { background: rgba(233,69,96,0.20); }

/* ── Área principal ── */
#main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* Header de lección con titulo y nav anterior/siguiente */
#leccion-header {
  padding: 20px 40px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--sidebar-bg);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

#leccion-header h1 {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--text);
  flex: 1;
  min-width: 0;
}

.nav-prev-next {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.btn-prev-next {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 14px;
  border-radius: 6px;
  text-decoration: none;
  font-size: 0.82rem;
  font-weight: 500;
  background: var(--card-bg);
  color: var(--text-muted);
  border: 1px solid var(--border);
  transition: all 0.15s;
}

.btn-prev-next:hover {
  border-color: var(--accent);
  color: var(--text);
}

.btn-prev-next.disabled {
  opacity: 0.3;
  cursor: default;
  pointer-events: none;
}

/* Contenido */
#contenido-wrap {
  flex: 1;
  padding: 28px 40px;
  overflow-y: auto;
  max-width: 960px;
}

#contenido-leccion video {
  width: 100%;
  max-width: 860px;
  border-radius: 8px;
  margin: 16px 0;
  background: #000;
}

#contenido-leccion figure {
  margin: 16px 0;
}

#contenido-leccion p {
  margin: 12px 0;
  color: var(--text);
}

#contenido-leccion a {
  color: var(--accent2);
  word-break: break-all;
}

#contenido-leccion a.link-externo::after {
  content: " ↗";
  font-size: 0.75em;
  opacity: 0.7;
}

#contenido-leccion a.link-local {
  color: var(--accent);
}

#contenido-leccion a.link-local::after {
  content: " →";
  font-size: 0.75em;
  opacity: 0.7;
}

#contenido-leccion .wp-block-buttons { margin: 16px 0; }

#contenido-leccion .wp-block-button__link {
  display: inline-block;
  padding: 10px 20px;
  background: rgba(245,166,35,0.12);
  border: 1px solid rgba(245,166,35,0.4);
  border-radius: 6px;
  color: var(--accent2) !important;
  text-decoration: none;
  font-weight: 500;
}
#contenido-leccion .wp-block-button__link:hover {
  background: rgba(245,166,35,0.22);
}

/* Materiales */
#materiales {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}

#materiales h2 {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 12px;
}

.mat-lista {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.mat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: var(--card-bg);
  border-radius: 6px;
  text-decoration: none;
  color: var(--text);
  font-size: 0.86rem;
  border: 1px solid var(--border);
  transition: border-color 0.15s;
}

.mat-item:hover { border-color: var(--accent2); color: var(--accent2); }

.mat-ext {
  font-size: 0.68rem;
  font-weight: 700;
  padding: 2px 5px;
  border-radius: 3px;
  background: rgba(233,69,96,0.2);
  color: var(--accent);
}
.mat-ext.drive {
  background: rgba(66,133,244,0.2);
  color: #4285f4;
}

/* Audio ancho completo */
#contenido-leccion audio {
  width: 100%;
  max-width: 860px;
  display: block;
  margin: 12px 0;
}

/* Imágenes de partitura (fondo blanco para transparencias) */
#contenido-leccion figure.partitura img,
#contenido-leccion figure img[src*=".webp"],
#contenido-leccion figure img[src*="materiales"] {
  background: #fff;
  border-radius: 4px;
  padding: 8px;
  max-width: 100%;
}

/* Suprimir UI de tabs del original (solo mostrar contenido) */
#contenido-leccion .ld-tabs-navigation { display: none !important; }
#contenido-leccion .ld-tab-content { display: block !important; }

/* Ocultar restos del original */
#contenido-leccion .learndash-wrapper,
#contenido-leccion .ld-focus-comments,
#contenido-leccion .ld-content-actions,
#contenido-leccion form { display: none !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }


/* Comentarios */
#comentarios {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}
#comentarios h2 {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 16px;
}
.comentario {
  margin-bottom: 12px;
  padding: 12px 16px;
  border-radius: 6px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-left: 3px solid var(--border);
}
.comentario.es-admin {
  border-left-color: var(--accent2);
  background: rgba(245,166,35,0.05);
}
.comentario.depth-2 { margin-left: 24px; }
.comentario.depth-3 { margin-left: 48px; }
.comentario-header {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 6px;
}
.comentario-autor {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text);
}
.comentario.es-admin .comentario-autor {
  color: var(--accent2);
}
.comentario-fecha {
  font-size: 0.75rem;
  color: var(--text-muted);
}
.comentario-cuerpo {
  font-size: 0.88rem;
  color: var(--text);
  line-height: 1.5;
}
@media (max-width: 700px) {
  body { flex-direction: column; }
  #sidebar { width: 100%; height: auto; position: static; }
  #leccion-header { padding: 16px 20px; }
  #contenido-wrap { padding: 20px; }
}
"""


def generar_visor(leccion_dir: Path, curso_dir: Path) -> bool:
    index_path = leccion_dir / "index.html"
    if not index_path.exists():
        return False

    with open(index_path, encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    titulo        = extraer_titulo(soup)
    nombre_curso  = extraer_nombre_curso(soup)
    comentarios    = extraer_comentarios(soup)   # antes de extraer_contenido (que hace decompose)
    contenido_html = extraer_contenido(soup, leccion_dir=leccion_dir, cursos_dir=CURSOS_DIR)
    sidebar_items  = extraer_sidebar_items(soup, curso_dir, leccion_dir)
    materiales     = extraer_materiales(soup, leccion_dir)

    # ── Anterior / Siguiente ─────────────────────────────────────────────────
    # Solo los items que tienen href (lecciones descargadas)
    items_nav = [it for it in sidebar_items if it.get("type") == "leccion" and it["href"]]
    idx_actual = next((i for i, it in enumerate(items_nav) if it["es_actual"]), None)

    if idx_actual is not None and idx_actual > 0:
        prev_href = items_nav[idx_actual - 1]["href"]
        btn_prev = f'<a href="{prev_href}" class="btn-prev-next">◀ Anterior</a>'
    else:
        btn_prev = '<span class="btn-prev-next disabled">◀ Anterior</span>'

    if idx_actual is not None and idx_actual < len(items_nav) - 1:
        next_href = items_nav[idx_actual + 1]["href"]
        btn_next = f'<a href="{next_href}" class="btn-prev-next">Siguiente ▶</a>'
    else:
        btn_next = '<span class="btn-prev-next disabled">Siguiente ▶</span>'

    # ── Sidebar HTML ─────────────────────────────────────────────────────────
    if sidebar_items:
        items_html = ""
        for item in sidebar_items:
            if item["type"] == "seccion":
                items_html += f'<div class="seccion-titulo">{item["texto"]}</div>\n'
            else:
                if item["href"]:
                    cls = ' class="actual"' if item["es_actual"] else ""
                    items_html += f'<a href="{item["href"]}"{cls}>{item["texto"]}</a>\n'
                else:
                    items_html += f'<span class="no-descargada">{item["texto"]}</span>\n'
    else:
        items_html = '<div class="seccion-titulo">Sin índice disponible</div>'

    # ── Materiales HTML ──────────────────────────────────────────────────────
    # ── Comentarios HTML ────────────────────────────────────────────────────
    if comentarios:
        items_com = ""
        for c in comentarios:
            admin_cls = " es-admin" if c["es_admin"] else ""
            depth_cls = f" depth-{c['depth']}" if c["depth"] > 1 else ""
            items_com += (
                f'<div class="comentario{admin_cls}{depth_cls}">'
                f'<div class="comentario-header">'
                f'<span class="comentario-autor">{c["autor"]}</span>'
                f'<span class="comentario-fecha">{c["fecha"]}</span>'
                f'</div>'
                f'<div class="comentario-cuerpo">{c["cuerpo"]}</div>'
                f'</div>'
            )
        coms_html = f'<div id="comentarios"><h2>Comentarios ({len(comentarios)})</h2>{items_com}</div>'
    else:
        coms_html = ""

    if materiales:
        mats_items = ""
        for m in materiales:
            target = 'target="_blank"' if not m.get("local") else ""
            ext_cls = "mat-ext drive" if m["ext"] == "DRIVE" else "mat-ext"
            mats_items += f'<a href="{m["href"]}" class="mat-item" {target}><span class="{ext_cls}">{m["ext"]}</span>{m["nombre"]}</a>'
        mats_html = f'<div id="materiales"><h2>Materiales</h2><div class="mat-lista">{mats_items}</div></div>'
    else:
        mats_html = ""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{titulo} — {nombre_curso}</title>
<style>{CSS}</style>
</head>
<body>

<nav id="sidebar">
  <div id="sidebar-header">
    <div class="label-curso">Curso</div>
    <div class="nombre-curso">{nombre_curso}</div>
    <div class="nombre-leccion">{titulo}</div>
  </div>
  <div id="nav-lecciones">
    {items_html}
  </div>
  <div id="sidebar-footer">
    <a href="../visor_curso.html" class="btn-nav btn-curso">📚 Volver al curso</a>
    <a href="../../visor_menu.html" class="btn-nav btn-menu">🏠 Menú principal</a>
  </div>
</nav>

<div id="main">
  <div id="leccion-header">
    <h1>{titulo}</h1>
    <div class="nav-prev-next">
      {btn_prev}
      {btn_next}
    </div>
  </div>

  <div id="contenido-wrap">
    <div id="contenido-leccion">
      {contenido_html}
    </div>
    {mats_html}
    {coms_html}
  </div>
</div>

<script>
document.addEventListener("DOMContentLoaded", function() {{
  var actual = document.querySelector("#nav-lecciones a.actual");
  if (actual) {{ actual.scrollIntoView({{ block: "center", behavior: "instant" }}); }}
}});
</script>
</body>
</html>"""

    visor_path = leccion_dir / "visor.html"
    with open(visor_path, "w", encoding="utf-8") as f:
        f.write(html)

    return True


def main():
    if not CURSOS_DIR.exists():
        print(f"[error] No se encontró: {CURSOS_DIR}")
        sys.exit(1)

    print(f"\n{'═'*60}")
    print(f"  Generador de visor.html")
    print(f"  Cursos en: {CURSOS_DIR}")
    print(f"{'═'*60}")

    total_ok = 0
    total_sin_index = 0
    total_cursos = 0

    for curso_dir in sorted(CURSOS_DIR.iterdir()):
        if not curso_dir.is_dir():
            continue
        if curso_dir.name in EXCLUIR_DIRS:
            print(f"\n  ⏭  {curso_dir.name}  (excluido)")
            continue

        lecciones = sorted([
            d for d in curso_dir.iterdir()
            if d.is_dir() and "lecciones" in PREFIJO_RE.sub("", d.name)
        ])
        if not lecciones:
            continue

        total_cursos += 1
        ok = 0
        sin_index = 0
        print(f"\n  📂 {curso_dir.name}  ({len(lecciones)} lecciones)")

        for leccion_dir in lecciones:
            resultado = generar_visor(leccion_dir, curso_dir)
            if resultado:
                ok += 1
                print(f"    ✓  {leccion_dir.name}")
            else:
                sin_index += 1
                print(f"    ✗  {leccion_dir.name}  (sin index.html)")

        total_ok += ok
        total_sin_index += sin_index

    print(f"\n{'═'*60}")
    print(f"  📊 RESUMEN")
    print(f"{'═'*60}")
    print(f"  Cursos procesados : {total_cursos}")
    print(f"  visor.html creados: {total_ok}")
    if total_sin_index:
        print(f"  Sin index.html    : {total_sin_index}")
    print(f"{'═'*60}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR FATAL] {e}")
        raise
    finally:
        input("\nPresioná Enter para cerrar...")
