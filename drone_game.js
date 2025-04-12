
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 5, 10);
scene.add(camera);
const renderer = new THREE.WebGLRenderer({canvas: document.getElementById('myCanvas')});
renderer.setSize(window.innerWidth, window.innerHeight);

const droneGeometry = new THREE.BoxGeometry(1, 1, 1);
const droneMaterial = new THREE.MeshBasicMaterial({color: 0x0000ff});
const drone = new THREE.Mesh(droneGeometry, droneMaterial);
scene.add(drone);

const numStars = 1000;
const starsGeometry = new THREE.BufferGeometry();
const starPositions = new Float32Array(numStars * 3);
for (let i = 0; i < numStars; i++) {
  starPositions[i * 3] = Math.random() * 1000 - 500;
  starPositions[i * 3 + 1] = Math.random() * 1000 - 500;
  starPositions[i * 3 + 2] = Math.random() * 1000 - 500;
}
starsGeometry.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
const starsMaterial = new THREE.PointsMaterial({color: 0xffffff, size: 2});
const stars = new THREE.Points(starsGeometry, starsMaterial);
scene.add(stars);

let speed = 0.1;
const keysPressed = {};
document.addEventListener('keydown', (e) => {keysPressed[e.code] = true;});
document.addEventListener('keyup', (e) => {keysPressed[e.code] = false;});

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

function animate() {
  requestAnimationFrame(animate);
  if (keysPressed['ArrowUp']) drone.position.z -= speed;
  if (keysPressed['ArrowDown']) drone.position.z += speed;
  if (keysPressed['ArrowLeft']) drone.position.x -= speed;
  if (keysPressed['ArrowRight']) drone.position.x += speed;
  renderer.render(scene, camera);
}
animate();
