# Instrucciones para la IA que trabaja en esta carpeta (DeepSeek, Claude u otra)

Esta carpeta es **Estudio de tutoriales**, la app de fabian que convierte la grabación de un tutorial de telefonía en un
video narrado. **Tú no editas video ni reprogramas la app.** Tu trabajo es escribir el guion, las etiquetas y el tráiler;
la app hace todo lo demás con sus propios pasos. Lee también `README.md` y, si existe, `PARAMETROS_DEEPSEEK.md`.

## Cuando el autor te pase un video: siempre este procedimiento

Todo se hace con `python deepseek/video.py`, que maneja la app (la abre sola si hace falta). Usa siempre el mismo
`--nombre` para el mismo video.

1. **Preparar** (gratis):
   `python deepseek/video.py preparar "RUTA\DEL\VIDEO.mp4" --nombre "NOMBRE" --idea "datos seguros que dio el autor"`
   Sube el video, lo transcribe con Whisper en la PC y deja en `mis_proyectos/NOMBRE/`:
   - `ia_prompt_guion.txt`: el encargo EXACTO de la app (reglas de estilo, humor, formato, transcripción completa y mapa
     del video con el texto de cada pantalla). Síguelo al pie de la letra.
   - `ia_capturas/` (y `ia_capturas/hojas/`): las capturas que nombra el encargo.
   - `hojas_2s/`: un cuadro cada 2 segundos de todo el video con el segundo escrito, 30 por hoja (1 minuto por hoja).
2. **Mirar el video**: abre TODAS las hojas de `hojas_2s/` y las capturas. Antes de escribir, anota para ti en qué
   segundo ocurre cada paso (pantalla bloqueada, se abre el programa, se pega la key, se reinicia, pantalla de inicio).
3. **Escribir el guion** como pide `ia_prompt_guion.txt`: `{"bloques": [...], "preguntas": [...]}` en un archivo,
   por ejemplo `mis_proyectos/NOMBRE/respuesta_guion.json`. Revisa bloque por bloque que el tramo `src_inicio`–`src_fin`
   MUESTRE lo que dice su texto (con las hojas), que los tramos vayan en orden y que no repitas una escena.
4. **Entregar**: `python deepseek/video.py entregar guion respuesta_guion.json --nombre "NOMBRE"`
   La app corrige tiempos y largo (y alarga con repetición de la escena si la voz no cabe). Lee el resumen,
   `mejoras_guion.txt` y `revision_guion.txt`; si hay saltos atrás o tramos que no coinciden, corrige y vuelve a entregar.
5. **Preguntar al autor**: muéstrale el resumen (bloques, duración, humor) y tus `preguntas`. La voz de ElevenLabs gasta
   créditos: **no sigas sin su «sí»**.
6. **Armar** (solo con su sí): `python deepseek/video.py armar --nombre "NOMBRE" --confirmo-creditos`
   Voz, montaje, subtítulos y música → `FINAL.mp4`.
7. **Extras**: `python deepseek/video.py encargo etiquetas --nombre "NOMBRE"` → escribe lo que pide
   `ia_prompt_etiquetas.txt` → `entregar etiquetas archivo.json`. Igual con `trailer`. Luego
   `python deepseek/video.py extras etiquetas trailer --nombre "NOMBRE" --confirmo-creditos` (el tráiler lleva voz: pregunta antes).
8. **Exportar**: `python deepseek/video.py exportar 480 720 --nombre "NOMBRE"`.

Si un paso falla, el script dice cuál y por qué: lee `registro.txt` y `diagnosticos/` del proyecto y explícale la causa
al autor. No lo reintentes a ciegas.

## Reglas que no se discuten

- La app ya hace las pausas como **repetición de la escena en movimiento**, no foto fija. Nunca pongas `"quieto": true`
  salvo que el autor lo pida.
- No gastes créditos de ElevenLabs ni de ninguna IA sin el «sí» del autor. Cambiar el texto de un bloque ya armado
  regenera su voz (gasta).
- Nunca abras, muestres ni copies `app/ajustes.json` ni ninguna clave, token o contraseña.
- No inventes datos: lo que no se ve en el video ni dice el autor va como pregunta, no como hecho.
- No reprogrames ni reinstales la app; no instales nada. Si algo de la app parece un error, descríbelo al autor.
- No intentes evadir las políticas de ninguna IA.
- Español latino, tuteando; humor nivel «poco» (un remate cada 7 u 8 bloques, nunca en pasos críticos).
