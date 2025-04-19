// scripts/serve.js
import { createServer } from 'http-server';
import { execSync } from 'child_process';

// Build the game
try {
  execSync('npm run build', { stdio: 'inherit' });
} catch (error) {
  console.error('Build failed:', error);
  process.exit(1);
}

// Start the server
const server = createServer({ root: './dist' });
server.listen(8080, () => {
  console.log('Server running at http://localhost:8080');
});
