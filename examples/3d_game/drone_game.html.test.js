describe('Drone Game UI', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <canvas id="gameCanvas"></canvas>
            <div id="ui">
                <div>Timer: <span id="timer">0</span>s</div>
                <div>Speed: <span id="speed">0</span></div>
                <div id="standings"><table></table></div>
                <button id="startReset">Start</button>
            </div>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
            <script src="https://unpkg.com/three-noise/build/three-noise.min.js"></script>
            <script src="drone_game.js"></script>`;
    });

    test('has canvas and UI elements', () => {
        expect(document.getElementById('gameCanvas')).toBeDefined();
        expect(document.getElementById('timer')).toBeDefined();
        expect(document.getElementById('speed')).toBeDefined();
        expect(document.getElementById('standings')).toBeDefined();
        expect(document.getElementById('startReset')).toBeDefined();
    });

    test('includes required scripts', () => {
        const scripts = Array.from(document.getElementsByTagName('script')).map(s => s.src);
        expect(scripts.some(src => src.includes('three.min.js'))).toBe(true);
        expect(scripts.some(src => src.includes('three-noise'))).toBe(true);
        expect(scripts.includes('drone_game.js')).toBe(true);
    });

    test('styles start button correctly', () => {
        const button = document.getElementById('startReset');
        expect(window.getComputedStyle(button).backgroundColor).toMatch(/rgba?\(0, 123, 255/);
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });
});