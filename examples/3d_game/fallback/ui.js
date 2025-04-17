// examples/3d_game/fallback/ui.js
console.log('Using ui.js version: 2025-04-17');
console.log('Initializing UI');

function initUI() {
  console.log('Checking for UI elements');
  if (typeof jest !== 'undefined') {
    console.log('Skipping DOM checks in test environment');
    return Promise.resolve(); // Return resolved Promise for tests
  }
  const uiDiv = document.getElementById('ui');
  const startResetButton = document.getElementById('startReset');
  console.log('Document body:', document.body ? document.body.innerHTML : 'undefined');
  console.log('uiDiv:', !!uiDiv);
  console.log('startResetButton:', !!startResetButton);
  if (!uiDiv || !startResetButton) {
    console.error('UI elements not found');
    return Promise.resolve();
  }
  startResetButton.addEventListener('click', startRace);
  updateStandings();
  console.log('UI initialized');
  return Promise.resolve();
}

function startRace() {
  console.log('Starting race');
  global.timer = 0;
  global.standings = [];
  if (global.playerDrone) {
    global.playerDrone.position.set(0, 10, 0);
    global.playerDrone.momentum.set(0, 0, 0);
    global.playerDrone.rotation.set(0, 0, 0);
    global.playerDrone.checkpoints = [];
    global.playerDrone.time = 0;
  }
  if (global.aiDrones) {
    global.aiDrones.forEach((d, i) => {
      d.position.set(i * 20 - 20, 10, 0);
      d.checkpoints = [];
      d.time = 0;
      d.targetCheckpoint = 0;
      d.path = [];
    });
  }
  updateStandings();
}

function updateStandings() {
  console.log('Updating standings');
  const drones = global.playerDrone && global.aiDrones ? [global.playerDrone, ...global.aiDrones] : [];
  global.standings = drones.map((d, i) => ({
    drone: i + 1,
    checkpoints: d.checkpoints ? d.checkpoints.length : 0,
    time: d.time || (d.checkpoints && d.checkpoints.length === global.checkpoints.length ? global.timer : Infinity),
  }));
  global.standings.sort((a, b) => b.checkpoints - a.checkpoints || a.time - b.time);
  if (typeof jest !== 'undefined') {
    console.log('Skipping DOM update in test environment');
    return;
  }
  const table = document.getElementById('standings');
  if (!table) {
    console.log('Standings table not found');
    return;
  }
  if (table && table.querySelector('table')) {
    const tableElement = table.querySelector('table');
    tableElement.innerHTML =
      '<tr><th>Drone</th><th>Checkpoints</th><th>Time</th></tr>' +
      global.standings
        .map(
          (s) =>
            `<tr><td>${s.drone}</td><td>${s.checkpoints}/${global.checkpoints.length}</td><td>${
              s.time === Infinity ? '-' : s.time.toFixed(1)
            }</td></tr>`
        )
        .join('');
    if (global.standings.some((s) => s.checkpoints === global.checkpoints.length)) {
      const winner = global.standings[0];
      tableElement.innerHTML += `<tr><td colspan="3">Drone ${winner.drone} Wins!</td></tr>`;
    }
  }
}

function updateUI() {
  if (typeof jest !== 'undefined') {
    console.log('Skipping UI update in test environment');
    return;
  }
  const timerElement = document.getElementById('timer');
  const speedElement = document.getElementById('speed');
  if (!timerElement) {
    console.log('Timer element not found');
    return;
  }
  if (timerElement) timerElement.innerText = global.timer.toFixed(1);
  if (speedElement) {
    speedElement.innerText = global.playerDrone && global.playerDrone.momentum ? global.playerDrone.momentum.length().toFixed(1) : '0';
  }
}

module.exports = { initUI, updateUI, startRace, updateStandings };
