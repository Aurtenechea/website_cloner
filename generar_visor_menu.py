"""
generar_visor_menu.py
=====================
Genera visor_menu.html en la raíz de CURSOS_DIR.
Lee el HTML del menú del sitio original para obtener títulos y orden de cursos,
luego verifica cuáles están descargados localmente.
Agrupa por categoría con filtro interactivo.

Fuente de datos: el archivo .htm descargado del menú del sitio
(Cursos_Online_de_Composición_Musical___Cresciente__Academia_Online.htm)
o el que configures en MENU_HTML.
"""

import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup

# ── Configuración ──────────────────────────────────────────────────────────────
CURSOS_DIR = Path(r"D:\nacho\cursos_descargados")
# CURSOS_DIR = Path(r"C:\cursos_descargados")

# Archivo HTML del menú del sitio (guardalo donde quieras)
MENU_HTML = Path(r"D:\nacho\cursos_descargados\cursos-online-musica\Cursos_Online_de_Composición_Musical___Cresciente__Academia_Online.htm")

EXCLUIR_DIRS = {"cursos-online-musica"}
# ──────────────────────────────────────────────────────────────────────────────

# Categorías del sitio original
CATEGORIAS = [
    # Núcleo: los tres ciclos principales
    ("Núcleo", lambda s, t: s.startswith("ciclo-")),

    # Minicursos: cursos breves específicos
    ("Minicursos", lambda s, t: any(k in s for k in [
        "cc0-a-sistema",        # Sistema de estudio y organización
        "experimentos-creativos",
        "musescore",
        "teoria-musical-basica-en-capsulas",
        "c1c-voz-y-cuerpo",
    ])),

    # Complementarios: cursos largos de apoyo
    ("Complementarios", lambda s, t: any(k in s for k in [
        "teoria-musical-basica-en-50",
        "lecto-escritura",
        "audioperceptiva",
        "armonia-aplicada-a-la-guitarra-1",
        "cc-armonia-aplicada-al-piano",
        "introduccion-a-la-produccion",
        "cc1-e-contrapunto",
        "armonia-modal-aplicada-a-la-composicion",
    ])),

    # Seminarios: todo lo demás (sesiones cortas, intensivos, talleres)
    ("Seminarios", lambda s, t: True),
]
CATEGORIA_DEFAULT = "Seminarios"


def slug_desde_url(url: str) -> str:
    partes = url.rstrip("/").split("/cursos/")
    if len(partes) < 2:
        return ""
    resto = partes[-1].rstrip("/")
    # Solo el primer segmento (slug del curso, no de la lección)
    return resto.split("/")[0]


def categorizar(slug: str, titulo: str) -> str:
    slug_lower = slug.lower()
    titulo_lower = titulo.lower()
    for nombre, fn in CATEGORIAS:
        if fn(slug_lower, titulo_lower):
            return nombre
    return CATEGORIA_DEFAULT


def extraer_cursos_del_menu(menu_html: Path) -> list[dict]:
    """Lee el HTML del menú y extrae la lista de cursos en orden."""
    with open(menu_html, encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    vistos = set()
    cursos = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/cursos/" not in href:
            continue
        if "Ir al curso" in a.get_text():
            continue
        # Solo links a la raíz del curso (sin /lecciones/)
        if "/lecciones/" in href:
            continue

        titulo = a.get_text(strip=True)
        if not titulo or len(titulo) < 4:
            continue

        slug = slug_desde_url(href)
        if not slug or slug in vistos:
            continue
        vistos.add(slug)

        cursos.append({
            "titulo": titulo,
            "slug": slug,
            "categoria": categorizar(slug, titulo),
        })

    return cursos


def enriquecer_con_local(cursos: list[dict], cursos_dir: Path) -> list[dict]:
    """Agrega info local: si está descargado, cuántas lecciones, etc."""
    # Mapear slugs a carpetas existentes
    carpetas_existentes = {d.name: d for d in cursos_dir.iterdir() if d.is_dir()}

    for curso in cursos:
        slug = curso["slug"]
        curso_dir = carpetas_existentes.get(slug)

        if curso_dir is None:
            curso.update({
                "descargado": False,
                "tiene_visor": False,
                "tiene_index": False,
                "n_lecciones": 0,
                "href": None,
            })
            continue

        visor = curso_dir / "visor_curso.html"
        index = curso_dir / "index.html"

        # Contar lecciones descargadas
        lecciones = [
            d for d in curso_dir.iterdir()
            if d.is_dir() and "lecciones" in re.sub(r'^\d+_', '', d.name)
            and (d / "visor.html").exists()
        ]

        curso.update({
            "descargado": True,
            "tiene_visor": visor.exists(),
            "tiene_index": index.exists(),
            "n_lecciones": len(lecciones),
            "href": f"{slug}/visor_curso.html" if visor.exists() else None,
        })

    return cursos


CSS = """
:root {
  --bg: #1a1a2e;
  --header-bg: #16213e;
  --card-bg: #0f3460;
  --card-hover: #1a4a80;
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
  min-height: 100vh;
  font-size: 16px;
  line-height: 1.6;
}

/* ── Header ── */
#header {
  background: var(--header-bg);
  border-bottom: 1px solid var(--border);
  padding: 24px 48px;
}

#header h1 {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 4px;
}

#header .subtitulo {
  color: var(--text-muted);
  font-size: 0.9rem;
}

/* ── Filtros ── */
#filtros {
  padding: 20px 48px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--border);
  background: var(--header-bg);
}

.filtro-btn {
  padding: 6px 16px;
  border-radius: 20px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  font-size: 0.82rem;
  cursor: pointer;
  transition: all 0.15s;
  font-family: var(--font);
}

.filtro-btn:hover {
  border-color: var(--accent);
  color: var(--text);
}

.filtro-btn.activo {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
  font-weight: 600;
}

/* ── Contenido ── */
#contenido {
  padding: 32px 48px;
}

.categoria-titulo {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--accent2);
  margin: 28px 0 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
}

.categoria-titulo:first-child { margin-top: 0; }

/* ── Grid de cursos ── */
.cursos-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
  margin-bottom: 8px;
}

/* ── Tarjeta de curso ── */
.curso-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 18px 20px;
  text-decoration: none;
  color: var(--text);
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: all 0.15s;
  cursor: pointer;
}

.curso-card:hover {
  background: var(--card-hover);
  border-color: var(--accent);
  transform: translateY(-2px);
}

.curso-card.no-descargado {
  opacity: 0.45;
  cursor: default;
  pointer-events: none;
}

.curso-card.no-visor {
  border-style: dashed;
  opacity: 0.7;
}

.curso-titulo {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text);
  line-height: 1.3;
}

.curso-meta {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.curso-badge {
  font-size: 0.7rem;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
}

.badge-ok {
  background: rgba(233,69,96,0.15);
  color: var(--accent);
  border: 1px solid rgba(233,69,96,0.3);
}

.badge-parcial {
  background: rgba(245,166,35,0.15);
  color: var(--accent2);
  border: 1px solid rgba(245,166,35,0.3);
}

.badge-no {
  background: rgba(144,144,160,0.15);
  color: var(--text-muted);
  border: 1px solid rgba(144,144,160,0.2);
}

.curso-lecciones {
  font-size: 0.78rem;
  color: var(--text-muted);
}

/* Stats globales */
#stats-globales {
  padding: 12px 48px;
  background: rgba(15,52,96,0.3);
  border-bottom: 1px solid var(--border);
  font-size: 0.82rem;
  color: var(--text-muted);
  display: flex;
  gap: 24px;
}

#stats-globales strong { color: var(--accent2); }

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

@media (max-width: 600px) {
  #header, #filtros, #contenido, #stats-globales { padding-left: 20px; padding-right: 20px; }
  .cursos-grid { grid-template-columns: 1fr; }
}
"""

JS = """
const categorias = new Set();
document.querySelectorAll('.curso-card').forEach(c => {
  categorias.add(c.dataset.cat);
});

const filtros = document.getElementById('filtros');

// Botón "Todos"
const btnTodos = document.createElement('button');
btnTodos.className = 'filtro-btn activo';
btnTodos.textContent = 'Todos';
btnTodos.dataset.cat = '';
filtros.appendChild(btnTodos);

// Un botón por categoría
categorias.forEach(cat => {
  const btn = document.createElement('button');
  btn.className = 'filtro-btn';
  btn.textContent = cat;
  btn.dataset.cat = cat;
  filtros.appendChild(btn);
});

// Botón solo descargados
const btnDesc = document.createElement('button');
btnDesc.className = 'filtro-btn';
btnDesc.textContent = '✓ Descargados';
btnDesc.dataset.cat = '__descargados__';
filtros.appendChild(btnDesc);

filtros.addEventListener('click', e => {
  const btn = e.target.closest('.filtro-btn');
  if (!btn) return;
  document.querySelectorAll('.filtro-btn').forEach(b => b.classList.remove('activo'));
  btn.classList.add('activo');
  const cat = btn.dataset.cat;
  filtrar(cat);
});

function filtrar(cat) {
  document.querySelectorAll('.categoria-seccion').forEach(sec => {
    let visible = 0;
    sec.querySelectorAll('.curso-card').forEach(card => {
      let mostrar = false;
      if (cat === '') mostrar = true;
      else if (cat === '__descargados__') mostrar = card.dataset.desc === '1';
      else mostrar = card.dataset.cat === cat;
      card.style.display = mostrar ? '' : 'none';
      if (mostrar) visible++;
    });
    // Ocultar sección si no tiene tarjetas visibles
    sec.style.display = visible > 0 ? '' : 'none';
  });
}
"""


def generar_menu(cursos: list[dict]) -> str:
    # Agrupar por categoría manteniendo orden de aparición
    orden_cats = []
    por_cat: dict[str, list] = {}
    for c in cursos:
        cat = c["categoria"]
        if cat not in por_cat:
            por_cat[cat] = []
            orden_cats.append(cat)
        por_cat[cat].append(c)

    # Stats
    total = len(cursos)
    descargados = sum(1 for c in cursos if c["descargado"])
    con_visor = sum(1 for c in cursos if c["tiene_visor"])
    total_lecciones = sum(c["n_lecciones"] for c in cursos)

    stats_html = (
        f'<strong>{total}</strong> cursos &nbsp;·&nbsp; '
        f'<strong>{descargados}</strong> descargados &nbsp;·&nbsp; '
        f'<strong>{con_visor}</strong> con visor &nbsp;·&nbsp; '
        f'<strong>{total_lecciones}</strong> lecciones'
    )

    # Tarjetas
    secciones_html = ""
    for cat in orden_cats:
        tarjetas = ""
        for c in por_cat[cat]:
            desc_attr = '1' if c["descargado"] else '0'

            if c["tiene_visor"]:
                badge = '<span class="curso-badge badge-ok">✓ Listo</span>'
                cls = "curso-card"
                tag_open = f'<a href="{c["href"]}" class="{cls}" data-cat="{cat}" data-desc="{desc_attr}">'
                tag_close = "</a>"
            elif c["descargado"] and c["tiene_index"]:
                badge = '<span class="curso-badge badge-parcial">~ Sin visor</span>'
                cls = "curso-card no-visor"
                tag_open = f'<div class="{cls}" data-cat="{cat}" data-desc="{desc_attr}">'
                tag_close = "</div>"
            elif c["descargado"]:
                badge = '<span class="curso-badge badge-parcial">↓ Descargado</span>'
                cls = "curso-card no-visor"
                tag_open = f'<div class="{cls}" data-cat="{cat}" data-desc="{desc_attr}">'
                tag_close = "</div>"
            else:
                badge = '<span class="curso-badge badge-no">✗ No descargado</span>'
                cls = "curso-card no-descargado"
                tag_open = f'<div class="{cls}" data-cat="{cat}" data-desc="{desc_attr}">'
                tag_close = "</div>"

            lec_txt = f'<span class="curso-lecciones">{c["n_lecciones"]} lecciones</span>' if c["n_lecciones"] else ""

            tarjetas += (
                f'{tag_open}'
                f'<div class="curso-titulo">{c["titulo"]}</div>'
                f'<div class="curso-meta">{badge}{lec_txt}</div>'
                f'{tag_close}\n'
            )

        secciones_html += (
            f'<div class="categoria-seccion" data-cat="{cat}">'
            f'<div class="categoria-titulo">{cat}</div>'
            f'<div class="cursos-grid">{tarjetas}</div>'
            f'</div>\n'
        )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cresciente — Mis Cursos</title>
<style>{CSS}</style>
</head>
<body>

<header id="header">
  <h1>🎵 Mis Cursos</h1>
  <div class="subtitulo">Cresciente: Academia Online — colección local</div>
</header>

<div id="stats-globales">{stats_html}</div>

<div id="filtros"></div>

<div id="contenido">
  {secciones_html}
</div>

<script>{JS}</script>
</body>
</html>"""


def main():
    if not CURSOS_DIR.exists():
        print(f"[error] No se encontró: {CURSOS_DIR}")
        sys.exit(1)

    print(f"\n{'═'*60}")
    print(f"  Generador de visor_menu.html")
    print(f"  Cursos en: {CURSOS_DIR}")
    print(f"{'═'*60}")

    # Leer menú del sitio si existe
    if MENU_HTML.exists():
        print(f"  Leyendo menú desde: {MENU_HTML.name}")
        cursos = extraer_cursos_del_menu(MENU_HTML)
        print(f"  Cursos encontrados en el menú: {len(cursos)}")
    else:
        print(f"  [aviso] No se encontró {MENU_HTML}")
        print(f"  Generando lista desde carpetas locales...")
        # Fallback: leer solo las carpetas locales
        cursos = []
        for d in sorted(CURSOS_DIR.iterdir()):
            if d.is_dir() and d.name not in EXCLUIR_DIRS and not d.name.startswith("."):
                titulo = d.name.replace("-", " ").title()
                cursos.append({
                    "titulo": titulo,
                    "slug": d.name,
                    "categoria": categorizar(d.name, titulo),
                })

    # Enriquecer con info local
    cursos = enriquecer_con_local(cursos, CURSOS_DIR)

    # Generar HTML
    html = generar_menu(cursos)

    salida = CURSOS_DIR / "visor_menu.html"
    salida.write_text(html, encoding="utf-8")
    print(f"\n  ✓ Generado: {salida}")

    desc = sum(1 for c in cursos if c["descargado"])
    visor = sum(1 for c in cursos if c["tiene_visor"])
    print(f"  Descargados : {desc}/{len(cursos)}")
    print(f"  Con visor   : {visor}/{len(cursos)}")
    print(f"{'═'*60}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR FATAL] {e}")
        raise
    finally:
        input("\nPresioná Enter para cerrar...")
