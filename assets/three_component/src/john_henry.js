import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const host = document.getElementById('scene');
const status = document.getElementById('status');
let renderer, scene, camera, controls, terrain, group, bounds, revision, markers=[], vertical=1, slopeKey=null, slopeOverlay=null;
const palette = {sin_marca:0x4db6e8, marca_aislada:0xf5b942, episodio_en_observacion:0xf5b942,
                 candidato_revision:0xc084fc, no_evaluable:0xa1a1aa};
function decode(s, Type) {
  const bytes = Uint8Array.from(atob(s), ch=>ch.charCodeAt(0));
  return new Type(bytes.buffer);
}
function render(){if(renderer)renderer.render(scene,camera);}
function resize(){
  const w=host.clientWidth,h=host.clientHeight;
  if(!renderer||!w||!h)return;
  renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();render();
}
function fit(){
  if(!bounds)return;
  const center=bounds.getCenter(new THREE.Vector3()), size=bounds.getSize(new THREE.Vector3());
  const span=Math.max(size.x,size.y,size.z,1);
  // Camera above the terrain, looking down at about 58 degrees.
  const back=new THREE.Vector3(.70,1.65,.75).normalize();
  const right=new THREE.Vector3().crossVectors(new THREE.Vector3(0,1,0),back).normalize();
  const up=new THREE.Vector3().crossVectors(back,right).normalize();
  const tanV=Math.tan(THREE.MathUtils.degToRad(camera.fov/2));
  const tanH=tanV*Math.max(camera.aspect,.1);
  let distance=span*.1;
  // Fit every corner of the displayed bounding box in the camera frustum.
  for(const x of [bounds.min.x,bounds.max.x])for(const y of [bounds.min.y,bounds.max.y])for(const z of [bounds.min.z,bounds.max.z]){
    const v=new THREE.Vector3(x,y,z).sub(center);
    distance=Math.max(distance,v.dot(back)+1.25*Math.max(Math.abs(v.dot(right))/tanH,Math.abs(v.dot(up))/tanV));
  }
  camera.position.copy(center).addScaledVector(back,distance);
  camera.near=span/10000;camera.far=span*100;camera.updateProjectionMatrix();
  controls.target.copy(center);controls.minDistance=span*.015;controls.maxDistance=Math.max(span*12,distance*2);controls.update();render();
}
function setup(){
  renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio||1,2));
  renderer.outputColorSpace=THREE.SRGBColorSpace;host.appendChild(renderer.domElement);
  scene=new THREE.Scene();scene.background=new THREE.Color('#122232');
  camera=new THREE.PerspectiveCamera(42,1,.1,100000);
  controls=new OrbitControls(camera,renderer.domElement);controls.addEventListener('change',render);
  scene.add(new THREE.HemisphereLight(0xffffff,0xb4a18e,1.8));
  const light=new THREE.DirectionalLight(0xffffff,1.1);light.position.set(-1,3,2);scene.add(light);
  document.querySelector('#header strong').textContent='John Henry Mine · escenario experimental';
  document.getElementById('header').style.maxWidth='58%';
  const legend=document.getElementById('legend');legend.replaceChildren();
  for(const [color,label] of [['#4db6e8','Sin marca'],['#c084fc','Candidato a revisión'],['#f5b942','Marca estadística'],['#a1a1aa','No evaluable']]){
    const el=document.createElement('div');el.style.margin='3px 0';
    const dot=document.createElement('span');dot.style.cssText=`display:inline-block;width:9px;height:9px;background:${color};border-radius:50%;margin-right:6px`;
    el.append(dot,document.createTextNode(label));legend.append(el);
  }
  const note=document.createElement('div');note.textContent='Instrumentos y estados simulados';note.style.marginTop='6px';legend.append(note);
  document.getElementById('reset').addEventListener('click',fit);new ResizeObserver(resize).observe(host);
  const ray=new THREE.Raycaster(), pointer=new THREE.Vector2();let start;
  renderer.domElement.addEventListener('pointerdown',e=>{start=[e.clientX,e.clientY];});
  renderer.domElement.addEventListener('pointerup',e=>{
    if(!start||Math.hypot(e.clientX-start[0],e.clientY-start[1])>5)return;
    const rect=renderer.domElement.getBoundingClientRect();
    pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);
    ray.setFromCamera(pointer,camera);const hit=ray.intersectObjects(markers,false)[0];
    if(hit)window.parent.postMessage({isStreamlitMessage:true,type:'streamlit:setComponentValue',value:{prism_id:hit.object.userData.id,nonce:Date.now()},dataType:'json'},'*');
  });resize();
}
// One solid color per displayed face; no interpolation between slope classes.
// This is a visualization of the existing unexaggerated vertex slope estimates.
function clearSlopeOverlay(){
  if(!slopeOverlay)return;
  if(slopeOverlay.parent)slopeOverlay.parent.remove(slopeOverlay);
  slopeOverlay.geometry.dispose();slopeOverlay.material.dispose();slopeOverlay=null;
}
function updateSlopeOverlay(mode,threshold){
  clearSlopeOverlay();
  const mat=terrain.material;
  const analytical=mode==='Pendientes';
  const visible=analytical||mode==='Ortofotografía + pendientes';
  mat.map=analytical?null:terrain.userData.texture;
  mat.color.set(analytical?0x596579:0xffffff);
  mat.vertexColors=false;mat.needsUpdate=true;
  const legend=document.getElementById('legend');
  document.getElementById('jh-slope-legend')?.remove();
  if(!visible)return;
  const g=terrain.geometry, positions=g.attributes.position.array;
  const indices=g.index.array, slopes=terrain.userData.slopes;
  const colors=[new THREE.Color(0xffde39),new THREE.Color(0xff861c),new THREE.Color(0xe83c39)];
  // Allocate only the highlighted faces. Avoid a second full terrain mesh.
  function classification(i){
    const a=slopes[indices[i]],b=slopes[indices[i+1]],c=slopes[indices[i+2]];
    if(!Number.isFinite(a)||!Number.isFinite(b)||!Number.isFinite(c))return -1;
    const mean=(a+b+c)/3;
    return mean<threshold?-1:mean<threshold+10?0:mean<threshold+20?1:2;
  }
  let count=0;
  for(let i=0;i<indices.length;i+=3)if(classification(i)>=0)count++;
  if(count){
    const p=new Float32Array(count*9),col=new Float32Array(count*9);
    let offset=0;
    for(let i=0;i<indices.length;i+=3){
      const cls=classification(i);if(cls<0)continue;
      for(let j=0;j<3;j++){
        const v=indices[i+j]*3;
        p[offset]=positions[v];p[offset+1]=positions[v+1];p[offset+2]=positions[v+2];
        colors[cls].toArray(col,offset);offset+=3;
      }
    }
    const overlayGeometry=new THREE.BufferGeometry();
    overlayGeometry.setAttribute('position',new THREE.BufferAttribute(p,3));
    overlayGeometry.setAttribute('color',new THREE.BufferAttribute(col,3));
    overlayGeometry.computeBoundingSphere();
    const overlayMaterial=new THREE.MeshBasicMaterial({vertexColors:true,side:THREE.DoubleSide,
      transparent:!analytical,opacity:analytical?1:.77,depthWrite:false,
      polygonOffset:true,polygonOffsetFactor:-1,polygonOffsetUnits:-2,toneMapped:false});
    slopeOverlay=new THREE.Mesh(overlayGeometry,overlayMaterial);
    slopeOverlay.renderOrder=1;
    // As a child, the overlay shares the terrain's vertical exaggeration.
    terrain.add(slopeOverlay);
  }
  const block=document.createElement('div');block.id='jh-slope-legend';
  block.style.cssText='border-top:1px solid #64748b;margin-top:9px;padding-top:8px;';
  const title=document.createElement('strong');title.textContent='Pendiente geométrica (°)';block.append(title);
  for(const [hex,label] of [['#ffde39',`${threshold}–<${threshold+10}°`],['#ff861c',`${threshold+10}–<${threshold+20}°`],['#e83c39',`≥ ${threshold+20}°`]]){
    const line=document.createElement('div'),dot=document.createElement('span');
    dot.style.cssText=`display:inline-block;width:10px;height:10px;margin-right:6px;background:${hex}`;
    line.append(dot,document.createTextNode(label));block.append(line);
  }
  const note=document.createElement('div');note.textContent='Inclinación, no riesgo';block.append(note);
  legend.append(block);
}
export function updateJohnHenry(args){
  if(!renderer)setup();
  const p=args.payload;
  const factor=[1,2,3,5].includes(args.vertical)?args.vertical:1;
  let needsFit=false;
  if(revision!==args.revision||!terrain){
    const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.BufferAttribute(decode(p.positions,Float32Array),3));
    g.setAttribute('uv',new THREE.BufferAttribute(decode(p.uv,Float32Array),2));
    g.setIndex(new THREE.BufferAttribute(decode(p.indices,Uint32Array),1));g.computeVertexNormals();g.computeBoundingBox();
    // North-up RGB: uv.v=1 at north; Three.js defaults to flipY for image textures.
    const tex=new THREE.TextureLoader().load('data:image/jpeg;base64,'+p.texture,render,undefined,()=>{status.textContent='No se pudo cargar la ortofotografía';});
    tex.colorSpace=THREE.SRGBColorSpace;tex.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());
    const mat=new THREE.MeshStandardMaterial({map:tex,roughness:.95,side:THREE.DoubleSide});
    if(terrain){clearSlopeOverlay();scene.remove(terrain);terrain.geometry.dispose();terrain.userData.texture.dispose();terrain.material.dispose();}
    terrain=new THREE.Mesh(g,mat);terrain.userData.texture=tex;terrain.userData.slopes=decode(p.slopes,Float32Array);scene.add(terrain);revision=args.revision;needsFit=true;slopeKey=null;
  }
  const threshold=Number(args.slope_threshold)||35;
  const mode=args.slope_mode||(args.slope_layer?'Pendientes':'Ortofotografía');
  const key=`${mode}-${threshold}`;
  if(key!==slopeKey){updateSlopeOverlay(mode,threshold);slopeKey=key;}
  if(needsFit||vertical!==factor){
    vertical=factor;terrain.scale.y=vertical;terrain.updateMatrixWorld(true);
    bounds=terrain.geometry.boundingBox.clone().applyMatrix4(terrain.matrixWorld);
    fit();
  }
  if(group){scene.remove(group);group.traverse(o=>{o.geometry?.dispose();o.material?.dispose();});}
  group=new THREE.Group();scene.add(group);markers=[];
  const size=bounds.getSize(new THREE.Vector3());const radius=Math.max(size.x,size.z)*.0035;
  for(const item of args.markers||[]){
    const color=palette[item.state]??0xa1a1aa;
    const pos=new THREE.Vector3().fromArray(item.position), base=new THREE.Vector3().fromArray(item.base);
    pos.y*=vertical;base.y*=vertical;
    const endpoint=new THREE.Vector3().fromArray(item.vector_endpoint||item.position);
    endpoint.y*=vertical;
    // A display glyph above the exact simulated coordinate, with a stem to its true location.
    const tip=pos.clone().add(new THREE.Vector3(0,radius*2.5,0));
    const marker=new THREE.Mesh(new THREE.SphereGeometry(radius,16,12),new THREE.MeshStandardMaterial({color,emissive:color,emissiveIntensity:.5}));
    marker.position.copy(tip);marker.userData.id=item.id;group.add(marker);markers.push(marker);
    const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([pos,tip]),new THREE.LineBasicMaterial({color}));group.add(line);
    if(base.distanceTo(endpoint)>0.000001){
      // Arrow is illustrative; no selectable marker is created at its endpoint.
      const vector=endpoint.clone().sub(base);
      const arrow=new THREE.ArrowHelper(vector.clone().normalize(),base,vector.length(),color,Math.min(vector.length()*.25,radius),Math.min(vector.length()*.15,radius*.6));group.add(arrow);
    }
  }
  status.textContent=`${p.vertices.toLocaleString('es')} vértices · ${p.triangles.toLocaleString('es')} triángulos · ${markers.length} prismas simulados · relieve ${vertical}× · flechas ${args.amplify||1}× · prismas sin amplificar`;
  render();
}
