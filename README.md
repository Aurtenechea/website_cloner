# Cresciente — Sistema de descarga y visualización offline

Scripts para descargar los cursos de [cresciente.net](https://cresciente.net) y navegarlos sin conexión a internet.

---

## Estructura de archivos generada

```
cursos_descargados/
├── visor_menu.html                  ← Menú principal con todos los cursos
├── cursos-online-musica/            ← Carpeta del HTML del menú del sitio
│   └── Cursos_Online_de_...htm
│
└── [curso-slug]/                    ← Una carpeta por curso
    ├── index_raw.html               ← Página del curso original (sin modificar)
    ├── index.html                   ← Página del curso con videos locales
    ├── visor_curso.html             ← Visor del curso (generado)
    ├── videos/                      ← Videos de la portada del curso
    │
    └── [NN_]lecciones_[slug]/       ← Una carpeta por lección (NN = orden)
        ├── index_raw.html           ← Lección original (sin modificar)
        ├── index.html               ← Lección con videos locales
        ├── visor.html               ← Visor de la lección (generado)
        ├── _descarga_completa.txt   ← Centinela: lección 100% descargada
        └── materiales/              ← PDFs, partituras, imágenes
```

---

## Scripts

### 1. `generar_links_cursos.py`
Entra a la página del catálogo del sitio y extrae las URLs de todos los cursos disponibles. Guarda el resultado en un archivo `.txt` (una URL por línea).

**Configurar:**
- `URL_CATALOGO` — URL de la página de catálogo
- `OUTPUT_FILE` — dónde guardar el archivo de links
- `COOKIES_FILE` — archivo de cookies del navegador

**Correr antes de:** `descargar_curso.py`

---

### 2. `extraer_links_lecciones.py`
*(antes: `indice2.py`)*

Entra a la página de un curso específico, lee el sidebar de lecciones y guarda la lista de URLs en un archivo `.txt`.

**Configurar:**
- `URL_CURSO` — URL de la página principal del curso
- `LINKS_FILE` — dónde guardar el archivo de links
- `COOKIES_FILE` — archivo de cookies del navegador

**Correr antes de:** `descargar_lecciones.py`

---

### 3. `descargar_lecciones.py`
*(antes: `descarga_deepseek7-1.py`)*

Descarga cada lección: guarda el HTML original (`index_raw.html`), reemplaza los iframes de video por `<video>` local, descarga los videos con `yt-dlp`, y descarga los materiales (PDFs, etc.).

Crea `_descarga_completa.txt` **solo si todo salió bien**.
Si ya existe `_descarga_completa.txt` en una lección, la saltea.

**Configurar:**
- `LINKS_FILES` — lista de archivos `.txt` con URLs de lecciones
- `CURSOS_DIR` — carpeta raíz donde se guardan los cursos
- `COOKIES_FILE` — archivo de cookies del navegador

**Requiere:** `yt-dlp` instalado (`pip install yt-dlp`)

---

### 4. `ordenar_lecciones.py`
*(antes: `ordenar_cursos7.py`)*

Renombra las carpetas de lecciones agregando un prefijo numérico (`001_`, `002_`, etc.) según el orden real del curso obtenido desde el sitio web.

Ejemplo: `lecciones_clase-1` → `001_lecciones_clase-1`

Tolerante a prefijos ya existentes. Se puede correr varias veces sin problema.

**Configurar:**
- `LINKS_FILES` — lista de archivos `.txt` con la URL del curso (primera línea no comentada)
- `CURSOS_DIR` — carpeta raíz de cursos

---

### 5. `chequear_lecciones.py`
*(antes: `chequear_cursos10.py`)*

Recorre los cursos y reporta el estado de cada lección: si está descargada, si tiene videos, si el centinela está presente. Útil para detectar descargas incompletas.

**Configurar:**
- `CURSOS_DIR` — carpeta raíz de cursos

---

### 6. `descargar_curso.py`

Descarga la página principal de cada curso (portada con descripción, video introductorio y lista de lecciones). Guarda `index_raw.html` e `index.html` (con video local reemplazado). Acepta lista de slugs o archivo de URLs.

**Configurar:**
- `CURSOS_SLUGS` — lista de slugs de cursos, o
- `CURSOS_URLS_FILE` — path a archivo con URLs (si se define, ignora CURSOS_SLUGS)
- `CURSOS_DIR` — carpeta raíz de cursos
- `COOKIES_FILE` — archivo de cookies

**Correr antes de:** `generar_visor_curso.py`

---

### 7. `generar_visor.py`

Lee el `index.html` de cada lección y genera un `visor.html` limpio con:
- Sidebar izquierdo con lista de lecciones y separadores de módulo
- Botones Anterior / Siguiente
- Video local
- Contenido de la lección (texto, imágenes, partituras con fondo blanco)
- Links a otras lecciones resueltos a rutas locales cuando es posible
- Materiales de descarga (PDFs, MSCZ, links a Drive)
- Comentarios

**Configurar:**
- `CURSOS_DIR` — carpeta raíz de cursos
- `EXCLUIR_DIRS` — carpetas que no son cursos (ej. `cursos-online-musica`)

---

### 8. `generar_visor_curso.py`

Lee el `index.html` de la raíz de cada curso y genera `visor_curso.html` con:
- Sidebar izquierdo con lista completa de lecciones y separadores de módulo
- Video introductorio local
- Descripción del curso formateada
- Estadísticas (lecciones descargadas, módulos)
- Comentarios de la página del curso

**Configurar:**
- `CURSOS_DIR` — carpeta raíz de cursos

**Requiere:** haber corrido `descargar_curso.py` y `generar_visor.py` primero.

---

### 9. `generar_visor_menu.py`

Genera `visor_menu.html` en la raíz de `CURSOS_DIR`. Lee el HTML del menú del sitio para obtener títulos y orden de cursos, verifica cuáles están descargados localmente y los agrupa por categoría (Núcleo, Complementarios, Minicursos, Seminarios) con filtros interactivos.

**Configurar:**
- `CURSOS_DIR` — carpeta raíz de cursos
- `MENU_HTML` — path al archivo `.htm` del menú del sitio descargado

---

## Scripts deprecados

Estos scripts ya no se usan — su funcionalidad fue reemplazada por los scripts nuevos:

| Script | Reemplazado por |
|---|---|
| `creador_de_index_indice10.py` | `generar_visor.py` + `descargar_curso.py` |
| `creador_de_index_indice_de_cursos4.py` | ídem (versión anterior) |
| `creador_de_index_cursos_claude.py` | `descargar_curso.py` (versión incompleta) |

---

## Orden de ejecución recomendado

```
Para obtener la lista de cursos disponibles:
  1. generar_links_cursos.py      → lista de URLs de todos los cursos

Para descargar un curso nuevo:
  2. extraer_links_lecciones.py   → genera el .txt de URLs de lecciones
  3. descargar_lecciones.py       → descarga HTML y videos de cada lección
  4. ordenar_lecciones.py         → numera las carpetas en orden

Para la portada del curso:
  5. descargar_curso.py           → descarga la página principal del curso

Para generar los visores offline:
  6. generar_visor.py             → crea visor.html en cada lección
  7. generar_visor_curso.py       → crea visor_curso.html en cada curso
  8. generar_visor_menu.py        → crea visor_menu.html raíz

Para verificar descargas:
     chequear_lecciones.py        → reporte de estado
```

**Punto de entrada:** abrir `visor_menu.html` en el navegador.

---

## Dependencias

```
pip install requests beautifulsoup4 yt-dlp
```

Cookies del navegador exportadas en formato Netscape (extensión "Get cookies.txt").

---

## Notas

- Los scripts son **no destructivos**: nunca borran archivos existentes, solo crean o renombran.
- `generar_visor.py`, `generar_visor_curso.py` y `generar_visor_menu.py` se pueden re-correr en cualquier momento para regenerar los visores con mejoras.
- Los visores funcionan 100% offline una vez generados. Los links a Drive y sitios externos se abren en el navegador si hay conexión.
- Las imágenes de partituras (`.webp` transparentes) se muestran con fondo blanco automáticamente.
- Los links dentro del contenido de una lección que apuntan a otras lecciones del sitio se resuelven automáticamente a rutas locales cuando el destino está descargado.
