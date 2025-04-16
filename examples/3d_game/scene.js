// examples/3d_game/fallback/scene.js
let scene, camera, renderer, clock;

function initScene() {
    if (typeof THREE === 'undefined') {
('THREE.js not loaded');
        throw new Error('THREE required');
    }
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('gameCanvas') });
    renderer.setSize(window.innerWidth, window.innerHeight);
    clock = new THREE.Clock();

    scene.add(new THREE.AmbientLight(0x404040));
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
    directionalLight.position.set(0, 100, 50);
    scene.add(directionalLight);

    camera.position.set(0, 30, 50);
}