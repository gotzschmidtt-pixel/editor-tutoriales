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
