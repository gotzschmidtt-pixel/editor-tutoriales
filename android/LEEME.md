# 📱 Estudio en el celular (APK)

El APK abre la app del PC en tu celular y la controla desde ahí. **El PC hace todo el trabajo**: tiene que quedar
prendido con la app abierta.

## 1. En la app del PC
1. Pulsa **📲 Celular**, elige un PIN de al menos 6 números, marca «Activar» y guarda. La app se reinicia.
2. Windows pregunta si deja entrar a Python: marca **Redes privadas y públicas** y acepta.
3. La ventana muestra las direcciones para el celular (Wi‑Fi de casa y, si lo tienes, Tailscale).

## 2. En el celular
1. Instala `Estudio.apk` (Android pide permitir «instalar apps de fuentes desconocidas» la primera vez).
2. Ábrelo y escribe la dirección que muestra el PC, por ejemplo `192.168.1.20` (el puerto 8765 se pone solo).
3. Pon el PIN. Queda recordado hasta que lo cambies en el PC.
4. El botón «atrás» en la pantalla principal ofrece cambiar la dirección del PC, recargar o salir.

## 3. Con datos móviles (fuera de casa): Tailscale
Tailscale arma una red privada entre tus aparatos, cifrada y sin abrir puertos del router. Es gratis para uso personal.
1. Instala Tailscale en el PC (https://tailscale.com/download/windows) y en el celular (Play Store), y entra con la
   **misma cuenta** en los dos.
2. En el PC, «📲 Celular» muestra la dirección «Tailscale» (100.x.x.x). Úsala en el APK con Tailscale encendido en el
   celular. Funciona igual en casa y afuera.
3. **No uses «Tailscale Funnel»** ni abras el puerto 8765 en el router: la app solo contesta a la red de casa y a
   Tailscale, y así tiene que quedar.

## Seguridad
- Apagado por defecto. Mientras no lo actives, la app solo escucha en tu PC, como siempre.
- Solo entran direcciones del Wi‑Fi de casa y de Tailscale, y siempre con PIN. 5 PIN equivocados: 5 minutos de espera.
- Desde el celular no se ve el PIN ni las claves de IA, y no se puede apagar ni cambiar el acceso.
- Cambiar el PIN en el PC cierra la sesión de todos los celulares.

## Armar el APK de nuevo
`./construir.sh` (Linux o WSL) con el SDK de Android (`platforms;android-34`, `build-tools;35.0.0`) y Java.
Usa siempre la misma clave (`CLAVE=…/estudio.keystore`): un APK firmado con otra no se instala encima del anterior.
