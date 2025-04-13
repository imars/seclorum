var scene, camera, renderer, playerDrone, drones, checkpoints, obstacles, clock, timer, speedDisplay, standingsDisplay;

scene = new THREE.Scene();
camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
renderer = new THREE.WebGLRenderer({canvas: document.getElementById('myCanvas')});
renderer.setSize(window.innerWidth, window.innerHeight);

const terrainSize = 1000;
const terrainGeometry = new THREE.PlaneGeometry(terrainSize, terrainSize, 100, 100);
for (let i = 0; i < terrainGeometry.vertices.length; i++) {
    const vertex = terrainGeometry.vertices[i];
    vertex.z = Math.sin(vertex.x / 10) * 10 + Math.random() * 20 -10;
}
const terrainMaterial = new THREE.MeshBasicMaterial({color: 0x00ff00, wireframe: true});
const terrain = new THREE.Mesh(terrainGeometry, terrainMaterial);
scene.add(terrain);

function createDrone(x, y, z, color) {
    const geometry = new THREE.BoxGeometry(2, 2, 2);
    const material = new THREE.MeshBasicMaterial({color: color});
    const drone = new THREE.Mesh(geometry, material);
    drone.position.set(x, y, z);
    scene.add(drone);
    return drone;
}

playerDrone = createDrone(0, 5, 0, 0xff0000);
drones = [createDrone(50, 5, 0, 0x0000ff), createDrone(-50, 5, 0, 0x00ff00)];

function createCheckpoint(x, y, z) {
    const geometry = new THREE.TorusGeometry(1, 0.3, 16, 100);
    const material = new THREE.MeshBasicMaterial({color: 0xffff00});
    const checkpoint = new THREE.Mesh(geometry, material);
    checkpoint.position.set(x, y, z);
    scene.add(checkpoint