// src/state.js
let state = {
  timer: 0,
  standings: [],
};

export function getTimer() {
  return state.timer;
}

export function setTimer(value) {
  state.timer = value;
}

export function getStandings() {
  return state.standings;
}

export function setStandings(value) {
  state.standings = value;
}

// For Jest compatibility
if (typeof document === 'undefined') {
  global.timer = state.timer;
  global.standings = state.standings;
}
