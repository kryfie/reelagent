'use strict';
// Browser-only storyboard playback. Original files never leave the device until
// user chooses an edit and explicitly requests the final MP4.
const REEL_VARIANTS = {
  film: {name:'Filmowy', desc:'Spokojne zbliżenia, łagodne tempo i elegancka typografia.'},
  dynamic: {name:'Dynamiczny', desc:'Mocniejsze otwarcie, szybszy rytm i energetyczne kadry.'},
  story: {name:'Historia', desc:'Ujęcia opowiadają historię i kończą się zaproszeniem.'}
};
let reelVariants=[], chosenVariant=0, previewPlaying=false, previewSeconds=0,
    previewTick=0, lastPreviewStamp=0, activeSceneKey='', activePreviewAsset=null;
function escapeText(s) { return String(s || '').replaceAll('\u0000',''); }
function durationString(t){return `0:${String(Math.floor(t)).padStart(2,'0')}`}
function invalidateVariants() {
  previewPause();reelVariants=[];chosenVariant=0;previewSeconds=0;activeSceneKey='';
  $('variant-navigator').hidden=true;$('live-preview').hidden=true;
  $('render-selected').disabled=true;
  if(!$('progress').hidden || !$('video').hidden)return;
  $('placeholder').hidden=false;$('result-actions').hidden=true;
}
function previewPause(){
  previewPlaying=false;cancelAnimationFrame(previewTick);previewTick=0;
  const c=$('live-clip');c.pause();
  if($('preview-play'))$('preview-play').textContent='▶ Odtwórz';
}
function previewPlay(){
  if(!reelVariants.length)return;
  if(previewSeconds>=length-.03)previewSeconds=0;
  previewPlaying=true;lastPreviewStamp=performance.now();
  $('preview-play').textContent='Ⅱ Pauza';
  if(!$('live-clip').hidden)$('live-clip').play().catch(()=>{});
  cancelAnimationFrame(previewTick);previewTick=requestAnimationFrame(previewFrame);
}
function previewFrame(now){
  if(!previewPlaying)return;
  previewSeconds+=Math.min((now-lastPreviewStamp)/1000,.09);
  lastPreviewStamp=now;
  if(previewSeconds>=length){previewSeconds=length;previewPause();}
  renderPreviewFrame();
  if(previewPlaying)previewTick=requestAnimationFrame(previewFrame);
}
function variantAt(index){
  if(!reelVariants.length)return;
  return reelVariants[(index+reelVariants.length)%reelVariants.length];
}
function selectVariant(index,{autoplay=true}={}){
  if(!reelVariants.length)return;
  previewPause();chosenVariant=(index+reelVariants.length)%reelVariants.length;
  const variant=variantAt(chosenVariant);
  style=variant.style;directorVariant=variant.variant;currentPlan=variant.scenes;
  previewSeconds=0;activeSceneKey='';activePreviewAsset=null;
  $('live-preview').dataset.style=variant.style;
  const data=REEL_VARIANTS[variant.style];
  $('variant-name').textContent=data.name;$('variant-description').textContent=data.desc;
  document.querySelectorAll('[data-style]').forEach(el=>{
    const chosen=el.dataset.style===variant.style;
    el.classList.toggle('active',chosen);el.setAttribute('aria-pressed',String(chosen));
  });
  [...$('variant-dots').children].forEach((d,i)=>{
    d.classList.toggle('active',i===chosenVariant);d.setAttribute('aria-current',String(i===chosenVariant));
  });
  [...$('variant-tabs').children].forEach((d,i)=>{
    d.classList.toggle('active',i===chosenVariant);d.setAttribute('aria-pressed',String(i===chosenVariant));
  });
  $('placeholder').hidden=true;$('video').hidden=true;$('live-preview').hidden=false;$('result-actions').hidden=true;
  $('render-selected').disabled=false;
  directorStatus(`3 propozycje gotowe · oglądasz ${data.name.toLowerCase()}. Możesz przesuwać je palcem.`);
  redrawScenes();renderPreviewFrame();
  if(autoplay)previewPlay();
}
function previewMedia(scene) {
  const item=mediaItems[scene.index];
  const img=$('live-image'), vid=$('live-clip');
  if(item.type==='video'){
    img.hidden=true;vid.hidden=false;
    if(activePreviewAsset!==item.url){vid.src=item.url;vid.load();activePreviewAsset=item.url;}
    // The browser can loop exactly like ffmpeg's -stream_loop -1.
    if(previewPlaying && vid.paused)vid.play().catch(()=>{});
  } else {
    if(!vid.hidden){vid.pause();vid.hidden=true;}
    img.hidden=false;
    if(activePreviewAsset!==item.url){img.src=item.url;activePreviewAsset=item.url;}
  }
}
function renderPreviewFrame(){
  if(!reelVariants.length)return;
  const variant=variantAt(chosenVariant), scenes=variant.scenes;
  const total=length, outroTime=1.8;
  const t=Math.max(0,Math.min(total,previewSeconds));
  $('preview-scrub').value=String(Math.round(t/total*1000));
  $('preview-time').textContent=durationString(t);
  const inOutro=t>=total-outroTime;
  $('live-outro').hidden=!inOutro;
  $('live-outro-text').hidden=!inOutro;
  $('live-copy').hidden=inOutro;
  if(inOutro){
    const last=scenes[scenes.length-1], item=mediaItems[last.index];
    const bg=$('live-outro');
    if(item.type==='photo'){
      bg.style.backgroundImage=`linear-gradient(#1c1828a8,#1c1828a8),url("${item.url}")`;
    } else {
      // Most browsers show a video still only while the clip is active.
      // Keep actual last video as background in preview; exported still is blurred.
      bg.style.backgroundImage='linear-gradient(145deg,#32243a,#101e2a)';
    }
    $('live-outro-brand').textContent=$('brand').value||'Moja marka';
    $('live-cta').textContent=$('cta').value||'Do zobaczenia!';
    $('live-image').hidden=true;$('live-clip').pause();$('live-clip').hidden=true;
    return;
  }
  let elapsed=t,scene=scenes[0],pos=0;
  for(let i=0;i<scenes.length;i++){
    if(elapsed<scenes[i].duration || i===scenes.length-1){scene=scenes[i];pos=i;break;}
    elapsed-=scenes[i].duration;
  }
  const key=`${chosenVariant}:${pos}`;
  if(activeSceneKey!==key){activeSceneKey=key;activePreviewAsset=null;}
  previewMedia(scene);
  const item=mediaItems[scene.index];
  $('live-copy').style.opacity=String(Math.min(1,Math.max(.05,elapsed/.28)));
  const progress=Math.min(1,Math.max(0,elapsed/scene.duration));
  if(item.type==='photo'){
    const z=scene.motion==='zoom_out'?1.09-.045*progress:1.005+.08*progress;
    let x=0;
    if(scene.motion==='pan_left')x=-2.4*progress;
    if(scene.motion==='pan_right')x=2.4*progress;
    $('live-image').style.transform=`translateX(${x}%) scale(${z})`;
  }
  const brand=$('brand').value||'Moja marka';
  $('live-brand').textContent=brand;
  $('live-counter').textContent=`${String(pos+1).padStart(2,'0')} / ${String(scenes.length).padStart(2,'0')}`;
  $('live-counter').hidden=variant.style!=='story';
  $('live-title').textContent=escapeText(item.caption);
  $('live-detail').textContent=escapeText(item.detail);
}
async function prepareVariants() {
  if(mediaItems.length<2)return;
  hideError();previewPause();
  $('generate').disabled=true;$('generate').textContent='✦ Przygotowuję 3 propozycje…';
  try{
    const response=await fetch('/api/director/plans',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({length,
      auto_director:$('director-enabled').checked,
      media:mediaItems.map(i=>({type:i.type,ai_description:i.ai_description||''}))})});
    const data=await response.json();
    if(!response.ok || !Array.isArray(data.variants) || data.variants.length!==3)throw new Error(data.detail||'Nie udało się przygotować propozycji.');
    reelVariants=data.variants;
    const tabs=$('variant-tabs'),dots=$('variant-dots');tabs.replaceChildren();dots.replaceChildren();
    reelVariants.forEach((v,i)=>{
      const tab=document.createElement('button');tab.type='button';tab.className='variant-tab';
      const label=document.createElement('strong');label.textContent=REEL_VARIANTS[v.style].name;
      const meta=document.createElement('small');meta.textContent=`${v.scenes.length} ujęć · ${length} s`;
      tab.append(label,meta);tab.addEventListener('click',()=>selectVariant(i));tabs.append(tab);
      const dot=document.createElement('button');dot.type='button';dot.className='variant-dot';dot.setAttribute('aria-label',`Wariant ${i+1}: ${REEL_VARIANTS[v.style].name}`);
      dot.addEventListener('click',()=>selectVariant(i));dots.append(dot);
    });
    $('variant-navigator').hidden=false;
    $('video').pause();$('video').hidden=true;
    $('result-actions').hidden=true;
    selectVariant(0,{autoplay:false});
    document.querySelector('.preview-panel').scrollIntoView({behavior:'smooth',block:'center'});
    // Keep the animation under explicit control on mobile; no music autoplay.
  }catch(e){errorMessage(e.message||'Wystąpił błąd.');}
  finally{$('generate').disabled=mediaItems.length<2;$('generate').innerHTML='<span>✦</span> Pokaż 3 propozycje <span class="generate-arrow">↗</span>';}
}
document.addEventListener('DOMContentLoaded',()=>{
$('prev-variant').addEventListener('click',()=>selectVariant(chosenVariant-1));
$('next-variant').addEventListener('click',()=>selectVariant(chosenVariant+1));
$('preview-play').addEventListener('click',()=>previewPlaying?previewPause():previewPlay());
$('preview-scrub').addEventListener('input',e=>{
  previewPause();previewSeconds=Number(e.target.value)/1000*length;
  activeSceneKey='';renderPreviewFrame();
});
// A horizontal finger gesture changes the variant; vertical scrolling still works.
let touchStart=null;
$('live-preview').addEventListener('touchstart',e=>{
  if(e.touches.length===1)touchStart={x:e.touches[0].clientX,y:e.touches[0].clientY};
},{passive:true});
$('live-preview').addEventListener('touchend',e=>{
  if(!touchStart)return;
  const dx=e.changedTouches[0].clientX-touchStart.x,dy=e.changedTouches[0].clientY-touchStart.y;
  touchStart=null;
  if(Math.abs(dx)>40 && Math.abs(dx)>Math.abs(dy)*1.3)selectVariant(chosenVariant+(dx<0?1:-1));
},{passive:true});
$('render-selected').addEventListener('click',()=>{
  if(reelVariants.length)start();
});

});
