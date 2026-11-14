# Reglas fijas de videos y Shorts (fabian)

Léelo ANTES de armar cualquier video, Short, guion, voz o miniatura. Aplica todo esto SIN preguntarle a fabian. Basta con
decir en una línea que lo aplicaste. Pregunta solo lo que no esté aquí ni en `AGENTS.md` / `mis_conocimientos`.
Cuando fabian diga «agrégalo a las reglas fijas», súmalo aquí, con la fecha.

## Voces (ElevenLabs, modelo eleven_v4)
- Español y portugués: Mauricio, id `94zOad0g7T7K4oa7zhDq`.
- Inglés: Brian, id `nPczCjzI2devNBz1zQrb`.
- Grabar gasta créditos: pide una sola vez su «SI» escrito, con el número de créditos. La clave va en la app (botón 🔑),
  nunca en el chat.

## Emociones en la voz
- Máximo 3 etiquetas por minuto, nunca dos seguidas.
- Prefiere [chuckles] a [laughs]. Casi nunca [whispers]. No pongas [excited] si la frase ya tiene «¡…!».
- Avatar HeyGen: solo en el inicio y en tramos cortos, con «Más expresivo» apagado.

## Círculos y difuminado
- Circula SIEMPRE el dato clave con zoom: serial, Key, Unlock code, IMEI, «Find device», estado del pedido.
- Nunca difumines nada.
- En el cierre no van círculos ni flechas.

## Páginas oficiales
- En todos los Shorts y tutoriales va «GSMPRIME.CO • XIAOMIUNLOCK.COM» en pantalla, y la voz las nombra:
  «G S M Prime punto co» y «Xiaomi Unlock punto com».
- NUNCA en miniaturas ni en portadas de Shorts. Nunca FRPUNLOCK.CO.
- Los videos de noticias no llevan publicidad de desbloqueo.

## Cierre de los Shorts
- Orden: … → frase de las webs → frase de testimonios → frase del play.
- Testimonios: «…cientos de testimonios en nuestro canal de WhatsApp; el enlace para unirte está en la descripción del
  tutorial completo».
- Frase del play, rotando (Short 1 → la 1, Short 2 → la 2, Short 3 → la 3; EN/PT en `short/resumen.py`, CIERRES):
  1. «Toca el enlace con el ícono de play, aquí abajo, y mira el tutorial completo.»
  2. «¿Quieres verlo paso a paso? El video completo está aquí abajo, en el enlace con el play.»
  3. «Mira el tutorial completo: toca el play que aparece abajo.»
- Cuando la voz dice «play», sale el ícono de play ABAJO a la izquierda, con una flecha hacia el enlace «Video relacionado».
- Nunca mandes «a la descripción» para ver el tutorial.
- Cada Short resume el proceso COMPLETO, con un gancho distinto.

## Montaje y subtítulos
- **Antes del minuto 2** (fabian, 13/11/2026): tarjetas de WhatsApp de soporte (Latinoamérica, México, España) en pantalla y la voz invita, de forma creativa, a escribir por WhatsApp y a comentar con el modelo exacto. Opciones por marca en GUIONES-IA `comentar/` (módulo COMENTAR).
- **Zoom en la pantalla de la PC** (fabian, 13/11/2026): cuando el programa, la web o el dato se ven chicos en la grabación de la pantalla (material extra), hacer zoom suave hasta la ventana o el campo que nombra la voz (Read Fastboot Info y serial, campo Erase FRP By Code con la KEY, pedido y KEY en la web). Zoom donde sea necesario para que se lea en el celular; después vuelve a la vista completa.
- **Clic en Erase FRP By Code: pantalla dividida y cámara lenta** (fabian, 14/11/2026): en el paso del clic en «Erase FRP By Code», SIEMPRE poner en simultáneo (pantalla dividida, lado a lado) a un lado el MATERIAL EXTRA (la grabación de la pantalla de la PC con el clic y la KEY) y al otro el video real de la cámara (el teléfono que se reinicia solo), sincronizados en el momento del clic y en cámara lenta (≈0,5×) unos segundos. Todas las marcas que tengan ese paso.
- Inicio: rota trozos de video de 3-5 s según lo que dice la voz. Nada de escenas largas ni capturas fijas.
- Subtítulos: estilo C «Shorts», en una línea, con la palabra dicha en amarillo, +50 % de tamaño y un poco más arriba.
- Logos: pop-up de a uno, grande y en el centro, cuando la voz lo nombra.
- Guiones: decir que sirve para «Android 15, 16, 17 o superiores» y para cualquier parche de seguridad.

## Procesos
- Honor SÍ necesita PC: nunca «SIN PC» ni «EN 1 MINUTO». La KEY tarda horas, según la saturación del servidor.
- Ganchos válidos para Honor: DESDE CASA, SIN LLEVARLO AL TÉCNICO, SIN DESTAPAR, POR SERVIDOR, UN CLIC, PC SENCILLA.
- SIN PC solo en Xiaomi Mi Account y en la liberación de bandas de iPhone.

## Portadas de Shorts y miniaturas
- Las hace ChatGPT con el estilo de `mis_conocimientos/miniaturas/ESTILO_MINIATURAS.md`, nunca dibujadas por la app.
- **NUNCA inventar pantallas** (fabian, 06/11/2026): en el teléfono solo van pantallas que fabian suministró (sus capturas
  o fotos reales del proceso). A ChatGPT se le pasa la captura real y se le pide copiarla tal cual, sin redibujar textos.
  Si falta la captura de una pantalla, pídesela; no la inventes.
- Los chats van SIEMPRE dentro del proyecto de ChatGPT, nunca sueltos.
- Portadas de Shorts:
  - el título arriba;
  - nada legible en el 30 % de abajo, porque lo tapa el título de YouTube;
  - un teléfono grande, rotando las vistas;
  - limpias: título + teléfono + 1 gancho;
  - sin páginas web.

## Descripción de YouTube
Primero una línea sobre el video, y después SIEMPRE el bloque de contacto:
- Canal de WhatsApp: https://www.whatsapp.com/channel/0029Vb600gcA2pLKICoAoZ10
- Soporte Latinoamérica 1: https://wa.me/573186888787
- Soporte México: https://wa.me/526645320704
- Soporte Europa (España): https://wa.me/34627450100

## Entregas
- Da siempre un enlace clickeable: http://estudio.localhost:8765/ver?ruta=… para archivos y /carpeta?ruta=… para carpetas.
- Da también la ruta completa de Windows.
- Los enlaces estudio.localhost solo abren en la PC donde están los archivos.
- **(OPCIONAL, en prueba) Pausas cortas al hablar** (fabian, 14/11/2026: «vamos muy rápido… como si fuese una persona real quien habla»): pausa de ~0,8 s al final de cada frase, ~0,3 s en cada coma de la voz y al terminar cada párrafo (bloque) una pausa más larga de ~1,6 s (fabian 14/11: «finalizando algún párrafo, debemos aún añadirle una pausa»; antes 0,8 s), además, cada ~20 palabras una pausa semilarga de ~1,4 s al terminar la frase, como respira una persona (fabian 14/11: «cada cierta parte pausas semi largas, emulando un tono humano»), y la voz ~3 % más lenta (~7 % en pasos críticos: serial, KEY, Erase FRP); además 3 o 4 RESPIROS por video de 2 a 4 s (distintos entre sí, en momentos clave: modo fastboot, KEY obtenida, tras Erase FRP, Omitir) donde la voz calla y la música sube (0,10 → 0,32) para que se escuche; todas las pausas varían un poco al azar para que no suene a algoritmo en bucle (fabian 14/11: «algo de sentido común»); punto medio ≈120 palabras por minuto; sin regrabar (se corta la voz ya grabada en los puntos). Es OPCIONAL, de ensayo y error: probarla y ajustar los tiempos según lo que diga fabian.
- **Pantalla «Verifica tu cuenta» de Google (Honor y FRP en general; fabian, 14/11/2026):** mientras se ve la pantalla de verificación SIN el botón «Omitir», va en cámara más lenta (≈0,5×, unos 8-10 s en pantalla), porque es esencial mostrarle al cliente que el teléfono SÍ tiene cuenta de Google. Ejemplo: Honor 400 Lite, minuto 1:17.

## Fallos que NO se pueden repetir (fabian, 14/11/2026, revisión del Honor 400 Lite con 49 fallos confirmados)
Antes de entregar cualquier video, revisarlo ENTERO (ver y escuchar como persona, no solo contra esta lista) buscando estos fallos:
**Imagen = voz**
- Si la voz dice «así empieza / bloqueado» se ve el ANTES; si dice «así termina / libre» se ve el DESPUÉS. Nunca la etiqueta equivocada.
- En el DURANTE (inicio y tutorial), el clic en ERASE FRP BY CODE y el campo donde se pega la KEY van claros: zoom a la ventana (botones + código legibles en el celular), círculo en el botón correcto (centrado en Erase, no en Reboot) y cámara lenta.
- No mostrar el resultado de un paso antes de explicarlo (serial ya leído, pedido ya enviado) y no repetir la misma toma (Place Order una sola vez).
- La acción va sobre la frase que la nombra («apagamos» → menú de apagar; «descargas» → página de descarga con círculo en Descargar; «termina en 77/W» → se ven LOS DOS lados con círculo en los últimos caracteres).
- Círculos fijos sobre el dato (nombre del modelo, KEY): si el teléfono se mueve, el círculo se quita; círculos del mismo color del kit, nunca blancos sobre fondo blanco; el cursor no tapa el dato.
- Bloques consecutivos sin salto atrás (el reinicio no se ve dos veces).
**Ritmo visual**
- Ninguna pantalla quieta más de 4-5 s sin zoom lento o toma de cámara; webs a velocidad normal (no cámara lenta de una página quieta).
- Toda parte acelerada lleva la etiqueta «PARTE ACELERADA» y deja 2-3 momentos legibles.
- El video termina con fundido a negro + 10-15 s para la pantalla final de YouTube (nunca cortar a mitad de un paneo).
**Legibilidad en celular**
- Capturas de WhatsApp/testimonios con zoom a las frases que nombra la voz (nunca tira finita con 60 % negro).
**Sonido**
- Música en bucle sin silencios ni reinicio audible (fundido 2-3 s entre vueltas), subidas/bajadas suaves (~1 s), mismo volumen en todas las partes (inicio, cuerpo, testimonios, cierre); el audio se rehace en cada armado; salida a 48 kHz.
- Pausas humanas también en el INICIO (no solo en el cuerpo).
**Subtítulos**
- Nunca encima de carteles (ANTES/DURANTE/DESPUÉS, testimonios, COMENTA) ni de botones: ahí van arriba o no van.
- La palabra amarilla solo cambia de color (sin agrandar: si no, se pegan las palabras); sin parpadeo entre palabras; nombres de botones y modelos nunca partidos («Erase FRP By Code», «Read Fastboot Info», «Honor 400 Lite»).
**Retención y confianza**
- El primer paso real antes del 1:30; inicio de 30-40 s que abre con el problema (0-3 s) y el resultado (4-8 s); testimonios ~25 s.
- Decir que la KEY tiene costo antes de decir «gratis»; nada en pantalla que contradiga a la voz («(Instant)», «Success» en segundos, pedidos «Rejected», carteles de otro país/modelo); si el programa se llama distinto en la ventana, aclararlo con una etiqueta.
