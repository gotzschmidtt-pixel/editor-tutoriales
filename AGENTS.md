# DeepSeek: cómo hacer los videos de fabian (todo en un archivo)

Pega este archivo al inicio del chat de DeepSeek, o déjalo como `AGENTS.md` en la carpeta `editor-tutoriales`.
Cuando fabian te pase un video, sigue la PARTE A paso a paso. La PARTE B tiene todos los parámetros exactos.

**Pedido fijo del autor:** cuando le digas dónde está o dónde dejar un archivo o carpeta, dale SIEMPRE la dirección completa
(por ejemplo `C:\Users\PC\Downloads\CLOUDE SINCRONIZACION\EDITOR DE VIDEO CLAUDE\editor-tutoriales\mis_musica\musica_fija.mp3`),
nunca solo el nombre o una ruta a medias como `mis_musica\musica_fija.mp3`.

**Conocimiento del canal (léelo primero):** `editor-tutoriales\mis_conocimientos\CONOCIMIENTO.md` tiene los procesos
(DFU, Recovery, ECID, FRP…), las reglas del guion y los datos que el autor ya confirmó en videos anteriores, y
`aprendido_de_proyectos.md` lo que contestó en cada proyecto. Úsalo y no vuelvas a preguntar lo que ya está ahí. Lo nuevo que
aprendas con el autor, anótalo en la sección que toca de `CONOCIMIENTO.md` (una línea por dato, con la fecha), sin borrar lo que hay.
La app (botón «🧠 Conocimiento») se lo pasa sola a la IA cuando escribe el guion, el tráiler y las etiquetas.

---

## ⚠ REGLAS DEL AUTOR PARA ESCRIBIR EL GUION (obligatorias, antes de escribir nada)

Antes de escribir el guion:

1. Haz una lista con el segundo exacto de cada evento de pantalla: cada botón que presiono, cada cambio de modo (Recovery, DFU), cada reinicio, la pantalla de inicio y cada ventana nueva del programa.
2. Corta cada bloque donde empieza y termina ese evento. No partas el video en trozos fijos (por ejemplo, de 18 segundos).
3. Si lo que digo en el audio no coincide con lo que se ve en ese momento, manda la imagen: narra lo que se ve y deja lo que digo para el bloque donde ocurre.
4. No inventes datos (versiones, modelos, botones). Si no se ve ni lo digo, escribe la frase sin ese dato y pregúntamelo al final.
5. Al final, para cada bloque, indica qué se ve en su primer y en su último segundo, para que pueda comprobarlo.
6. Un evento es el momento de la ACCIÓN (cuando presiono un botón o hago clic), no cuando aparece el resultado en pantalla. El mapa de la app marca cuándo cambia la pantalla: úsalo para orientarte, pero busca la acción en las hojas, unos segundos antes.

**Por qué:** en IOS27_FRP el guion cortó el video en trozos fijos de 18 s y escribió cada texto según el audio. En 4 zonas
(Recovery, DFU, la placa, el reinicio) la voz quedó un bloque corrida respecto a la imagen, y hubo datos inventados.

**Cómo se entrega:**
- Regla 1: la lista va en `mis_proyectos/NOMBRE/eventos_pantalla.txt`, una línea por evento («m:ss qué pasa»), y también
  en `"eventos"` de `respuesta_guion.json`: `[{"s": 140.0, "evento": "pulsa volumen más"}, ...]`.
- Regla 5: en cada bloque de `respuesta_guion.json`, los campos `"ve_inicio"` y `"ve_fin"`. Muéstralos también al autor
  en el chat, junto con las preguntas.

---

# PARTE A · Qué hacer cuando te pasan un video

## A1. Quién hace qué

- **Tú (la IA):** miras el video (en hojas de fotos), escribes el guion, las etiquetas y el tráiler en JSON, revisas que
  todo coincida con la imagen y le preguntas al autor lo que no sepas.
- **La app «Estudio de tutoriales»** (en la PC, carpeta `editor-tutoriales`): transcribe, saca capturas y el mapa del
  video, genera la voz con ElevenLabs (voz Mauricio, `eleven_v4`), monta el video con repetición de escena en vez de foto
  fija, pone música, etiquetas, flechas y tráiler, y exporta. La clave de ElevenLabs está guardada en la app
  (`app\ajustes.json`); las herramientas de voz y música la leen solas. Desde el 27/10/2026 el autor te autoriza a
  leer las claves API de `ajustes.json` cuando las necesites (ver B12).
- **Las herramientas de la PC que usas:** las de la app una por una (transcribir, capturas y mapa, voz, montaje, música,
  etiquetas, tráiler; ver A3), ffmpeg/ffprobe y la gráfica NVIDIA o Intel (las herramientas la usan solas).

## A2. Antes de empezar, pregúntale al autor (en un solo mensaje, con opciones)

1. Nombre del proyecto y ruta del video.
2. Datos seguros del video (modelo, método, versiones de Android, webs a nombrar). Ejemplo de datos que suele dar:
   «método 2026–2027, Android 15, 16 y 17, xiaomiunlock.com y gsmprime.co».
3. Duración buscada: parecida a la grabación (por defecto) o un número de minutos.
4. Humor: sin / poco / normal (el que usa el autor desde el 28/10/2026) / mucho.
5. Extras: etiquetas (por defecto); flechas, testimonios, nuevos modelos, tarjetas si subió material. El tráiler va
   aparte, después de que apruebe el video (paso 8b).
6. Si autoriza gastar créditos de ElevenLabs al armar (voz) y en el tráiler. Sin su «sí», paras antes de la voz.

Si no contesta algo, usa el valor por defecto y díselo.

**Después de mirar el video (A3 paso 2) vuelve a preguntar:** todo lo que no te quede claro, **hasta 15 preguntas**
(y aparte hasta 10 ideas para mejorar el video) numeradas y con opciones (qué pieza o cable es, qué botón, qué versión, en qué momento pasa algo, si un paso se salta,
qué decir de una web). Mejor preguntar que adivinar. Escríbelas también en `"preguntas"` de `respuesta_guion.json`
(`{"tipo": "dato" | "mejora", "bloque": "L07", "pregunta": "¿…?", "opciones": ["…", "…"]}`): así el autor las ve y las
contesta en la app, junto al guion.

## A3. Procedimiento recomendado: con la app (`deepseek/video.py`)

Desde la carpeta `editor-tutoriales`, con el mismo `--nombre` en todos los pasos:

1. **Preparar (gratis):**
   `python deepseek/video.py preparar "RUTA\video.mp4" --nombre "NOMBRE" --idea "datos seguros"`
   Transcribe con Whisper (gratis). Scribe de ElevenLabs acierta más los nombres técnicos pero gasta créditos (ver la tabla
   de abajo): pregúntale al autor y, si dice que sí, agrega `--confirmo-creditos`.
   Deja en `mis_proyectos/NOMBRE/`: `ia_prompt_guion.txt` (el encargo exacto de la app, con la transcripción y el mapa
   del video), `ia_capturas/` (capturas y hojas) y `hojas_2s/` (un cuadro cada 2 s con el segundo escrito, 1 min por hoja).
2. **Mirar TODO el video:** abre cada hoja de `hojas_2s/`. Anota en qué segundo pasa cada cosa: pantalla bloqueada,
   se abre el programa, se conecta el cable, se pega la key, se pulsa el botón, reinicio, pantalla de inicio.
   Después abre `acciones/acciones.txt` y sus hojas: son cuadros grandes cada medio segundo donde el autor dice que hace
   algo («presiono», «power», «clic», «exit», «DFU»). De ahí sale el **segundo exacto de cada acción** (regla 6).
3. **Escribir el guion**: primero cumple las **REGLAS DEL AUTOR** de arriba de todo (la lista de eventos en
   `eventos_pantalla.txt` y los bloques cortados por evento). Después sigue `ia_prompt_guion.txt` y la PARTE B. Guárdalo en
   `mis_proyectos/NOMBRE/respuesta_guion.json`, con `"ve_inicio"` y `"ve_fin"` en cada bloque.
4. **Revisar tú mismo antes de entregar** (lista de A4). Corrige lo que falle.
5. **Entregar:** `python deepseek/video.py entregar guion mis_proyectos/NOMBRE/respuesta_guion.json --nombre "NOMBRE"`
   La app corrige tiempos y largo, quita bloques con el texto repetido y el «ok» suelto, y frena los pasos de
   configuración a ×2 como máximo. Lee `mejoras_guion.txt` y `revision_guion.txt`: si avisa saltos atrás, «muestra la
   misma escena que», «faltan palabras», humor sin repartir, tramos que no coinciden o «quedó corto», corrige y vuelve a
   entregar.
6. **Que el autor revise y edite el guion ANTES de la voz.** Dile: «el guion está en la app: elige el proyecto NOMBRE y
   pulsa 📝 Ver y editar guion». Ahí lee cada bloque con su tramo, lo edita y contesta tus preguntas
   («💾 Solo guardar respuestas»). Cuando diga que respondió: `python deepseek/video.py preguntas --nombre "NOMBRE"`
   muestra sus respuestas; corrige `respuesta_guion.json` con ellas **y con lo que él editó** (léelo de
   `mis_proyectos/NOMBRE/guion.json`, que ya tiene sus cambios), y vuelve a entregar. Repite hasta que diga «sí».
   **Sus cambios mandan:** si el autor editó el guion en la app después de tu última entrega, `entregar` se niega y deja
   su versión en `guion_editado_por_autor.json`. Parte de ese archivo (no de tu respuesta vieja), aplica solo lo que
   falte y entrega con `--parti-del-guion-actual`. Si no tienes nada que cambiar, no entregues: arma con su guion.
7. **Armar (gasta ElevenLabs):** antes, `python deepseek/video.py clave` (gratis) comprueba la clave de ElevenLabs y dice
   cuántos créditos quedan (`CREDITOS_ELEVENLABS=…`). Si no alcanzan para los caracteres de voz del guion, avísale al
   autor y no armes. Después: `python deepseek/video.py armar --nombre "NOMBRE" --confirmo-creditos`
8. **Etiquetas:** `python deepseek/video.py encargo etiquetas --nombre "NOMBRE"` → escribe lo que pide
   `ia_prompt_etiquetas.txt` → `python deepseek/video.py entregar etiquetas archivo.json --nombre "NOMBRE"`. Luego
   `python deepseek/video.py extras etiquetas --nombre "NOMBRE"`.
8b. **Tráiler (módulo aparte, al final):** solo cuando el autor aprobó el video. `encargo trailer` → lee
   `ia_prompt_trailer.txt` (trae el guion aprobado y las respuestas que ya dio) y las imágenes → escribe `trailer.json`
   (B9) con las mejores tomas ANTES · DURANTE · DESPUÉS, cada una con `por_que`, y en `"preguntas"` hasta 10 dudas e
   ideas → `entregar trailer archivo.json`. Dile al autor que lo revise en la app, «🎬 Tráiler»: ve cada toma con su
   imagen, la cambia y contesta. Cuando diga que respondió: `python deepseek/video.py preguntas trailer --nombre "NOMBRE"`,
   corrige y vuelve a entregar. **Sus cambios mandan** igual que en el guion (`trailer_editado_por_autor.json`,
   `--parti-del-guion-actual`). Con su «sí»: `python deepseek/video.py extras etiquetas trailer --nombre "NOMBRE"
   --confirmo-creditos` (la frase de voz gasta ElevenLabs), o que él pulse «▶ Armar tráiler».
9. **Exportar:** `python deepseek/video.py exportar 480 720 --nombre "NOMBRE"` y dile dónde quedó `FINAL.mp4`.

Si un paso falla: lee `registro.txt` y `diagnosticos/`, explícale la causa real al autor y no reintentes a ciegas.

## A3b. Plan B: modo directo (las herramientas de la app una por una)

Úsalo solo si la app no abre o si el autor te pide rehacer un solo paso. Aquí nada te frena antes de gastar: pide
el «sí» del autor antes de los pasos 7, 10 (si genera música) y 12.


No hace falta abrir la app. Usas sus herramientas una por una, como lo hizo Claude en su nube con los videos de Honor y
Raspberry. `R` es la carpeta de la app (`editor-tutoriales`). Antes de todo, en la terminal: `set PYTHONUTF8=1`.

**Preparar la carpeta del video:** crea `R\mis_proyectos\NOMBRE\`, copia ahí el video como `original.mp4`, guarda los
datos del autor en `idea.txt` y trabaja SIEMPRE dentro de esa carpeta (todos los comandos van desde ahí).

| # | Qué | Comando | ¿Gasta? |
|---|---|---|---|
| 1 | Transcribir (texto con tiempos por palabra) | `python R\transcripcion\transcribir.py --video original.mp4 --salida transcripcion --motor scribe` (si falla por la clave: `--motor whisper`) | Scribe (ElevenLabs) descuenta créditos del plan de fabian: ~330 créditos por minuto (un video de ~10 min ≈ 3.000 créditos). El precio en dólares (~$0,22/hora) es solo para cuentas que pagan la API aparte, no para su plan de créditos. Acierta DFU, ECID, 3uTools. Avísale cuántos créditos costará antes de transcribir. Whisper: gratis pero se equivoca más |
| 2 | Capturas nítidas, mapa del video (OCR de cada pantalla) y el encargo exacto del guion | `python R\ia\ia.py --proyecto . --tarea guion --modo prompt --ajustes R\app\ajustes.json` → `ia_prompt_guion.txt`, `ia_capturas\`, `mapa_video.json` | No |
| 3 | Hojas de un cuadro cada 2 s (método Claude) | el comando ffmpeg de B10, una hoja por minuto, en `hojas_2s\` | No |
| 4 | **Tú:** mirar todo y escribir el guion | lees `ia_prompt_guion.txt`, todas las hojas y capturas; escribes `respuesta_guion.json` y repasas la lista A4 | Tus tokens |
| 5 | La app corrige tiempos, largo y orden | `python R\ia\ia.py --proyecto . --tarea guion --modo revisar --ajustes R\app\ajustes.json --entrada respuesta_guion.json` → `guion.json`, `mejoras_guion.txt`, `revision_guion.txt` | No |
| 6 | **Preguntar al autor** con el resumen | bloques, duración, humor, preguntas. Espera su «sí» | — |
| 7 | Voz de Mauricio, ElevenLabs v4 | `python R\voz\voz.py --guion guion.json --salida voz` | **Sí (ElevenLabs)** |
| 8 | Montaje 1080p (pausas = repetición de escena) | `python R\montaje\montaje.py --original original.mp4 --guion guion.json --salida 1_montaje.mp4` | No |
| 9 | Voz y subtítulos sobre el video | `python R\voz\mezclar_voz.py 1_montaje.mp4 guion.json voz 3_voz.mp4` | No |
| 10 | Música que baja sola bajo la voz | `python R\musica\musica.py --video 3_voz.mp4 --salida 4_musica.mp4 --pista R\mis_musica\musica_fija.mp3` (si no existe esa pista: `--guardar_pista musica.mp3`, que **gasta** ElevenLabs Music) | Según pista |
| 11 | Etiquetas: escribe `etiquetas.json` (formato B9) y ponlas | `python R\etiquetas\etiquetas.py --guion guion.json --voz voz --etiquetas etiquetas.json --video 4_musica.mp4 --salida 5_etiquetas.mp4` | No |
| 12 | Tráiler: escribe `trailer.json` (formato B9) y únelo | `python R\trailer\trailer.py --video original.mp4 --plan trailer.json --salida trailer.mp4 --unir 5_etiquetas.mp4 --final FINAL.mp4 --srt 3_voz.srt --donde inicio` | **Sí (voz del tráiler)** |
| 13 | Sin tráiler | `ffmpeg -y -i 5_etiquetas.mp4 -c copy FINAL.mp4` | No |
| 14 | Exportar 480p | `python R\codificar\codificar.py ffmpeg -y -i FINAL.mp4 -vf scale=-2:480 -c:v libx264 -preset veryfast -crf 23 -c:a aac -b:a 128k FINAL_480p.mp4` | No |

Notas:
- Las herramientas de voz y música leen la clave de ElevenLabs por su cuenta (de la app). Puedes leer las claves de
  `ajustes.json` si te hacen falta (autorizado por el autor el 27/10/2026), pero no las muestres en el chat ni las
  escribas en archivos del proyecto.
- Todo lo que codifica video usa sola la gráfica NVIDIA o Intel si la hay.
- Para el paso 2 y el 5 se pasa la ruta de `ajustes.json` a la herramienta. Puedes abrirlo (ver B12); no lo muestres.
- Si cambias el texto de un bloque después de la voz, repite 5 → 7 (solo regenera los bloques cambiados) → 8 → 9…
- Si un paso falla, lee el error, explícale la causa real al autor y no lo reintentes a ciegas.

## A4. Lista de revisión del guion (que todo coincida con el video)

Estos son los errores que encontró la auditoría del guion de Honor FRP. Revísalos SIEMPRE:

- [ ] **Cada tramo muestra lo que dice su texto.** Si la voz dice «pega la key», en las hojas de ese tramo se ve la key
      pegándose, no ya pegada ni todavía sin pegar. Si la voz dice «haz clic en Erase FRP», se ve el clic, no el reinicio.
- [ ] **Sin escenas repetidas:** dos bloques no usan el mismo trozo de video.
- [ ] **En orden:** cada `src_inicio` es mayor o igual que el `src_fin` del bloque anterior (no se vuelve atrás).
- [ ] **Largo:** total de palabras ≈ minutos del video final × 60 × 2.6. Si faltan palabras, explica más cada paso
      (por qué se hace, qué pasa si sale mal); no dejes minutos de imagen sin voz.
- [ ] **Pasos críticos** (key, código, PIN, contraseña, IMEI, serial, elegir la opción exacta) con `"tipo": "critico"` y
      velocidad 1 (máx. 1.5).
- [ ] **⭐ Cortes importantes del autor** (`mis_proyectos/NOMBRE/cortes_importantes.json`, los marca en la app: Recovery,
      DFU, botones…): cada uno se muestra ENTERO, a velocidad 1, en bloques `"tipo": "critico"`; nunca se acelera, recorta
      ni salta. La app los fuerza a ×1 igual, y avisa si un bloque no los muestra. (Pedido del autor, 28/10/2026: en
      IOS27_FRP se aceleraron la entrada a Recovery y a DFU, lo más delicado del video.)
- [ ] **Lo que el autor marcó en la app, todo junto:** `mis_proyectos/NOMBRE/para_claude_marcas.txt` (y `.json`), que deja
      «💾 Guardar para Claude» en Cortes importantes: los cortes importantes y sus señales (círculo, flecha o recuadro con
      segundo, video, zona en % y etiqueta). LÉELO antes de escribir el guion: los cortes van enteros a ×1 y cada etiqueta
      se nombra en la voz cerca de su segundo. Las señales y etiquetas las pone la app sola al armar (no las copies a
      senales.json ni a etiquetas.json).
- [ ] **Humor:** el número del nivel, repartido a lo largo del video (no todo al inicio), nunca en pasos críticos.
- [ ] **Sin `"quieto": true`** (la pausa es repetición en movimiento) salvo que el autor lo pida.
- [ ] **Números y años escritos como se dicen** («dos mil veintiséis»), sin palabras sueltas como «ok» que la voz leería.
- [ ] **Cada acción dicha en su bloque** (pedido del autor, 28/10/2026): cuando el autor dice lo que hace («volumen más y
      power», «no los soltamos», «aparece el menú», «pegamos la DNS», «Omitir»), el bloque cuyo tramo contiene ese segundo
      lo nombra en la voz. La app lista esos momentos en el encargo («MOMENTOS DE ACCIÓN», con una captura de cada uno) y la
      revisión avisa si una acción quedó en otro bloque o se perdió. (En MOTOROLA_FRP_2026 el guion dijo «los mantenemos
      apretados… aparece el menú» sobre 2:14, cuando eso pasa en 2:44–2:55, y se perdió «volumen más y power».)
- [ ] **Nada inventado:** lo dudoso va en `preguntas`.

## A4b. Claude en la nube: entregar para que el autor revise en la app (pedido del autor, 28/10/2026)

Cuando Claude (o cualquier IA en la nube) hace el guion desde el paquete de «☁ Hacer en la nube con Claude», **antes del
guion final y de la voz** le devuelve al autor un `.zip` (por ejemplo `respuesta_MOTOROLA_FRP_2026.zip`) que él importa con
«📥 Importar lo de Claude» en la app:
- `respuesta_guion.json`: el guion (formato B2) con `"preguntas"` (dudas, de 2 a 15, con opciones) e ideas/mejoras
  (`"tipo": "mejora"`), y `ve_inicio`/`ve_fin` en cada bloque. Respeta `para_claude_marcas.txt` (cortes importantes enteros
  a ×1, sus señales y etiquetas).
- `etiquetas.json` (B9) y `senales.json` (círculos y flechas), cada propuesta con `por_que` y, si no está seguro, `duda`:
  el autor las ve en «Editor por pistas → 📋 Propuestas de la IA» y dice sí, las mueve o las quita.
- **Tráiler (pedido del autor, 28/10/2026: que lo redirijas al tráiler con propuestas, siempre):** según lo que aprendiste
  y analizaste del video, entrega una propuesta de tráiler para el INICIO del video:
  - `trailer.json` (B9) con `"donde": "inicio"`, las mejores tomas ANTES · DURANTE · DESPUÉS (cada una con `por_que`),
    `titulo`, `subtitulo` y la frase de `voz` (máx. 15 palabras), y en `"preguntas"` tus dudas (`"tipo": "dato"`) e ideas
    (`"tipo": "mejora"`), con opciones; si una pregunta es de una toma, ponle `"fase"`. La app las separa en
    `preguntas_trailer.json` y el autor las contesta en «🎬 Tráiler».
  - `ideas_trailer.md`: cómo lo harías y por qué (el gancho, el orden de las tomas, 2 o 3 variantes de la frase de voz,
    música o ritmo, qué evitar). La app lo muestra arriba de todo en «🎬 Tráiler».
  Al importar, la app abre «🎬 Tráiler» sola. La voz del tráiler gasta ElevenLabs: solo se arma con el «sí» del autor.
- Opcional: `ideas.md` (notas sueltas para el autor).
El autor contesta en la app y te manda de vuelta su guion editado y sus respuestas; recién con su «sí» se hace la voz.

## A5. Sobre «hacerlo en la nube» y la velocidad

- DeepSeek Harness corre los comandos en la PC del autor (modo Workspace Write = su carpeta). El modelo piensa en los
  servidores de DeepSeek, pero ffmpeg, la voz y el montaje se hacen en la PC. No hay una nube de DeepSeek que arme el
  video; no subas el video ni la clave de ElevenLabs a otros servicios (fuera de DeepSeek y la propia ElevenLabs).
- La velocidad depende de la PC. Medido con Honor FRP (etiquetas + flechas + testimonios): PC1 con NVIDIA 17 min 47 s;
  **PC2 (Core Ultra 7, gráfica Intel) 5 min 43 s, con batería**. La nube de Claude armó la Raspberry en 7 min.
  Usa la **PC2 enchufada al cargador** para que sea igual de rápido.

---

# PARTE B · Parámetros exactos

## B2. Formato del guion (`guion.json`)

```json
{"bloques": [
  {"id": "L01", "ancla": "Portada: ELIMINAR CUENTA HONOR",
   "texto": "¿Has visto cientos de videos en YouTube para quitar la cuenta...?",
   "humor": false,
   "montaje": {"modo": "lento", "src_inicio": 0.0, "src_fin": 12.0, "velocidad": 1.0}},
  {"id": "L09", "tipo": "critico", "ancla": "Campo de la key con la key puesta", "texto": "...", "humor": false,
   "montaje": {"modo": "lento+congelar", "src_inicio": 301.0, "src_fin": 309.0, "velocidad": 1.0, "congelar_s": 3}}
 ],
 "preguntas": [{"tipo": "dato", "bloque": "L07", "pregunta": "¿Qué ...?", "opciones": ["lo más probable", "otra"]}]}
```

- `id`: L01, L02… `ancla`: qué se ve en pantalla (corto). `texto`: lo que dice la voz.
- `montaje.modo`:
  - `lento`: tramo del original a una `velocidad` de 0.6 a 6 (1 = normal; más de 1 para esperas, cargas, instalaciones;
    menos de 1 solo para un detalle rápido).
  - `congelar`: pausa en ese momento (`src_inicio`, `congelar_s`). Ver punto 6: NO es una foto quieta.
  - `lento+congelar`: el tramo y luego una pausa al final.
  - `imagen`: muestra una imagen del proyecto (un mapa, por ejemplo) durante `congelar_s`.
- Los tramos van en orden y dentro de la duración del original. Se salta lo que no aporta (esperas largas, errores, repeticiones).
- Cada tramo tiene que MOSTRAR lo que dice su texto (si la voz dice «pega la key», el tramo es donde se ve la key puesta).
- `preguntas`: hasta 15 de tipo «dato» (lo que no se ve ni se dice claro) y siempre de 2 a 10 de tipo «mejora».
- Responde SOLO con el JSON, sin texto alrededor.

## B3. Duración y ritmo (`ia/ia.py`, `voz/voz.py`)

| Parámetro | Valor | Qué significa |
|---|---|---|
| Palabras por segundo | **2.6** (`PALABRAS_POR_S`) | Es la velocidad de la voz. Para que el video no tenga imagen sin voz, total de palabras ≈ minutos de video × 60 × 2.6. |
| Imagen sin voz por bloque | **1.5 s** máx. (`RELLENO`) | Nada de minutos sin voz. |
| Velocidad máxima | **6×** (`VEL_MAX`) | Para esperas y cargas. |
| Velocidad en pasos clave | **1, máx. 1.5** (`VEL_CRITICO`) | Poner key, escribir código/PIN/contraseña, IMEI, serial, usuario: tiene que leerse. Marcar `"tipo": "critico"`. |
| Duración buscada | Parecida al original, o lo que pida la idea del autor | Si el guion queda corto, el video queda corto: explica con calma. |
| Desfase de la voz | **0.3 s** después del inicio de cada bloque | |

Referencia real (Honor FRP, versión final en la PC): 56 bloques, unas 2.65 palabras por segundo, 22 pausas hechas como
repetición en movimiento (ninguna foto fija), 4 remates de humor y 8 etiquetas. Ojo: tiene 1678 palabras para 14:21 de
video, así que queda un 26 % de imagen sin voz; no lo tomes como meta de largo: la regla de arriba manda. El borrador hecho a mano en la nube
(`guion_honor.md`) tenía 38 bloques de unas 29 palabras cada uno.

## B4. Humor (`HUMOR_NIVELES` en `ia/ia.py`)

| Nivel | Nombre | Máximo |
|---|---|---|
| 0 | sin humor | ningún chiste; solo invitación sencilla a comentar |
| 1 | poco | UN remate cada 7 u 8 bloques |
| **2** (el del autor desde el 28/10/2026) | normal | un remate cada 4 o 5 bloques |
| 3 | mucho | un remate cada 3 bloques |

Reglas del humor:
- Nunca en dos bloques seguidos. Cada remate es UNA frase corta (máx. 12 palabras), dicha de pasada, sin exagerar.
- Picante ligero, doble sentido suave, nada grosero.
- Solo en bloques que NO son críticos: esperas, cargas, el antes y el después, el cierre.
- En pasos críticos (pines, códigos, keys, archivos, valores, copiar/pegar, borrar, conectar): nada de chistes.
- Cada remate con un TEMA distinto (no repetir ex, suegra, vecina…). Marcar `"humor": true` y `"humor_tema"`.
- Al inicio, invitación a comentar las dudas con un toque de humor (cuenta como un remate). Ejemplo real: «déjala en
  los comentarios, que aquí no mordemos… bueno, solo un poquito».

## B5. Estilo de la narración

- Español latino, tuteando, entretenido y fácil de entender.
- Botones, menús y archivos escritos tal cual aparecen en pantalla.
- **No inventar datos**: precios, pines, webs, archivos, versiones solo si están en la transcripción, las capturas o la
  idea del autor. Si falta, la frase va sin el dato y se pregunta.
- Estructura que funciona (guion Honor): gancho con el problema del espectador → ANTES y DESPUÉS → a qué modelos sirve →
  «es fácil» → lo que NO hay que hacer (entregar el teléfono, test point) → invitación a comentar → pasos numerados
  («Paso uno: …») → cierre con webs y WhatsApp.
- Números y años escritos como se dicen («dos mil veintiséis», «Android quince») para que la voz los lea bien.
- Las webs del autor (xiaomiunlock.com, gsmprime.co) se dicen por su nombre y llevan etiqueta «web».
- Cerca del cierre, en un bloque propio: en el canal de WhatsApp y en la página hay capturas de conversaciones reales con clientes.
- Si se usa el estilo del canal «Psicótico»: leer `perfil_estilo.md` (tono de verdad incómoda, autoridad del técnico).
- Datos a recordar del autor: método 2026–2027, Android 15, 16 y 17, últimos Honor (Honor 600, Honor 8 Lite).

## B6. Pausas: repetición en movimiento, no congelado (`montaje/montaje.py`)

Lo que fabian prefiere ya es lo que hace la app: **una «pausa» no es una foto quieta**, es la escena repitiéndose.

- `VENTANA = 2.4 s`: se toman 2.4 s de escena alrededor del cuadro más nítido del momento.
- Se reproducen **ida y vuelta** (adelante y en reversa) a **0.7×** (`LENTO_ESCENA`), en bucle, con un **zoom suave del
  6 %** que alterna acercar/alejar entre bloques.
- Después de un tramo (`lento+congelar`), la repetición arranca hacia atrás desde el último cuadro: el empalme no salta.
- **Con la cara del autor en la escena NO hay reversa** (pedido del autor, 28/10/2026: se nota como retroceso): la app
  detecta la cara (YuNet de OpenCV) y repite solo hacia adelante, con un fundido de 0,4 s en cada vuelta, usando solo el
  pedazo donde la cara sigue en pantalla. `"repetir": "adelante"` o `"ida_vuelta"` en el montaje del bloque lo fuerza.
- Solo con `"quieto": true` en el montaje vuelve a ser un cuadro fijo (con zoom del 10 %). **No uses `quieto` salvo que
  el autor lo pida.**
- Cuando la voz de un bloque no cabe en su tramo (el guion se alargó), la app alarga ese bloque con esta pausa en
  movimiento al final (`lento` pasa a `lento+congelar`); la imagen de los otros bloques no se toca. Si es el video entero
  el que queda corto, primero baja la velocidad de los tramos acelerados. Si queda largo, acelera tramos y quita pausas
  sin voz.

## B7. Voz ElevenLabs (`voz/voz.py`)

| Parámetro | Valor |
|---|---|
| Voz | «Mauricio», id `94zOad0g7T7K4oa7zhDq` |
| Modelo | **`eleven_v4`** |
| Idioma | `es` |
| Estabilidad | **0.5** (`voice_settings.stability`) |
| Endpoint | `text-to-speech/{voz}/with-timestamps`, salida `mp3_44100_128` |
| Por bloque | un `L01.mp3` + `L01.align.json` (tiempos por carácter) |

La voz de todo el video se normaliza a **−16 LUFS** (`loudnorm=I=-16:TP=-1.5`; el tráiler a −15).

Solo se regeneran los bloques cuyo texto cambió (cada cambio gasta créditos). Las etiquetas usan los tiempos por
carácter para aparecer justo cuando la voz dice la frase.

## B8. Música (`musica/musica.py`)

Volumen base **0.22** (≈ 10 dB bajo la voz). Baja sola cuando habla la voz: `sidechaincompress` con threshold 0.03,
ratio 6, attack 20 ms, release 400 ms.

## B9. Etiquetas y tráiler

**Etiquetas** (`etiquetas.json`): `bloque`, `frase` (2 a 4 palabras COPIADAS TAL CUAL del texto del bloque), `tipo`
(web | archivo | dato | precio | pin | consejo), `titulo` (1 a 3 palabras), `texto` (el dato, corto), `dur` (3 a 6 s);
`color` hex solo para `pin`. Ejemplo: `{"bloque": "L15", "frase": "gsmprime", "tipo": "web", "titulo": "Descarga aquí", "texto": "gsmprime.co", "dur": 4.5}`.
En Honor FRP fueron 8 etiquetas de 4 s, pero **al autor le gustan bien etiquetados**: unas 3 etiquetas y 1 a 1,5 flechas o
círculos por minuto, como el de la Raspberry (7 min: 21 etiquetas y 9 flechas). Agrega `por_que` (por qué conviene, una frase) y, solo si no estás seguro, `duda`
(la pregunta para el autor): la app las muestra en «📋 Propuestas de la IA» del editor por pistas, donde el autor dice sí,
la mueve o la quita antes de ponerlas. Lo mismo vale para `senales.json`.

**Tráiler** (`trailer.json`), unos 10 s: `titulo` (máx. 5 palabras), `subtitulo` (frase con gancho), `voz` (máx. 15
palabras), `clips` con `fase` ANTES (teléfono bloqueado) · DURANTE (cuando se pone la key y avanza) · DESPUÉS (pantalla
de inicio, ya libre), cada uno con `ventana` [desde, hasta], `dur` de 1.2 a 2.6 s y `por_que` (nota para el autor). Nada de
pantallas negras ni manos tapando. Aparte, `"preguntas"`: hasta 10, `{"tipo": "dato"|"mejora", "pregunta", "opciones"}`;
la app las guarda en `preguntas_trailer.json` y el autor las contesta en «🎬 Tráiler».

## B10. Qué ve la IA del video (capturas)

**Cómo trabajó Claude en la nube** (el método de los guiones hechos a mano, como Honor FRP):
- Transcripción completa con tiempos por palabra (nunca cortada).
- **Un cuadro cada 2 segundos** de TODO el video, a 320 px de ancho, con el segundo escrito en amarillo, en hojas de
  **6 × 5 = 30 cuadros (1 minuto por hoja)**. Un video de 10 min son 10 hojas y 300 cuadros.
- Con eso se escribe bloque por bloque, revisando contra las hojas que cada tramo muestra lo que dice la voz.
- Comando usado (por minuto):
  `ffmpeg -ss INICIO -t 60 -i original.mp4 -vf "fps=1/2,scale=320:-1,drawtext=text='%{eif\:t+INICIO\:d}s':x=5:y=5:fontsize=22:fontcolor=yellow:box=1:boxcolor=black,tile=6x5" -frames:v 1 hoja.jpg`

**Lo que manda la app a la IA:**
- **14 capturas** por defecto (ajuste `capturas`, de 4 a 60), repartidas por todo el video, el cuadro más nítido de
  cada tramo más los momentos de más movimiento, a 768 px.
- **Mapa**: un cuadro nítido en cada cambio de pantalla de todo el video, y al menos uno cada 15 s aunque no cambie
  nada (máx. 150).
- **«Todo con IA»**: hasta **240 cuadros** (`IA_CUADROS`), uno cada 2 s, o más espaciados en videos largos.
- **Hojas de contacto** del mapa: 4 × 4 = 16 miniaturas por hoja, 384 px, con minuto:segundo.

**DeepSeek y las imágenes:** la app tiene DeepSeek marcado «sin imágenes» (`deepseek-chat`), así que solo recibe la
transcripción y los segundos. Si tu versión de DeepSeek no ve imágenes, pide al autor una descripción breve de qué se ve
en cada minuto, o trabaja con la transcripción y marca en `preguntas` lo que no puedas confirmar.

## B11. Algoritmos de la app (no hay que reprogramarlos)

- **Nitidez** (`nitidez/`): mide nitidez y movimiento de cada cuadro; congelados, capturas y miniaturas caen siempre en
  el cuadro más quieto y enfocado.
- **Ajuste de largo** (`ia.py` `ajustar_largo`, `voz.py`): con la duración real de cada voz, estira o acorta cada bloque
  y recalcula sus tiempos.
- **Revisión del guion** (`revision_guion.txt`, `mejoras_guion.txt`): avisa si un tramo vuelve atrás, si dos bloques muestran
  la misma escena, si más del 15 % del video queda sin voz, si el humor queda amontonado o si lo narrado ocurre en otro
  momento. Quita bloques repetidos y el «ok» suelto; los pasos de configuración van a ×2 como máximo.
- **Flechas y círculos** (`senales/`): se dibujan cuando la voz nombra la pieza y la siguen si la cámara se mueve (OpenCV).
- **Codificación**: NVIDIA (NVENC) → Intel Quick Sync → procesador, solo lo que haya en la PC.

## B12. Reglas del dueño (obligatorias)

- DeepSeek puede leer y usar las claves API de `app\ajustes.json` (cambio pedido por el autor el 27/10/2026). No las
  muestres en el chat, no las copies a archivos del proyecto ni las mandes a otros servicios fuera de DeepSeek y del
  servicio de cada clave. Contraseñas y tokens personales: sigue sin pedirlos.
- No presentar suposiciones como hechos.
- No gastar créditos de ElevenLabs ni de IA sin preguntar.
- Puedes cambiar y editar el código de la app (autorizado por el autor el 27/10/2026). Antes de tocar un archivo,
  guarda una copia (`archivo.py.antes_deepseek`); haz cambios sobre lo que existe, sin reconstruir la app entera; prueba
  que la app siga abriendo (`/api/latido`), y dile al autor qué archivos cambiaste, con la ruta completa, y para qué.
  Claude también edita esta app: los dos pueden. Para no pisarse, uno a la vez: antes de editar un archivo, vuelve a
  leerlo (puede haberlo cambiado Claude) y no edites mientras el autor te diga que Claude está trabajando.
- OJO: «⬇ Actualizar la app» baja la versión de GitHub y la copia ENCIMA: borra los cambios hechos solo en esta PC. Lo
  que cambies aquí tiene que subirse también a GitHub (pídeselo al autor o a Claude) o se pierde en la próxima
  actualización.
- No intentar evadir las políticas de ninguna IA.
