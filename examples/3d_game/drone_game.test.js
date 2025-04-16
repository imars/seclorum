describe('Drone Racing Game', () => {
    beforeEach(() => {
        window.innerWidth = 500;
        window.innerHeight = 500;
        document.body.innerHTML = `
            <canvas id="gameCanvas"></canvas>
            <div id="ui">
                <div>Timer: <span id="timer">0</span>s</div>
                <div>Speed: <span id="speed">0</span></div>
                <table id="standings"></table>
                <button id="startReset">Start</button>
            </div>`;
        jest.spyOn(window, 'requestAnimationFrame').mockImplementation(cb => cb());
        init();
    });

    test('initializes scene and drones', () => {
        expect(scene).toBeDefined();
        expect(camera).toBeDefined();
        expect(renderer).toBeDefined();
        expect(playerDrone).toBeDefined();
        expect(aiDrones.length).toBe(3);
        expect(terrain).toBeDefined();
        expect(checkpoints.length).toBe(6);
        expect(obstacles.length).toBe(20);
    });

    test('handles player controls with momentum', () => {
        const initialPos = playerDrone.position.clone();
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp' }));
        animate();
        expect(playerDrone.position.z).toBeLessThan(initialPos.z);
        window.dispatchEvent(new KeyboardEvent('keyup', { key: 'ArrowUp' }));
        animate();
        expect(playerDrone.momentum.length()).toBeLessThan(1);
    });

    test('moves AI drones with pathfinding', () => {
        const aiDrone = aiDrones[0];
        const initialPos = aiDrone.position.clone();
        animate();
        expect(aiDrone.position.distanceTo(initialPos)).toBeGreaterThan(0);
        expect(aiDrone.path.length).toBeGreaterThan(0);
    });

    test('updates standings table', () => {
        playerDrone.checkpoints = [0, 1];
        updateStandings();
        const table = document.getElementById('standings');
        expect(table.innerHTML).toContain('Drone 1');
        expect(table.innerHTML).toContain('2/6');
    });

    test('detects checkpoint collisions', () => {
        playerDrone.position.copy(checkpoints[0].position);
        checkCollisions();
        expect(playerDrone.checkpoints).toContain(0);
        playerDrone.checkpoints = Array.from({ length: checkpoints.length }, (_, i) => i);
        checkCollisions();
        expect(standings.some(s => s.drone === 1 && s.time > 0)).toBe(true);
    });

    test('penalizes obstacle collisions', () => {
        playerDrone.position.copy(obstacles[0].position);
        checkCollisions();
        expect(standings.some(s => s.drone === 1 && s.penalty)).toBe(true);
    });

    test('resets race on button click', () => {
        playerDrone.checkpoints = [0];
        document.getElementById('startReset').click();
        expect(playerDrone.checkpoints.length).toBe(0);
        expect(timer).toBe(0);
    });

    afterEach(() => {
        window.requestAnimationFrame.mockRestore();
        document.body.innerHTML = '';
    });
});