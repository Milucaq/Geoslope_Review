import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

let renderer, scene, camera, controls, group, bounds, revision, labels = [], markers = [];
let focusPoint = null;
const host = document.getElementById('scene');
const status = document.getElementById('status');
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const palette = {sin_marca:0x4db6e8, marca_aislada:0xf5b942,
  episodio_en_observacion:0xf5b942, candidato_revision:0xc084fc, no_evaluable:0xa1a1aa};
const send = (type, fields={}) => window.parent.postMessage({isStreamlitMessage:true,type,...fields}, '*');

function render() {
  if (!renderer) return;
  renderer.render(scene,camera);
  camera.updateMatrixWorld();
  const w=host.clientWidth,h=host.clientHeight;
  for(const item of labels) {
    const v=item.position.clone().project(camera);
    item.el.hidden= v.z < -1 || v.z > 1 || Math.abs(v.x)>1 || Math.abs(v.y)>1;
    item.el.style.left=`${(v.x+1)*w/2}px`;
    item.el.style.top=`${(1-v.y)*h/2-12}px`;
  }
}
function resize() {
  const w=host.clientWidth,h=host.clientHeight;
  if(!renderer || !w || !h) return;
  renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();render();
}
function fit() {
  if(!bounds || !controls) return;
  const size=bounds.getSize(new THREE.Vector3());
  const center=focusPoint || bounds.getCenter(new THREE.Vector3());
  const span=Math.max(size.x,size.y,size.z,1);
  const d=span*(focusPoint ? 0.38:1.75)/Math.min(camera.aspect||1,1);
  camera.position.copy(center).add(new THREE.Vector3(0.8,0.65,1).normalize().multiplyScalar(d));
  camera.near=Math.max(span/20000,0.0001);camera.far=span*100;
  camera.updateProjectionMatrix();controls.target.copy(center);
  controls.minDistance=span*0.005;controls.maxDistance=span*20;controls.update();render();
}
function setup() {
  renderer=new THREE.WebGLRenderer({antialias:true});
  renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  host.appendChild(renderer.domElement);
  scene=new THREE.Scene();scene.background=new THREE.Color('#122232');
  camera=new THREE.PerspectiveCamera(42,1,0.001,100000);
  controls=new OrbitControls(camera,renderer.domElement);controls.addEventListener('change',render);
  scene.add(new THREE.HemisphereLight(0xe4efff,0x534638,2));
  const sun=new THREE.DirectionalLight(0xffeed6,2);sun.position.set(-1,3,2);scene.add(sun);
  document.querySelector('#header strong').textContent='Ubicaciones instrumentales · datos originales';
  document.getElementById('header').style.maxWidth='60%';
  const legend=document.getElementById('legend');legend.replaceChildren();
  for(const [color,name] of [['#4db6e8','Sin marca'],['#c084fc','Candidato a revisión'],['#f5b942','Marca estadística'],['#a1a1aa','No evaluable']]) {
    const line=document.createElement('div');line.style.margin='3px 0';
    const dot=document.createElement('span');dot.style.cssText=`display:inline-block;width:9px;height:9px;border-radius:50%;background:${color};margin-right:6px`;
    line.append(dot,document.createTextNode(name));legend.append(line);
  }
  document.getElementById('reset').addEventListener('click',()=>{focusPoint=null;fit();});
  new ResizeObserver(resize).observe(host);
  let down;
  renderer.domElement.addEventListener('pointerdown',e=>{down=[e.clientX,e.clientY];});
  renderer.domElement.addEventListener('pointerup',e=>{
    if(!down || Math.hypot(e.clientX-down[0],e.clientY-down[1])>5) return;
    const rect=renderer.domElement.getBoundingClientRect();
    pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);
    raycaster.setFromCamera(pointer,camera);
    const hit=raycaster.intersectObjects(markers,false)[0];
    if(hit) send('streamlit:setComponentValue',{value:{prism_id:hit.object.userData.id,camera:null,nonce:Date.now()},dataType:'json'});
  });
  resize();
}
export function updateInstrumental(args) {
  if(!renderer) setup();
  const p=args.payload;
  if(group) {
    scene.remove(group);group.traverse(o=>{o.geometry?.dispose();o.material?.dispose();});
  }
  labels.forEach(x=>x.el.remove());labels=[];markers=[];
  group=new THREE.Group();scene.add(group);
  const geom=new THREE.BufferGeometry();
  geom.setAttribute('position',new THREE.Float32BufferAttribute(p.positions,3));
  geom.computeBoundingBox();bounds=geom.boundingBox.clone();
  const size=bounds.getSize(new THREE.Vector3());const span=Math.max(size.x,size.y,size.z,1);
  if(p.indices.length) {
    geom.setIndex(p.indices);geom.computeVertexNormals();
    const mat=new THREE.MeshStandardMaterial({color:0xa99a7e,roughness:0.95,side:THREE.DoubleSide,transparent:true,opacity:0.77,depthWrite:false});
    const mesh=new THREE.Mesh(geom,mat);mesh.renderOrder=0;group.add(mesh);
    const wire=new THREE.LineSegments(new THREE.WireframeGeometry(geom),new THREE.LineBasicMaterial({color:0x665f54,transparent:true,opacity:0.25}));
    group.add(wire);
  } else {geom.dispose();}
  for(const item of p.markers) {
    const chosen=item.id===p.selected;
    const radius=span*(chosen?0.012:0.008);
    const ball=new THREE.Mesh(new THREE.SphereGeometry(radius,16,12),new THREE.MeshStandardMaterial({color:palette[item.state]??0x94a3b8,emissive:palette[item.state]??0x94a3b8,emissiveIntensity:0.35}));
    ball.position.fromArray(item.position);ball.userData.id=item.id;ball.renderOrder=2;group.add(ball);markers.push(ball);
    if(chosen) {
      const ring=new THREE.Mesh(new THREE.SphereGeometry(radius*1.45,12,10),new THREE.MeshBasicMaterial({color:0xffffff,wireframe:true}));ring.position.copy(ball.position);group.add(ring);
    }
    if(p.labels || chosen) {
      const el=document.createElement('span');el.textContent=item.id;
      el.style.cssText='position:absolute;pointer-events:none;z-index:2;transform:translate(-50%,-100%);font:11px system-ui;color:white;background:#122232dd;padding:2px 4px;border-radius:3px;white-space:nowrap';
      host.append(el);labels.push({el,position:ball.position.clone()});
    }
  }
  focusPoint=p.focus ? markers.find(x=>x.userData.id===p.selected)?.position.clone()||null : null;
  status.textContent=`${p.markers.length}/${p.reference_count} prismas · ${p.indices.length/3} triángulos · ${p.indices.length?'TIN experimental':'sin superficie'} · unidades pendientes`;
  if(revision!==args.revision) {revision=args.revision;fit();} else render();
}
