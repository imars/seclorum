/**
 * @jest-environment jsdom
 */
describe('Game Initialization and Components', () => {
    beforeEach(() => {
        // Mock dependencies
        window.THREE = {
            Scene: jest.fn(),
            PerspectiveCamera: jest.
                fn(),
            WebGLRenderer: jest.fn(() => ({
                setSize: jest.fn(),
                render: jest.fn()
            })),
            PlaneGeometry: jest.fn(() => ({
                vertices: [{ x: 0, y: 0, z: 0 }],
                computeVertexNormals: jest.fn()
            })),
            MeshStandardMaterial: jest.fn(),
            Mesh: jest.fn(),
            AmbientLight: jest.fn(),
            DirectionalLight: jest.fn()
        };

        global.simplexNoise = {
            createNoise2D: jest.fn(() => jest.fn(() => 0))
        };

        jest.spyOn(window, 'requestAnimationFrame').mockImplementation(cb => cb());
        jest.spyOn(console, 'error').mockImplementation(() => {});
    });

    test('initializes game components', () => {
        expect(THREE.Scene).toHaveBeenCalled();
    });
});
