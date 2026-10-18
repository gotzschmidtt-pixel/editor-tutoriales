import json
# Plan del video largo: cada bloque toma un tramo del video original (src) y lo estira.
# modo: "lento" (src a velocidad vel), "congelar" (fotograma src0 durante dur s), "imagen" (mapa de pines), "lento+congelar"
B = [
 ("L01","libre","lento",0,11,0.5,None,"Gráfico ANTES: mesa de trabajo, Pico y flux",
  "¿Qué tal, queridas y queridos? Hoy les vengo a enseñar a preparar, soldar, comprar y programar una Raspberry Pi Pico 2, en unos pasos muy sencillos. Y tranquilos: no necesitan ser técnicos ni tener una estación profesional. Con una soldadora casera es suficiente.",None),
 ("L02","libre","lento",12,18,0.45,None,"Gráfico DESPUÉS: Pico conectada con luz verde",
  "Así es como va a quedar: la placa conectada, con su lucecita verde encendida. Esta tarjeta es necesaria para poder hacer el bypass, así que vale la pena dejarla bien hecha.",None),
 ("L02b","libre","congelar",15,None,None,17,"Congelado: gráfico DESPUÉS, invitación a comentar",
  "Antes de empezar: si te surge cualquier duda, déjala en los comentarios o escríbenos por WhatsApp, que aquí respondemos. Y si este video te ahorra un viaje al técnico, regálanos un like: es gratis y nos pone de buenas.",None),
 ("L03","libre","congelar",1,None,None,16,"Congelado: mesa con todo el material",
  "Para este trabajo vas a necesitar: una Raspberry Pi Pico 2, un cable Lightning que ya no uses, un cautín, estaño, flux y una computadora. Y unos guantes, si quieres verte como en serie de hospital.",None),
 ("L04","libre","congelar",36,None,None,20,"Congelado: primer plano de la Pico 2",
  "¿Todavía no tienes la placa? En la descripción te dejo los enlaces para comprarla en AliExpress, por unos diez dólares, o por Mercado Libre. Si vives en Colombia, te la enviamos a todo el país; y si estás fuera, escríbenos y te la mandamos.",None),
 ("L05","libre","congelar",37.5,None,None,12,"Congelado: Pico 2 en mano",
  "Y si no quieres soldar, hay modelos que ya vienen listos, sin cables: las Waveshare RP2350 USB-A y RP2350 Zero.",None),
 ("L06","accion","lento",18,30,0.5,None,"Cable Lightning cortado y pelado, cuatro hilos",
  "Empezamos. Toma el cable Lightning, córtalo y pela la punta con cuidado. Adentro vas a encontrar cuatro hilos: el rojo y el negro son la alimentación, y el verde y el blanco son los datos. Normalmente el verde es D más y el blanco D menos.",None),
 ("L07","accion","lento",30,39,0.5,None,"Aplica flux sobre los pads de la Pico",
  "Ahora ponemos un poco de flux sobre los pads de la placa. El flux limpia la superficie y hace que el estaño corra mejor, así la soldadura queda brillante y firme.",None),
 ("L08","dato","lento",39,44,0.5,None,"Pantalla de la estación marca 450",
  "Nosotros tenemos la estación en 450 grados, pero puedes ajustarla a tu gusto.",None),
 ("L09","accion","lento",44,69,1.0,None,"Estañando las puntas de los cuatro hilos",
  "Antes de soldar, estañamos las puntas de los cables: una gotita de estaño en cada hilo. Si queda un brillito plateado, vas bien; si parece una bolita de chicle, te pasaste. Con calma, que esto no es carrera. Y si prefieres no soldar, compra la placa y llévala con un técnico para que te suelde los cables.",None),
 ("L10","accion","imagen",None,None,None,27,"Mapa de pines de la Pico 2 (imagen que enviaste)",
  "Antes de soldar, veamos el mapa. El verde, D más, va al GP12, que es el pin 16. El blanco, D menos, va al GP13, el pin 17. Del lado del conector USB, el rojo va al VBUS, pin 40, y el negro a tierra, GND, pin 38. Este mapa también te lo dejo en la descripción.",None),
 ("L11","accion","lento",69,90,0.75,None,"Suelda verde (pin 16) y blanco (pin 17); gráfico de comentarios",
  "Ahora sí, soldamos los datos: el verde al pin 16 y el blanco al pin 17. Acerca el cautín, toca el pad y el cable al mismo tiempo, y retíralo en uno o dos segundos. Si te queda alguna duda con los pines, déjala en los comentarios con el modelo de tu placa.",None),
 ("L12","accion","lento",90,126,1.0,None,"Suelda rojo (pin 40) y negro (pin 38) junto al USB y revisa",
  "Del otro lado, junto al conector USB, va la alimentación: el rojo al pin 40, VBUS, y el negro al pin 38, GND. Cuando termines, revisa cada punto con buena luz. Ningún punto debe tocar al de al lado: un puente de estaño aquí y la placa no responde. Si ves uno, pasa el cautín limpio con un poco de flux y se separa. Mejor una soldadura lenta y bien hecha que repetirla dos veces.",None),
 ("L13","libre","lento",126,138,0.6,None,"Placa terminada + gráfico WhatsApp Support",
  "Así quedan los cuatro cables soldados: verde y blanco de un lado, rojo y negro del otro. Si necesitas ayuda en cualquier paso, escríbenos a los números de WhatsApp que ves en pantalla.",None),
 ("L14","accion","lento",138,148,0.8,None,"Lleva la Pico al portátil y la conecta",
  "Ahora la programamos. Conecta la Pico a la computadora por su propio puerto USB. Si alumbra verde, es normal.",None),
 ("L15","accion","lento+congelar",148,156,0.4,10,"Página de descarga: 'Descargar Files Board' y lista de archivos .uf2",
  "Para programarla necesitas un archivo obligatorio. Lo descargas en gsmprime punto co o en xiaomiunlock punto com, con el botón Descargar Files Board. Ahí vas a ver un archivo para cada placa: uno para la Waveshare USB-A, otro para la Zero, otro para la Tiny 2350 de Pimoroni y otro para la Pico 2. Descarga el que corresponde a tu tarjeta.",None),
 ("L16","accion","lento",156,166,0.7,None,"Conecta la tarjeta, se abre la ventana",
  "Con el archivo listo, conecta la tarjeta a la computadora. Se va a abrir una ventana automáticamente, como si fuera una memoria USB.",None),
 ("L17","accion","lento",166,177,0.6,None,"Avast: unidad externa RP2350 + carpeta del firmware",
  "Windows la reconoce como una unidad llamada RP2350. Si tu antivirus pregunta qué hacer, dale a No analizar. Y abrimos la carpeta donde descargamos el firmware.",None),
 ("L18","accion","lento",177,183,0.4,None,"Arrastra usbliter8.pico2.uf2 a RP2350 (D:)",
  "Ahora arrastramos el archivo de nuestra placa a la unidad RP2350. En este caso, usbliter ocho, punto pico dos, punto uf dos.",None),
 ("L19","accion","lento",183,189,0.7,None,"Pico conectada con luz verde",
  "La ventana desaparece sola y la placa queda programada. Así de fácil.",None),
 ("L20","libre","congelar",186,None,None,20,"Congelado: Pico programada",
  "Un par de consejos. Si la placa no se comunica con el iPhone, revisa las soldaduras y prueba invirtiendo el verde y el blanco: no se daña nada. Y si la ventana no aparece, prueba con otro cable o puerto USB.",
  "Consejos que agregué yo (no salen en tu narración). ¿Los dejamos?"),
 ("L21","libre","lento+congelar",189,195.5,0.5,4,"Plano general de la mesa, cierre",
  "Eso es todo. Muy, muy fácil. Encuentras todo en gsmprime punto co y xiaomiunlock punto com. Si te sirvió, suscríbete y nos vemos en el próximo video.",None),
]
t = 0.0; out = []
for (i,tipo,modo,s0,s1,vel,frz,ancla,texto,conf) in B:
    dur = 0.0
    if modo.startswith("lento"): dur += (s1-s0)/vel
    if modo in ("congelar","imagen") or modo.endswith("congelar"): dur += frz
    b = {"id":i,"tipo":tipo,"inicio_min":round(t,1),"fin_max":round(t+dur,1),"ancla":ancla,"texto":texto,
         "montaje":{"modo":modo,"src_inicio":s0,"src_fin":s1,"velocidad":vel,"congelar_s":frz}}
    if conf: b["confirmar"]=conf
    w = len(texto.split()); b["voz_estimada_s"]=round(w/2.6,1)
    pass
    out.append(b); t += dur
d = {"video":"COMO SOLDAR RASPBERRY OSCAR .mp4","version":"larga","duracion_s":round(t,1),
     "nota":"Versión larga (~7 min). Tiempos en segundos del video NUEVO (estirado). 'montaje' indica de qué tramo del original sale cada bloque y cómo se estira. Narración basada en el video original, tu voz en 'Mi video' y el mapa de pines que enviaste.",
     "bloques":out}
json.dump(d,open('/mnt/project-files/guion-pico/guion_pico_largo.json','w'),ensure_ascii=False,indent=1)
print(round(t,1), f"{int(t//60)}:{int(t%60):02d}")
