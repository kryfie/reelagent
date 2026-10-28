// Optional, completely client-side Florence-2 director's eyes.
// This module loads only after the user explicitly presses the AI button.
// No files are uploaded to third-party APIs for inference.
let instancePromise = null;

async function loadModel(status) {
  if (!navigator.gpu) throw new Error('To urządzenie nie udostępnia WebGPU. Reżyser automatyczny działa bez niego.');
  if (!instancePromise) {
    instancePromise = (async () => {
      status('Pobieram Florence-2 (~340 MB przy pierwszym użyciu)…');
      const { Florence2ForConditionalGeneration, AutoProcessor, AutoTokenizer, RawImage } =
        await import('https://cdn.jsdelivr.net/npm/@huggingface/transformers@3/+esm');
      const id = 'onnx-community/Florence-2-base-ft';
      const [model, processor, tokenizer] = await Promise.all([
        Florence2ForConditionalGeneration.from_pretrained(id, {
          device: 'webgpu',
          dtype: {embed_tokens:'fp16', vision_encoder:'fp16', encoder_model:'q4', decoder_model_merged:'q4'}
        }),
        AutoProcessor.from_pretrained(id),
        AutoTokenizer.from_pretrained(id),
      ]);
      return {model, processor, tokenizer, RawImage};
    })().catch(err => { instancePromise = null; throw err; });
  }
  return instancePromise;
}

async function snapshot(file) {
  const objectUrl = URL.createObjectURL(file);
  try {
    let frame;
    if (file.type.startsWith('video/') || /\.(mov|mp4|webm|m4v)$/i.test(file.name)) {
      const v = document.createElement('video');
      v.src = objectUrl; v.preload='auto'; v.muted=true; v.playsInline=true;
      await new Promise((resolve,reject)=>{v.onloadeddata=resolve;v.onerror=()=>reject(new Error('Nie mogę odczytać klatki filmu.'));});
      if (v.duration > 1) {
        await new Promise(resolve=>{v.onseeked=resolve;v.currentTime=Math.min(1, v.duration/2);setTimeout(resolve,2500);});
      }
      frame=v;
    } else {
      const img = new Image(); img.src=objectUrl;
      await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=()=>reject(new Error('Nie mogę otworzyć zdjęcia.'));});
      frame=img;
    }
    const canvas=document.createElement('canvas');
    const w=frame.videoWidth||frame.naturalWidth, h=frame.videoHeight||frame.naturalHeight;
    const scale=Math.min(1,512/Math.max(w,h));
    canvas.width=Math.max(1,Math.round(w*scale));canvas.height=Math.max(1,Math.round(h*scale));
    canvas.getContext('2d').drawImage(frame,0,0,canvas.width,canvas.height);
    return canvas.toDataURL('image/jpeg',.78);
  } finally {URL.revokeObjectURL(objectUrl);}
}

export async function describeMedia(files, status) {
  const {model, processor, tokenizer, RawImage} = await loadModel(status);
  const result=[];
  for(let i=0;i<files.length;i++){
    status(`AI analizuje ujęcie ${i+1}/${files.length}…`);
    try {
      const image=await RawImage.fromURL(await snapshot(files[i]));
      const task='<MORE_DETAILED_CAPTION>';
      const inputs=await processor(image, processor.construct_prompts(task));
      const ids=await model.generate({...inputs, max_new_tokens:75});
      const decoded=processor.batch_decode(ids,{skip_special_tokens:false})[0];
      const parsed=processor.post_process_generation(decoded,task,image.size);
      result.push(String(parsed[task]||'').slice(0,350));
    } catch(err) {result.push('');}
  }
  return result;
}
