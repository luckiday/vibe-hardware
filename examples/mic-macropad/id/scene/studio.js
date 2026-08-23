// studio.js — environment, light rig and backdrop. Kept apart from the device so
// the device can be regenerated without touching the lighting, which is the same
// discipline studio.blend enforces on the Blender side.
import * as THREE from 'three';
import { RoomEnvironment } from './vendor/RoomEnvironment.js';

export function buildStudio(scene, renderer) {
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.background = new THREE.Color('#EDEBE6');

  const key = new THREE.DirectionalLight(0xffffff, 2.1);
  key.position.set(-120, 190, 150);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.camera.near = 40; key.shadow.camera.far = 520;
  const s = 130;
  Object.assign(key.shadow.camera, { left: -s, right: s, top: s, bottom: -s });
  key.shadow.bias = -0.0012; key.shadow.normalBias = 0.4;
  scene.add(key);

  const fill = new THREE.DirectionalLight(0xffffff, 0.5); fill.position.set(150, 80, 90); scene.add(fill);
  const rim = new THREE.DirectionalLight(0xffffff, 0.35); rim.position.set(0, 40, -190); scene.add(rim);
  scene.add(new THREE.HemisphereLight(0xffffff, 0xb8b4ac, 0.55));

  const floor = new THREE.Mesh(new THREE.PlaneGeometry(1400, 1400),
    new THREE.MeshStandardMaterial({ color: '#E7E4DE', roughness: 0.95 }));
  floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; floor.name = 'backdrop';
  scene.add(floor);
  return { key, floor };
}
