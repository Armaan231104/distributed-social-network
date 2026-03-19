document.addEventListener("DOMContentLoaded", () => {
  const overlay = document.getElementById("glass-overlay");
  const button = document.getElementById("toggle-torch");

  let pulse = 0;
  const baseRadius = 300;
  const pulseSpeed = 0.04;
  const pulseAmount = 40;

  // restore last mouse position or default to center
  let mouseX = localStorage.getItem("torchX") 
                 ? parseInt(localStorage.getItem("torchX")) 
                 : window.innerWidth / 2;
  let mouseY = localStorage.getItem("torchY") 
                 ? parseInt(localStorage.getItem("torchY")) 
                 : window.innerHeight / 2;

  let animationId;

  // read saved state
  let isActive = localStorage.getItem("torchMode") === "on";

  // set overlay & icon based on saved state
  if (isActive) {
    overlay.style.display = "block";
    overlay.style.opacity = "1";
    animate();
  }

  document.addEventListener("mousemove", (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;

    // save position in localStorage
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
function applyMasonryRowWise() {
  
    const main = document.querySelector('.main-content');
    if (!main) return;

    const grid = main.querySelector('.posts-grid');
    if (!grid) return;

    const items = Array.from(grid.children);
    // Determine number of columns
    let COLS = 3;
    if (window.innerWidth <= 700) COLS = 1;
    else if (window.innerWidth <= 1000) COLS = 2;

    // Reset transforms
    items.forEach(item => item.style.transform = 'translateY(0px)');

    // Keep track of cumulative height diff per column
    let colOffset = new Array(COLS).fill(0);

    // Process items row by row
    for (let i = 0; i < items.length; i += COLS) {
        const rowItems = items.slice(i, i + COLS);

        // Find tallest item in this row
        const tallest = Math.max(...rowItems.map(item => item.offsetHeight));

        if (COLS === 2 && rowItems.length === 2) {
            // Special 2-col logic: shorter item gets half the difference
            const h0 = rowItems[0].offsetHeight;
            const h1 = rowItems[1].offsetHeight;
            const diff = Math.abs(h0 - h1) / 2;

            if (h0 > h1) {
                rowItems[0].style.transform = `translateY(${0}px)`;
                rowItems[1].style.transform = `translateY(${diff}px)`;
                colOffset[0] += 0;
                colOffset[1] += diff;
            } else if (h1 > h0) {
                rowItems[0].style.transform = `translateY(${diff}px)`;
                rowItems[1].style.transform = `translateY(${0}px)`;
                colOffset[0] += diff;
                colOffset[1] += 0;
            } else {
                continue
            }

            // Add the difference to cumulative offset
            colOffset = colOffset.map((offset, idx) => offset + Math.abs(h0 - h1)/2);

            // Add hover scale for both items
            rowItems.forEach((item, idx) => {
                const colIndex = idx;
                item.addEventListener('mouseenter', () => {
                    const currentTransform = item.style.transform || '';
                    const translateMatch = currentTransform.match(/translateY\([^)]+\)/);
                    const translateValue = translateMatch ? translateMatch[0] : 'translateY(0px)';
                    item.style.transform = `${translateValue} scale(1.01)`;
                });
                item.addEventListener('mouseleave', () => {
                    const currentTransform = item.style.transform || '';
                    const translateMatch = currentTransform.match(/translateY\([^)]+\)/);
                    const translateValue = translateMatch ? translateMatch[0] : 'translateY(0px)';
                    item.style.transform = `${translateValue} scale(1)`;
                });
            });

        } else {
            // Normal logic for 3 cols or single items
            rowItems.forEach((item, idx) => {
                const colIndex = idx; // column in this row
                const diff = tallest - item.offsetHeight; // difference to tallest

                // Apply translate based on cumulative offset
                item.style.transform = `translateY(-${colOffset[colIndex]}px)`;

                // Add hover scale
                item.addEventListener('mouseenter', () => {
                    const currentTransform = item.style.transform || '';
                    const translateMatch = currentTransform.match(/translateY\([^)]+\)/);
                    const translateValue = translateMatch ? translateMatch[0] : 'translateY(0px)';
                    item.style.transform = `${translateValue} scale(1.01)`;
                });
                item.addEventListener('mouseleave', () => {
                    const currentTransform = item.style.transform || '';
                    const translateMatch = currentTransform.match(/translateY\([^)]+\)/);
                    const translateValue = translateMatch ? translateMatch[0] : 'translateY(0px)';
                    item.style.transform = `${translateValue} scale(1)`;
                });

                // Add the difference to this column's cumulative offset
                colOffset[colIndex] += diff;
            });
        }
    }
}

// Wait for full load to ensure offsets are correct
window.addEventListener('load', () => {
    applyMasonryRowWise();
});
window.addEventListener('resize', () => {
    applyMasonryRowWise();
});
// Run initially
window.addEventListener('load', () => {
    applyMasonryRowWise();
});
// Re-run on resize
window.addEventListener('resize', () => {
    applyMasonryRowWise();
});