// Renderiza muchas composiciones con un solo empaquetado (más rápido que llamar a la CLI por cada una).
// Uso: node render_lote.mjs trabajos.json   ->  [{"id": "Senal", "props": {...}, "salida": "x.mov", "alfa": true}]
import fs from 'node:fs';
import path from 'node:path';
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';

const trabajos = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const browserExecutable = process.env.REMOTION_CHROME || null;
const serveUrl = await bundle({entryPoint: path.resolve(import.meta.dirname, 'src/index.ts')});
for (const t of trabajos) {
  const composition = await selectComposition({serveUrl, id: t.id, inputProps: t.props, browserExecutable});
  const alfa = t.alfa ? {codec: 'prores', proResProfile: '4444', imageFormat: 'png', pixelFormat: 'yuva444p10le'} : {codec: 'h264'};
  await renderMedia({composition, serveUrl, inputProps: t.props, outputLocation: t.salida, browserExecutable, concurrency: 4, ...alfa});
  console.log('listo', t.salida);
}
