export default {
  testEnvironment: 'jsdom',
  testMatch: ['**/*.test.js'],
  testEnvironment: 'jest-environment-jsdom',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  transform: {
    '^.+\\.js$': 'babel-jest',
  },
};
