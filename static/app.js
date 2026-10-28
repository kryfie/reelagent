'use strict';
const $ = id => document.getElementById(id);
let selected = [], theme = 'cafe', pace = 'fast', jobId = null, jobVideoBlob = null, fileForSharing = null, jobPoll = null;

function makeThumbs() {
  const gallery = $('gallery');
  gallery.replaceChildren();
  selected.forEach((item, i) => {
    const box = document.createElement('div'); box.className = 'thumb';
    const img = document.createElement('img'); img.src = item.url; img.alt = `Zdjęcie ${i+1}`;
    const num = document.createElement('span'); num.className = 'thumb-num'; num.textContent = `${i+1}`;
    const controls = document.createElement('div'); controls.className='thumb-controls';
    const actions = [
      ['←', () => move(i,-1), i===0, 'Przesuń w lewo'],
      ['→', () => move(i,1), i===selected.length-1, 'Przesuń w prawo'],
      ['×', () => remove(i), false, 'Usuń zdjęcie']
    ];
    actions.forEach(([label,fn,disabled,tooltip])=>{
      const b=document.createElement('button'); b.type='button';b.textContent=label;b.disabled=disabled;b.title=tooltip;b.setAttribute('aria-label',tooltip);b.addEventListener('click',e=>{e.stopPropagation();fn()});controls.appendChild(b);
    });
    box.append(img,num,controls);gallery.appendChild(box);
  });
  $('counter').textContent=selected.length ? `${selected.length} / 8 zdjęć · użyj strzałek, aby zmienić kolejność` : 'Nie wybrano jeszcze zdjęć';
  $('generate').disabled = selected.length < 2 || !!jobPoll;
}
function move(i, shift) {const j = i+shift; if (j<0 || j>=selected.length) return; [selected[i],selected[j]]=[selected[j],selected[i]];makeThumbs()}
function remove(i) {URL.revokeObjectURL(selected[i].url);selected.splice(i,1);makeThumbs()}
function addPhotos(files) {
  const images = [...files].filter(file => file.type.startsWith('image/') || /\.(heic|heif|jpg|jpeg|png|webp)$/i.test(file.name));
  const available = 8 - selected.length;
  if (images.length > available) showError('Można dodać maksymalnie 8 zdjęć.');
  images.slice(0,available).forEach(file => { selected.push({file,url:URL.createObjectURL(file)}) });
  makeThumbs();
}
$('photos-input').addEventListener('change',e=>{addPhotos(e.target.files);e.target.value=''});
const dropzone=$('dropzone');
dropzone.addEventListener('dragover',e=>{e.preventDefault();dropzone.classList.add('dragover')});
dropzone.addEventListener('dragleave',()=>dropzone.classList.remove('dragover'));
dropzone.addEventListener('drop',e=>{e.preventDefault();dropzone.classList.remove('dragover');addPhotos(e.dataTransfer.files)});
dropzone.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();$('photos-input').click()}});
document.querySelectorAll('[data-theme]').forEach(btn=>btn.addEventListener('click',()=>{
  theme=btn.dataset.theme;
  document.querySelectorAll('[data-theme]').forEach(b=>{const active=b===btn;b.classList.toggle('selected',active);b.setAttribute('aria-pressed',String(active))});
}));
document.querySelectorAll('[data-pace]').forEach(btn=>btn.addEventListener('click',()=>{
  pace=btn.dataset.pace;
  document.querySelectorAll('[data-pace]').forEach(b=>{const active=b===btn;b.classList.toggle('selected',active);b.setAttribute('aria-pressed',String(active))});
}));

function showError(text) {$('error').textContent=text;$('error').hidden=false}
function hideError(){$('error').hidden=true;$('error').textContent=''}
function setProgress(label, percent) {
  $('progress-overlay').hidden=false;$('placeholder').hidden=true;$('video').hidden=true;
  $('progress-label').textContent=label;$('progress-percent').textContent=`${percent}%`;
  $('progress-bar').style.width=`${percent}%`;
}
function stopPoll() {if(jobPoll){clearTimeout(jobPoll);jobPoll=null}}

async function compactImage(file) {
  // iOS often exports HEIC. Drawing to canvas creates a portable JPEG and
  // bounds uploads on phones. If unsupported, send original to server (HEIC-capable).
  if (!file.type.startsWith('image/') && !/\.(heic|heif)$/i.test(file.name)) return file;
  const url=URL.createObjectURL(file);
  try {
    const img = await new Promise((resolve,reject)=>{
      const element = new Image();
      element.onload=()=>resolve(element);
      element.onerror=()=>reject(new Error('Nie udało się zmniejszyć zdjęcia.'));
      element.src=url;
    });
    const maxSide=1600;
    const scale=Math.min(1,maxSide/Math.max(img.naturalWidth,img.naturalHeight));
    const canvas=document.createElement('canvas');
    canvas.width=Math.max(1,Math.round(img.naturalWidth*scale));
    canvas.height=Math.max(1,Math.round(img.naturalHeight*scale));
    const ctx=canvas.getContext('2d');if(!ctx) return file;
    ctx.fillStyle='#ffffff';ctx.fillRect(0,0,canvas.width,canvas.height);
    ctx.drawImage(img,0,0,canvas.width,canvas.height);
    const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.86));
    return blob ? new File([blob],file.name.replace(/\.[^.]*$/, '')+'.jpg',{type:'image/jpeg'}) : file;
  } catch {return file} finally {URL.revokeObjectURL(url)}
}

async function start() {
  if(selected.length<2) return;
  hideError();$('result-actions').hidden=true;jobVideoBlob=null;fileForSharing=null;
  $('generate').disabled=true;
  setProgress('Przygotowuję zdjęcia…',2);
  try {
    const fd=new FormData();
    for(let i=0;i<selected.length;i++) {
      const file=await compactImage(selected[i].file);
      fd.append('photos',file,file.name);
      setProgress(`Przygotowuję zdjęcie ${i+1} / ${selected.length}…`,Math.min(8,2+i));
    }
    ['brand','title','subtitle','cta','pin'].forEach(id=>fd.append(id,$(id).value));
    fd.append('theme',theme);fd.append('pace',pace);
    if($('music').files[0])fd.append('audio',$('music').files[0]);
    if($('logo').files[0])fd.append('logo',await compactImage($('logo').files[0]));
    setProgress('Przesyłam zdjęcia…',10);
    const resp=await fetch('/api/jobs',{method:'POST',body:fd});
    const data=await resp.json();
    if(!resp.ok)throw new Error(typeof data.detail==='string'?data.detail:'Nie udało się przesłać zdjęć.');
    jobId=data.id;
    schedulePoll();
    document.querySelector('.preview-panel').scrollIntoView({behavior:'smooth',block:'center'});
  } catch (err) {stopPoll();$('progress-overlay').hidden=true;$('placeholder').hidden=false;showError(err.message||'Wystąpił błąd.');makeThumbs()}
}
$('generate').addEventListener('click',start);
function schedulePoll() {jobPoll=setTimeout(checkJob,1300)}
async function checkJob() {
  jobPoll=null;
  try {
    const resp=await fetch('/api/jobs/'+encodeURIComponent(jobId));
    if(!resp.ok)throw new Error('Nie znaleziono zadania. Serwer mógł zostać ponownie uruchomiony.');
    const status=await resp.json();
    if(status.state==='error')throw new Error(status.message||'Nie udało się przygotować filmu.');
    if(status.state==='ready') {await onReady(status);return}
    setProgress(status.message||'Pracuję nad filmem…',status.progress||0);
    schedulePoll();
  } catch(err) {
    $('progress-overlay').hidden=true;$('placeholder').hidden=false;showError(err.message||'Błąd serwera.');makeThumbs();
  }
}
async function onReady(status) {
  $('progress-overlay').hidden=true;$('placeholder').hidden=true;
  const videoUrl='/api/jobs/'+encodeURIComponent(jobId)+'/video';
  $('video').src=videoUrl;$('video').hidden=false;$('video').load();
  $('result-actions').hidden=false;
  $('download').href=videoUrl+'?download=1';
  $('result-info').textContent=`Gotowe · ${status.duration || '—'} s · ${((status.bytes||0)/1024/1024).toFixed(1)} MB`;
  $('share').disabled=true;$('share').textContent='Przygotowuję udostępnianie…';
  makeThumbs();
  try {
    const resp=await fetch(videoUrl);
    if(!resp.ok)throw new Error('Brak gotowego filmu.');
    jobVideoBlob=await resp.blob();
    fileForSharing=new File([jobVideoBlob],'moja-rolka.mp4',{type:'video/mp4'});
    $('share').disabled=false;$('share').textContent='↗ Udostępnij / Zapisz w Zdjęciach';
  } catch {
    $('share').textContent='↓ Użyj przycisku Pobierz MP4';
  }
}
$('share').addEventListener('click',async()=>{
  if(!fileForSharing)return;
  if(navigator.share && navigator.canShare && navigator.canShare({files:[fileForSharing]})){
    try {await navigator.share({files:[fileForSharing],title:'Moja rolka'});return}
    catch(err){if(err.name==='AbortError')return}
  }
  showError('Na tym urządzeniu udostępnianie plików może nie działać. Użyj „Pobierz film MP4”, a następnie wybierz udostępnianie lub zapis w Zdjęciach.');
});
$('reset').addEventListener('click',()=>{
  stopPoll();jobId=null;fileForSharing=null;jobVideoBlob=null;$('video').pause();$('video').removeAttribute('src');$('video').load();$('video').hidden=true;
  $('placeholder').hidden=false;$('result-actions').hidden=true;hideError();makeThumbs();
  window.scrollTo({top:0,behavior:'smooth'});
});
makeThumbs();
