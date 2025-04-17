// Assumes global THREE and simplexNoise from CDNs
if (typeof simplexNoise === 'undefined') {
('simplexNoise not loaded. Ensure CDN is available.');
    throw new Error('simplexNoise required');
}
let scene, camera, renderer, playerDrone, aiDrones = [], terrain, checkpoints = [], obstacles = [], timer = 0, standings = [];
const clock = new THREE.Clock();

init();
animate();

function init() {
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('gameCanvas') });
    renderer.setSize(window.innerWidth, window.innerHeight);

    // Terrain with simplex-noise
    const terrainGeometry = new THREE.PlaneGeometry(1000, 1000, 100, 100);
    const noise = simplexNoise.createNoise2D();
    const vertices = terrainGeometry.attributes.position.array;
    for (let i = 2; i < vertices.length; i += 3) {
        const x = vertices[i-2], y = vertices[i-1];
        vertices[i] = noise(x * 0.05, y * 0.05) * 30;
    }
    terrainGeometry.attributes.position.needsUpdate = true;
    terrainGeometry.computeVertexNormals();
    terrain = new THREE.Mesh(terrainGeometry, new THREE.MeshStandardMaterial({ color: 0x228B22, roughness: 0.8 }));
    terrain.rotation.x = -Math.PI / 2;
    scene.add(terrain);

    // Lighting
    scene.add(new THREE.AmbientLight(0x404040));
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
    directionalLight.position.set(0, 100, 50);
    scene.add(directionalLight);

    // Player Drone
    playerDrone = createDrone(0x0000ff, { x: 0, y: 10, z: 0 });
    playerDrone.momentum = new THREE.Vector3();
    scene.add(playerDrone);

    // AI Drones
    for (let i = 0; i < 3; i++) {
        const aiDrone = createDrone(0xff0000, { x: i * 20 - 20, y: 10, z: 0 });
        aiDrone.path = [];
        aiDrone.targetCheckpoint = 0;
        scene.add(aiDrone);
        aiDrones.push(aiDrone);
    }

    // Checkpoints
    for (let i = 0; i < 6; i++) {
        const checkpoint = new THREE.Mesh(
            new THREE.TorusGeometry(8, 1, 16, 100),
            new THREE.MeshBasicMaterial({ color: 0xffff00 })
        );
        checkpoint.position.set(Math.random() * 100 - 50, 10, -i * 150 - 50);
        scene.add(checkpoint);
        checkpoints.push(checkpoint);
    }

    // Obstacles
    for (let i = 0; i < 20; i++) {
        const type = Math.random() < 0.5 ? 'tree' : 'rock';
        const obstacle = new THREE.Mesh(
            type === 'tree' ? new THREE.CylinderGeometry(2, 2, 15, 16) : new THREE.BoxGeometry(5, 5, 5),
            new THREE.MeshStandardMaterial({ color: type === 'tree' ? 0x8B4513 : 0x808080 })
        );
        obstacle.position.set(Math.random() * 200 - 100, type === 'tree' ? 7.5 : 2.5, Math.random() * -800 - 50);
        scene.add(obstacle);
        obstacles.push(obstacle);
    }

    // Camera
    camera.position.set(0, 30, 50);
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    document.getElementById('startReset').addEventListener('click', startRace);

    updateStandings();
}

function createDrone(color, pos) {
    const drone = new THREE.Mesh(
        new THREE.SphereGeometry(2, 16, 16),
        new THREE.MeshStandardMaterial({ color })
    );
    drone.position.set(pos.x, pos.y, pos.z);
    drone.checkpoints = [];
    drone.time = 0;
    return drone;
}

function onKeyDown(event) {
    playerDrone.controls = playerDrone.controls || {};
    switch (event.key) {
        case 'ArrowUp': case 'w': playerDrone.controls.forward = true; break;
        case 'ArrowDown': case 's': playerDrone.controls.backward = true; break;
        case 'ArrowLeft': playerDrone.controls.left = true; break;
        case 'ArrowRight': playerDrone.controls.right = true; break;
    }
}

function onKeyUp(event) {
    playerDrone.controls = playerDrone.controls || {};
    switch (event.key) {
        case 'ArrowUp': case 'w': playerDrone.controls.forward = false; break;
        case 'ArrowDown': case 's': playerDrone.controls.backward = false; break;
        case 'ArrowLeft': playerDrone.controls.left = false; break;
        case 'ArrowRight': playerDrone.controls.right = false; break;
    }
}

function startRace() {
    timer = 0;
    standings = [];
    playerDrone.position.set(0, 10, 0);
    playerDrone.momentum.set(0, 0, 0);
    playerDrone.checkpoints = [];
    playerDrone.time = 0;
    aiDrones.forEach((d, i) => {
        d.position.set(i * 20 - 20, 10, 0);
        d.checkpoints = [];
        d.time = 0;
        d.targetCheckpoint = 0;
        d.path = [];
    });
    updateStandings();
}

function updatePlayerDrone(delta) {
    const accel = 0.5, friction = 0.9, maxSpeed = 5;
    playerDrone.controls = playerDrone.controls || {};
    const move = new THREE.Vector3();
    if (playerDrone.controls.forward) move.z -= accel;
    if (playerDrone.controls.backward) move.z += accel;
    if (playerDrone.controls.left) move.x -= accel;
    if (playerDrone.controls.right) move.x += accel;
    playerDrone.momentum.add(move.multiplyScalar(delta));
    playerDrone.momentum.clampLength(0, maxSpeed);
    playerDrone.momentum.multiplyScalar(friction);
    playerDrone.position.add(playerDrone.momentum);
    playerDrone.position.y = 10;
}

function updateAIDrones(delta) {
    aiDrones.forEach(d => {
        if (d.targetCheckpoint >= checkpoints.length) return;
        const target = checkpoints[d.targetCheckpoint].position;
        if (d.path.length === 0 || d.position.distanceTo(d.path[d.path.length - 1]) < 5) {
            d.path = aStarPath(d.position, target, obstacles);
        }
        if (d.path.length > 0) {
            const next = d.path.shift();
            const direction = next.clone().sub(d.position).normalize();
            d.position.add(direction.multiplyScalar(3 * delta));
            d.position.y = 10;
        }
    });
}

function aStarPath(start, goal, obstacles) {
    const gridSize = 10, grid = [];
    for (let x = -500; x <= 500; x += gridSize) {
        grid[x] = [];
        for (let z = -1000; z <= 0; z += gridSize) {
            grid[x][z] = obstacles.some(o => new THREE.Vector3(x, 10, z).distanceTo(o.position) < 10) ? Infinity : 1;
        }
    }
    const open = [{ pos: start.clone(), g: 0, h: start.distanceTo(goal), f: start.distanceTo(goal), path: [] }];
    const closed = new Set();
    while (open.length) {
        open.sort((a, b) => a.f - b.f);
        const current = open.shift();
        const key = `${Math.round(current.pos.x / gridSize)},${Math.round(current.pos.z / gridSize)}`;
        if (closed.has(key)) continue;
        closed.add(key);
        if (current.pos.distanceTo(goal) < 10) {
            return current.path.concat([goal]);
        }
        for (let dx of [-gridSize, 0, gridSize]) {
            for (let dz of [-gridSize, 0, gridSize]) {
                if (dx === 0 && dz === 0) continue;
                const nextPos = current.pos.clone().add(new THREE.Vector3(dx, 0, dz));
                const nextKey = `${Math.round(nextPos.x / gridSize)},${Math.round(nextPos.z / gridSize)}`;
                if (closed.has(nextKey) || (grid[Math.round(nextPos.x)] && grid[Math.round(nextPos.x)][Math.round(nextPos.z)] === Infinity)) continue;
                const g = current.g + gridSize;
                const h = nextPos.distanceTo(goal);
                open.push({ pos: nextPos, g, h, f: g + h, path: current.path.concat([nextPos]) });
            }
        }
    }
    return [];
}

function checkCollisions() {
    const drones = [playerDrone, ...aiDrones];
    drones.forEach((d, i) => {
        checkpoints.forEach((c, j) => {
            if (!d.checkpoints.includes(j) && d.position.distanceTo(c.position) < 8) {
                d.checkpoints.push(j);
                if (d.checkpoints.length === checkpoints.length) {
                    d.time = timer;
                    updateStandings();
                }
            }
        });
        obstacles.forEach(o => {
            if (d.position.distanceTo(o.position) < 5) {
                d.momentum ? d.momentum.multiplyScalar(0.5) : d.position.set(d.position.x, 10, d.position.z);
                if (d === playerDrone) standings.push({ drone: i + 1, time: Infinity, penalty: true });
            }
        });
    });
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
    checkCollisions();
    updateUI();

    camera.position.lerp(
        playerDrone.position.clone().add(new THREE.Vector3(0, 20, 30)),
        0.1
    );
    camera.lookAt(playerDrone.position);
    renderer.render(scene, camera);
}