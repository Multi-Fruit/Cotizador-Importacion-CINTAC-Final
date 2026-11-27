(() => {
    const viewport = document.querySelector('.rate-window');
    const list = viewport.querySelector('.rate-list');
    const track = list.parentElement;
    const toggle = document.querySelector('.rate-toggle');
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let paused = motion.matches;
    let frame = 0;
    let position = 0;
    let previousTime = null;
    let width = 0;

    function tick(time) {
        if (previousTime !== null) position += Math.min(time - previousTime, 100) * 0.032;
        previousTime = time;
        position %= width;
        viewport.scrollLeft = position;
        frame = requestAnimationFrame(tick);
    }

    function updateMotion() {
        cancelAnimationFrame(frame);
        previousTime = null;
        position = viewport.scrollLeft;
        const accion = paused ? 'Reanudar el carril de tarifas' : 'Pausar el carril de tarifas';
        toggle.firstElementChild.textContent = paused ? '▶' : 'Ⅱ';
        toggle.setAttribute('aria-label', accion);
        toggle.title = accion;
        if (width > viewport.clientWidth && !paused && !document.hidden &&
            !viewport.matches(':hover, :focus')) frame = requestAnimationFrame(tick);
    }

    function measure() {
        width = list.offsetWidth;
        toggle.hidden = false;
        const overflow = width > viewport.clientWidth;
        toggle.hidden = !overflow;
        track.lastElementChild.hidden = !overflow;
        track.lastElementChild.style.display = overflow ? '' : 'none';
        updateMotion();
    }

    function filter() {
        const operation = document.querySelector('input[name="operacion"]:checked')?.value;
        for (const entry of list.children) entry.hidden = !!operation && entry.dataset.operacion !== operation;
        if (track.children.length > 1) track.lastElementChild.remove();
        const copy = list.cloneNode(true);
        copy.setAttribute('aria-hidden', 'true');
        track.append(copy);
        viewport.querySelector('.rate-empty').hidden = !!list.querySelector(':scope > :not([hidden])');
        viewport.scrollLeft = 0;
        measure();
    }

    toggle.addEventListener('click', () => { paused = !paused; updateMotion(); });
    motion.addEventListener('change', () => { paused = motion.matches; updateMotion(); });
    for (const event of ['mouseenter', 'mouseleave', 'focus', 'blur']) viewport.addEventListener(event, updateMotion);
    document.addEventListener('visibilitychange', updateMotion);
    window.addEventListener('resize', measure);
    document.querySelectorAll('input[name="operacion"]').forEach(input => input.addEventListener('change', filter));
    filter();
})();
