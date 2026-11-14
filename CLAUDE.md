# Instrucciones para Claude en esta app

Antes de trabajar, lee estos dos archivos y cúmplelos sin preguntarle a fabian lo que ya dicen:
1. `REGLAS_FIJAS_VIDEOS.md`: voces (Mauricio `94zOad0g7T7K4oa7zhDq`, Brian `nPczCjzI2devNBz1zQrb`), emociones, círculos,
   páginas, cierre con play, contacto, Honor y portadas.
2. `AGENTS.md`: cómo funciona la app, paso a paso, y todas las decisiones del autor.

Responde a fabian en español, corto y simple. Antes de gastar créditos (ElevenLabs, GPT, HeyGen), pídele su «SI» escrito.

## Versión de la app y zip de actualización (fabian, 14-nov-2026)
- La app muestra su versión arriba («APP v1.5.0»), leída del archivo `VERSION`. **Cada cambio que llegue a la rama de la app
  sube `VERSION`**: arreglo o ajuste = último número (1.5.0 → 1.5.1); módulo nuevo = número del medio (1.5.x → 1.6.0).
- El zip de actualización se arma SIEMPRE con `python empaquetar_app.py` (sale `editor-tutoriales_v<VERSION>_<fecha>.zip`)
  y se sube TAMBIÉN al Google Drive de fabian, con la versión en el nombre (conector Google Drive, o la carpeta de
  «Drive para escritorio» con `--drive` / `"carpeta_drive"` en ajustes.json).
