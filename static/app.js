'use strict';
const $ = name => document.getElementById(name);
let mediaItems = [], style = 'film', length = 15, jobId = null, pollTimer = null, shareFile = null;
const MAX_FILES = 8;
const defaults = [
  ['Masz ochotę na coś wyjątkowego?', 'Zobacz, co dla Ciebie mamy'],
  ['Spójrz na te detale', 'Prawdziwy smak i dobra atmosfera'],
  ['To dopiero początek', 'Małe przyjemności mają znaczenie'],
  ['Poczuj ten klimat', 'Wpadnij do nas przy okazji'],
  ['Warto się zatrzymać', 'Na moment tylko dla siebie'],
  ['Zobacz więcej', 'A może dziś?'],
  ['Chwila dla Ciebie', 'U nas zawsze coś dobrego'],
  ['Co wybierasz?', 'Daj znać w komentarzu']
];

function errorMessage(text) { $('error').textContent=text; $('error').hidden=false; }
function hideError() { $('error').hidden=true; $('error').textContent=''; }
function stopPolling() { if(pollTimer) clearTimeout(pollTimer); pollTimer=null; }

function redrawScenes() {
  const list=$('scene-list'); list.replaceChildren();
  mediaItems.forEach((item,i)=>{
    const el=document.createElement('div');el.className='scene-card';
    const thumb=document.createElement('div');thumb.className='scene-thumb';
    let preview;
    if(item.type==='video') {
      preview=document.createElement('video');preview.src=item.url;preview.muted=true;preview.playsInline=true;preview.preload='metadata';
    } else {
      preview=document.createElement('img');preview.src=item.url;preview.alt=`Materiał ${i+1}`;
    }
    const number=document.createElement('span');number.className='scene-index';number.textContent=String(i+1).padStart(2,'0');
    thumb.append(preview,number);
    if(item.type==='video') {const tag=document.createElement('span');tag.className='video-tag';tag.textContent='▶ FILM';thumb.appendChild(tag)}
    const body=document.createElement('div');body.className='scene-body';
    const top=document.createElement('div');top.className='scene-row';
    const strong=document.createElement('strong');strong.textContent=`Scena ${i+1}`;
    const ctrls=document.createElement('div');ctrls.className='scene-controls';
    [
      ['↑','Przesuń scenę w górę',()=>moveScene(i,-1),i===0],
      ['↓','Przesuń scenę w dół',()=>moveScene(i,1),i===mediaItems.length-1],
      ['×','Usuń scenę',()=>removeScene(i),false]
    ].forEach(([icon,label,fn,disabled])=>{
      const button=document.createElement('button');button.type='button';button.textContent=icon;button.title=label;button.setAttribute('aria-label',label);button.disabled=disabled;button.addEventListener('click',fn);ctrls.append(button);
    });top.append(strong,ctrls);
    const label1=document.createElement('label');label1.textContent='Główny napis';
    const inp1=document.createElement('input');inp1.type='text';inp1.maxLength=72;inp1.placeholder='Np. Świeże churros!';inp1.value=item.caption;
    inp1.setAttribute('aria-label',`Napis główny sceny ${i+1}`);inp1.addEventListener('input',()=>{item.caption=inp1.value});
    const label2=document.createElement('label');label2.textContent='Mniejszy napis (opcjonalny)';
    const inp2=document.createElement('input');inp2.type='text';inp2.maxLength=100;inp2.placeholder='Np. Dziś do kawy';inp2.value=item.detail;
    inp2.setAttribute('aria-label',`Napis dodatkowy sceny ${i+1}`);inp2.addEventListener('input',()=>{item.detail=inp2.value});
    body.append(top,label1,inp1,label2,inp2);el.append(thumb,body);list.appendChild(el);
  });
  $('media-counter').textContent=mediaItems.length?`${mediaItems.length} / ${MAX_FILES} materiałów · edytuj napisy pod każdą sceną`:'Nie wybrano materiałów';
  $('generate').disabled=mediaItems.length<2 || !!pollTimer;
}
function moveScene(i,step) { const j=i+step;if(j<0||j>=mediaItems.length)return;[mediaItems[i],mediaItems[j]]=[mediaItems[j],mediaItems[i]];redrawScenes() }
function removeScene(i) { URL.revokeObjectURL(mediaItems[i].url);mediaItems.splice(i,1);redrawScenes() }
function addMedia(files) {
  const valid=[...files].filter(file=>file.type.startsWith('image/')||file.type.startsWith('video/')||/\.(heic|heif|jpg|jpeg|png|webp|mp4|mov|m4v|webm)$/i.test(file.name));
  const slots=MAX_FILES-mediaItems.length;
  if(valid.length>slots)errorMessage('Maksymalnie 8 zdjęć i filmów łącznie.');
  valid.slice(0,slots).forEach(file=>{
    const type=file.type.startsWith('video/')||/\.(mp4|mov|m4v|webm)$/i.test(file.name)?'video':'photo';
    if(type==='video' && file.size>55*1024*1024){errorMessage(`Film ${file.name} przekracza 55 MB. Skróć go przed dodaniem.`);return}
    if(type==='photo' && file.size>12*1024*1024){errorMessage(`Zdjęcie ${file.name} przekracza 12 MB. Wybierz mniejszy plik.`);return}
    const i=mediaItems.length;
    mediaItems.push({file,url:URL.createObjectURL(file),type,caption:defaults[i%defaults.length][0],detail:defaults[i%defaults.length][1]});
  });
  redrawScenes();
}
$('media-input').addEventListener('change',event=>{addMedia(event.target.files);event.target.value=''});
const drop=$('dropzone');
drop.addEventListener('dragover',event=>{event.preventDefault();drop.classList.add('dragover')});
drop.addEventListener('dragleave',()=>drop.classList.remove('dragover'));
drop.addEventListener('drop',event=>{event.preventDefault();drop.classList.remove('dragover');addMedia(event.dataTransfer.files)});
drop.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();$('media-input').click()}});
document.querySelectorAll('[data-style]').forEach(btn=>btn.addEventListener('click',()=>{
  style=btn.dataset.style;document.querySelectorAll('[data-style]').forEach(b=>{const active=b===btn;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active))});
}));
document.querySelectorAll('[data-length]').forEach(btn=>btn.addEventListener('click',()=>{
  length=Number(btn.dataset.length);document.querySelectorAll('[data-length]').forEach(b=>b.classList.toggle('active',b===btn));
}));
$('toggle-guide').addEventListener('change',()=>{$('guide').hidden=!$('toggle-guide').checked});

async function shrinkImage(file) {
  if(!file.type.startsWith('image/') && !/\.(heic|heif)$/i.test(file.name))return file;
  const blobUrl=URL.createObjectURL(file);
  try {
    const img=await new Promise((resolve,reject)=>{
      const e=new Image();e.onload=()=>resolve(e);e.onerror=()=>reject(Error('Nie udało się odczytać zdjęcia.'));e.src=blobUrl;
    });
    const f=Math.min(1,1600/Math.max(img.naturalHeight,img.naturalWidth));
    const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.floor(img.naturalWidth*f));canvas.height=Math.max(1,Math.floor(img.naturalHeight*f));
    const ctx=canvas.getContext('2d');if(!ctx)return file;
    ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(img,0,0,canvas.width,canvas.height);
    const out=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.84));
    return out?new File([out],file.name.replace(/\.[^.]+$/,'')+'.jpg',{type:'image/jpeg'}):file;
  }catch{return file}finally{URL.revokeObjectURL(blobUrl)}
}
function progress(label,value){$('progress').hidden=false;$('placeholder').hidden=true;$('video').hidden=true;$('progress-label').textContent=label;$('progress-percent').textContent=`${value}%`;$('progress-fill').style.width=value+'%'}
function hideProgress(){ $('progress').hidden=true; }
function setBusy(on){$('generate').disabled=on||mediaItems.length<2}
async function start() {
  if(mediaItems.length<2)return;
  hideError();stopPolling();setBusy(true);$('result-actions').hidden=true;shareFile=null;
  progress('Przygotowuję materiały…',2);
  try{
    const fd=new FormData();
    for(let i=0;i<mediaItems.length;i++){
      const item=mediaItems[i];const file=item.type==='photo'?await shrinkImage(item.file):item.file;
      fd.append('media',file,file.name);progress(`Pakuję ujęcie ${i+1} z ${mediaItems.length}…`,Math.min(8,3+i));
    }
    fd.append('scene_text',JSON.stringify(mediaItems.map(x=>({caption:x.caption,detail:x.detail}))));
    fd.append('brand',$('brand').value);fd.append('cta',$('cta').value);fd.append('style',style);fd.append('length',String(length));fd.append('pin',$('pin').value);
    if($('logo-input').files[0]){const f=await shrinkImage($('logo-input').files[0]);fd.append('logo',f,f.name)}
    if($('music-input').files[0])fd.append('audio',$('music-input').files[0]);
    progress('Wysyłam pliki na serwer…',10);
    const response=await fetch('/api/jobs',{method:'POST',body:fd});
    const payload=await response.json();
    if(!response.ok)throw new Error(payload.detail||'Błąd przesyłania plików.');
    jobId=payload.id;pollTimer=setTimeout(checkJob,1200);
    document.querySelector('.preview-panel').scrollIntoView({behavior:'smooth',block:'center'});
  }catch(err){hideProgress();$('placeholder').hidden=false;errorMessage(err.message||'Wystąpił błąd.');setBusy(false)}
}
$('generate').addEventListener('click',start);
async function checkJob(){
  pollTimer=null;
  try{
    const response=await fetch('/api/jobs/'+encodeURIComponent(jobId));
    if(!response.ok)throw new Error('Zadanie wygasło lub serwer został zrestartowany.');
    const status=await response.json();
    if(status.state==='error')throw new Error(status.message||'Nie udało się przygotować filmu.');
    if(status.state==='ready'){await ready(status);return}
    progress(status.message||'Montuję…',status.progress||10);
    pollTimer=setTimeout(checkJob,1400);
  }catch(err){hideProgress();$('placeholder').hidden=false;errorMessage(err.message||'Błąd zadania.');setBusy(false)}
}
async function ready(data){
  hideProgress();$('placeholder').hidden=true;
  const url='/api/jobs/'+encodeURIComponent(jobId)+'/video';
  const video=$('video');video.src=url;video.hidden=false;video.load();
  $('result-actions').hidden=false;
  $('download').href=url+'?download=1';
  $('result-info').textContent=`Gotowa rolka · ${data.duration||'—'} s · ${((data.bytes||0)/1024/1024).toFixed(1)} MB`;
  $('share').disabled=true;$('share').textContent='Przygotowuję udostępnianie…';setBusy(false);
  try{
    const response=await fetch(url);if(!response.ok)throw Error('Brak pliku.');
    const blob=await response.blob();shareFile=new File([blob],'reelagent-rolka.mp4',{type:'video/mp4'});
    $('share').disabled=false;$('share').textContent='↗ Udostępnij / Zapisz w Zdjęciach';
  }catch{$('share').textContent='↓ Pobierz MP4 przyciskiem poniżej'}
}
$('share').addEventListener('click',async()=>{
  if(!shareFile)return;
  if(navigator.canShare && navigator.canShare({files:[shareFile]}) && navigator.share) {
    try{await navigator.share({files:[shareFile],title:'Moja rolka'});return}catch(err){if(err.name==='AbortError')return}
  }
  errorMessage('Udostępnianie plików nie jest dostępne na tym urządzeniu. Pobierz MP4 i zapisz go w Zdjęciach.');
});
$('reset').addEventListener('click',()=>{
  stopPolling();jobId=null;shareFile=null;const v=$('video');v.pause();v.removeAttribute('src');v.load();v.hidden=true;
  $('placeholder').hidden=false;$('result-actions').hidden=true;hideProgress();hideError();redrawScenes();
  window.scrollTo({top:0,behavior:'smooth'});
});
redrawScenes();
