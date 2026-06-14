/* ═══════════════ MAPA MUNDIAL DE FONDO (dot-matrix) ═══════════════
   Dibuja un mapamundi moderno hecho de puntos en una grilla.
   Los puntos forman la silueta de los continentes. Al pasar el mouse,
   los puntos cercanos se iluminan (efecto linterna).
*/

(function() {
  // Mapa de continentes como grilla de bits (1 = tierra, 0 = agua)
  // Resolución baja, estilo dot-matrix. 60 columnas x 28 filas aprox.
  // Generado para aproximar la forma real de los continentes.
  const WORLD = [
    "000000000000000000000000000000000000000000000000000000000000",
    "000000000111100000000000000000000000000000000000000000000000",
    "000000011111111110000000000011111110000000000000000000000000",
    "000001111111111111000001111111111111111100000000000000000000",
    "000011111111111111100011111111111111111111000000000000011000",
    "000011111111111111000111111111111111111111110000000000111100",
    "000001111111111110000111111111111111111111111000000001111110",
    "000000011111111000001111111111111111111111110000000011111100",
    "000000001111110000000111111111111111111111000000000111111110",
    "000000000111100000000011111111111111111100000000001111111110",
    "000000000011000000000001111111111111110000000000011111111100",
    "000000000111000000000000011111111111000000000000111111111000",
    "000000001111000000000000001111111100000000000001111111100000",
    "000000001111100000000000000111111000000000000000011111000000",
    "000000001111100000000000000011110000000000000000001100000000",
    "000000011111000000000000000011100000000000000000000000000000",
    "000000011110000000000000000011000000000000000000000000000000",
    "000000011110000000000000000111000000000000000000011000000000",
    "000000011100000000000000000110000000000000000000111100000000",
    "000000011100000000000000001110000000000000000001111110000000",
    "000000011000000000000000001100000000000000000001111110000000",
    "000000010000000000000000011100000000000000000000111100000000",
    "000000000000000000000000011000000000000000000000011000000000",
    "000000000000000000000000010000000000000000000000000000000000",
    "000000000000000000000000110000000000000000000000000000000000",
    "000000000000000000000001100000000000000000000000000000000000",
    "000000000000000000000000000000000000000000000000000000000000",
  ];

  function buildMap() {
    const existing = document.getElementById('world-map-bg');
    if (existing) return;

    const cols = WORLD[0].length;
    const rows = WORLD.length;
    const spacing = 22;       // px entre puntos
    const dotR = 1.8;         // radio del punto
    const w = cols * spacing;
    const h = rows * spacing;

    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("id", "world-map-bg");
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    svg.setAttribute("preserveAspectRatio", "xMidYMid slice");

    const dots = [];
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        if (WORLD[y][x] === '1') {
          const cx = x * spacing + spacing / 2;
          const cy = y * spacing + spacing / 2;
          const c = document.createElementNS(svgNS, "circle");
          c.setAttribute("cx", cx);
          c.setAttribute("cy", cy);
          c.setAttribute("r", dotR);
          c.setAttribute("class", "wm-dot");
          svg.appendChild(c);
          dots.push({ el: c, cx, cy });
        }
      }
    }

    const container = document.createElement('div');
    container.id = 'world-map-container';
    container.appendChild(svg);
    document.body.insertBefore(container, document.body.firstChild);

    // Efecto linterna: ilumina puntos cercanos al cursor
    let raf = null;
    let mouseX = -9999, mouseY = -9999;

    function illuminate() {
      const rect = svg.getBoundingClientRect();
      const scaleX = w / rect.width;
      const scaleY = h / rect.height;
      const mx = (mouseX - rect.left) * scaleX;
      const my = (mouseY - rect.top) * scaleY;
      const radius = 180;

      for (const d of dots) {
        const dist = Math.hypot(d.cx - mx, d.cy - my);
        if (dist < radius) {
          const intensity = 1 - dist / radius;
          d.el.style.fill = `rgba(200, 241, 53, ${intensity * 0.9})`;
          d.el.style.r = (dotR + intensity * 2.5).toString();
        } else {
          d.el.style.fill = '';
          d.el.style.r = '';
        }
      }
      raf = null;
    }

    window.addEventListener('mousemove', (e) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
      if (!raf) raf = requestAnimationFrame(illuminate);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildMap);
  } else {
    buildMap();
  }
})();
