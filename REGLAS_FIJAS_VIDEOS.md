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
- (fabian, 15/11/2026) En los Shorts sacados de un largo: zooms al teléfono y a los botones clave, y los subtítulos
  NUNCA en el centro de la pantalla (no tapan el teléfono ni lo que se explica): van abajo o arriba, en la zona libre.
  Uno de los Shorts dura un minuto y pico; los otros, a criterio, cada uno con un gancho distinto.

## Montaje y subtítulos
- Inicio: rota trozos de video de 3-5 s según lo que dice la voz. Nada de escenas largas ni capturas fijas.
- Subtítulos: estilo C «Shorts», en una línea, con la palabra dicha en amarillo, +50 % de tamaño y un poco más arriba.
- Logos: pop-up de a uno, grande y en el centro, cuando la voz lo nombra.
- Guiones: decir que sirve para «Android 15, 16, 17 o superiores» y para cualquier parche de seguridad.
- OPCIONAL, en prueba (fabian, 14/11/2026), PARA TODAS LAS MARCAS (Xiaomi, Honor, Samsung, Motorola, iPhone…),
  tráiler incluido: si el video va muy rápido, deja pausas cortas entre frases, como cuando
  habla una persona real. Es ensayo y error: pruébalo y pregúntale a fabian si le gusta antes de volverlo fijo. Al terminar cada párrafo, una pausa algo más larga (fabian, 14/11/2026). Y cada
  cierto tramo, una pausa semilarga, como haría una persona al hablar (fabian, 14/11/2026). Además, pausas largas
  (respiros con música) de unos 3 s; su cantidad NO es fija en 3 o 4: imita el promedio de respiros de una narración
  humana real, medido en sus videos más vistos (fabian, 14/11/2026), bien repartidas (no seguidas), para que se escuche la música: evita que suene lineal, «muy IA».
  No exactas: varía entre 2 y 4 s y en lugares distintos, que no parezca un algoritmo en bucle; con sentido común (fabian, 14/11/2026).
  Velocidad (fabian, 15/11/2026): la meta es ~140 palabras/min como sus videos top, pero NO se logra bajando mucho la
  velocidad de ElevenLabs (a 0,85 suena arrastrada). Bajarla lo mínimo, para que no suene ni arrastrada ni robótica
  (≈0,93-0,95), y llegar al ritmo con las pausas y los respiros.
  Ojo con el principio: es donde más faltaban pausas en el HONOR 400 LITE (fabian, 14/11/2026).

## Primeros dos minutos de los videos largos (fabian, 13/11/2026)
- REGLA: dentro de los primeros 2 minutos SIEMPRE se muestran nuestras tarjetas de WhatsApp (en pantalla, cuando la voz
  dice WhatsApp) y la voz invita a comentar (p. ej. «déjame en los comentarios tu modelo y te ayudo»). Vale para todas
  las marcas (Xiaomi, Honor, Samsung…). Revisarlo antes de entregar cualquier video.
- CAMBIO (fabian, 15/11/2026): si choca con el inicio corto (30-40 s y primer paso antes del 1:30), las tarjetas de
  WhatsApp y la invitación a comentar pueden ir cerca del MINUTO 3, dentro de una espera del proceso (por ejemplo
  mientras carga o reinicia el teléfono), sin frenar los pasos.

## Fallos que NO se pueden repetir (fabian, 14/11/2026, HONOR 400 LITE)
- La imagen tiene que coincidir con lo que dice la voz: si dice «así empieza», se ve el ANTES (teléfono bloqueado,
  etiqueta ANTES), nunca la etiqueta DESPUÉS ni pantallas de configuración ya libres.
- En el DURANTE tiene que verse claro el clic en «ERASE FRP BY CODE» y dónde se pega la Key: zoom o círculo sobre el
  botón y sobre el campo, en cámara lenta, sin cortes que confundan.
- Pausas: no ir lineal; sobre todo al principio (ver la regla opcional de pausas en «Montaje y subtítulos»).
- El TRÁILER también: círculo y zoom en el clic de ERASE FRP BY CODE, y pausas buenas, no todo de corrido.
- Cartel de título (ej. «HONOR SIN CUENTA GOOGLE / Desde casa · PC sencilla · KEY oficial»), fabian 15/11/2026: dura
  muy poco, es estático y se ve anticuado (fondo degradado plano con texto). Debe durar lo suficiente para leerlo,
  tener movimiento (entrada animada, video o teléfono de fondo, elementos que aparecen) y un estilo moderno, en vez de
  una placa fija.
- Tomas de datos (etiqueta trasera, caja, serial, IMEI), fabian 15/11/2026: si en la toma NO se lee el dato (serial,
  IMEI…), no se usa ni se le pide al cliente que lo compare; se quita esa parte o se usa una toma donde sí se lea.
- Pop-ups (ej. «cualquier parche de seguridad»), fabian 15/11/2026: nada con aspecto infantil o de caricatura; estilo
  serio, moderno y técnico. Aprobado por fabian (15/11/2026) el pop-up del parche TIPO ANDROID: tarjeta oscura
  Material You con el escudo verde y check, «CUALQUIER PARCHE DE SEGURIDAD» y «Android 15 · 16 · 17»
  (GUIONES-IA main, estilo_video/honor400_titulo/parche_seguridad_android.png). Usar ese estilo en todas las marcas.
- Inicio de un video de un modelo concreto (ej. HONOR 400 LITE), fabian 15/11/2026, todas las marcas: justo después de
  nombrar el modelo, la voz dice que el método funciona igual para todos los modelos de la marca. Es solo en la voz:
  en los títulos de Honor sigue prohibido «Todos los Modelos».
- REGLAS FIJAS de la revisión grande del HONOR 400 LITE (fabian, 15/11/2026, todas las marcas):
  · El subtítulo nunca va encima de carteles, testimonios, botones ni del cartel COMENTA: en esos tramos sube arriba o
    se quita.
  · Los nombres de botones y modelos nunca se parten («Erase FRP By Code» entero). La palabra en amarillo solo cambia
    de color, no se agranda, así no se pegan las palabras. El subtítulo dura hasta que empieza el siguiente, sin parpadear.
  · No se muestra el resultado de un paso antes de explicarlo (ej. el serial ya leído), no se repite la misma toma
    (ej. Place Order una sola vez) y la imagen sigue a la voz («apagamos» → menú de apagar; «termina en 77» → se ven los dos lados).
  · Ninguna pantalla queda quieta más de 4-5 s sin zoom lento o sin una toma de cámara. No hay saltos atrás entre bloques.
  · Siempre va la etiqueta «PARTE ACELERADA» cuando algo va rápido, con 3 momentos claros que se lean.
  · La música va en bucle sin silencios: sin el silencio final de la canción, vueltas unidas con fundido, subidas y
    bajadas de ~1 s y el mismo volumen en todas las partes (testimonios incluidos). Audio a 48 kHz. Se rehace el audio
    en cada armado.
  · El video termina con fundido a negro (sin cortar a mitad de un paneo) y deja 10-15 s para la pantalla final de YouTube.
  · La voz dice que la Key oficial tiene un costo ANTES de decir «gratis» (el programa sí es gratis).
  · Inicio de 30-40 s; el primer paso real antes del 1:30; abrir con el problema («Verifica tu cuenta») y luego el
    teléfono libre en los primeros 10-30 s. Lo legal en una frase, sin repeticiones.
  · Testimonios al final: unos 25 s, con zoom a las 2-3 frases que nombra la voz, y el cartel del país correcto.
  · Confianza: no mostrar «(Instant)», «Success» en segundos ni pedidos «Rejected» si la voz dice que tarda horas;
    recortar y poner «HORAS DESPUÉS…». Si la ventana del programa tiene otro nombre (Easy-Unlocker), una etiqueta lo aclara.
  · Ventanas de PC chicas: recortar solo los botones y el código, al doble de tamaño. El círculo va quieto y encierra
    solo lo que dice la voz (el botón exacto o el modelo), sin que lo tape el cursor.
- La frase de las CAUSAS es importante y NO se quita (fabian, 15/11/2026): por qué el teléfono quedó con la cuenta
  («lo formateaste, lo compraste de segunda mano, te lo regalaron…»). Para respetar el inicio corto, va en una sola
  frase rápida justo después del gancho, o dentro del primer paso, en vez de borrarla.
- Pantalla muy cargada (fabian, 15/11/2026, «muy cargado», HONOR 400 LITE 0:28): nunca el cartel del título y
  varias fichas a la vez sobre el video. Máximo UN elemento grande en pantalla. El título va solo; después, UNA ficha
  a la vez (DESDE CASA, SIN TÉCNICO…), cuando la voz la dice, y se va antes de que entre la siguiente. Que se vea el
  teléfono.
- TESTIMONIOS DE WHATSAPP (fabian, 16/11/2026, HONOR 400 LITE 7:15: el subtítulo «llegó su Key» tapaba el número): en
  cada captura, PRIMERO se muestra entera la cabecera del chat con el PREFIJO del país y el número TACHADO (+506 8…, el
  tachado de siempre), 1-2 s sin nada encima. Después, el zoom a las frases que nombra la voz. El subtítulo y los
  carteles nunca tapan el prefijo ni el número: en ese tramo el subtítulo baja o se oculta. Todas las marcas.
- ORDEN DEL TRÁILER (fabian, 16/11/2026, video_completo_v4: DURANTE salía en 0:24 y ANTES en 0:26): SIEMPRE
  ANTES → DURANTE → DESPUÉS, nunca otro orden, y cada cartel solo una vez. El revisor automático debe comprobarlo.
- SUPER RECARGADO (fabian, 16/11/2026, video_completo_v4 0:39: título + ficha + subtítulo encima del teléfono y de
  una pantalla de fondo ya llena): como máximo UNA capa de texto a la vez. Si está el título o una ficha, el subtítulo
  se oculta en ese tramo (o la ficha no sale), y nunca hay dos carteles juntos. Si el fondo ya tiene mucho texto o
  color (monitor con carteles, cajas), se usa una sola etiqueta chica o ninguna. Ante la duda, menos.
- Tamaño de etiquetas y carteles (fabian, 15/11/2026, «muy agresivas, muy grandes»): nunca tapan el teléfono. El
  título ocupa como máximo ~50-60 % del ancho y va arriba, en el borde. Las fichas son más chicas (~25-30 % del ancho),
  en una esquina o abajo a un lado. Entrada suave, sin golpe.
  Pero tampoco diminutas (fabian, 16/11/2026, la ficha «PC SENCILLA» quedó «muy pequeña»): la ficha mide al menos
  ~25 % del ancho y la letra al menos ~4-5 % del alto del cuadro, para que se lea en el celular. Punto medio: ni
  tapar el teléfono ni que no se lea. Lo mismo para los carteles ANTES / DURANTE / DESPUÉS del tráiler (16/11/2026:
  el ANTES chico también se ve diminuto): al menos ~20-25 % del ancho, en la esquina.
- Transiciones del inicio (fabian, 15/11/2026, «muy rápidas»): en el inicio cada toma dura lo suficiente para verla
  (~3-5 s, nunca cambios de 1 s seguidos), con transiciones suaves (fundido o deslizamiento de ~0,4-0,6 s), no cortes
  en ráfaga. Las etiquetas entran y salen con calma. Vale también para el tráiler ANTES · DURANTE · DESPUÉS (ej. 0:28
  del HONOR 400 LITE 1080p60): cada fase al menos ~3-4 s, con transición suave, y el cartel ANTES/DURANTE/DESPUÉS más
  chico, en una esquina, sin tapar el teléfono ni la PC.
  OJO, fundidos (fabian, 16/11/2026, «aún se mira raro»: 0:11, 0:18 y 0:23 del HONOR_400_LITE_ES_corregido se ven dos
  tomas encimadas como doble exposición): «suave» NO es un fundido largo. Nada de fundidos cruzados largos entre tomas
  con texto o pantallas (se mezclan dos «Verifica tu cuenta» y nada se lee). Usar corte limpio o deslizamiento rápido;
  si hay fundido, ≤0,3 s. Los carteles (ANTES, VERSIÓN EXCLUSIVA…) aparecen enteros y opacos, nunca medio transparentes
  durante una mezcla. Lo que debe ser más lento es la DURACIÓN de cada toma (3-5 s), no la transición.
- Antes de entregar, revisa el video entero (tráiler incluido) buscando estos fallos.

## Procesos
- Honor SÍ necesita PC: nunca «SIN PC» ni «EN 1 MINUTO». La KEY tarda horas, según la saturación del servidor.
- Ganchos válidos para Honor: DESDE CASA, SIN LLEVARLO AL TÉCNICO, SIN DESTAPAR, POR SERVIDOR, UN CLIC, PC SENCILLA.
- Honor, descarga del programa (HONOR Frp KEY - Fastboot Reader), fabian 15/11/2026: la voz y el cartel dicen que el
  programa se descarga desde la DESCRIPCIÓN DEL VIDEO (enlace en la descripción), aunque en pantalla se vea la web.
- Honor, clic en «ERASE FRP BY CODE» (fabian, 14/11/2026, corregida): SIEMPRE en pantalla dividida, la PC de un lado + MATERIAL EXTRA del otro, en simultáneo y en cámara lenta.
- Honor, pantalla «Verifica tu cuenta» de Google (fabian, 14/11/2026): en cámara más lenta mientras NO aparece «Omitir»; es esencial mostrar al cliente que el teléfono SÍ tiene cuenta de Google.
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
ORDEN FIJO (fabian, 16/11/2026): la descripción EMPIEZA con este bloque, en este orden, y TODO LO DEMÁS va DEBAJO
(la línea sobre el video, los capítulos, el aviso «Importante», la invitación a comentar y los hashtags):
```
📥 Descarga aquí PROGRAMA HONOR FRP:
https://gsmprime.co/descargas/honor-frp-key-unlock-fastboot-reader

🌐 Grupo De TESTIMONIOS WhatsApp :
https://www.whatsapp.com/channel/0029Vb600gcA2pLKICoAoZ10

Visita Nuestras paginas oficales:
https://gsmprime.co/testimonios/honor/
https://www.xiaomiunlock.com/

📞 Para más detalles, contacta nuestro soporte en WhatsApp 🤙:
🌎 Soporte Latinoamérica 1:
https://wa.me/573186888787
🌎 Soporte México:
https://wa.me/526645320704
🌎 Soporte Europa (España):
https://wa.me/34627450100
```
En otros idiomas se traducen los textos (no los enlaces).
En los SHORTS (fabian, 16/11/2026) va el mismo bloque y en el mismo orden, pero los soportes llevan el NÚMERO escrito, sin enlace wa.me: +57 3186888787, +52 6645320704 y +34 627450100.
 En otras marcas va el mismo orden, con su programa y su
página de testimonios.
Antes (regla anterior): primero una línea sobre el video, y después SIEMPRE el bloque de contacto:
- Canal de WhatsApp: https://www.whatsapp.com/channel/0029Vb600gcA2pLKICoAoZ10
- Soporte Latinoamérica 1: https://wa.me/573186888787
- Soporte México: https://wa.me/526645320704
- Soporte Europa (España): https://wa.me/34627450100

## Entregas
- Da siempre un enlace clickeable: http://estudio.localhost:8765/ver?ruta=… para archivos y /carpeta?ruta=… para carpetas.
- Da también la ruta completa de Windows.
- Los enlaces estudio.localhost solo abren en la PC donde están los archivos.
- REGLA (fabian, 16/11/2026), todas las marcas y todos los idiomas: cada video que se entrega (largo y Short) va
  CATEGORIZADO en su propia carpeta, con TITULO.txt (el título principal más 2 o 3 recomendados), DESCRIPCION.txt
  (con los CAPÍTULOS con tiempos reales sacados del video final, en los largos), ETIQUETAS.txt (las etiquetas de
  YouTube, máximo 500 caracteres) y HASHTAGS.txt (3-5). Todo en el idioma del video, con las reglas de títulos de cada
  marca y el bloque de contacto de WhatsApp.
- **Textos de YouTube finos (fabian 16/11/2026, todas las marcas):**
  - DESCRIPCIÓN: después del bloque fijo, una línea gancho con emoji (🔓 ¿…? ¡…!), secciones con separador ━━━ y título con emoji (✅ ¿QUÉ NECESITAS?, 🔧 ¿CÓMO FUNCIONA?), pasos numerados 1️⃣ 2️⃣…, ⚠️ IMPORTANTE y cierre 💬 invitando a comentar modelo y país. Signos completos (¿? ¡!), comillas «», nada de texto en bloque, emojis con medida.
  - CAPÍTULOS: cada uno con su emoji y un título corto (ej. «5:07 ✅ Erase FRP By Code: ¡1 clic y listo!»), tiempos reales del video final.
  - TÍTULOS: unos 10 recomendados por video EN ORDEN DE BÚSQUEDAS REALES; el 1 junta la búsqueda más fuerte con la fórmula que más rinde en el canal (ej. «Cómo Quitar Cuenta de Google en Honor 400 Lite en 1 Clic | Sin PC Avanzada 2026»), según el contexto del video y lo más buscado en su YouTube y en Google; con las reglas de títulos de cada marca, 100 caracteres o menos. En Shorts, 10 con #shorts y cada Short encabeza con un título distinto.
  - HASHTAGS: 3-5 que COMPLEMENTAN las etiquetas con algo distinto (no repetirlas) y varían entre videos y entre largo y Shorts (ej. #Honor400Lite #AdiósCuentaGoogle #DesbloqueoLegal #HonorMagicOS #Xiaomiunlock; Shorts: #CelularLibre #TrucosAndroid).
- **Fuentes de títulos y etiquetas (fabian 16/11/2026, todas las marcas):** no solo su YouTube. Juntar 3 fuentes: (1) las búsquedas reales de su canal (API de YouTube); (2) lo más top en Google y en el autocompletado de YouTube (suggestqueries, ej. «quitar cuenta google honor 400 lite con pc», «honor 400 5g»); (3) los títulos de la competencia en YouTube (ej. «FRP Bypass» sale en 32 de 87 títulos de Honor). Después se filtran con las reglas de la marca: en Honor nunca «sin pc», «gratis/free» ni «todos los modelos», aunque se busquen. Emojis en el TÍTULO: no, porque en su canal rinden ×0,65; van en la descripción.
- ETIQUETAS CON BÚSQUEDAS REALES (fabian, 16/11/2026, todas las marcas): las etiquetas salen de las búsquedas que traen gente a
  sus videos (API de YouTube); nunca «magicos 9». Base por proceso (Honor FRP, Xiaomi Mi Account, Xiaomi FRP) en
  mis_conocimientos/youtube_canal/etiquetas_base/ y marcas/ETIQUETAS_POR_BUSQUEDAS.md. Orden: modelo → códigos técnicos →
  primos → búsquedas base → generales, 500 caracteres o menos.
- ETIQUETAS de un video de MODELO EXCLUSIVO (fabian, 16/11/2026, todas las marcas): además del modelo, van sus modelos
  «primos» de la misma serie (ej. HONOR 400 LITE → honor 400, honor 400 pro, honor 400 smart) y sus códigos técnicos,
  SOLO los del modelo del video (ej. Honor 400 Lite: ABR-NX1, ABR-NX3, ABR-N31C1). El método es exclusivo pero también
  general: la voz dice que sirve para todos los modelos. Más adelante el mismo video se reedita en versión general
  para todos los modelos.
- CARPETAS (fabian, 16/11/2026): toda entrega va en C:\ElementosGPT\videos_finales\MARCA\MODELO\IDIOMA (ES, EN, PT)
  o \MARCA\MODELO\SHORTS\SHORT_n_IDIOMA\. Primero una carpeta por marca (HONOR, XIAOMI, SAMSUNG, MOTOROLA, IPHONE…);
  cada video, con sus textos, en su propia carpeta. Ej.: videos_finales\HONOR\HONOR_400_LITE\ES\.

## Detalle técnico (versión de la app en la nube, fusionada el 16/11/2026)
Reglas que estaban solo en la rama de la app. Si algo choca con lo de arriba, manda lo de arriba.

### Otras líneas
- Inicio de los Shorts (fabian 15/11/2026, de la revisión grande): en los primeros 1-3 s el problema («Verifica tu cuenta» o la pantalla de bloqueo) y enseguida el teléfono libre; el primer paso real antes de los 10-15 s, sin introducción. Lo de «inicio de 30-40 s» y «primer paso antes del 1:30» es solo para los videos largos.
- **Antes del minuto 2** (fabian, 13/11/2026): tarjetas de WhatsApp de soporte (Latinoamérica, México, España) en pantalla y la voz invita, de forma creativa, a escribir por WhatsApp y a comentar con el modelo exacto. Opciones por marca en GUIONES-IA `comentar/` (módulo COMENTAR). Excepción (fabian 15/11/2026): si no cabe antes de 2:00 sin atrasar el primer paso (antes del 1:30), puede ir hasta el minuto 3; las páginas siguen entre 1:00 y 2:00.
- **Zoom en la pantalla de la PC** (fabian, 13/11/2026): cuando el programa, la web o el dato se ven chicos en la grabación de la pantalla (material extra), hacer zoom suave hasta la ventana o el campo que nombra la voz (Read Fastboot Info y serial, campo Erase FRP By Code con la KEY, pedido y KEY en la web). Zoom donde sea necesario para que se lea en el celular; después vuelve a la vista completa.
- **Clic en Erase FRP By Code: pantalla dividida y cámara lenta** (fabian, 14/11/2026): en el paso del clic en «Erase FRP By Code», SIEMPRE poner en simultáneo (pantalla dividida, lado a lado) a un lado el MATERIAL EXTRA (la grabación de la pantalla de la PC con el clic y la KEY) y al otro el video real de la cámara (el teléfono que se reinicia solo), sincronizados en el momento del clic y en cámara lenta (≈0,5×) unos segundos. Todas las marcas que tengan ese paso.
- Pop-ups de datos (parche de seguridad, versión de Android, etc.) nunca «de niños»: estilo tarjeta de Ajustes de Android oscura, el aprobado por fabian el 15/11/2026 (GUIONES-IA `estilo_video/honor400_titulo/parche_seguridad_android.png`), para todas las marcas, unos 3 s en pantalla.
- **Carpetas por marca (fabian 16/11/2026):** en C:\ElementosGPT\videos_finales\ va PRIMERO una carpeta por marca (HONOR, XIAOMI, SAMSUNG, MOTOROLA, IPHONE…), después el modelo y adentro ES, EN, PT y SHORTS. Ejemplo: videos_finales\HONOR\HONOR_400_LITE\ES\ con el video y sus TITULO, DESCRIPCION, ETIQUETAS y HASHTAGS .txt.
- **Pausas humanas al hablar — TODAS LAS MARCAS (Honor, Xiaomi, Samsung, Motorola, iPhone…) y todos los tutoriales, Shorts y tráileres; el tráiler/inicio también (fabian 14/11: «que no quede solo para Honor sino multimarca»)** (fabian, 14/11/2026: «vamos muy rápido… como si fuese una persona real quien habla»): pausa de ~0,8 s al final de cada frase, ~0,3 s en cada coma de la voz y al terminar cada párrafo (bloque) una pausa más larga de ~1,6 s (fabian 14/11: «finalizando algún párrafo, debemos aún añadirle una pausa»; antes 0,8 s), además, cada ~20 palabras una pausa semilarga de ~1,4 s al terminar la frase, como respira una persona (fabian 14/11: «cada cierta parte pausas semi largas, emulando un tono humano»), y la voz ~3 % más lenta (~7 % en pasos críticos: serial, KEY, Erase FRP); además 3 o 4 RESPIROS por video de 2 a 4 s (distintos entre sí, en momentos clave: modo fastboot, KEY obtenida, tras Erase FRP, Omitir) donde la voz calla y la música sube (0,10 → 0,32) para que se escuche; todas las pausas varían un poco al azar para que no suene a algoritmo en bucle (fabian 14/11: «algo de sentido común»); punto medio ≈120 palabras por minuto; sin regrabar (se corta la voz ya grabada en los puntos). Es OPCIONAL, de ensayo y error: probarla y ajustar los tiempos según lo que diga fabian.
- **Velocidad de la voz — FIJA desde el 15/11/2026 (fabian: «bajarle el mínimo para que no se note arrastrada ni robótica»)**: la app usa SOLA el estilo «Voz natural + pausas largas» del módulo 🎵 Ritmo (por defecto en cada video nuevo, todas las marcas): voz ×0,95 (×0,93 en serial/KEY/Erase, ×0,97 en pasos obvios y en los primeros 2 minutos), pausa de frase ~0,95 s, semilarga ~1,6 s cada ~20 palabras, ~1,6 s al final de cada párrafo y un respiro de 2-3,8 s con la música arriba cada ~30 s de voz, NUNCA antes del minuto 2 (WhatsApp y «comenta» antes de 2:00). NUNCA bajar la voz a ×0,85 (suena arrastrada). La velocidad se baja en la edición (sin regrabar): NO mandar también speed a ElevenLabs (frenaría dos veces). Meta: ~115-120 palabras/min contando pausas (~155 hablando). El guion se escribe a ~2 palabras por segundo de bloque. Otros estilos para elegir: «Calibrado con tus videos» (voz ×0,90), «Humano», «Pausas v2», «Antes».
- **Pantalla de bloqueo (Verifica tu cuenta de Google, Mi Account, iCloud…) en TODAS las marcas; fabian, 14/11/2026):** mientras se ve la pantalla de verificación SIN el botón «Omitir», va en cámara más lenta (≈0,5×, unos 8-10 s en pantalla), porque es esencial mostrarle al cliente que el teléfono SÍ tiene cuenta de Google. Ejemplo: Honor 400 Lite, minuto 1:17.

### Fallos que NO se pueden repetir — TODAS LAS MARCAS (fabian, 14/11/2026; salieron de la revisión del Honor 400 Lite, 49 fallos confirmados)
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

### Revisor automático antes de entregar — TODAS LAS MARCAS, en la app y en la nube (fabian, 15/11/2026)
fabian: «¿cómo hacemos para que esto no vuelva a suceder… tanto acá en la nube de Claude como en la app?». Lo que pasó en el Honor 400 Lite: un tramo salió 5,6 s más corto (cuadros viejos de un círculo de otro tamaño) y desde 4:37 TODA la imagen iba adelantada a la voz (la Key antes de «la Key aparece», Android 17 sobre «MagicOS 9»); además saldos ($4535) y $50 a la vista y WhatsApp en 2:13.
- `revision/revisor_auto.py` corre SOLO al final de cada video (app: paso final; nube: final.py) y NO se entrega si falla. Gratis, en la PC. Revisa:
  1. Imagen y sonido duran lo mismo (si no, hay desfase) y, con `--bloques`, que cada tramo dure lo que dice su voz.
  2. Sin precios ni saldos en pantalla (OCR de «$…», «… USD»). Se cambia la toma o se recorta, nunca se difumina.
  3. WhatsApp + «comenta» antes de 2:00 y GSMPRIME.CO / XIAOMIUNLOCK.COM entre 1:00 y 2:00 (aunque la voz lo deletree). No en noticias (`--noticia`).
  4. «Así empieza / bloqueado» nunca sobre el cartel DESPUÉS, ni «termina / libre» sobre ANTES.
  5. Ritmo (aviso): máx. 130 palabras/min contando las pausas y al menos un respiro de 1,4 s por minuto.
  6. Chasquidos en el sonido (aviso), planos de más de 5 s al inicio, subtítulos, palabras que la voz nombra y se tienen que leer.
- Cualquier script que arme imágenes de a cuadros (círculos, etiquetas) BORRA la carpeta antes de volver a generarla: los cuadros viejos de otro tamaño cortaban el tramo.
- Claude en la nube, además, mira el video entero como espectador antes de entregarlo (no solo esta lista).

### Inicio de un video de un modelo concreto — TODAS LAS MARCAS (fabian, 15/11/2026)
- Si el video es «VERSIÓN EXCLUSIVA» de un modelo (ej. HONOR 400 LITE), la voz dice ENSEGUIDA que el método funciona igual para todos los modelos de la marca («Y si tienes otro Honor, tranquilo: este método sirve para todos los modelos de Honor»). Nunca se recorta esa frase del tráiler. Solo en la voz: en títulos de Honor sigue sin ir «Todos los Modelos» (03/11).
- El cartel de título (ej. «HONOR SIN CUENTA GOOGLE · Desde casa · PC sencilla · KEY oficial») dura TODA la frase que lo dice (5-7 s, no 1 s), con movimiento (palabras que entran, destello, fichas que aparecen cuando la voz las nombra) y sobre video real, nunca un fondo quieto. Estilo moderno, hecho con el ChatGPT de fabian (vidrio esmerilado del kit).
- Pop-ups de datos (parche de seguridad, versiones): serios y profesionales, nada que parezca para niños.
- Descargar el programa (fabian 15/11/2026, todas las marcas): la voz y el cartel dicen que se descarga desde el ENLACE EN LA DESCRIPCIÓN DEL VIDEO; en pantalla no se muestra la web de descargas (se ve el programa).
- Tomas de datos que no se leen (fabian 15/11/2026, todas las marcas): si en la etiqueta trasera, la caja, el serial o el IMEI no se lee el dato, esa toma no va y la voz no le pide al cliente que compare. Se quita la frase (recortando la voz, sin regrabar) o se usa una toma donde sí se lea.

### Etiquetas y transiciones calmadas — TODAS LAS MARCAS (fabian, 15/11/2026: «etiquetas muy agresivas, muy grandes… las transiciones en el inicio están muy rápidas»)
- **Título del inicio** (ej. «HONOR SIN CUENTA GOOGLE»): arriba, ocupa como mucho el 50-60 % del ancho, NUNCA encima del teléfono. Entra suave (crece de 0,9 a 1,0 en ~0,5 s), sin rebote ni latido fuerte.
- **Fichas** («DESDE CASA», «SIN TÉCNICO», «PC SENCILLA»…): tamaño medio, al menos ~25 % del ancho y letra legible en el celular (fabian 16/11: a 13 % «quedó muy pequeño»), en una esquina (abajo a la izquierda), sin tapar el teléfono ni lo que la voz nombra; entran suaves cuando la voz las dice.
- **Tomas del inicio**: lo lento es la DURACIÓN de cada toma (3-5 s), no la transición (fabian 16/11: «aún se mira raro», los fundidos de 0,45 s dejaban dos tomas encimadas, como doble exposición). Transición = corte limpio o deslizamiento rápido; si hay fundido, ≤0,3 s y nunca mezclando pantallas con texto. Carteles siempre opacos y enteros, nada medio transparente.
- **ANTES / DURANTE / DESPUÉS**: SIEMPRE en ese orden (fabian 15/11: en el video viejo DURANTE salía antes que ANTES); cada fase en pantalla al menos 3-4 s, con un cartel tipo píldora en la esquina de arriba a la izquierda (rojo / naranja / verde) de TAMAÑO MEDIO: ~20-25 % del ancho (fabian 16/11: el de 13 % «quedó muy pequeño»), nunca un cartel grande en el centro, y corte limpio entre fases (uno sale antes de que entre el otro).
- En Shorts las etiquetas son tarjetas tipo celular (oscuras, redondeadas, chicas), arriba de la zona del video; subtítulos abajo, nunca al centro.
- **Pantalla NO recargada (fabian 15/11/2026, captura del título a 0:39: «está super recargado»)**: como mucho 2 elementos gráficos a la vez además de los subtítulos (ej. título chico arriba + 1 ficha en la esquina). Nunca título grande + ficha + flecha + subtítulo juntos encima del teléfono. Cada elemento entra cuando la voz lo nombra y sale antes del siguiente; el teléfono y la acción siempre se ven limpios. Revisar cada cartel como lo vería él en el celular: si hay que «buscar» el teléfono entre carteles, sobra uno. Mientras está el título o una ficha, el subtítulo se oculta en ese tramo (final_subs.py ya lo hace en el título del inicio). Si el fondo ya está lleno (monitor con carteles, cajas), va una sola etiqueta chica o ninguna. Ante la duda, menos.
- **Testimonios de WhatsApp — prefijo y número tachado (fabian 16/11/2026, TODAS las marcas, CADA captura)**: cada captura de testimonio se muestra primero ENTERA ~1-1,3 s, con la cabecera visible (prefijo del país + número tachado), sin nada encima; recién después va el zoom a las frases que nombra la voz. El subtítulo nunca tapa el prefijo ni el número: en los testimonios no va subtítulo arriba (la frase amarilla ya resume). En la nube: testimonios_zoom.py (FULLBOX) y final_subs.py.
