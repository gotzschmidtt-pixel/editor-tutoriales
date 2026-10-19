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

## La app con botones

Doble clic en `iniciar.bat` (o `python app/app.py`): se abre **Estudio de tutoriales** en tu navegador, en http://localhost:8765.
Creas un proyecto, subes el video grabado (y si quieres el material extra, la imagen y la música), pegas el guion y aprietas
**Hacer todo**, o cada paso por separado. Cada proyecto queda en `mis_proyectos/<nombre>/` y el video terminado es `FINAL.mp4`.
El guion, las etiquetas, las señales, los insertos y el tráiler se editan en la misma página; el botón *Cargar ejemplo* trae los de la Pico 2.

**Con tu IA:** en *⚙ Ajustes IA* eliges proveedor (OpenAI, DeepSeek, Gemini, Ollama u otro compatible) y pegas tu clave.
*✨ Escribir con IA* llena el guion, las etiquetas o el tráiler solo. *📋 Prompt para copiar* te da el texto y las capturas para pegar en
cualquier chat, y *✅ Revisar respuesta pegada* corrige y guarda lo que te contestó. Escribe antes en «idea» los datos seguros del video.

## Instalar en tu PC (Windows)

1. Descarga el zip del código y descomprímelo, por ejemplo en `C:\editor-tutoriales`.
2. Doble clic en `instalar.bat`. Instala Python, Node.js y ffmpeg (con winget), las librerías, Chromium y Remotion, y te pide tu API key de ElevenLabs.
   Si te dice que falta algo en el PATH, cierra la ventana y ábrelo otra vez.
3. Para ver y editar el tráiler o las señales en el navegador: abre una terminal en la carpeta `remotion` y escribe `npm run studio`.
4. Para abrir la app: doble clic en `iniciar.bat`.

La API key está en ElevenLabs → Developers → API Keys. Sin clave funciona todo menos voz, música y transcripción en línea.

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
