# Define la ruta raíz donde buscar
$rutaBase = "D:\nacho\cursos_descargados"

# Nombre exacto del archivo a eliminar
$archivoBuscado = "_descarga_completa.txt"

# ------------------------------------------------
# OPCIÓN 1: SOLO PREVISUALIZAR (MÁS SEGURO)
# Muestra qué archivos se eliminarían, pero NO los borra.
# ------------------------------------------------
# Write-Host "`n--- PREVISUALIZACIÓN: Archivos que se eliminarán ---" -ForegroundColor Cyan
# Get-ChildItem -Path $rutaBase -Filter $archivoBuscado -Recurse -File | 
#     Select-Object FullName |
#     Format-Table -AutoSize

# ------------------------------------------------
# OPCIÓN 2: ELIMINAR PIDIENDO CONFIRMACIÓN (RECOMENDADA)
# Te preguntará archivo por archivo (Sí/No/Todos).
# Descomenta la línea de abajo y comenta la OPCIÓN 1 para usarla.
# ------------------------------------------------
Get-ChildItem -Path $rutaBase -Filter $archivoBuscado -Recurse -File | 
    Remove-Item -Confirm

# ------------------------------------------------
# OPCIÓN 3: ELIMINAR DIRECTAMENTE (SIN PREGUNTAR)
# Úsala SOLO si ya revisaste la previsualización y estás seguro.
# Descomenta la línea de abajo y comenta las demás para usarla.
# ------------------------------------------------
# Get-ChildItem -Path $rutaBase -Filter $archivoBuscado -Recurse -File | 
#     Remove-Item -Force

Write-Host "`nScript finalizado." -ForegroundColor Green