#!/usr/bin/env bash
# Arma el APK «Estudio» sin Android Studio: solo el SDK de Android (platforms;android-34 y build-tools;35.0.0) y Java.
#   ANDROID_SDK=/ruta/al/sdk CLAVE=/ruta/estudio.keystore ./construir.sh
# La clave firma el APK. Guárdala: las actualizaciones tienen que ir firmadas con la misma o Android no las instala
# encima. Si no existe, se crea una nueva (contraseña en CLAVE_PASS, por defecto «estudio»).
set -euo pipefail
cd "$(dirname "$0")"
SDK=${ANDROID_SDK:-/opt/android/sdk}
BT=$SDK/build-tools/35.0.0
JAR=$SDK/platforms/android-34/android.jar
CLAVE=${CLAVE:-$PWD/estudio.keystore}
PASS=${CLAVE_PASS:-estudio}
O=$PWD/salida
rm -rf "$O" && mkdir -p "$O/clases" "$O/res"

"$BT/aapt2" compile --dir res -o "$O/res"
"$BT/aapt2" link -I "$JAR" --manifest AndroidManifest.xml -o "$O/sin_codigo.apk" "$O"/res/*.flat
javac -source 8 -target 8 -bootclasspath "$JAR" -classpath "$BT/core-lambda-stubs.jar" -Xlint:-options -d "$O/clases" $(find src -name '*.java')
"$BT/d8" --min-api 24 --lib "$JAR" --output "$O" $(find "$O/clases" -name '*.class')
cp "$O/sin_codigo.apk" "$O/sin_firmar.apk"
(cd "$O" && zip -q sin_firmar.apk classes.dex)
"$BT/zipalign" -f -p 4 "$O/sin_firmar.apk" "$O/alineado.apk"
if [ ! -f "$CLAVE" ]; then
  keytool -genkeypair -keystore "$CLAVE" -storepass "$PASS" -keypass "$PASS" -alias estudio -keyalg RSA -keysize 2048 \
    -validity 10000 -dname "CN=Estudio de tutoriales" >/dev/null
fi
"$BT/apksigner" sign --ks "$CLAVE" --ks-pass "pass:$PASS" --out "$O/Estudio.apk" "$O/alineado.apk"
"$BT/apksigner" verify "$O/Estudio.apk"
echo "Listo: $O/Estudio.apk"
