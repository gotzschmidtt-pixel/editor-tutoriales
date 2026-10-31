# ▶️ YouTube en la app

Botón «▶️ YouTube» (arriba en la app). Se abre una página con 4 partes:

1. **Tu canal**: se conecta una sola vez (gratis).
2. **Publicar**: la IA propone 5 títulos con el estilo de tus videos más vistos, la descripción con tus páginas, los
   capítulos (el segundo exacto de cada paso en FINAL.mp4), las etiquetas y el comentario para fijar. Corriges y publicas:
   privado, no listado, público o programado. Sube también los subtítulos, la miniatura (`miniatura*.jpg/png` del proyecto)
   y el comentario. Fijar el comentario lo haces tú en YouTube: la API no lo permite.
3. **Aprender**: con el video ya publicado, baja la retención y los comentarios, te muestra en qué bloque se fue la gente
   y qué preguntan, y anota lo útil en «🧠 Conocimiento» para los próximos guiones.
4. **Ideas**: junta los comentarios de todo el canal con lo que la gente escribe en el buscador de YouTube.

## Conectar (una vez, unos 10 minutos)
En https://console.cloud.google.com/ con la cuenta de tu canal:
1. Crea un proyecto («Estudio»).
2. «APIs y servicios» → «Biblioteca»: activa **YouTube Data API v3** y **YouTube Analytics API**.
3. «Pantalla de consentimiento de OAuth»: tipo **Externo**, nombre «Estudio», tu correo. Al terminar pulsa
   **Publicar la app** (en modo «Prueba» Google pide conectar otra vez cada 7 días).
4. «Credenciales» → «Crear credenciales» → «ID de cliente de OAuth» → **App de escritorio**. Descarga el JSON.
5. En la app: «▶️ YouTube» → sube el JSON → «🔑 Conectar YouTube». Google avisa que la app no está verificada:
   es tuya, pulsa «Configuración avanzada» → «Ir a Estudio» y marca todas las casillas.

El permiso queda en `app/ajustes.json` y no sale de tu PC. Conectar solo se puede desde el PC (no desde el celular).

## Límites
- La API deja unas 6 subidas por día (cuota gratis de 10.000 unidades).
- La miniatura personalizada pide el canal verificado con tu teléfono (youtube.com/verify).
- La retención aparece uno o dos días después de publicar.
- Los subtítulos en otros idiomas se suben solo si el video no tiene testimonios ni nuevos modelos (que corren los tiempos).
