/* ═══════════════ MAPA MUNDIAL VECTORIAL (croquis de continentes) ═══════════════
   Mapa SVG con los contornos de los continentes en líneas grises.
   Al pasar el mouse sobre una región, se ilumina en lima.
*/

(function() {
  const CONTINENTS = [
    { name: "Norteamérica",
      d: "M 175 70 L 230 60 L 290 75 L 310 110 L 285 130 L 300 155 L 270 175 L 250 165 L 235 195 L 210 200 L 220 165 L 195 150 L 205 120 L 175 130 L 160 100 Z M 240 205 L 265 210 L 250 235 L 225 230 Z" },
    { name: "Sudamérica",
      d: "M 285 270 L 315 265 L 335 290 L 330 330 L 345 360 L 325 410 L 300 440 L 285 415 L 295 375 L 275 345 L 280 305 Z" },
    { name: "Europa",
      d: "M 480 95 L 520 85 L 545 100 L 535 120 L 555 130 L 540 150 L 510 155 L 495 140 L 470 145 L 475 120 L 460 110 Z" },
    { name: "África",
      d: "M 490 195 L 540 185 L 575 200 L 590 240 L 575 290 L 545 330 L 515 340 L 500 310 L 480 270 L 485 230 Z" },
    { name: "Asia",
      d: "M 560 90 L 640 75 L 720 90 L 790 80 L 850 105 L 830 140 L 860 165 L 820 185 L 770 175 L 730 195 L 700 175 L 660 185 L 630 160 L 600 170 L 575 145 L 590 120 L 560 115 Z" },
    { name: "Oceanía",
      d: "M 800 330 L 850 320 L 885 340 L 875 375 L 835 385 L 805 365 Z M 890 400 L 910 395 L 915 415 L 895 420 Z" },
  ];

  function buildVectorMap() {
    if (document.getElementById('world-map-bg')) return;
    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    svg.setAttribute("id", "world-map-bg");
    svg.setAttribute("viewBox", "0 0 1000 500");
    svg.setAttribute("preserveAspectRatio", "xMidYMid slice");

    const grid = document.createElementNS(svgNS, "g");
    grid.setAttribute("class", "wm-grid");
    for (let x = 0; x <= 1000; x += 100) {
      const line = document.createElementNS(svgNS, "line");
      line.setAttribute("x1", x); line.setAttribute("y1", 0);
      line.setAttribute("x2", x); line.setAttribute("y2", 500);
      grid.appendChild(line);
    }
    for (let y = 0; y <= 500; y += 100) {
      const line = document.createElementNS(svgNS, "line");
      line.setAttribute("x1", 0); line.setAttribute("y1", y);
      line.setAttribute("x2", 1000); line.setAttribute("y2", y);
      grid.appendChild(line);
    }
    svg.appendChild(grid);

    const paths = [];
    CONTINENTS.forEach(cont => {
      const path = document.createElementNS(svgNS, "path");
      path.setAttribute("d", cont.d);
      path.setAttribute("class", "wm-continent");
      path.setAttribute("data-name", cont.name);
      svg.appendChild(path);
      paths.push(path);
    });

    const container = document.createElement('div');
    container.id = 'world-map-container';
    container.appendChild(svg);
    document.body.insertBefore(container, document.body.firstChild);

    let raf = null;
    let mouseX = -9999, mouseY = -9999;
    let centers = null;

    function computeCenters() {
      centers = paths.map(p => {
        const b = p.getBBox();
        return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
      });
    }

    function illuminate() {
      const rect = svg.getBoundingClientRect();
      const scaleX = 1000 / rect.width;
      const scaleY = 500 / rect.height;
      const mx = (mouseX - rect.left) * scaleX;
      const my = (mouseY - rect.top) * scaleY;
      if (!centers) computeCenters();

      paths.forEach((path, i) => {
        const c = centers[i];
        const dist = Math.hypot(c.x - mx, c.y - my);
        const radius = 260;
        if (dist < radius) {
          const intensity = 1 - dist / radius;
          path.style.stroke = `rgba(200, 241, 53, ${0.25 + intensity * 0.75})`;
          path.style.fill = `rgba(200, 241, 53, ${intensity * 0.12})`;
          path.style.strokeWidth = (0.8 + intensity * 1.2).toFixed(2);
        } else {
          path.style.stroke = '';
          path.style.fill = '';
          path.style.strokeWidth = '';
        }
      });
      raf = null;
    }

    window.addEventListener('mousemove', (e) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
      if (!raf) raf = requestAnimationFrame(illuminate);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildVectorMap);
  } else {
    buildVectorMap();
  }
})();
