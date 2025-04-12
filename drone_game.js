let scene, camera, renderer, droneModel, drones, terrain;
const clock = new THREE.Clock();

init();
animate();

function init() {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
  renderer = new THREE.WebGLRenderer();
  renderer.setSize(window.innerWidth, window.innerHeight);
  document.body.appendChild(renderer.domElement);

  const ambientLight = new THREE.AmbientLight(0x404040);
  scene.add(ambientLight);
  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
  scene.add(directionalLight);


  //Load drone model (replace with your model path)
  const loader = new THREE.GLTFLoader();
  loader.load('drone.gltf', function(gltf){
    droneModel = gltf.scene;
    createDrones(3);
  });

  //Generate terrain (replace with your terrain generation)
  terrain = new THREE.Mesh(new THREE.PlaneGeometry(1000,1000), new THREE.MeshBasicMaterial({color: 0x00ff00}));
  scene.add(terrain);

  camera.position.set(0, 50, 100);

  window.addEventListener('keydown', onKeyDown);
}

function createDrones(numDrones) {
  drones = [];
  for (let i = 0; i < numDrones; i++) {
    const drone = droneModel.clone();
    drone.position.set(i * 20, 10, 0);
    scene.add(drone);
    drones.push({ model: drone, speed: 0, acceleration: 0.1});
  }
}


function onKeyDown(event) {
  const speedIncrement = 0.5;
  switch (event.key) {
    case 'ArrowUp': drones.forEach(d => d.speed += speedIncrement); break;
    case 'ArrowDown': drones.forEach(d => d.speed -= speedIncrement); break;
    case 'Arrow