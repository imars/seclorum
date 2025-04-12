var scene, camera, renderer, drone, checkpoints, clock;
const checkpointRadius = 1;
const droneSpeed = 0.2;
const numCheckpoints = 5;

init();
animate();

function init() {
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    renderer = new THREE.WebGLRenderer();
    renderer.setSize(window.innerWidth, window.innerHeight);
    document.body.appendChild(renderer.domElement);

    camera.position.z = 5;

    const geometry = new THREE.BoxGeometry(1, 1, 1);
    const material = new THREE.MeshBasicMaterial({ color: 0x0000ff });
    drone = new THREE.Mesh(geometry, material);
    scene.add(drone);

    checkpoints = [];
    for (let i = 0; i < numCheckpoints; i++) {
        const cpGeometry = new THREE.SphereGeometry(checkpointRadius, 32, 32);
        const cpMaterial = new THREE.MeshBasicMaterial({ color: 0xff0000 });
        const checkpoint = new THREE.Mesh(cpGeometry, cpMaterial);
        checkpoint.position.set(Math.random() * 10 - 5, Math.random() * 5 - 2.5, Math.random() * 10 - 5);
        scene.add(checkpoint);
        checkpoints.push(checkpoint);
    }

    clock = new THREE.Clock();
    window.addEventListener('keydown', onKeyDown, false);
}

function onKeyDown(e) {
    switch (e.keyCode) {
        case 87: // W
            drone.position.z -= droneSpeed;
            break;
        case 83: // S
            drone.position.z += droneSpeed;
            break;
        case 65: // A
            drone.position.x -= droneSpeed;
            break;
        case 68: // D
            drone.position.x += droneSpeed;
            break;
    }
}


function animate() {
    requestAnimationFrame(animate);
    const