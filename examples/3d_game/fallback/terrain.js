// examples/3d_game/fallback/terrain.js
let terrain;

function initTerrain() {
    if (typeof THREE === 'undefined') {
        console.error('THREE.js not loaded');
        throw new Error('THREE required');
    }
    if (typeof simplexNoise === 'undefined') {
        console.error('simplexNoise not loaded. Using flat terrain.');
        window.simplexNoise = { createNoise2D: () => (x, y) => 0 };
    }
    const terrainGeometry = new THREE.PlaneGeometry(1000, 1000, 100, 100);
    const noise = simplexNoise.createNoise2D();
    const vertices = terrainGeometry.attributes.position.array;
    for (let i = 2; i < vertices.length; i += 3) {
        const x = vertices[i-2], y = vertices[i-1];
        vertices[i] = noise(x * 0.02, y * 0.02) * 50;
    }
    terrainGeometry.attributes.position.needsUpdate = true;
    terrainGeometry.computeVertexNormals();
    terrain = new THREE.Mesh(
        terrainGeometry,
        new THREE.MeshStandardMaterial({ color: 0x228B22, roughness: 0.8 })
    );
    terrain.rotation.x = -Math.PI / 2;
    scene.add(terrain);
}
