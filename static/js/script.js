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
        rgba(0,0,0,0.95) 100%
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