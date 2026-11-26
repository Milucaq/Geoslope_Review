import { updateJohnHenry } from './john_henry.js';
import { updateInstrumental } from './instrumental.js';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const host = document.getElementById('scene');
const status = document.getElementById('status');
const send = (type, fields = {}) => window.parent.postMessage({isStreamlitMessage: true, type, ...fields}, '*');
let renderer, scene, camera, controls, mesh, bounds, revision;
const render = () => { if (renderer && scene && camera) renderer.render(scene, camera); };
function resize() {
  if (!renderer) return;
  const w = host.clientWidth, h = host.clientHeight;
  if (!w || !h) return;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  render();
}
function setup() {
  renderer = new THREE.WebGLRenderer({antialias:true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  host.appendChild(renderer.domElement);
  scene = new THREE.Scene();
  scene.background = new THREE.Color('#122232');
  camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100000);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.addEventListener('change', render);
  scene.add(new THREE.HemisphereLight(0xe6efff, 0x594636, 2.0));
  const sun = new THREE.DirectionalLight(0xffe6c9, 2.4);
  sun.position.set(-1, 2, -1); scene.add(sun);
  new ResizeObserver(resize).observe(host);
  resize();
}
function resetCamera() {
  if (!bounds || !controls) return;
  const size = bounds.getSize(new THREE.Vector3());
  const center = bounds.getCenter(new THREE.Vector3());
  const span = Math.max(size.x, size.y, size.z, 1);
  const distance = span * 1.65 / Math.min(1, camera.aspect || 1);
  camera.position.copy(center).add(new THREE.Vector3(0.75, 0.65, 0.85).normalize().multiplyScalar(distance));
  camera.near = Math.max(span / 10000, 0.01); camera.far = distance * 15;
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.minDistance = span * 0.01; controls.maxDistance = distance * 5;
  controls.update(); render();
}
function update(args) {
  const p = args.payload;
  if (revision === args.revision && mesh) return;
  if (!renderer) setup();
  const {rows, cols, positions, elevation_min, elevation_max, exaggeration} = p;
  if (rows < 2 || cols < 2 || positions.length !== rows*cols*3) throw Error('Malla inválida');
  const geom = new THREE.BufferGeometry();
  geom.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  const idx = [];
  for (let r=0; r<rows-1; r++) for (let c=0; c<cols-1; c++) {
    const a=r*cols+c, b=a+1, d=a+cols+1, e=a+cols;
    idx.push(a,e,b,b,e,d);
  }
  geom.setIndex(idx); geom.computeVertexNormals(); geom.computeBoundingBox();
  const colors = new Float32Array(rows*cols*3);
  const low = new THREE.Color('#55463d'), mid = new THREE.Color('#9e8163'), high = new THREE.Color('#d2c1a1');
  const minY=geom.boundingBox.min.y, range=Math.max(geom.boundingBox.max.y-minY, 1e-9);
  const color = new THREE.Color();
  for (let i=0;i<rows*cols;i++) {
    const t=(positions[i*3+1]-minY)/range;
    if(t<0.5) color.copy(low).lerp(mid,t*2); else color.copy(mid).lerp(high,(t-0.5)*2);
    colors.set([color.r,color.g,color.b],i*3);
  }
  geom.setAttribute('color',new THREE.BufferAttribute(colors,3));
  const material = new THREE.MeshStandardMaterial({vertexColors:true, roughness:0.96, metalness:0, side:THREE.DoubleSide});
  if (mesh) { scene.remove(mesh); mesh.geometry.dispose(); mesh.material.dispose(); }
  mesh = new THREE.Mesh(geom,material); scene.add(mesh); bounds=geom.boundingBox;
  document.getElementById('lo').textContent=elevation_min.toFixed(1);
  document.getElementById('hi').textContent=elevation_max.toFixed(1);
  status.textContent=`Copernicus GLO-30 · ${rows*cols} vértices · exageración vertical ${exaggeration}×`;
  revision=args.revision; resetCamera();
}
document.getElementById('reset').addEventListener('click', resetCamera);
document.getElementById('full').addEventListener('click', async () => {
  try { if(document.fullscreenElement) await document.exitFullscreen(); else await host.requestFullscreen(); } catch { status.textContent='Pantalla completa no disponible en este navegador.'; }
});
document.addEventListener('fullscreenchange',()=>{host.style.height=document.fullscreenElement?'100vh':'540px';resize();});
window.addEventListener('message',event=>{
  if(event.source!==window.parent || event.data?.type!=='streamlit:render') return;
  try { if (event.data.args.mode === 'john_henry') updateJohnHenry(event.data.args); else if (event.data.args.mode === 'instrumental') updateInstrumental(event.data.args); else update(event.data.args); } catch (err) { console.error(err); status.textContent='No se pudo renderizar la malla. Comprueba WebGL o usa el visor Plotly.'; }
});
send('streamlit:componentReady',{apiVersion:1});
send('streamlit:setFrameHeight',{height:540});
