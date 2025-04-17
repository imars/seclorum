console.log('Initializing terrain');

function initTerrain() {
    if (!window.THREE || !window.simplexNoise) {
        console.error('THREE.js or simplexNoise not loaded');
        return;
    }
    const planeGeometry = new window.THREE.PlaneGeometry(1000, 1000, 100, 100);
    const noise = window.simplexNoise.createNoise2D();
    const vertices = planeGeometry.attributes.position.array;
    for (let i = 2; i < vertices.length; i += 3) {
        const x = vertices[i - 2];
        const y = vertices[i - 1];
        vertices[i] = noise(x * 0.02, y * 0.02) * 50;
    }
    planeGeometry.attributes.position.needsUpdate = true;
    planeGeometry.computeVertexNormals();
    const material = new window.THREE.MeshStandardMaterial({ color: 0x228B22, roughness: 0.8 });
    const terrain = new window.THREE.Mesh(planeGeometry, material);
    terrain.rotation.x = -Math.PI / 2;
    global.scene.add(terrain);
    console.log('Terrain initialized');
}

module.exports = { initTerrain };
