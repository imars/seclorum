// jest.e2e.config.js
export default {
  testEnvironment: 'node',
  testMatch: ['**/*.e2e.js'],
  setupFilesAfterEnv: ['<rootDir>/jest.e2e.setup.js'],
};
