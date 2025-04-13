let scene, camera, renderer, drone;

function init() {
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('myCanvas') });
    renderer.setSize(window.innerWidth, window.innerHeight);
    document.body.appendChild(renderer.domElement);

    drone = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial({ color: 0xff0000 }));
    drone.position.set(0, 0, 10);
    scene.add(drone);

    camera.position.set(0, -20, 15);
    camera.lookAt(drone.position);

    document.addEventListener('keydown', onKeyDown);
    animate();
}

function onKeyDown(event) {
    switch (event.key) {
        case 'ArrowUp': drone.position.z += 0.5; break;
        case 'ArrowDown': drone.position.z -= 0.5; break;
        case 'ArrowLeft': drone.position.x -= 0.5; break;
        case 'ArrowRight': drone.position.x += 0.5; break;
        case 'w': drone.position.y += 0.5; break;
        case 's': drone.position.y -= 0.5; break;
    }
}

function animate() {
    requestAnimationFrame(animate);
    renderer.render(scene, camera);
}

init();
