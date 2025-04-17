module.exports = {
  testEnvironment: 'jest-environment-jsdom',
  testMatch: ['**/*.test.js'],
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  testSequentially: true, // Run tests sequentially
};
