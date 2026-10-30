// Uso: node render_frames.js <carpeta_salida> <duracion_s> '<items_json>' [izquierda|derecha] [x,y,ancho,alto]
// Congela la plantilla en cada fotograma (25 fps) y guarda PNG con fondo transparente. Con el recorte, la foto es solo de
// la zona donde van las etiquetas (abajo, de un lado): mucho menos para dibujar y comprimir que la pantalla entera.
const { chromium } = require('playwright');
const path = require('path'), fs = require('fs');
const [, , outDir, total, itemsJson, lado, recorte] = process.argv;
(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const url = require('url').pathToFileURL(path.join(__dirname, 'plantilla.html')).href +
    '?total=' + total + '&items=' + encodeURIComponent(itemsJson) + (lado ? '&lado=' + lado : '');
  await page.goto(url);
  await page.evaluate(() => document.fonts.ready);
  const [x, y, width, height] = recorte ? recorte.split(',').map(Number) : [];
  const clip = recorte ? { x, y, width, height } : undefined;
  const n = Math.round(+total * 25);
  for (let f = 0; f < n; f++) {
    await page.evaluate(ms => window.seek(ms), f * 40);
    await page.screenshot({ path: `${outDir}/f_${String(f).padStart(4, '0')}.png`, omitBackground: true, clip });
  }
  await browser.close();
})();
