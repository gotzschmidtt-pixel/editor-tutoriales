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
- Inicio de los Shorts (fabian 15/11/2026, de la revisión grande): en los primeros 1-3 s el problema («Verifica tu cuenta» o la pantalla de bloqueo) y enseguida el teléfono libre; el primer paso real antes de los 10-15 s, sin introducción. Lo de «inicio de 30-40 s» y «primer paso antes del 1:30» es solo para los videos largos.

## Montaje y subtítulos
- **Antes del minuto 2** (fabian, 13/11/2026): tarjetas de WhatsApp de soporte (Latinoamérica, México, España) en pantalla y la voz invita, de forma creativa, a escribir por WhatsApp y a comentar con el modelo exacto. Opciones por marca en GUIONES-IA `comentar/` (módulo COMENTAR). Excepción (fabian 15/11/2026): si no cabe antes de 2:00 sin atrasar el primer paso (antes del 1:30), puede ir hasta el minuto 3; las páginas siguen entre 1:00 y 2:00.
- **Zoom en la pantalla de la PC** (fabian, 13/11/2026): cuando el programa, la web o el dato se ven chicos en la grabación de la pantalla (material extra), hacer zoom suave hasta la ventana o el campo que nombra la voz (Read Fastboot Info y serial, campo Erase FRP By Code con la KEY, pedido y KEY en la web). Zoom donde sea necesario para que se lea en el celular; después vuelve a la vista completa.
- **Clic en Erase FRP By Code: pantalla dividida y cámara lenta** (fabian, 14/11/2026): en el paso del clic en «Erase FRP By Code», SIEMPRE poner en simultáneo (pantalla dividida, lado a lado) a un lado el MATERIAL EXTRA (la grabación de la pantalla de la PC con el clic y la KEY) y al otro el video real de la cámara (el teléfono que se reinicia solo), sincronizados en el momento del clic y en cámara lenta (≈0,5×) unos segundos. Todas las marcas que tengan ese paso.
- Inicio: rota trozos de video de 3-5 s según lo que dice la voz. Nada de escenas largas ni capturas fijas.
- Subtítulos: estilo C «Shorts», en una línea, con la palabra dicha en amarillo, +50 % de tamaño y un poco más arriba.
- Logos: pop-up de a uno, grande y en el centro, cuando la voz lo nombra.
- Pop-ups de datos (parche de seguridad, versión de Android, etc.) nunca «de niños»: estilo tarjeta de Ajustes de Android oscura, el aprobado por fabian el 15/11/2026 (GUIONES-IA `estilo_video/honor400_titulo/parche_seguridad_android.png`), para todas las marcas, unos 3 s en pantalla.
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
**Videos largos de Honor (fabian, 16/11/2026: «LO DEMAS, DEBAJO DE ESTA»):** la descripción EMPIEZA con su bloque fijo, exacto
y en este orden, y todo lo demás va debajo (línea del video, capítulos, cuerpo, hashtags). La app lo pone sola
(`youtube.con_contacto(..., marca)`, bloque en `mis_conocimientos/youtube_canal/contacto_descripcion.json` → `por_marca.honor`):
1. 📥 Descarga aquí PROGRAMA HONOR FRP: https://gsmprime.co/descargas/honor-frp-key-unlock-fastboot-reader
2. 🌐 Grupo De TESTIMONIOS WhatsApp: https://www.whatsapp.com/channel/0029Vb600gcA2pLKICoAoZ10
3. Visita Nuestras páginas oficiales: https://gsmprime.co/testimonios/honor/ y https://www.xiaomiunlock.com/
4. 📞 Soportes: Latinoamérica 1 https://wa.me/573186888787 · México https://wa.me/526645320704 · Europa (España) https://wa.me/34627450100
- En EN y PT se traducen solo los rótulos; los enlaces quedan iguales.
- **Shorts de Honor** (fabian 16/11): el MISMO bloque primero, pero los soportes con su NÚMERO y no el enlace:
  +57 3186888787 · +52 6645320704 · +34 627450100 (`por_marca.honor_short`).

**Otras marcas:** primero una línea sobre el video, y después SIEMPRE el bloque de contacto:
- Canal de WhatsApp: https://www.whatsapp.com/channel/0029Vb600gcA2pLKICoAoZ10
- Soporte Latinoamérica 1: https://wa.me/573186888787
- Soporte México: https://wa.me/526645320704
- Soporte Europa (España): https://wa.me/34627450100

- **Etiquetas de un modelo exclusivo, todas las marcas (fabian 16/11/2026):** además del modelo exacto, poner sus MODELOS PRIMOS de la misma serie (ej. Honor 400 Lite → Honor 400, 400 Pro, 400 Smart) y los CÓDIGOS TÉCNICOS solo del modelo del video (ej. ABR-NX1, ABR-NX3, ABR-N31C1; buscarlos en GSMArena «Models» y en «Acerca del teléfono»), más los términos generales de la marca (frp honor, erase frp by code…). Orden: modelo exacto → códigos técnicos → primos → generales, en 500 caracteres o menos. El método es exclusivo pero también general: más adelante el mismo video se edita para los otros modelos. Nunca decir en título ni descripción que el método sirve en un primo sin probarlo: los primos van solo en etiquetas.

**Entrega (fabian 16/11):** cada video y Short, categorizado por idioma/tipo, con títulos recomendados, descripción con
capítulos, etiquetas (500 caracteres o menos), 3-5 hashtags, categoría y comentario fijado.

## Entregas
- **Carpetas por marca (fabian 16/11/2026):** en C:\ElementosGPT\videos_finales\ va PRIMERO una carpeta por marca (HONOR, XIAOMI, SAMSUNG, MOTOROLA, IPHONE…), después el modelo y adentro ES, EN, PT y SHORTS. Ejemplo: videos_finales\HONOR\HONOR_400_LITE\ES\ con el video y sus TITULO, DESCRIPCION, ETIQUETAS y HASHTAGS .txt.
- Da siempre un enlace clickeable: http://estudio.localhost:8765/ver?ruta=… para archivos y /carpeta?ruta=… para carpetas.
- Da también la ruta completa de Windows.
- Los enlaces estudio.localhost solo abren en la PC donde están los archivos.
- **Pausas humanas al hablar — TODAS LAS MARCAS (Honor, Xiaomi, Samsung, Motorola, iPhone…) y todos los tutoriales, Shorts y tráileres; el tráiler/inicio también (fabian 14/11: «que no quede solo para Honor sino multimarca»)** (fabian, 14/11/2026: «vamos muy rápido… como si fuese una persona real quien habla»): pausa de ~0,8 s al final de cada frase, ~0,3 s en cada coma de la voz y al terminar cada párrafo (bloque) una pausa más larga de ~1,6 s (fabian 14/11: «finalizando algún párrafo, debemos aún añadirle una pausa»; antes 0,8 s), además, cada ~20 palabras una pausa semilarga de ~1,4 s al terminar la frase, como respira una persona (fabian 14/11: «cada cierta parte pausas semi largas, emulando un tono humano»), y la voz ~3 % más lenta (~7 % en pasos críticos: serial, KEY, Erase FRP); además 3 o 4 RESPIROS por video de 2 a 4 s (distintos entre sí, en momentos clave: modo fastboot, KEY obtenida, tras Erase FRP, Omitir) donde la voz calla y la música sube (0,10 → 0,32) para que se escuche; todas las pausas varían un poco al azar para que no suene a algoritmo en bucle (fabian 14/11: «algo de sentido común»); punto medio ≈120 palabras por minuto; sin regrabar (se corta la voz ya grabada en los puntos). Es OPCIONAL, de ensayo y error: probarla y ajustar los tiempos según lo que diga fabian.
- **Velocidad de la voz — FIJA desde el 15/11/2026 (fabian: «bajarle el mínimo para que no se note arrastrada ni robótica»)**: la app usa SOLA el estilo «Voz natural + pausas largas» del módulo 🎵 Ritmo (por defecto en cada video nuevo, todas las marcas): voz ×0,95 (×0,93 en serial/KEY/Erase, ×0,97 en pasos obvios y en los primeros 2 minutos), pausa de frase ~0,95 s, semilarga ~1,6 s cada ~20 palabras, ~1,6 s al final de cada párrafo y un respiro de 2-3,8 s con la música arriba cada ~30 s de voz, NUNCA antes del minuto 2 (WhatsApp y «comenta» antes de 2:00). NUNCA bajar la voz a ×0,85 (suena arrastrada). La velocidad se baja en la edición (sin regrabar): NO mandar también speed a ElevenLabs (frenaría dos veces). Meta: ~115-120 palabras/min contando pausas (~155 hablando). El guion se escribe a ~2 palabras por segundo de bloque. Otros estilos para elegir: «Calibrado con tus videos» (voz ×0,90), «Humano», «Pausas v2», «Antes».
- **Pantalla de bloqueo (Verifica tu cuenta de Google, Mi Account, iCloud…) en TODAS las marcas; fabian, 14/11/2026):** mientras se ve la pantalla de verificación SIN el botón «Omitir», va en cámara más lenta (≈0,5×, unos 8-10 s en pantalla), porque es esencial mostrarle al cliente que el teléfono SÍ tiene cuenta de Google. Ejemplo: Honor 400 Lite, minuto 1:17.

## Fallos que NO se pueden repetir — TODAS LAS MARCAS (fabian, 14/11/2026; salieron de la revisión del Honor 400 Lite, 49 fallos confirmados)
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

## Revisor automático antes de entregar — TODAS LAS MARCAS, en la app y en la nube (fabian, 15/11/2026)
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

## Inicio de un video de un modelo concreto — TODAS LAS MARCAS (fabian, 15/11/2026)
- Si el video es «VERSIÓN EXCLUSIVA» de un modelo (ej. HONOR 400 LITE), la voz dice ENSEGUIDA que el método funciona igual para todos los modelos de la marca («Y si tienes otro Honor, tranquilo: este método sirve para todos los modelos de Honor»). Nunca se recorta esa frase del tráiler. Solo en la voz: en títulos de Honor sigue sin ir «Todos los Modelos» (03/11).
- El cartel de título (ej. «HONOR SIN CUENTA GOOGLE · Desde casa · PC sencilla · KEY oficial») dura TODA la frase que lo dice (5-7 s, no 1 s), con movimiento (palabras que entran, destello, fichas que aparecen cuando la voz las nombra) y sobre video real, nunca un fondo quieto. Estilo moderno, hecho con el ChatGPT de fabian (vidrio esmerilado del kit).
- Pop-ups de datos (parche de seguridad, versiones): serios y profesionales, nada que parezca para niños.
- Descargar el programa (fabian 15/11/2026, todas las marcas): la voz y el cartel dicen que se descarga desde el ENLACE EN LA DESCRIPCIÓN DEL VIDEO; en pantalla no se muestra la web de descargas (se ve el programa).
- Tomas de datos que no se leen (fabian 15/11/2026, todas las marcas): si en la etiqueta trasera, la caja, el serial o el IMEI no se lee el dato, esa toma no va y la voz no le pide al cliente que compare. Se quita la frase (recortando la voz, sin regrabar) o se usa una toma donde sí se lea.

## Etiquetas y transiciones calmadas — TODAS LAS MARCAS (fabian, 15/11/2026: «etiquetas muy agresivas, muy grandes… las transiciones en el inicio están muy rápidas»)
- **Título del inicio** (ej. «HONOR SIN CUENTA GOOGLE»): arriba, ocupa como mucho el 50-60 % del ancho, NUNCA encima del teléfono. Entra suave (crece de 0,9 a 1,0 en ~0,5 s), sin rebote ni latido fuerte.
- **Fichas** («DESDE CASA», «SIN TÉCNICO», «PC SENCILLA»…): tamaño medio, al menos ~25 % del ancho y letra legible en el celular (fabian 16/11: a 13 % «quedó muy pequeño»), en una esquina (abajo a la izquierda), sin tapar el teléfono ni lo que la voz nombra; entran suaves cuando la voz las dice.
- **Tomas del inicio**: lo lento es la DURACIÓN de cada toma (3-5 s), no la transición (fabian 16/11: «aún se mira raro», los fundidos de 0,45 s dejaban dos tomas encimadas, como doble exposición). Transición = corte limpio o deslizamiento rápido; si hay fundido, ≤0,3 s y nunca mezclando pantallas con texto. Carteles siempre opacos y enteros, nada medio transparente.
- **ANTES / DURANTE / DESPUÉS**: SIEMPRE en ese orden (fabian 15/11: en el video viejo DURANTE salía antes que ANTES); cada fase en pantalla al menos 3-4 s, con un cartel tipo píldora en la esquina de arriba a la izquierda (rojo / naranja / verde) de TAMAÑO MEDIO: ~20-25 % del ancho (fabian 16/11: el de 13 % «quedó muy pequeño»), nunca un cartel grande en el centro, y corte limpio entre fases (uno sale antes de que entre el otro).
- En Shorts las etiquetas son tarjetas tipo celular (oscuras, redondeadas, chicas), arriba de la zona del video; subtítulos abajo, nunca al centro.
- **Pantalla NO recargada (fabian 15/11/2026, captura del título a 0:39: «está super recargado»)**: como mucho 2 elementos gráficos a la vez además de los subtítulos (ej. título chico arriba + 1 ficha en la esquina). Nunca título grande + ficha + flecha + subtítulo juntos encima del teléfono. Cada elemento entra cuando la voz lo nombra y sale antes del siguiente; el teléfono y la acción siempre se ven limpios. Revisar cada cartel como lo vería él en el celular: si hay que «buscar» el teléfono entre carteles, sobra uno. Mientras está el título o una ficha, el subtítulo se oculta en ese tramo (final_subs.py ya lo hace en el título del inicio). Si el fondo ya está lleno (monitor con carteles, cajas), va una sola etiqueta chica o ninguna. Ante la duda, menos.
- **Testimonios de WhatsApp — prefijo y número tachado (fabian 16/11/2026, TODAS las marcas, CADA captura)**: cada captura de testimonio se muestra primero ENTERA ~1-1,3 s, con la cabecera visible (prefijo del país + número tachado), sin nada encima; recién después va el zoom a las frases que nombra la voz. El subtítulo nunca tapa el prefijo ni el número: en los testimonios no va subtítulo arriba (la frase amarilla ya resume). En la nube: testimonios_zoom.py (FULLBOX) y final_subs.py.
