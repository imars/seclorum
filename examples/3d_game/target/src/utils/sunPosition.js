// src/utils/sunPosition.js
import { getSetting, setSetting } from '../settings.js';
import * as THREE from 'three';

export function getSunPosition(time, latitude, longitude) {
  const timeOfDay = getSetting('skybox.sun.timeOfDay');
  const adjustedTime = timeOfDay !== null ? new Date(time.getFullYear(), time.getMonth(), time.getDate(), timeOfDay) : time;

  const dayOfYear = Math.floor((adjustedTime - new Date(adjustedTime.getFullYear(), 0, 1)) / (1000 * 60 * 60 * 24));
  const hour = adjustedTime.getHours() + adjustedTime.getMinutes() / 60 + adjustedTime.getSeconds() / 3600;

  // Solar time adjustment
  const solarTime = hour + longitude / 15;

  // Solar declination (in radians)
  const declination = 23.45 * Math.sin((2 * Math.PI * (dayOfYear - 81)) / 365) * (Math.PI / 180);

  // Hour angle (in radians)
  const hourAngle = ((solarTime - 12) * 15) * (Math.PI / 180);

  // Altitude (angle above horizon)
  const sinAltitude = (
    Math.sin(latitude * Math.PI / 180) * Math.sin(declination) +
    Math.cos(latitude * Math.PI / 180) * Math.cos(declination) * Math.cos(hourAngle)
  );
  const altitude = Math.asin(Math.max(-1, Math.min(1, sinAltitude)));

  // Azimuth (angle from north, clockwise)
  let cosAzimuth = (
    (Math.sin(declination) - Math.sin(latitude * Math.PI / 180) * Math.sin(altitude)) /
    (Math.cos(latitude * Math.PI / 180) * Math.cos(altitude))
  );
  cosAzimuth = Math.max(-1, Math.min(1, cosAzimuth));
  let azimuth = Math.acos(cosAzimuth);
  if (hourAngle > 0) azimuth = 2 * Math.PI - azimuth;

  // Convert to Cartesian coordinates
  // Three.js: +x = east, +z = north, +y = up
  const x = Math.cos(altitude) * Math.sin(azimuth);
  const y = Math.sin(altitude);
  const z = Math.cos(altitude) * Math.cos(azimuth);

  const direction = new THREE.Vector3(x, y, z);
  if (isNaN(x) || isNaN(y) || isNaN(z)) {
    console.error('Invalid sun direction:', { x, y, z, altitude: altitude * 180 / Math.PI });
    return new THREE.Vector3(0, 0, -1).normalize(); // North, temporary fallback
  }

  console.log('Sun position calculated:', {
    time: adjustedTime.toISOString(),
    latitude,
    longitude,
    hour,
    solarTime,
    declination: declination * 180 / Math.PI,
    hourAngle: hourAngle * 180 / Math.PI,
    altitude: altitude * 180 / Math.PI,
    azimuth: azimuth * 180 / Math.PI,
    direction: { x, y, z },
  });

  return direction.normalize();
}
