let scene, camera, renderer, drones = [], terrain, checkpoints = [], clock;

const init = () => {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
  renderer = new THREE.WebGLRenderer();
  renderer.setSize(window.innerWidth, window.innerHeight);
  document.body.appendChild(renderer.domElement);

  //Lighting
  const ambientLight = new THREE.AmbientLight(0x404040);
  scene.add(ambientLight);
  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
  scene.add(directionalLight);

  //Terrain (placeholder - replace with actual terrain generation)
  const geometry = new THREE.PlaneGeometry(100, 100);
  const material = new THREE.MeshBasicMaterial({color: 0x00ff00});
  terrain = new THREE.Mesh(geometry, material);
  scene.add(terrain);

  //Drone (placeholder - replace with model loading)
  const droneGeometry = new THREE.BoxGeometry(1, 1, 1);
  const droneMaterial = new THREE.MeshBasicMaterial({color: 0xff0000});


  //Checkpoints (placeholder)
  const checkpointGeometry = new THREE.SphereGeometry(0.5, 16, 16);
  const checkpointMaterial = new THREE.MeshBasicMaterial({color: 0x0000ff});
  checkpoints.push(new THREE.Mesh(checkpointGeometry, checkpointMaterial));
  checkpoints[0].position.set(20, 1, 0);
  scene.add(checkpoints[0]);

  //Add more checkpoints as needed

  //Add multiple drones.
  for (let i = 0; i < 2; i++) {
    const drone = new THREE.Mesh(droneGeometry.clone(), droneMaterial.clone());
    drone.position.set(i * 5, 1, 0);
    scene.add(drone);
    drones.push(drone);
  }

  camera.position.z = 5;
  clock =