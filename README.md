# Proyecto de Descarga de Cursos

Este script automatiza la descarga de videos y materiales adjuntos de lecciones web, organizándolos en carpetas por curso y lección.

## ⚠️ Requisitos Previos

Para que los scripts funcionen, **debes crear manualmente** estos dos archivos en la carpeta principal:

1. **links.txt**: 
   - Debe contener una URL válida por línea.
   - El script leerá este archivo de arriba hacia abajo para procesar cada lección.

2. **cookies.txt**: 
   - Debe contener las cookies de sesión exportadas en formato *Netscape HTTP Cookie File* (7 columnas separadas por tabulaciones).
   - Es estrictamente necesario para que el script (y yt-dlp) puedan acceder al contenido protegido saltando el inicio de sesión.
   - **Nota de seguridad:** Este archivo está ignorado en Git para evitar filtrar credenciales.

## Dependencias
- Librerías de Python: equests, eautifulsoup4
- Software externo: yt-dlp (debe estar instalado y accesible desde las variables de entorno / PATH).
