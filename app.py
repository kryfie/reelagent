"""ReelAgent 2.0 — photo/video to safe-zone vertical MP4.

Pilot for one trusted user. Runs native FFmpeg on Render; no paid AI API.
Uploads and outputs are short-lived. Files are never committed to GitHub.
"""
from __future__ import annotations

import json
import logging
import math
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, UnidentifiedImageError

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

BASE = Path(__file__).parent
TMP_ROOT = Path(os.environ.get('REEL_TMP_DIR', tempfile.gettempdir())) / 'reelagent-v2-jobs'
TMP_ROOT.mkdir(parents=True, exist_ok=True)
WIDTH, HEIGHT, FPS = 540, 960, 20
MAX_MEDIA, MIN_MEDIA = 8, 2
MAX_IMAGE = 12 * 1024 * 1024
MAX_VIDEO = 55 * 1024 * 1024
MAX_AUDIO = 15 * 1024 * 1024
MAX_TOTAL = 145 * 1024 * 1024
EXPIRE_SECONDS = 3600
# Conservative common safe zone for TikTok and Instagram overlays at 540x960:
# RIGHT: x >= 414 excluded (buttons), BOTTOM: y >= 690 excluded (description),
# TOP: y < 145 excluded (platform header). All rendered text stays inside.
SAFE = (38, 150, 404, 670)

app = FastAPI(title='ReelAgent 2.0', docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory=str(BASE / 'static')), name='static')
pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='reel-render')
lock = threading.Lock()
jobs: dict[str, dict[str, Any]] = {}
logger = logging.getLogger('reelagent')
logging.basicConfig(level=logging.INFO)

STYLES = {
    'film': {'bg': (23, 16, 15), 'accent': (244, 190, 124), 'fg': (255, 250, 244)},
    'dynamic': {'bg': (20, 17, 30), 'accent': (255, 111, 145), 'fg': (255, 255, 255)},
    'story': {'bg': (14, 27, 34), 'accent': (106, 235, 205), 'fg': (248, 255, 253)},
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    fn = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    return ImageFont.truetype(fn, size)


def text_lines(draw: ImageDraw.ImageDraw, value: str, fnt, width: int, limit: int = 3):
    """Wrap Polish text, including single long tokens; never exceed safe width."""
    value = ' '.join(value.split())
    output = []
    for word in value.split(' '):
        if not word:
            continue
        if not output:
            output.append('')
        candidate = (output[-1] + ' ' + word).strip()
        if draw.textbbox((0, 0), candidate, font=fnt)[2] <= width:
            output[-1] = candidate
        elif output[-1]:
            output.append(word)
        else:
            output[-1] = word
        # split tokens wider than our safe region
        while output and draw.textbbox((0, 0), output[-1], font=fnt)[2] > width:
            s = output[-1]
            cut = len(s) - 1
            while cut > 1 and draw.textbbox((0, 0), s[:cut], font=fnt)[2] > width:
                cut -= 1
            output[-1] = s[:cut]
            output.append(s[cut:])
    if len(output) > limit:
        output = output[:limit]
        last = output[-1].rstrip('…')
        while last and draw.textbbox((0, 0), last + '…', font=fnt)[2] > width:
            last = last[:-1]
        output[-1] = last + '…'
    return output


def draw_copy(d, text, x, y, max_width, *, size=37, color=(255,255,255), limit=3, gap=8, bold=True):
    f = font(size, bold)
    lines = text_lines(d, text, f, max_width, limit)
    step = size + gap
    for i, line in enumerate(lines):
        d.text((x, y + i*step), line, font=f, fill=color, stroke_width=1 if size > 25 else 0, stroke_fill=(0,0,0,160) if size > 25 else None)
    return y + len(lines)*step


def logo_on(img: Image.Image, logo: Image.Image | None, x: int, y: int, max_side=52):
    if logo is None:
        return
    im = ImageOps.contain(logo, (max_side, max_side), Image.Resampling.LANCZOS).convert('RGBA')
    img.alpha_composite(im, (x, y))


def subtitle_overlay(path: Path, *, style: str, caption: str, detail: str, brand: str, idx: int, count: int, logo: Image.Image | None):
    """Only text within SAFE, regardless of style and image dimensions."""
    pal=STYLES[style]
    fg, accent = pal['fg'], pal['accent']
    layer=Image.new('RGBA',(WIDTH,HEIGHT),(0,0,0,0))
    d=ImageDraw.Draw(layer,'RGBA')
    left,top,right,bottom=SAFE
    if style=='film':
        # Floating editorial panel in central-left safe area.
        d.rounded_rectangle((left,306,right,606),radius=21,fill=(12,10,10,160))
        d.rounded_rectangle((left+20,333,left+65,338),radius=2,fill=accent+(255,))
        draw_copy(d,caption,left+20,364,right-left-40,size=36,color=fg,limit=3,gap=10)
        draw_copy(d,detail,left+20,523,right-left-40,size=19,color=(248,236,219),limit=2,gap=6,bold=False)
    elif style=='dynamic':
        d.rounded_rectangle((left,298,right,599),radius=15,fill=(16,9,26,196))
        d.polygon([(left,298),(left+14,298),(left+14,599),(left,599)],fill=accent+(255,))
        d.rounded_rectangle((left+23,319,left+168,355),radius=8,fill=accent+(255,))
        d.text((left+34,325),'ZOBACZ TO',font=font(16,True),fill=(16,12,24))
        draw_copy(d,caption,left+24,385,right-left-41,size=38,color=fg,limit=3,gap=8)
        draw_copy(d,detail,left+24,523,right-left-41,size=19,color=(255,237,241),limit=2,gap=6,bold=False)
    else: # story
        d.rounded_rectangle((left,306,right,610),radius=22,fill=(8,24,29,185))
        d.text((left+20,330),f'SCENA {idx:02d} / {count:02d}',font=font(17,True),fill=accent)
        d.line((left+20,367,right-20,367),fill=accent+(185,),width=2)
        draw_copy(d,caption,left+20,394,right-left-40,size=34,color=fg,limit=3,gap=8)
        draw_copy(d,detail,left+20,527,right-left-40,size=19,color=(226,250,242),limit=2,gap=6,bold=False)
    # Brand remains within the safe zone, never in app top bar.
    d.rounded_rectangle((left,155,min(right,left+250),211),radius=17,fill=(0,0,0,155))
    if logo:
        logo_on(layer, logo, left+8,161,39)
        name_x=left+55
    else:
        name_x=left+13
    brand_s=brand[:27]
    brand_lines=text_lines(d,brand_s,font(17,True),right-name_x-12,1)
    if brand_lines:
        d.text((name_x,175),brand_lines[0],font=font(17,True),fill=fg)
    layer.save(path)


def grab_frame(input_path: Path, output_path: Path):
    ff_run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss','0.2','-i',str(input_path),'-frames:v','1',str(output_path)],timeout=45)


def ending_png(dest: Path, last_image: Path, *, brand: str, cta: str, style: str, logo: Image.Image | None):
    pal=STYLES[style]
    with Image.open(last_image) as im:
        photo=ImageOps.fit(ImageOps.exif_transpose(im).convert('RGB'),(WIDTH,HEIGHT),method=Image.Resampling.LANCZOS)
    photo=photo.filter(ImageFilter.GaussianBlur(22))
    shade=Image.new('RGBA',(WIDTH,HEIGHT),pal['bg']+(218,))
    canvas=photo.convert('RGBA');canvas.alpha_composite(shade)
    d=ImageDraw.Draw(canvas,'RGBA'); left,top,right,bottom=SAFE
    d.rounded_rectangle((left,270,right,640),radius=24,fill=(0,0,0,105))
    d.rounded_rectangle((left+20,302,left+75,307),radius=2,fill=pal['accent']+(255,))
    if logo: logo_on(canvas,logo,left+20,328,57)
    d=ImageDraw.Draw(canvas,'RGBA')
    draw_copy(d,brand,left+20,405,right-left-40,size=32,color=pal['fg'],limit=2)
    draw_copy(d,cta,left+20,516,right-left-40,size=25,color=pal['accent'],limit=3,gap=7)
    canvas.convert('RGB').save(dest,optimize=True)


def ff_run(cmd: list[str], timeout=210):
    try:
        result=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=False)
    except subprocess.TimeoutExpired:
        raise RuntimeError('Generowanie trwało zbyt długo. Spróbuj krótszego filmu lub mniejszych plików.')
    if result.returncode:
        logger.warning('ffmpeg/ffprobe failed: %s',result.stderr[-1600:].decode('utf8','replace'))
        raise RuntimeError('Nie udało się przetworzyć materiału. Sprawdź format pliku i spróbuj ponownie.')
    return result.stdout


def video_meta(path: Path):
    raw=ff_run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=codec_name,width,height','-show_entries','format=duration',
                '-of','json',str(path)],timeout=25)
    try:
        data=json.loads(raw)
        stream=data['streams'][0]
        duration=float(data['format']['duration'])
        width,height=int(stream['width']),int(stream['height'])
        if not 0.5 <= duration <= 90 or not 150 <= width <= 3840 or not 150 <= height <= 3840:
            raise ValueError('Wymiary lub długość nieobsługiwane')
        return duration
    except (ValueError, KeyError, IndexError, TypeError):
        raise HTTPException(400,'Film musi mieć od 0,5 do 90 sekund i rozdzielczość co najmniej 150 px.')


def photo_meta(path: Path):
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            w,h=im.size
            if min(w,h)<150 or w*h>35_000_000:
                raise HTTPException(400,'Zdjęcie jest za małe lub za duże.')
    except HTTPException:
        raise
    except (UnidentifiedImageError,OSError,ValueError):
        raise HTTPException(400,'Nie udało się odczytać zdjęcia. Użyj JPG, PNG, WEBP lub HEIC.')


def photo_clip(photo_path: Path, overlay_path: Path, out: Path, secs: float, style: str, clip_idx: int):
    """True camera movement on full-frame photograph, text fixed over moving image."""
    with Image.open(photo_path) as src:
        image=ImageOps.exif_transpose(src).convert('RGB')
        image=ImageOps.fit(image,(650,1156),method=Image.Resampling.LANCZOS)
        temp=out.with_suffix('.jpg')
        image.save(temp,'JPEG',quality=90)
    frames=round(secs*FPS)
    # zoom and gentle pan in opposite directions; dynamic jumps between visual angles.
    if style=='dynamic':
        z="max(1.03,1.13-on*0.0019)" if clip_idx%2 else "min(1.14,1.02+on*0.0025)"
    elif style=='story':
        z="min(1.09,1.01+on*0.0009)"
    else:
        z="min(1.085,1.005+on*0.00075)"
    pan_x = "iw/2-(iw/zoom/2)" if clip_idx%2==0 else "(iw-iw/zoom)*0.35"
    pan_y = "ih/2-(ih/zoom/2)"
    base=f"zoompan=z='{z}':x='{pan_x}':y='{pan_y}':d=1:s={WIDTH}x{HEIGHT}:fps={FPS},setsar=1[base]"
    vf=f'[0:v]{base};[base][1:v]overlay=shortest=1,format=yuv420p'
    try:
        ff_run(['ffmpeg','-hide_banner','-loglevel','error','-y','-loop','1','-framerate',str(FPS),'-i',str(temp),'-loop','1','-i',str(overlay_path),
                '-filter_complex',vf,'-frames:v',str(frames),'-r',str(FPS),'-an','-c:v','libx264','-preset','ultrafast','-crf','25',
                '-pix_fmt','yuv420p',str(out)],timeout=155)
    finally:
        temp.unlink(missing_ok=True)


def video_clip(video_path: Path, overlay_path: Path, out: Path, secs: float, real_duration: float):
    # If uploaded footage is shorter than the scene, freeze last frame; always remove original audio.
    # scale+crop: avoid black bars, leave source media fullscreen.
    vf=f'[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},fps={FPS},setsar=1,format=yuv420p[base];[base][1:v]overlay=shortest=1:format=auto,format=yuv420p'
    frames=round(secs*FPS)
    ff_run(['ffmpeg','-hide_banner','-loglevel','error','-y','-stream_loop','-1','-i',str(video_path),'-loop','1','-i',str(overlay_path),
            '-filter_complex',vf,'-frames:v',str(frames),'-r',str(FPS),'-an','-c:v','libx264','-preset','ultrafast',
            '-crf','25','-pix_fmt','yuv420p',str(out)],timeout=155)


def still_clip(png: Path, out: Path, secs: float):
    ff_run(['ffmpeg','-hide_banner','-loglevel','error','-y','-loop','1','-framerate',str(FPS),'-i',str(png),
            '-t',str(secs),'-vf',f'fps={FPS},format=yuv420p','-an','-c:v','libx264','-preset','ultrafast','-crf','25',
            '-pix_fmt','yuv420p',str(out)],timeout=85)


def generate_video(job_id: str, media: list[dict[str, Any]], opts: dict, logo_path: Path | None, audio_path: Path | None):
    directory=TMP_ROOT/job_id
    try:
        with lock:
            jobs[job_id].update(state='working',message='Układam sceny…',progress=4)
        logo=None
        if logo_path:
            with Image.open(logo_path) as im:
                logo=ImageOps.exif_transpose(im).convert('RGBA').copy()
        total=float(opts['length'])
        end_length=1.8
        secs=(total-end_length)/len(media)
        clips=[]
        last_still=None
        for index,entry in enumerate(media):
            overlay=directory/f'overlay-{index:02}.png'
            subtitle_overlay(overlay,style=opts['style'],caption=entry['caption'],detail=entry['detail'],brand=opts['brand'],idx=index+1,count=len(media),logo=logo)
            clip=directory/f'clip-{index:02}.mp4'
            if entry['type']=='photo':
                photo_clip(entry['path'],overlay,clip,secs,opts['style'],index)
                last_still=entry['path']
            else:
                video_clip(entry['path'],overlay,clip,secs,entry['duration'])
                frame=directory/f'last-video-frame-{index:02}.png'
                grab_frame(entry['path'],frame)
                last_still=frame
            clips.append(clip)
            with lock:
                jobs[job_id].update(message=f'Montuję scenę {index+1} z {len(media)}…',progress=round(8+78*(index+1)/len(media)))
        outro=directory/'outro.png'
        ending_png(outro,last_still,brand=opts['brand'],cta=opts['cta'],style=opts['style'],logo=logo)
        outro_clip=directory/'outro.mp4'
        still_clip(outro,outro_clip,end_length)
        clips.append(outro_clip)
        playlist=directory/'playlist.txt'
        playlist.write_text(''.join("file '"+str(c)+"'\n" for c in clips),encoding='utf8')
        silent=directory/'silent.mp4'
        ff_run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(playlist),
                '-c','copy','-movflags','+faststart',str(silent)],timeout=100)
        final=directory/'reelagent.mp4'
        if audio_path:
            with lock:
                jobs[job_id].update(message='Dodaję muzykę…',progress=94)
            fade=max(0,total-.65)
            ff_run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(silent),'-stream_loop','-1','-i',str(audio_path),
                    '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','128k',
                    '-af',f'afade=t=out:st={fade:.2f}:d=0.65','-t',f'{total:.3f}',
                    '-movflags','+faststart',str(final)],timeout=100)
        else:
            shutil.copy2(silent,final)
        with lock:
            jobs[job_id].update(state='ready',message='Gotowa rolka!',progress=100,
                                duration=round(len(media)*secs+end_length,1),bytes=final.stat().st_size)
        for file in directory.iterdir():
            if file != final:
                file.unlink(missing_ok=True)
    except Exception as exc:
        logger.exception('Job %s failed',job_id)
        with lock:
            jobs[job_id].update(state='error',message=str(exc)[:300])
        shutil.rmtree(directory,ignore_errors=True)


def cleanup():
    now=time.time()
    with lock:
        expired=[key for key,val in jobs.items() if val['state'] not in ('working','queued') and now-val['created']>EXPIRE_SECONDS]
        for key in expired: jobs.pop(key,None)
    for key in expired: shutil.rmtree(TMP_ROOT/key,ignore_errors=True)


@app.get('/')
def home():
    return FileResponse(BASE/'static'/'index.html',media_type='text/html')


@app.get('/api/health')
def health():
    return {'ok':True,'version':'2.0','video':True,'safe_zone':SAFE}


@app.post('/api/jobs')
async def create_job(request: Request,
                     media: list[UploadFile] = File(...),
                     scene_text: str = Form('[]'),
                     brand: str = Form('Churreria Mundo'),
                     cta: str = Form('Wpadaj do nas!'),
                     style: str = Form('film'),
                     length: int = Form(15),
                     pin: str = Form(''),
                     audio: UploadFile | None = File(None),
                     logo: UploadFile | None = File(None)):
    cleanup()
    import hmac
    required=os.getenv('APP_PIN','').strip()
    if required and not hmac.compare_digest(pin,required):
        raise HTTPException(403,'Nieprawidłowy kod dostępu.')
    if style not in STYLES or length not in (10,15,20):
        raise HTTPException(400,'Wybierz poprawny szablon i długość.')
    if not MIN_MEDIA <= len(media) <= MAX_MEDIA:
        raise HTTPException(400,'Dodaj od 2 do 8 zdjęć lub filmów.')
    try:
        texts=json.loads(scene_text)
        if not isinstance(texts,list) or len(texts)!=len(media): raise ValueError()
        for entry in texts:
            if not isinstance(entry,dict): raise ValueError()
            if not isinstance(entry.get('caption',''),str) or not isinstance(entry.get('detail',''),str): raise ValueError()
    except (TypeError, ValueError, json.JSONDecodeError):
        raise HTTPException(400,'Nieprawidłowe napisy scen.')
    with lock:
        if sum(1 for x in jobs.values() if x['state'] in ('queued','working'))>=2:
            raise HTTPException(429,'Generator jest zajęty. Spróbuj za chwilę.')
    job_id=uuid.uuid4().hex
    directory=TMP_ROOT/job_id
    directory.mkdir(mode=0o700)
    total_bytes=0
    async def save(up: UploadFile,name: str, cap: int):
        nonlocal total_bytes
        path=directory/name; consumed=0
        with path.open('wb') as fp:
            while chunk := await up.read(1024*1024):
                consumed+=len(chunk);total_bytes+=len(chunk)
                if consumed>cap or total_bytes>MAX_TOTAL:
                    raise HTTPException(413,'Za duże pliki. Zmniejsz zdjęcia lub wybierz krótsze filmy.')
                fp.write(chunk)
        if not consumed: raise HTTPException(400,'Jeden z plików jest pusty.')
        return path
    try:
        clips=[]
        for i,up in enumerate(media):
            ext=Path(up.filename or '').suffix.lower()
            mimetype=(up.content_type or '').lower()
            is_video=ext in ('.mp4','.mov','.m4v','.webm') or mimetype.startswith('video/')
            if is_video and ext not in ('.mp4','.mov','.m4v','.webm'):
                raise HTTPException(400,'Wideo: użyj MP4, MOV lub WEBM.')
            dest=await save(up,f'asset-{i:02}.input',MAX_VIDEO if is_video else MAX_IMAGE)
            if is_video:
                d=video_meta(dest);kind='video'
            else:
                photo_meta(dest);d=0;kind='photo'
            clips.append({'path':dest,'type':kind,'duration':d,
                          'caption':texts[i].get('caption','').strip()[:72],
                          'detail':texts[i].get('detail','').strip()[:100]})
        logo_path=None
        if logo and logo.filename:
            logo_path=await save(logo,'logo.input',MAX_IMAGE)
            photo_meta(logo_path)
        audio_path=None
        if audio and audio.filename:
            if Path(audio.filename).suffix.lower() not in ('.mp3','.wav','.m4a','.aac'):
                raise HTTPException(400,'Muzyka musi być MP3, WAV lub M4A.')
            audio_path=await save(audio,'audio.input',MAX_AUDIO)
        opts={'brand':brand.strip()[:50] or 'Moja marka','cta':cta.strip()[:78] or 'Do zobaczenia!',
              'style':style,'length':length}
        with lock:
            jobs[job_id]={'state':'queued','message':'Czekam na montaż…','progress':0,'created':time.time()}
        pool.submit(generate_video,job_id,clips,opts,logo_path,audio_path)
        return {'id':job_id}
    except Exception:
        shutil.rmtree(directory,ignore_errors=True)
        raise


@app.get('/api/jobs/{job_id}')
def get_job(job_id: str):
    cleanup()
    with lock:
        job=jobs.get(job_id)
        if not job: raise HTTPException(404,'Film wygasł lub zadanie nie istnieje.')
        return {k:v for k,v in job.items() if k!='created'}


@app.get('/api/jobs/{job_id}/video')
def get_video(job_id: str,download: int=0):
    cleanup()
    with lock:
        job=jobs.get(job_id)
        if not job or job['state']!='ready': raise HTTPException(404,'Film nie jest gotowy.')
    path=TMP_ROOT/job_id/'reelagent.mp4'
    if not path.exists(): raise HTTPException(404,'Film nie jest już dostępny.')
    return FileResponse(path,media_type='video/mp4',filename='reelagent-rolka.mp4',
                        content_disposition_type='attachment' if download else 'inline')


@app.exception_handler(413)
async def too_large(request: Request,exc: HTTPException):
    return JSONResponse(status_code=413,content={'detail':exc.detail})
