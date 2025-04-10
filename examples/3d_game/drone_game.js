import Three from 'three'

Three.RAF = requestAnimationFrame

function init() {
    var scene = new Three.Scene();
    var camera = new Three.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    var renderer = new Three.WebGLRenderer({
        canvas: document.getElementById('canvas'),
        antialias: true
    });
    renderer.setSize(window.innerWidth, window.innerHeight);

    scene.background = new Three.Color(0xd3d3d3);

    var droneGeometry = new Three.BoxGeometry(1, 1, 2);
    var droneMaterial = new Three.MeshBasicMaterial({
        color: 0x4CAF50
    });
    var drone = new Three.Mesh(droneGeometry, droneMaterial);
    scene.add(drone);

    camera.position.z = 5;

    function animate() {
        requestAnimationFrame(animate);
        drone.rotation.x += 0.01;
        drone.rotation.y += 0.01;
        renderer.render(scene, camera);
    }

    animate();
}

window.addEventListener('keydown', function(event) {
    switch (event.key) {
        case 'ArrowUp':
            drone.position.z += 1;
            break;
        case 'ArrowDown':
            drone.position.z -= 1;
            break;
        case 'ArrowLeft':
            drone.position.x -= 1;
            break;
        case 'ArrowRight':
            drone.position.x += 1;
            break;
    }
});

window.addEventListener('keyup', function(event) {
    switch (event.key) {
        case 'ArrowUp':
            drone.position.z = Math.max(-10, Math.min(10, drone.position.z));
            break;
        case 'ArrowDown':
            drone.position.z = Math.max(-10, Math.min(10, drone.position.z));
            break;
        case 'ArrowLeft':
            drone.position.x = Math.max(-10, Math.min(10, drone.position.x));
            break;
        case 'ArrowRight':
            drone.position.x = Math.max(-10, Math.min(10, drone.position.x));
            break;
    }
});

init();