// Uso: node etiqueta_capa.js <trabajos.json>
// Para la vista previa: cada etiqueta dibujada con la MISMA plantilla del armado (etiquetas/plantilla.html, arriba a la
// derecha), congelada cuando ya entró, en PNG transparente del tamaño de la zona donde el armado la pega.
// trabajos.json = [{items, total, ms, lado, recorte: [x, y, ancho, alto], salida}]. Un solo navegador para todas.
const { chromium } = require('playwright');
const path = require('path'), fs = require('fs');
(async () => {
  const trabajos = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const base = require('url').pathToFileURL(path.join(__dirname, '..', 'etiquetas', 'plantilla.html')).href;
  for (const t of trabajos) {
    await page.goto(base + '?total=' + t.total + '&items=' + encodeURIComponent(JSON.stringify(t.items)) + '&lado=' + t.lado);
    await page.evaluate(() => document.fonts.ready);
    await page.evaluate(() => window.listo || null);
    await page.evaluate(ms => window.seek(ms), t.ms);
    const [x, y, width, height] = t.recorte;
    await page.screenshot({ path: t.salida, omitBackground: true, clip: { x, y, width, height } });
  }
  await browser.close();
})();
