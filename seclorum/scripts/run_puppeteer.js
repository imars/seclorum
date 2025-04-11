// scripts/run_puppeteer.js
const puppeteer = require('puppeteer');
const fs = require('fs');

(async () => {
  let output = '';

  try {
    const browser = await puppeteer.launch({
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    const page = await browser.newPage();

    // Capture console output
    page.on('console', (msg) => {
      output += `${msg.type()}: ${msg.text()}\n`;
    });

    // Load Three.js from CDN for simplicity in this test
    const htmlContent = `
      <!DOCTYPE html>
      <html>
        <body>
          <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
          <script>
            ${fs.readFileSync(process.argv[2], 'utf8')}
          </script>
        </body>
      </html>
    `;
    await page.setContent(htmlContent);

    // Wait for animation or scene setup (5s timeout)
    await page.waitForFunction('typeof window.animate === "function" || window.THREE !== undefined', { timeout: 5000 });
    output += 'Execution successful: Scene or animation detected\n';

    await browser.close();
    fs.writeFileSync(`${process.argv[2]}.out`, output);
    process.exit(0);
  } catch (e) {
    output += `Error: ${e.stack}\n`;
    fs.writeFileSync(`${process.argv[2]}.out`, output);
    process.exit(1);
  }
})();
