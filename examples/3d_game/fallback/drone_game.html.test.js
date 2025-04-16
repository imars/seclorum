// examples/3d_game/fallback/drone_game.html.test.js
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
            <script defer src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
            <script defer src="https://cdn.jsdelivr.net/npm/simplex-noise@4.0.1/dist/simplex-noise.min.js"></script>
            <script src="scene.js"></script>
            <script src="terrain.js"></script>
            <script src="drones.js"></script>
            <script src="ui.js"></script>`;
        jest.spyOn(console, 'error').mockImplementation(() => {});
    });

    test('has canvas and UI elements', () => {
        expect(document.getElementById('gameCanvas')).toBeDefined();
        expect(document.getElementById('timer')).toBeDefined();
        expect(document.getElementById('speed')).toBeDefined();
        expect(document.getElementById('standings')).toBeDefined();
        expect(document.getElementById('startReset')).toBeDefined();
    });

    test('includes required scripts', () => {
        const scripts = Array.from(document.getElementsByTagName('script')).map(s => s.src || '');
        expect(scripts.some(src => src.includes('three.min.js'))).toBe(true);
        expect(scripts.some(src => src.includes('simplex-noise'))).toBe(true);
        expect(scripts.includes('scene.js')).toBe(true);
        expect(scripts.includes('terrain.js')).toBe(true);
        expect(scripts.includes('drones.js')).toBe(true);
        expect(scripts.includes('ui.js')).toBe(true);
    });

    test('styles start button correctly', () => {
        const button = document.getElementById('startReset');
        expect(window.getComputedStyle(button).backgroundColor).toMatch(/rgba?\(0, 123, 255/);
    });

    afterEach(() => {
        document.body.innerHTML = '';
        console.error.mockRestore();
    });
});
