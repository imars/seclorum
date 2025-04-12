const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer();
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

const droneGeometry = new THREE.BoxGeometry(1, 1, 1);
const droneMaterial = new THREE.MeshBasicMaterial({ color: 0x0000ff });

const drones = [];
const numDrones = 3;
for (let i = 0; i < numDrones; i++) {
  const drone = new THREE.Mesh(droneGeometry, droneMaterial);
  drone.position.set(0, 1, i * 5);
  scene.add(drone);
  drones.push({ mesh: drone, velocity: new THREE.Vector3(0, 0, 0), checkpointsPassed: 0 });
}

const terrainGeometry = new THREE.PlaneGeometry(100, 100, 10, 10);
const terrainMaterial = new THREE.MeshBasicMaterial({ color: 0x00ff00 });
const terrain = new THREE.Mesh(terrainGeometry, terrainMaterial);
scene.add(terrain);

const checkpoints = [];
for (let i = 0; i < 5; i++) {
  const checkpoint = new THREE.Mesh(new THREE.SphereGeometry(0.5), new THREE.MeshBasicMaterial({ color: 0xff0000 }));
  checkpoint.position.set(Math.random() * 50 -25, 1, Math.random() * 50 - 25);
  scene.add(checkpoint);
  checkpoints.push(checkpoint);
}

const ambientLight = new THREE.AmbientLight(0x404040);
scene.add(ambientLight);
const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
scene.add(directionalLight);

camera.position.z = 5;

let timer = 0;
let gameStarted = false;

const timerDisplay = document.getElementById('timer');
const speedDisplay = document