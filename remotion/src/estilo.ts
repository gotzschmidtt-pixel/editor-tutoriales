// Estilo de marca: un solo lugar para cambiar colores y fuente en todos los videos
export const estilo = {
  rosa: '#ff2bd6',
  azul: '#2bd9ff',
  verde: '#38f28a',
  amarillo: '#ffd23f',
  marcador: '#ff2d55', // círculos y recuadros: rojo marcador, como los que dibuja el autor en sus capturas
  // Cómo se dibujan círculos y recuadros: 'contorno' (rosa, con la forma del botón; lo eligió el autor) o 'marcador' (rojo, a mano)
  senal: 'contorno' as 'contorno' | 'marcador',
  fondo: 'rgba(12,14,22,0.82)',
  fuente: '"Inter", "DejaVu Sans", Arial, sans-serif',
  colorFase: {ANTES: '#ff4d6d', DURANTE: '#ffb020', 'DESPUÉS': '#38f28a'} as Record<string, string>,
};
