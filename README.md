# Editor de tutoriales

Herramientas para convertir un video de tutorial en un video narrado con voz de ElevenLabs,
con música de fondo y etiquetas animadas. Todavía no es una app instalable: son los módulos
que se usaron con el video de la Pico 2 y que la app irá juntando por fases.

## Lo que hay hoy

| Carpeta | Qué hace |
|---|---|
| `app/` | La app con botones: una página local que corre cada paso y muestra el resultado. |
| `montaje/` | Arma el video según el plan de montaje del guion (cámara lenta, congelados nítidos con zoom, imágenes). |
| `voz/` | Genera la voz por bloques con ElevenLabs (`voz.py`) y la coloca en el video con subtítulos (`mezclar_voz.py`). |
| `ia/` | La parte creativa (guion, etiquetas, tráiler) con la IA que elijas: GPT, DeepSeek, Gemini u Ollama local. Arma el prompt con capturas y transcripción, y corrige lo que la IA devuelve (tiempos, frases que no existen). |
| `etiquetas/` | Encuentra el segundo exacto en que la voz dice una frase (tiempos por carácter de ElevenLabs) y superpone una etiqueta animada: páginas web, pines, archivos, precios, consejos. |
| `musica/` | Genera música con ElevenLabs Music, la repite hasta cubrir el video y la baja sola cuando habla la voz. |
| `nitidez/` | Mide nitidez y movimiento de cada cuadro y elige el más quieto y enfocado. Los congelados, capturas y miniaturas nunca caen en una mano moviéndose ni en una toma borrosa. |
| `trailer/` | Tráiler de inicio **ANTES · DURANTE · DESPUÉS**: corta las mejores tomas de cada fase, Remotion pone los sellos animados, destellos, zoom y la placa final, con voz y música. |
| `trailer/pistas.py` | Pistas del autor para el tráiler: en cada fase (ANTES, DURANTE, DESPUÉS) le das capturas, audios o texto y la app los convierte en segundos candidatos (busca la captura en el video, transcribe el audio y busca lo que dice) para que la IA elija los tramos cerca de ahí. |
| `tarjetas/` | Tarjetas de **COMENTARIOS** y **WHATSAPP** encima del video: entran cuando la voz invita a comentar o a escribir (lo busca en los subtítulos), o en el segundo que digas. No cambian la duración. |
| `alimentacion/` | **ALIMENTACIÓN**: aprende tu estilo de tus videos (links de YouTube o MP4) y de perfiles escritos: ritmo, aperturas, cierres, frases típicas, cortes por minuto y cómo armas el tráiler del inicio. Con el link de tu canal (`youtube.com/@tucanal`) lee todos tus videos (subtítulos y los primeros 3 minutos de imagen) y deja el catálogo de títulos para que la IA recomiende tus otros videos. Guarda un perfil por canal en `mis_estilos/` que la IA usa al escribir el guion y el tráiler. |
| `acortar/` | **ACORTAR**: mira la grabación entera y quita lo que sobra hasta la duración que pidas: corta silencios con la pantalla quieta, acelera esperas (reinicio del celular, clave del Wi-Fi, cargas) y, con IA, corta las partes que no suman. Tu voz nunca se acelera. Deja `acortado.mp4` y `acortar.json`, que el guion con IA usa para apuntar a esa duración. |
| Mis páginas (en la app) | Tus webs y canales (nombre, link, para qué sirven), guardados para todos los proyectos. La IA los nombra en el guion donde ayudan y en el cierre, y les pone su etiqueta «web» con la dirección exacta. |
| `senales/` | Flechas, círculos y recuadros que se dibujan solos sobre lo importante cuando la voz lo nombra, y siguen a la pieza si la cámara se mueve (OpenCV). Con `--prueba` saca un cuadro por señal para revisar posiciones. |
| `insertos/` | Usa material extra (grabación de pantalla, fotos, otro video) como cortes y zooms sobre el video, o para reemplazar pausas congeladas, sin cambiar la duración. Encuadre por claves sincronizadas con frases de la voz; `--prueba` muestra cada encuadre. |
| `remotion/` | Proyecto Remotion (React) con las composiciones `Trailer`, `Etiqueta` y `Senal`. Colores y fuente de marca en `src/estilo.ts`. |
| `transcripcion/` | Voz a texto con tiempos por palabra: Scribe (en línea) o Whisper (en tu PC, sin internet). Saca .txt, .srt y .json. |
| `proyectos/pico2/` | Los scripts del video «Cómo soldar la Pico 2»: guion por bloques, voz v4, video estirado a 7 min. Tienen rutas de ese proyecto; sirven de ejemplo. |

## Flujo

1. **Guion por bloques** (`proyectos/pico2/largo.py`): cada bloque dice qué tramo del video original usa, cómo se estira (lento, congelar, imagen) y qué se narra.
2. **Voz** (`voz.py`): genera cada bloque con la voz Mauricio en `eleven_v4` y guarda `<bloque>.mp3` y `<bloque>.align.json`.
3. **Video** (`render.py final`): arma el video a 1080p según el plan de montaje. Cada congelado usa el cuadro que elige `nitidez/` y lleva un zoom lento.
   Luego `mezclar_voz.py` coloca cada bloque de voz en su segundo y saca el .srt.
   `insertos/insertos.py` pone encima el material extra (cortes y zooms) antes de la voz.
4. **Música** (`musica/musica.py`): mezcla la música con bajada automática bajo la voz.
5. **Etiquetas** (`etiquetas/etiquetas.py`): superpone las etiquetas en el momento en que se dicen.
6. **Señales** (`senales/senales.py`): flechas y círculos animados sobre las partes importantes.
7. **Tráiler** (`trailer/trailer.py --unir`): crea el tráiler y lo pega delante del video, corriendo los subtítulos.

En la app, «▶ Hacer todo» llega hasta el paso 4 y deja un FINAL.mp4 para ver si el guion gusta. Los extras (etiquetas,
flechas, comentarios, testimonios, nuevos modelos y tráiler) se ponen después con «✨ Agregar extras», eligiendo cuáles;
se rehacen sobre ese video sin repetir la voz ni el montaje.

## La app con botones

**Tarjeta NVIDIA o gráfica Intel.** Si la PC tiene una NVIDIA que codifica video (NVENC), o si no una gráfica Intel con Quick
Sync, todos los pasos que arman video la usan en vez del procesador; si la tarjeta falla en un tramo, ese tramo y el resto del paso se hacen con el procesador (`codificar/`). Si tu
ffmpeg es más nuevo que lo que acepta el driver de tu tarjeta, pon un ffmpeg compatible en la carpeta `ffmpeg_nvidia/` (al
actualizar la app no se toca): la tarjeta codifica con ese y todo lo demás sigue con el de siempre. Se apaga con
`"nvidia": false` en `app/ajustes.json`.

**🎚 Editor por pistas** (botón al lado de «Hacer todo»): el video con sus pistas debajo (video, voz por bloque, música,
subtítulos, etiquetas y flechas). Se arrastran etiquetas y flechas en el tiempo, se hace clic en el video para que una flecha
apunte ahí, se cambia el texto de un bloque de voz o de un subtítulo, el volumen de la música, y se borra o agrega lo que
quieras. «Armar el video» vuelve a poner tus extras tal cual (la IA no los rehace) y, si cambiaste voz o música, rehace solo
eso antes. Lo movido a mano queda anclado a su bloque (`"bloque"` + `"en"`, segundos desde que empieza el bloque) en
etiquetas.json y senales.json, así sigue a su bloque si el video se alarga o se acorta.

La pista **📝 Guion** muestra cada bloque en su tramo del video, con su miniatura. Al elegir un bloque ves de qué parte de tu
grabación sale, la velocidad, la pausa y cuánto dura su voz; puedes cambiar el texto (la app estima cuánto se alargará o
acortará el video), pedir «✨ Reescribir con IA» solo ese bloque, dividirlo, unirlo con el siguiente, borrarlo y deshacer.
Al «Armar el video» se genera la voz solo de los bloques cambiados y el video se alarga o acorta solo. Cada vez que se
guarda el guion, la versión anterior queda en `historial_guion/` (las últimas 40).

Doble clic en `iniciar.bat` (o `python app/app.py`): se abre **Estudio de tutoriales** en tu navegador, en http://localhost:8765.
Creas un proyecto, subes el video grabado (y si quieres el material extra, la imagen y la música), pegas el guion y aprietas
**Hacer todo**, o cada paso por separado. Cada proyecto queda en `mis_proyectos/<nombre>/` y el video terminado es `FINAL.mp4`.
El guion, las etiquetas, las señales, los insertos y el tráiler se editan en la misma página; el botón *Cargar ejemplo* trae los de la Pico 2.

**Con tu IA:** en *⚙ Ajustes IA* eliges proveedor (Claude, OpenAI, DeepSeek, Gemini, Qwen, Ollama u otro compatible) y pegas tu clave.
Los modelos con visión (GPT-5 y GPT-4.1, Qwen-VL por Alibaba Cloud u OpenRouter, Qwen 3 VL en tu PC con Ollama, Gemma 3,
Claude) reciben las capturas del video; si escribes a mano un modelo con visión conocido, la casilla «ve imágenes» se marca sola.
*✨ Escribir con IA* llena el guion, las etiquetas o el tráiler solo. *📋 Prompt para copiar* te da el texto y las capturas para pegar en
cualquier chat, y *✅ Revisar respuesta pegada* corrige y guarda lo que te contestó. Escribe antes en «idea» los datos seguros del video.

**Controles que no dependen de la IA:** la IA recibe la transcripción completa (nunca se corta: si es larga se agrupa en
tramos) y capturas repartidas por todo el video más las de los momentos de mayor movimiento. Al revisar el guion, la app avisa
si un tramo vuelve atrás en el video o si lo que narra un bloque se dice en otro momento de tu grabación (`revision_guion.txt`).
*Generar voz* solo regenera los bloques cuyo texto cambió y, con la duración real de cada voz, alarga en el guion los bloques
donde no cabía; después vuelve a *Montar video*.

**Alimentación:** en el panel *📚* creas un estilo (por ejemplo, tu canal), pegas links de YouTube o subes MP4 y perfiles
escritos (.md), y *🧠 Aprender mi estilo* lo analiza (los videos ya analizados no se repiten). Marca «Usar este estilo» para que
la IA lo siga al escribir el guion y el tráiler. Si YouTube bloquea una descarga, baja el video y súbelo como MP4.

**Tráiler con pistas:** en el panel *🎞️ Tráiler* eliges ANTES, DURANTE o DESPUÉS y agregas pistas: capturas (arrastradas o
con *📸 Capturar del reproductor* sobre `original.mp4`, que guarda el segundo), audios o notas de voz (*🎙 Grabar*) y texto
(«cuando muestro la placa sin soldar», «en el 2:10»). *✨ Armar tráiler con estas pistas* le pide el tráiler a tu IA usando esos
momentos como referencia; son orientativos, no cortes exactos.

**Comentarios y WhatsApp:** en el panel *💬* subes tus imágenes en cada grupo, eliges momento (auto, 1:25, inicio, mitad, final),
segundos y esquina, y *▶ Poner tarjetas en el video* saca `7_tarjetas.mp4`. *Hacer todo* las pone antes del tráiler si subiste alguna.

## Con una IA de chat que corre comandos (DeepSeek, Claude, etc.)

`AGENTS.md` le explica a la IA el procedimiento y `deepseek/video.py` maneja la app paso a paso: `preparar` (sube el video,
transcribe con Whisper y deja el encargo del guion con capturas, mapa y hojas de un cuadro cada 2 s), `entregar` (la app
corrige y guarda lo que escribió la IA), `armar` y `extras` (piden `--confirmo-creditos` porque la voz gasta ElevenLabs) y
`exportar`. La IA escribe los JSON; el video lo hace la app con sus mismos parámetros.

## Guion con 3 IAs a la vez (GPT, Claude y Gemini)

En «⚙ Ajustes IA» marca «✍️ Guion con 3 IAs a la vez» y pon el modelo y la clave de cada una («🔍 Comprobar y ver
modelos» lista los modelos que tu cuenta puede usar, sin gastar). El video se analiza una sola vez y las tres escriben su
guion al mismo tiempo: tarda lo que la más lenta, pero se paga un guion a cada una. Cada versión pasa por los mismos
controles (largo, humor, tiempos) y queda en `guion_gpt.json`, `guion_claude.json` y `guion_gemini.json`. En la revisión del
guion eliges la que prefieras o pulsas «🧩 Combinar» para que tu IA principal arme una con lo mejor de cada una (un pedido
más, sin volver a mirar el video). Si una IA falla o rechaza el pedido, las otras siguen y el diagnóstico lo anota; no se
reintenta un rechazo.

## Diagnóstico cuando la IA (o un paso) no completa su trabajo

Cada llamada a una IA queda anotada en `mis_proyectos/<proyecto>/diagnosticos/llamadas_<ejecución>.jsonl` (proveedor,
modelo, operación, código HTTP, mensaje original de la API, id de solicitud, motivo de fin, intento, duración y un hash
del pedido; nunca claves, guion, imágenes ni audio). Si un paso falla, o si alguna llamada falló aunque el paso siguió,
se escribe `diagnostico_<fecha>_<id>.txt` y `.json` con la etapa (1 a 9), la clase de error (A rechazo por políticas ·
B cuenta deshabilitada · C autenticación o permisos · D créditos · E límites · F formato · G programa · H red o servicio ·
I desconocida), si la causa está confirmada por la API o no, qué falta saber y qué hacer. La app abre la ventana «LA IA
NO PUDO COMPLETAR ESTA OPERACIÓN» con Ver diagnóstico, Exportar TXT/JSON y Reintentar (solo si reintentar tiene sentido:
nunca tras un rechazo explícito, permisos o facturación). Con `"diagnostico_guardar_respuesta": true` en
`app/ajustes.json` se guarda además un extracto redactado de lo que contestó la IA.

- **Modelo pedido y modelo que respondió:** cada llamada anota los dos, según el campo `model` de la respuesta. Con
  Claude también se leen los bloques `fallback` y `usage.iterations`: si el servidor pasó el pedido a otro modelo
  (solo lo hace tras un rechazo por políticas) se anota de cuál a cuál y por qué. Si la API no da el modelo, se dice
  «no confirmado».
- **Tipo de respuesta:** distingue un rechazo con HTTP 200 (`stop_reason: refusal`, `refusal`, `content_filter`) de un
  JSON inválido, una respuesta vacía, una cortada por largo y un error HTTP.
- **Resultado de cada ejecución:** completado correctamente, completado con incidencias (el paso o el video salió pero
  alguna solicitud falló o fue rechazada, o un opcional se saltó) o interrumpido. Queda en
  `diagnosticos/resumen_<fecha>_<id>.txt` y `.json`, con los modelos usados.
- **Reintentar sin pagar dos veces:** mientras un paso no termina bien, las respuestas de la IA se guardan en
  `cache_ia/<paso>/`. «Reintentar» sigue desde el paso que falló y reutiliza esas respuestas en vez de volver a
  pedirlas; la que hizo fallar el paso no se reutiliza. Al terminar bien el paso, se borran.

## Instalar en tu PC (Windows)

1. Descarga el zip del código y descomprímelo, por ejemplo en `C:\editor-tutoriales`.
2. Doble clic en `instalar.bat`. Instala Python, Node.js y ffmpeg (con winget), las librerías, Chromium y Remotion, y te pide tu API key de ElevenLabs.

**Llevar la app a otra PC.** Todo lo que la app descarga queda en `descargas_app/` (librerías de Python, modelos de Whisper,
y lo que guarde `guardar_para_otra_pc.bat`: ffmpeg, los instaladores de Python y Node, el navegador de las etiquetas y, si
quieres, los modelos de Ollama). Corre `guardar_para_otra_pc.bat`, copia la carpeta `editor-tutoriales` entera a la PC nueva
y ahí corre `instalar.bat`: usa lo guardado y solo baja lo que falte.
   Si te dice que falta algo en el PATH, cierra la ventana y ábrelo otra vez.
3. Para ver y editar el tráiler o las señales en el navegador: abre una terminal en la carpeta `remotion` y escribe `npm run studio`.
4. Al final crea **Estudio.exe** y el acceso directo «Estudio de tutoriales» en el escritorio. Ábrelo desde ahí: la app sale en su
   propia ventana, sin ventana negra, y se apaga sola unos minutos después de cerrarla (si no hay un paso trabajando).
   Para rehacer solo el .exe (por ejemplo tras una actualización del código): doble clic en `crear_exe.bat`.
   `iniciar.bat` sigue sirviendo: abre la app con la ventana negra, útil para ver errores.

La API key está en ElevenLabs → Developers → API Keys; pégala en el botón **🔑 Clave ElevenLabs** de la app.
Sin clave funciona todo menos voz, música y transcripción en línea.

**IA open source en tu PC (sin internet, gratis):** doble clic en `instalar_ia_local.bat`. Instala Ollama y baja Gemma 3
(12B, o 4B para PC sencilla) o Qwen 2.5 VL. Después, en *⚙ Ajustes IA*, elige el Ollama que bajaste; no necesita clave.

Estudio.exe es un lanzador (`lanzador/estudio.py` con PyInstaller): usa el Python, ffmpeg, Node y Remotion que instaló `instalar.bat`
y abre la app con Edge o Chrome en modo aplicación. No los lleva dentro, por eso pesa poco y se actualiza con solo cambiar el código.

### Actualizar sin perder nada

Pulsa **«⬇ Actualizar la app»** (arriba). Baja la versión nueva de GitHub y la copia encima de **esta misma carpeta**:
`mis_proyectos`, `mis_estilos` y `app/ajustes.json` (tus claves) no se tocan, y cada archivo que se reemplaza
queda antes guardado en `descargas_app/respaldo_app_<fecha>.zip`. La app se reinicia sola al terminar.

## Requisitos

- Python 3 con numpy y opencv-python-headless, ffmpeg y Node con Playwright (Chromium), para renderizar las etiquetas.
- Remotion: `cd remotion && npm install`. `npm run studio` abre el editor visual en el navegador.
- Acceso a la API de ElevenLabs. En el entorno de Claude la clave la pone el proxy; en tu PC se lee de la variable `ELEVENLABS_API_KEY`.

## Ejemplo: etiquetas

```bash
python3 etiquetas/etiquetas.py --guion guion.json --voz voz_v4 \
  --etiquetas etiquetas/ejemplos/pico2_etiquetas.json \
  --video con_voz_y_musica.mp4 --salida final.mp4
```

Cada etiqueta del JSON indica el bloque, la frase que la dispara y lo que muestra:

```json
{"bloque": "L15", "frase": "gsmprime", "tipo": "web", "titulo": "Descarga aquí", "texto": "gsmprime.co"}
```

## Ejemplo: tráiler ANTES · DURANTE · DESPUÉS

```bash
python3 trailer/trailer.py --video original.mp4 --plan trailer/ejemplos/pico2_trailer.json \
  --salida trailer.mp4 --unir final.mp4 --final final_con_trailer.mp4 --srt final.srt
```

En el plan, cada clip dice su fase y la ventana del video original donde buscar; el tramo exacto lo elige `nitidez/`.
