/* ═══════════════ MAPA MUNDIAL DE ALTA DENSIDAD ═══════════════
   Mapa formado por miles de puntos finos que dibujan las siluetas
   detalladas de los continentes. Efecto linterna: los puntos cercanos
   al cursor se iluminan en lima.
*/

(function() {
  function buildMap() {
    if (document.getElementById('world-map-bg')) return;
    const WORLD = window.WORLD_MAP_DATA;
    if (!WORLD) return;

    const cols = WORLD[0].length;
    const rows = WORLD.length;
    const spacing = 7;     // px entre puntos (densidad alta)
    const dotR = 0.9;      // radio pequeño
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

    let raf = null;
    let mouseX = -9999, mouseY = -9999;

    function illuminate() {
      const rect = svg.getBoundingClientRect();
      const scaleX = w / rect.width;
      const scaleY = h / rect.height;
      const mx = (mouseX - rect.left) * scaleX;
      const my = (mouseY - rect.top) * scaleY;
      const radius = 110;

      for (const d of dots) {
        const dist = Math.hypot(d.cx - mx, d.cy - my);
        if (dist < radius) {
          const intensity = 1 - dist / radius;
          d.el.style.fill = `rgba(200, 241, 53, ${intensity * 0.9})`;
          d.el.style.r = (dotR + intensity * 1.6).toString();
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
