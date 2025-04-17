// examples/3d_game/fallback/scene.js
console.log('Initializing scene');
let scene, camera, renderer, clock;

function initScene() {
    if (!window.THREE) {
        console.error('THREE.js not loaded');
        return;
    }
    scene = new window.THREE.Scene();
    camera = new window.THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    renderer = new window.THREE.WebGLRenderer({ canvas: document.getElementById('gameCanvas') });
    renderer.setSize(window.innerWidth, window.innerHeight);
    scene.add(new window.THREE.AmbientLight(0x404040));
    const directionalLight = new window.THREE.DirectionalLight(0xffffff, 0.5);
    directionalLight.position.set(0, 100, 50);
    scene.add(directionalLight);
    clock = new window.THREE.Clock();
    global.scene = scene;
    global.camera = camera;
    global.renderer = renderer;
    global.clock = clock;
    console.log('Scene initialized');
}

module.exports = { initScene, scene, camera, renderer, clock };
