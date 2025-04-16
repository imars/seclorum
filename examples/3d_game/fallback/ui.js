// examples/3d_game/fallback/ui.js
let timer = 0, standings = [];

function initUI() {
    if (typeof THREE === 'undefined') {
        console.error('THREE.js not loaded');
        throw new Error('THREE required');
    }
    document.getElementById('startReset').addEventListener('click', startRace);
    updateStandings();
}

function startRace() {
    timer = 0;
    standings = [];
    playerDrone.position.set(0, 10, 0);
    playerDrone.momentum.set(0, 0, 0);
    playerDrone.checkpoints = [];
    playerDrone.time = 0;
    playerDrone.controls = {};
    aiDrones.forEach((d, i) => {
        d.position.set(i * 20 - 20, 10, 0);
        d.checkpoints = [];
        d.time = 0;
        d.targetCheckpoint = 0;
        d.path = [];
    });
    updateStandings();
}

function updateStandings() {
    const drones = [playerDrone, ...aiDrones];
    standings = drones.map((d, i) => ({
        drone: i + 1,
        checkpoints: d.checkpoints.length,
        time: d.time || (d.checkpoints.length === checkpoints.length ? timer : Infinity)
    }));
    standings.sort((a, b) => b.checkpoints - a.checkpoints || a.time - b.time);
    const table = document.getElementById('standings');
    table.innerHTML = '<tr><th>Drone</th><th>Checkpoints</th><th>Time</th></tr>' +
        standings.map(s => `<tr><td>${s.drone}</td><td>${s.checkpoints}/${checkpoints.length}</td><td>${s.time === Infinity ? '-' : s.time.toFixed(1)}</td></tr>`).join('');
    if (standings.some(s => s.checkpoints === checkpoints.length)) {
        const winner = standings[0];
        table.innerHTML += `<tr><td colspan="3">Drone ${winner.drone} Wins!</td></tr>`;
    }
}

function updateUI() {
    document.getElementById('timer').innerText = timer.toFixed(1);
    document.getElementById('speed').innerText = playerDrone.momentum ? playerDrone.momentum.length().toFixed(1) : '0';
}

function animate() {
    requestAnimationFrame(animate);
    const delta = clock.getDelta();
    timer += delta;

    updatePlayerDrone(delta);
    updateAIDrones(delta);
    checkCollisions(timer, standings, updateStandings);
    updateUI();

    camera.position.lerp(
        playerDrone.position.clone().add(new THREE.Vector3(0, 20, 30)),
        0.1
    );
    camera.lookAt(playerDrone.position);
    renderer.render(scene, camera);
}
