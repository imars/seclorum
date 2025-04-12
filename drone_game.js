let scene, camera, renderer, drones = [], checkpoints = [], terrain, clock;
const droneGeometry = new THREE.BoxGeometry(1, 1, 2);
const checkpointGeometry = new THREE.TorusGeometry(1, 0.2, 16, 100);
const speeds = [];
const checkpointOrder = [];

function init() {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
  renderer = new THREE.WebGLRenderer();
  renderer.setSize(window.innerWidth, window.innerHeight);
  document.body.appendChild(renderer.domElement);
  camera.position.set(0, 50, 0);
  scene.add(camera);
  clock = new THREE.Clock();
  generateTerrain();
  createCheckpoints();
  createDrones();
  document.getElementById('startButton').addEventListener('click', startRace);
}

function generateTerrain() {
  const size = 1000;
  const data = new Float32Array(size * size);
  for (let i = 0; i < size * size; i++) {
    data[i] = Math.sin(i / 100) * 10;
  }
  const geometry = new THREE.PlaneGeometry(size, size, size - 1, size - 1);
  geometry.setAttribute('a_height', new THREE.BufferAttribute(data, 1));
  const material = new THREE.ShaderMaterial({
    vertexShader: `
      varying float vHeight;
      attribute float a_height;
      void main() {
        vHeight = a_height;
        vec3 pos = position;
        pos.y += a_height * 5;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
      }
    `,
    fragmentShader: `
      varying float vHeight;
      void main() {
        gl_FragColor = vec4(vec3(vHeight / 50 + 0.5), 1.0);
      }
    `
  });
  terrain = new THREE.