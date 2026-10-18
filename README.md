# Editor de tutoriales

Herramientas para convertir un video de tutorial en un video narrado con voz de ElevenLabs,
con música de fondo y etiquetas animadas. Todavía no es una app instalable: son los módulos
que se usaron con el video de la Pico 2 y que la app irá juntando por fases.

## Lo que hay hoy

| Carpeta | Qué hace |
|---|---|
| `etiquetas/` | Encuentra el segundo exacto en que la voz dice una frase (tiempos por carácter de ElevenLabs) y superpone una etiqueta animada: páginas web, pines, archivos, precios, consejos. |
| `musica/` | Genera música con ElevenLabs Music, la repite hasta cubrir el video y la baja sola cuando habla la voz. |
| `proyectos/pico2/` | Los scripts del video «Cómo soldar la Pico 2»: guion por bloques, voz v4, video estirado a 7 min. Tienen rutas de ese proyecto; sirven de ejemplo. |

## Flujo

1. **Guion por bloques** (`proyectos/pico2/largo.py`): cada bloque dice qué tramo del video original usa, cómo se estira (lento, congelar, imagen) y qué se narra.
2. **Voz** (`voz.py`): genera cada bloque con la voz Mauricio en `eleven_v4` y guarda `<bloque>.mp3` y `<bloque>.align.json`.
3. **Video** (`render.py final`): arma el video a 1080p según el plan de montaje.
4. **Música** (`musica/musica.py`): mezcla la música con bajada automática bajo la voz.
5. **Etiquetas** (`etiquetas/etiquetas.py`): superpone las etiquetas en el momento en que se dicen.

## Requisitos

- Python 3, ffmpeg y Node con Playwright (Chromium), para renderizar las etiquetas.
- Acceso a la API de ElevenLabs. En el entorno de Claude la clave la pone el proxy; en tu PC tendrías que agregar la cabecera `xi-api-key`.

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
