document.addEventListener("DOMContentLoaded", () => {
  const overlay = document.getElementById("glass-overlay");
  const button = document.getElementById("toggle-torch");

  let pulse = 0;
  const baseRadius = 300;
  const pulseSpeed = 0.04;
  const pulseAmount = 40;

  let mouseX = localStorage.getItem("torchX")
    ? parseInt(localStorage.getItem("torchX"))
    : window.innerWidth / 2;
  let mouseY = localStorage.getItem("torchY")
    ? parseInt(localStorage.getItem("torchY"))
    : window.innerHeight / 2;

  let animationId;
  let isActive = localStorage.getItem("torchMode") === "on";

  if (isActive) {
    overlay.style.display = "block";
    overlay.style.opacity = "1";
    animate();
  }

  document.addEventListener("mousemove", (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
    localStorage.setItem("torchX", mouseX);
    localStorage.setItem("torchY", mouseY);
  });

  function animate() {
    const radius = baseRadius + Math.sin(pulse) * pulseAmount;
    const softEdge = 0.5;
    overlay.style.background = `
      radial-gradient(
        circle ${radius}px at ${mouseX}px ${mouseY}px,
        transparent 0%,
        rgba(0,0,0,0.6) ${softEdge * 100}%,
        rgba(0,0,0,0.97) 100%
      )
    `;
    pulse += pulseSpeed;
    animationId = requestAnimationFrame(animate);
  }

  button.addEventListener("click", () => {
    isActive = !isActive;
    localStorage.setItem("torchMode", isActive ? "on" : "off");
    if (isActive) {
      overlay.style.display = "block";
      overlay.style.opacity = "1";
      animate();
    } else {
      overlay.style.opacity = "0";
      cancelAnimationFrame(animationId);
      setTimeout(() => overlay.style.display = "none", 500);
    }
  });
});

// ── MASONRY ──
function applyMasonryRowWise() {
  const main = document.querySelector('.main-content');
  if (!main) return;
  const grid = main.querySelector('.posts-grid');
  if (!grid) return;

  const items = Array.from(grid.children);
  let COLS = 3;
  if (window.innerWidth <= 700) COLS = 1;
  else if (window.innerWidth <= 1000) COLS = 2;

  items.forEach(item => item.style.transform = 'translateY(0px)');
  let colOffset = new Array(COLS).fill(0);

  for (let i = 0; i < items.length; i += COLS) {
    const rowItems = items.slice(i, i + COLS);
    const tallest = Math.max(...rowItems.map(item => item.offsetHeight));

    if (COLS === 2 && rowItems.length === 2) {
      const h0 = rowItems[0].offsetHeight;
      const h1 = rowItems[1].offsetHeight;
      const diff = Math.abs(h0 - h1) / 2;

      if (h0 > h1) {
        rowItems[0].style.transform = `translateY(0px)`;
        rowItems[1].style.transform = `translateY(${diff}px)`;
        colOffset[0] += 0;
        colOffset[1] += diff;
      } else if (h1 > h0) {
        rowItems[0].style.transform = `translateY(${diff}px)`;
        rowItems[1].style.transform = `translateY(0px)`;
        colOffset[0] += diff;
        colOffset[1] += 0;
      } else {
        continue;
      }

      colOffset = colOffset.map(offset => offset + Math.abs(h0 - h1) / 2);

      rowItems.forEach(item => {
        item.addEventListener('mouseenter', () => {
          const t = item.style.transform.match(/translateY\([^)]+\)/);
          item.style.transform = `${t ? t[0] : 'translateY(0px)'} scale(1.015)`;
        });
        item.addEventListener('mouseleave', () => {
          const t = item.style.transform.match(/translateY\([^)]+\)/);
          item.style.transform = `${t ? t[0] : 'translateY(0px)'} scale(1)`;
        });
      });

    } else {
      rowItems.forEach((item, idx) => {
        const diff = tallest - item.offsetHeight;
        item.style.transform = `translateY(-${colOffset[idx]}px)`;

        item.addEventListener('mouseenter', () => {
          const t = item.style.transform.match(/translateY\([^)]+\)/);
          item.style.transform = `${t ? t[0] : 'translateY(0px)'} scale(1.015)`;
        });
        item.addEventListener('mouseleave', () => {
          const t = item.style.transform.match(/translateY\([^)]+\)/);
          item.style.transform = `${t ? t[0] : 'translateY(0px)'} scale(1)`;
        });

        colOffset[idx] += diff;
      });
    }
  }
}

window.addEventListener('load', applyMasonryRowWise);
window.addEventListener('resize', applyMasonryRowWise);
