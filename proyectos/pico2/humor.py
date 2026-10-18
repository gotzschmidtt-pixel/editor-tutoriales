import json
p='/mnt/project-files/guion-pico/guion_pico_largo.json'; d=json.load(open(p))
T={
'L02b':"Una cosa: si te surge una duda, no te la guardes, que guardarse cosas hace daño. Déjala en los comentarios, que aquí sí contestamos, no como tu ex. Y si te ahorramos el técnico, regálanos un like.",
'L01':"¿Qué tal, queridas y queridos? Hoy vamos a preparar, soldar y programar una Raspberry Pi Pico 2. Una placa chiquita, pero que rinde como grande. Ya saben lo que dicen: el tamaño no importa, importa cómo la conectas. Y tranquilos: no hace falta ser técnico ni tener estación profesional. Con una soldadora casera basta.",
'L02':"Así va a quedar: conectada y con su lucecita verde, feliz. Sin esta tarjeta no hay bypass, así que la vamos a tratar con cariño.",
'L03':"Lo que vas a necesitar: la Pico 2, un cable Lightning que ya no uses, cautín, estaño, flux y una computadora. Los guantes son opcionales, pero dan ese look de doctor de telenovela.",
'L04':"¿No tienes la placa? Tranquilo, no hay que vender un riñón. En la descripción te dejo enlaces de AliExpress, por unos diez dólares, y de Mercado Libre. Si estás en Colombia, te la enviamos a todo el país; y si estás fuera, escríbenos y te la mandamos.",
'L05':"¿Y si no quieres soldar? Hay modelos que ya vienen listos: las Waveshare RP2350 USB-A y RP2350 Zero. Llegar y usar.",
'L06':"Empezamos. Corta el cable Lightning y pélalo con cuidado: aquí se desviste despacito, sin arrancar nada. Adentro hay cuatro hilos. Rojo y negro son la alimentación; verde y blanco son los datos. Normalmente el verde es D más y el blanco D menos. Apréndete esa parejita.",
'L07':"Ahora, un poco de flux sobre los pads. El flux es el que hace que todo fluya: limpia, ayuda a que el estaño corra y deja la soldadura brillante. Sin flux, la relación entre cable y placa no funciona.",
'L08':"La estación la tenemos en 450 grados. Caliente, pero no tanto. Tú ajústala a tu gusto.",
'L09':"Primero estañamos las puntas: una gotita de estaño en cada hilo. Si queda un brillito plateado, vas bien. Si parece una bolita de chicle, te emocionaste. Con calma, que esto no es carrera: aquí gana el que dura más. Y si soldar no es lo tuyo, llévala con un técnico y que él se ensucie las manos.",
'L10':"Ahora, el mapa. Y aquí sí, ponte serio. El verde, D más, va al GP12, que es el pin 16. El blanco, D menos, va al GP13, el pin 17. Junto al conector USB, el rojo va al VBUS, pin 40, y el negro a tierra, GND, pin 38. Este mapa te lo dejo en la descripción.",
'L11':"Soldamos los datos: verde al pin 16, blanco al pin 17. Toca el pad y el cable al mismo tiempo, y retira el cautín en uno o dos segundos. Rapidito y con precisión, que aquí quedarse mucho rato quema. Si te queda alguna duda con los pines, déjala en los comentarios con el modelo de tu placa.",
'L12':"Del otro lado, junto al USB, va la alimentación: rojo al pin 40, VBUS, y negro al pin 38, GND. Ahora revisa cada punto con buena luz. Ningún punto puede tocar al de al lado: aquí cada uno en su casa. Un puente de estaño y la placa no responde. Si ves uno, pasa el cautín limpio con un poquito de flux y se separan solitos. Mejor una soldadura lenta y bien hecha que repetirla dos veces.",
'L13':"Y así queda: cuatro cables bien puestos. Verde y blanco de un lado, rojo y negro del otro. Una pareja de datos y una de energía, todos felices. Si necesitas ayuda, escríbenos a los WhatsApp que ves en pantalla.",
'L14':"Ahora la programamos. Conecta la Pico a la computadora por su propio puerto USB. ¿Alumbra verde? Normal, solo está emocionada.",
'L15':"Para programarla necesitas un archivo obligatorio. Lo descargas en gsmprime punto co o en xiaomiunlock punto com, con el botón Descargar Files Board. Ahí hay un archivo para cada placa: Waveshare USB-A, Zero, la Tiny 2350 de Pimoroni y la Pico 2. Elige el de tu tarjeta; aquí no se vale ponerle el de otra.",
'L16':"Con el archivo listo, conecta la tarjeta. Se abre una ventana sola, como si fuera una memoria USB. Fácil, sin rogarle.",
'L17':"Windows la reconoce como una unidad llamada RP2350. Si tu antivirus se pone celoso y pregunta, dale a No analizar. Luego abrimos la carpeta donde quedó el firmware.",
'L19':"La ventana desaparece sola y la placa queda programada. Así de fácil. Ni dolió.",
'L20':"Un par de consejos. Si la placa no se entiende con el iPhone, revisa las soldaduras y prueba invirtiendo el verde y el blanco: no se daña nada, a veces solo están en la posición equivocada. Y si la ventana no aparece, prueba otro cable u otro puerto USB.",
'L21':"Eso es todo. Muy, muy fácil. Todo lo encuentras en gsmprime punto co y xiaomiunlock punto com. Si te sirvió, suscríbete, que eso nos calienta... el corazón. Nos vemos en el próximo video.",
}
for b in d['bloques']:
    if b['id'] in T: b['texto']=T[b['id']]
    w=len(b['texto'].split()); b['voz_estimada_s']=round(w/2.6,1)
    dur=b['fin_max']-b['inicio_min']
    print(b['id'],dur,b['voz_estimada_s'],'!!' if b['voz_estimada_s']>dur*0.95 else '')
d['nota']+=' Tono: entretenido, sencillo, con humor picante ligero fuera de los pasos críticos (pines y archivo).'
json.dump(d,open(p,'w'),ensure_ascii=False,indent=1)
