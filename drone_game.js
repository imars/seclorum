let scene, camera, renderer, drone, terrain;
const clock = new THREE.Clock();

init();
animate();

function init() {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(window.innerWidth, window.innerHeight);
  document.body.appendChild(renderer.domElement);

  const ambientLight = new THREE.AmbientLight(0x404040);
  scene.add(ambientLight);
  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
  scene.add(directionalLight);

  const loader = new THREE.GLTFLoader();
  loader.load('drone.glb', function (gltf) {
    drone = gltf.scene;
    scene.add(drone);
    drone.position.set(0, 5, 0);
  });


  terrain = generateTerrain();
  scene.add(terrain);

  camera.position.set(0, 20, 30);
  camera.lookAt(0, 0, 0);

  window.addEventListener('keydown', onKeyDown);
}

function generateTerrain() {
  const geometry = new THREE.PlaneGeometry(100, 100, 100, 100);
  const material = new THREE.MeshStandardMaterial({ color: 0x00ff00 });
  const terrain = new THREE.Mesh(geometry, material);
  terrain.rotation.x = -Math.PI / 2;
  // geometry.vertices is deprecated.  Use geometry.attributes.position.array
  const vertices = geometry.attributes.position.array;
  for (let i = 0; i < vertices.length; i += 3) {
    const x = vertices[i];
    const y = vertices[i + 1];
    vertices[i + 2] = Math.sin(x / 5) * Math.cos(y / 5) * 10;
  }
  geometry.attributes.position.needs