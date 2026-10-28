'use strict';
const $ = name => document.getElementById(name);
let mediaItems = [], style = 'film', length = 15, jobId = null, pollTimer = null, shareFile = null, directorVariant=0, currentPlan=null, adding=false;
const MAX_FILES=8, MAX_VIDEO_MB=15, MAX_IMAGE_MB=8, MAX_TOTAL_MB=60, MAX_VIDEO_S=8;
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
    const strong=document.createElement('strong');const planned=currentPlan?.findIndex(x=>x.index===i);strong.textContent=`Scena ${i+1}`+(planned>=0 ? ` · montaż: ${planned+1}` : '');
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
    inp1.setAttribute('aria-label',`Napis główny sceny ${i+1}`);inp1.addEventListener('input',()=>{item.caption=inp1.value;if(reelVariants.length)renderPreviewFrame()});
    const label2=document.createElement('label');label2.textContent='Mniejszy napis (opcjonalny)';
    const inp2=document.createElement('input');inp2.type='text';inp2.maxLength=100;inp2.placeholder='Np. Dziś do kawy';inp2.value=item.detail;
    inp2.setAttribute('aria-label',`Napis dodatkowy sceny ${i+1}`);inp2.addEventListener('input',()=>{item.detail=inp2.value;if(reelVariants.length)renderPreviewFrame()});
    body.append(top,label1,inp1,label2,inp2);if(item.ai_description){const ai=document.createElement('span');ai.className='ai-label';ai.textContent='AI: '+item.ai_description.slice(0,90);body.append(ai)}el.append(thumb,body);list.appendChild(el);
  });
  $('media-counter').textContent=mediaItems.length?`${mediaItems.length} / ${MAX_FILES} materiałów · edytuj napisy pod każdą sceną`:'Nie wybrano materiałów';
  $('generate').disabled=mediaItems.length<2 || !!pollTimer;
}
function moveScene(i,step) { const j=i+step;if(j<0||j>=mediaItems.length)return;[mediaItems[i],mediaItems[j]]=[mediaItems[j],mediaItems[i]];invalidateVariants();redrawScenes() }
function removeScene(i) { URL.revokeObjectURL(mediaItems[i].url);mediaItems.splice(i,1);currentPlan=null;invalidateVariants();redrawScenes() }
function videoDuration(itemUrl) {
  return new Promise((resolve,reject)=>{
    const el=document.createElement('video');el.preload='metadata';el.muted=true;el.playsInline=true;
    const clear=()=>{clearTimeout(timer);el.removeAttribute('src');el.load()};
    const timer=setTimeout(()=>{clear();resolve(null)},6500);
    el.onloadedmetadata=()=>{const d=el.duration;clear();resolve(Number.isFinite(d)?d:null)};
    el.onerror=()=>{clear();resolve(null)};
    el.src=itemUrl;
  });
}
async function addMedia(files) {
  if(adding)return;
  adding=true;const failed=[];
  try {
    const valid=[...files].filter(file=>file.type.startsWith('image/')||file.type.startsWith('video/')||/\.(heic|heif|jpg|jpeg|png|webp|mp4|mov|m4v|webm)$/i.test(file.name));
    const slots=MAX_FILES-mediaItems.length;
    if(valid.length>slots)failed.push('Można dodać maksymalnie 8 materiałów.');
    for(const file of valid.slice(0,slots)){
      const type=file.type.startsWith('video/')||/\.(mp4|mov|m4v|webm)$/i.test(file.name)?'video':'photo';
      const maxMB=type==='video'?MAX_VIDEO_MB:MAX_IMAGE_MB;
      if(file.size>maxMB*1024*1024){failed.push(`${file.name}: maksymalnie ${maxMB} MB.`);continue}
      const sum=mediaItems.reduce((acc,m)=>acc+m.file.size,0)+file.size;
      if(sum>MAX_TOTAL_MB*1024*1024){failed.push('Łącznie nie można przekroczyć 60 MB materiałów.');break}
      const url=URL.createObjectURL(file);
      if(type==='video'){
        $('record-status').textContent='Sprawdzam długość nagrania…';
        const dur=await videoDuration(url);
        if(dur!==null && (dur<.5 || dur>MAX_VIDEO_S+.05)){
          URL.revokeObjectURL(url);failed.push(`${file.name}: ${dur.toFixed(1)} s. Dopuszczamy tylko 0,5–8 s.`);continue;
        }
      }
      const i=mediaItems.length;
      mediaItems.push({file,url,type,caption:defaults[i%defaults.length][0],detail:defaults[i%defaults.length][1],ai_description:''});
    }
    currentPlan=null;invalidateVariants();
    redrawScenes();
    if(mediaItems.length>=2)directorStatus('Materiały gotowe. Kliknij „Pokaż 3 propozycje”.');
    if(failed.length)errorMessage(failed.join(' '));
    else hideError();
  } finally {adding=false;$('record-status').textContent='';}
}
$('media-input').addEventListener('change',async event=>{const files=[...event.target.files];event.target.value='';await addMedia(files)});
const drop=$('dropzone');
drop.addEventListener('dragover',event=>{event.preventDefault();drop.classList.add('dragover')});
drop.addEventListener('dragleave',()=>drop.classList.remove('dragover'));
drop.addEventListener('drop',event=>{event.preventDefault();drop.classList.remove('dragover');addMedia(event.dataTransfer.files)});
drop.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();$('media-input').click()}});
document.querySelectorAll('[data-style]').forEach(btn=>btn.addEventListener('click',()=>{
  if(reelVariants.length){const i=reelVariants.findIndex(v=>v.style===btn.dataset.style);selectVariant(i);}
  else {style=btn.dataset.style;document.querySelectorAll('[data-style]').forEach(b=>{const active=b===btn;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active))});}
}));
document.querySelectorAll('[data-length]').forEach(btn=>btn.addEventListener('click',()=>{
  length=Number(btn.dataset.length);currentPlan=null;invalidateVariants();document.querySelectorAll('[data-length]').forEach(b=>b.classList.toggle('active',b===btn));
}));
$('toggle-guide').addEventListener('change',()=>{$('guide').hidden=!$('toggle-guide').checked});
$('brand').addEventListener('input',()=>{if(reelVariants.length)renderPreviewFrame()});
$('cta').addEventListener('input',()=>{if(reelVariants.length)renderPreviewFrame()});

// Style memory is stored ONLY on the current device; never on public GitHub.
$('save-brand').addEventListener('click',()=>{
  try {
    localStorage.setItem('reelagent-brand-2-3',JSON.stringify({
      brand:$('brand').value,cta:$('cta').value,style,length,auto_director:$('director-enabled').checked,variant:directorVariant
    }));
    directorStatus('Zapisałem styl marki na tym urządzeniu. Kolejne rolki zaczną od tych ustawień.');
  } catch {directorStatus('Przeglądarka zablokowała pamięć lokalną. Nadal możesz wygenerować rolkę.');}
});
try {
  const saved=JSON.parse(localStorage.getItem('reelagent-brand-2-3')||'null');
  if(saved && typeof saved==='object') {
    if(typeof saved.brand==='string')$('brand').value=saved.brand.slice(0,50);
    if(typeof saved.cta==='string')$('cta').value=saved.cta.slice(0,78);
    if(['film','dynamic','story'].includes(saved.style)) style=saved.style;
    if([10,15,20].includes(saved.length)) length=saved.length;
    $('director-enabled').checked=saved.auto_director!==false;
    if(Number.isInteger(saved.variant) && saved.variant>=0 && saved.variant<=12)directorVariant=saved.variant;
    document.querySelectorAll('[data-style]').forEach(b=>{const active=b.dataset.style===style;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active))});
    document.querySelectorAll('[data-length]').forEach(b=>b.classList.toggle('active',Number(b.dataset.length)===length));
    $('director-status').textContent='Wczytano zapisany styl marki z tego urządzenia.';
  }
} catch {}

// Director's scene plans are now created together for three styles.
function directorStatus(message){$('director-status').textContent=message}
function previewPlan(){invalidateVariants();directorStatus('Zaktualizowano materiały. Kliknij „Pokaż 3 propozycje”.');}
$('director-enabled').addEventListener('change',previewPlan);
$('director-ai').addEventListener('click',async()=>{
  if(mediaItems.length<2){errorMessage('Dodaj najpierw zdjęcia lub filmy.');return}
  const b=$('director-ai');b.disabled=true;hideError();
  try {
    if(!navigator.gpu)throw new Error('Brak WebGPU na tym urządzeniu. Użyj standardowego Reżysera; to nie blokuje generowania.');
    const {describeMedia}=await import('/static/director-ai.js?v=2.4');
    const desc=await describeMedia(mediaItems.map(m=>m.file),directorStatus);
    desc.forEach((t,i)=>{mediaItems[i].ai_description=t});
    const cnt=desc.filter(Boolean).length;
    directorStatus(`Florence-2 opisał ${cnt}/${desc.length} ujęć. Zastosuję te informacje do wyboru montażu.`);
    previewPlan();
  } catch(err){errorMessage(`Opcjonalne AI niedostępne: ${err.message||'Błąd modelu'}. Film możesz wygenerować normalnie.`)}
  finally{b.disabled=false}
});

// Camera recording is explicitly limited to five seconds.
let cameraStream=null, cameraRecorder=null, cameraChunks=[], recordingTimer=null;
function closeCamera(){
  if(cameraRecorder && cameraRecorder.state==='recording')cameraRecorder.stop();
  if(recordingTimer)clearTimeout(recordingTimer);
  recordingTimer=null;
  cameraStream?.getTracks().forEach(t=>t.stop());cameraStream=null;
  $('camera-preview').srcObject=null;$('camera-panel').hidden=true;
  $('record-start').disabled=false;
}
$('record-close').addEventListener('click',closeCamera);
$('record-start').addEventListener('click',async()=>{
  hideError();
  if(mediaItems.length>=MAX_FILES){errorMessage('Masz już 8 materiałów.');return}
  if(!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder==='undefined'){
    $('record-status').textContent='Otwieram aparat telefonu. Nagranie przytnij do maks. 8 sekund.';
    $('camera-fallback').click();return;
  }
  try {
    cameraStream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:720},height:{ideal:1280}},audio:false});
    $('camera-preview').srcObject=cameraStream;$('camera-panel').hidden=false;
    $('record-start').disabled=true;
    $('record-countdown').textContent='Gotowe do nagrywania 5 sekund';
  } catch {
    $('record-status').textContent='Nie można otworzyć kamery w przeglądarce. Uruchamiam aparat systemowy.';
    $('camera-fallback').click();
  }
});
$('camera-fallback').addEventListener('change',async e=>{const files=[...e.target.files];e.target.value='';await addMedia(files)});
$('record-go').addEventListener('click',()=>{
  if(!cameraStream)return;
  const mime=['video/mp4','video/webm;codecs=vp8','video/webm'].find(t=>MediaRecorder.isTypeSupported(t));
  if(!mime){errorMessage('Ta przeglądarka nie obsługuje nagrywania. Użyj systemowej kamery.');closeCamera();return}
  cameraChunks=[];
  cameraRecorder=new MediaRecorder(cameraStream,{mimeType:mime,videoBitsPerSecond:1_800_000});
  cameraRecorder.ondataavailable=e=>{if(e.data.size)cameraChunks.push(e.data)};
  cameraRecorder.onerror=()=>errorMessage('Nie udało się nagrać filmu.');
  cameraRecorder.onstop=async()=>{
    const bytes=new Blob(cameraChunks,{type:mime});
    closeCamera();
    if(bytes.size>MAX_VIDEO_MB*1024*1024){errorMessage('Nagranie przekroczyło 15 MB. Spróbuj ponownie.');return}
    const ext=mime.startsWith('video/mp4')?'mp4':'webm';
    await addMedia([new File([bytes],`ujecie-${Date.now()}.${ext}`,{type:mime})]);
  };
  cameraRecorder.start(250);
  $('record-go').disabled=true;
  let seconds=5;
  $('record-countdown').textContent=`Nagrywam… ${seconds} s`;
  const ticker=setInterval(()=>{$('record-countdown').textContent=`Nagrywam… ${--seconds} s`;if(seconds<=0)clearInterval(ticker)},1000);
  recordingTimer=setTimeout(()=>{
    clearInterval(ticker);
    if(cameraRecorder?.state==='recording')cameraRecorder.stop();
    $('record-go').disabled=false;
  },5000);
});

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
function progress(label,value){$('progress').hidden=false;$('placeholder').hidden=true;$('video').hidden=true;$('live-preview').hidden=true;$('progress-label').textContent=label;$('progress-percent').textContent=`${value}%`;$('progress-fill').style.width=value+'%'}
function hideProgress(){ $('progress').hidden=true; }
function setBusy(on){$('generate').disabled=on||mediaItems.length<2}
async function start() {
  if(mediaItems.length<2 || !reelVariants.length)return;
  previewPause();hideError();stopPolling();setBusy(true);$('render-selected').disabled=true;$('result-actions').hidden=true;shareFile=null;
  progress('Przygotowuję materiały…',2);
  try{
    const fd=new FormData();
    for(let i=0;i<mediaItems.length;i++){
      const item=mediaItems[i];const file=item.type==='photo'?await shrinkImage(item.file):item.file;
      fd.append('media',file,file.name);progress(`Pakuję ujęcie ${i+1} z ${mediaItems.length}…`,Math.min(8,3+i));
    }
    const selection=variantAt(chosenVariant);
    fd.append('scene_text',JSON.stringify(mediaItems.map(x=>({caption:x.caption,detail:x.detail,ai_description:x.ai_description||''}))));
    fd.append('brand',$('brand').value);fd.append('cta',$('cta').value);fd.append('style',selection.style);fd.append('length',String(length));fd.append('auto_director',String($('director-enabled').checked));fd.append('variant',String(selection.variant));fd.append('pin',$('pin').value);
    if($('logo-input').files[0]){const f=await shrinkImage($('logo-input').files[0]);fd.append('logo',f,f.name)}
    if($('music-input').files[0]){const f=$('music-input').files[0];if(f.size>8*1024*1024)throw Error('Muzyka może mieć najwyżej 8 MB.');fd.append('audio',f)}
    progress('Wysyłam pliki na serwer…',10);
    const response=await fetch('/api/jobs',{method:'POST',body:fd});
    const payload=await response.json();
    if(!response.ok)throw new Error(payload.detail||'Błąd przesyłania plików.');
    jobId=payload.id;pollTimer=setTimeout(checkJob,1200);
    document.querySelector('.preview-panel').scrollIntoView({behavior:'smooth',block:'center'});
  }catch(err){hideProgress();$('placeholder').hidden=false;errorMessage(err.message||'Wystąpił błąd.');setBusy(false);$('render-selected').disabled=false;}
}
$('generate').addEventListener('click',prepareVariants);
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
  }catch(err){hideProgress();$('placeholder').hidden=false;errorMessage(err.message||'Błąd zadania.');setBusy(false);$('render-selected').disabled=false;}
}
async function ready(data){
  hideProgress();$('placeholder').hidden=true;$('live-preview').hidden=true;
  const url='/api/jobs/'+encodeURIComponent(jobId)+'/video';
  const video=$('video');video.src=url;video.hidden=false;video.load();
  $('result-actions').hidden=false;$('render-selected').disabled=false;
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
  $('result-actions').hidden=true;hideProgress();hideError();if(reelVariants.length){selectVariant(chosenVariant,{autoplay:false});}else{$('placeholder').hidden=false;}redrawScenes();
  window.scrollTo({top:0,behavior:'smooth'});
});
redrawScenes();
