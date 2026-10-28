"""ReelAgent Starter: minimal photo-to-MP4 web application.

Files are temporary; no API keys, account or database required. Designed for a
single-user pilot, NOT a multi-tenant public video rendering service.
"""
from __future__ import annotations

import asyncio
import logging
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
TMP_ROOT = Path(os.environ.get('REEL_TMP_DIR', tempfile.gettempdir())) / 'reelagent-jobs'
TMP_ROOT.mkdir(parents=True, exist_ok=True)
MAX_PHOTOS = 8
MIN_PHOTOS = 2
MAX_BYTES_PER_IMAGE = 12 * 1024 * 1024
MAX_BYTES_TOTAL = 70 * 1024 * 1024
MAX_AUDIO_BYTES = 15 * 1024 * 1024
MAX_AGE = 60 * 60
WIDTH, HEIGHT = 540, 960  # Faster than 1080p on tiny free CPUs; ideal vertical aspect ratio
FPS = 20

app = FastAPI(title='ReelAgent Starter', docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory=str(BASE / 'static')), name='static')

pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='reel-render')
lock = threading.Lock()
jobs: dict[str, dict[str, Any]] = {}

THEMES = {
    'cafe': {'bg': (28, 21, 22), 'accent': (245, 183, 119), 'fg': (255, 243, 225), 'shade': (23, 17, 19)},
    'fresh': {'bg': (13, 29, 39), 'accent': (117, 239, 195), 'fg': (240, 255, 252), 'shade': (8, 21, 28)},
    'pop': {'bg': (36, 19, 54), 'accent': (255, 119, 158), 'fg': (255, 242, 249), 'shade': (24, 15, 38)},
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('reelagent')


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    filename = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    return ImageFont.truetype(filename, size)


def wrap_text(draw: ImageDraw.ImageDraw, txt: str, fnt: ImageFont.FreeTypeFont, maxw: int, maxlines: int = 2):
    words = txt.split()
    lines = []
    line = ''
    for w in words:
        candidate = (line + ' ' + w).strip()
        if draw.textbbox((0, 0), candidate, font=fnt)[2] <= maxw:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    if len(lines) > maxlines:
        lines = lines[:maxlines]
        while draw.textbbox((0, 0), lines[-1] + '…', font=fnt)[2] > maxw and lines[-1]:
            lines[-1] = lines[-1][:-1]
        lines[-1] += '…'
    return lines


def mix(c1, c2, ratio):
    return tuple(round(a + (b - a) * ratio) for a, b in zip(c1, c2))


def gradient_base(pal):
    im = Image.new('RGB', (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(im)
    for y in range(HEIGHT):
        r = y / HEIGHT
        draw.line((0, y, WIDTH, y), fill=mix(pal['bg'], pal['shade'], r))
    return im


def rounded_photo(image: Image.Image, bounds: tuple[int, int], radius=22):
    w, h = bounds
    fill = ImageOps.fit(image, bounds, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    # Show all of the photo: blend a soft, edge-to-edge background with a contained original.
    blurred = fill.filter(ImageFilter.GaussianBlur(18))
    blurred = Image.blend(blurred, Image.new('RGB', bounds, (15, 15, 18)), .18)
    contained = ImageOps.contain(image, (w - 10, h - 10), Image.Resampling.LANCZOS)
    blurred.paste(contained, ((w-contained.width)//2, (h-contained.height)//2))
    mask = Image.new('L', bounds)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w-1, h-1), radius=radius, fill=255)
    return blurred, mask


def draw_logo(im: Image.Image, logo: Image.Image | None, x: int, y: int, max_side: int = 80):
    if logo is None:
        return
    lg = ImageOps.contain(logo, (max_side, max_side), Image.Resampling.LANCZOS)
    if lg.mode != 'RGBA':
        lg = lg.convert('RGBA')
    im.paste(lg, (x + (max_side-lg.width)//2, y + (max_side-lg.height)//2), lg)


def scene(image_path: Path, dest: Path, pal: dict, title: str, brand: str, subtitle: str, idx: int, total: int, logo: Image.Image | None):
    with Image.open(image_path) as src:
        photo = ImageOps.exif_transpose(src).convert('RGB')
    canvas = gradient_base(pal)
    draw = ImageDraw.Draw(canvas)
    accent, fg = pal['accent'], pal['fg']

    draw.rounded_rectangle((24, 27, 52, 55), radius=9, fill=accent)
    draw.text((64, 30), 'REEL STUDIO', font=font(17, True), fill=fg)
    page = f'{idx:02d} / {total:02d}'
    page_width = draw.textbbox((0,0), page, font=font(14))[2]
    draw.text((WIDTH-26-page_width, 33), page, font=font(14), fill=accent)

    # Keep title consistent for the brand and across scenes.
    f = font(31, True)
    lines = wrap_text(draw, title, f, WIDTH-50, maxlines=2)
    for j, line in enumerate(lines):
        draw.text((25, 86 + j*43), line, font=f, fill=fg)

    top = 200
    photo_w, photo_h = WIDTH-48, 562
    framed, mask = rounded_photo(photo, (photo_w, photo_h))
    canvas.paste(framed, (24, top), mask)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((41, top+18, 134, top+56), radius=14, fill=accent)
    draw.text((55, top+27), 'NOWE', font=font(14, True), fill=pal['shade'])

    draw.line((26, 793, WIDTH-26, 793), fill=mix(pal['accent'], pal['bg'], .55), width=2)
    subfont = font(20)
    sublines = wrap_text(draw, subtitle or 'Poznaj nas bliżej', subfont, 465, 2)
    for j, line in enumerate(sublines):
        draw.text((26, 811+j*27), line, font=subfont, fill=fg)

    draw.text((26, 903), brand.upper()[:35], font=font(18, True), fill=accent)
    draw_logo(canvas, logo, WIDTH-116, 864, 70)
    canvas.save(dest, optimize=True)


def ending(dest: Path, pal: dict, title: str, brand: str, cta: str, logo: Image.Image | None):
    canvas = gradient_base(pal)
    d = ImageDraw.Draw(canvas)
    accent, fg = pal['accent'], pal['fg']
    for radius, alpha in [(220, 24), (155, 32), (85, 43)]:
        # subtle ripple with outlines, not too busy
        cy = 390
        d.ellipse((WIDTH//2-radius, cy-radius, WIDTH//2+radius, cy+radius), outline=mix(accent, pal['bg'], .72), width=3)
    d.rounded_rectangle((WIDTH//2-56, 290, WIDTH//2+56, 402), radius=25, fill=accent)
    d.text((WIDTH//2-23, 309), '✦', font=font(48, True), fill=pal['shade'])
    draw_logo(canvas, logo, WIDTH//2-45, 304, 90)
    d = ImageDraw.Draw(canvas)
    fnt = font(39, True)
    lines = wrap_text(d, title, fnt, 486, 2)
    y = 474
    for line in lines:
        bb = d.textbbox((0, 0), line, font=fnt)
        d.text(((WIDTH-(bb[2]-bb[0]))//2, y), line, font=fnt, fill=fg)
        y += 53
    cfont = font(25, True)
    cta_lines = wrap_text(d, cta, cfont, WIDTH-105, 2)
    y = 640
    for line in cta_lines:
        bb = d.textbbox((0,0), line, font=cfont)
        d.text(((WIDTH-(bb[2]-bb[0]))//2, y), line, font=cfont, fill=accent)
        y += 38
    bfont = font(17, True)
    brand_text = brand.upper()[:35]
    bb=d.textbbox((0,0), brand_text, font=bfont)
    d.text(((WIDTH-(bb[2]-bb[0]))//2, 855), brand_text, font=bfont, fill=fg)
    canvas.save(dest, optimize=True)


def ff_run(args: list[str], timeout=250):
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if proc.returncode:
        raise RuntimeError('Nie udało się przygotować filmu. ' + proc.stderr.decode('utf-8', 'replace')[-350:])


def render_clip(png_path: Path, out: Path, duration: float, motion: bool):
    frames = round(duration*FPS)
    zoom = "zoompan=z='min(zoom+0.0008,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=540x960:fps=20" if motion else 'scale=540:960'
    # Fade creates soft transitions while keeping individual segments trivially concatenable.
    fade_duration = .13
    fade_out = max(0, duration-fade_duration)
    vf = f'{zoom},format=yuv420p,fade=t=in:st=0:d={fade_duration},fade=t=out:st={fade_out}:d={fade_duration}'
    ff_run(['ffmpeg','-hide_banner','-loglevel','error','-y','-loop','1','-framerate',str(FPS),'-i',str(png_path),
            '-vf',vf,'-frames:v',str(frames),'-r',str(FPS),'-an','-c:v','libx264',
            '-preset','ultrafast','-crf','23','-pix_fmt','yuv420p',str(out)], timeout=150)


def generate_video(job_id: str, input_photos: list[Path], opts: dict[str, str], audio_path: Path | None, logo_path: Path | None):
    directory = TMP_ROOT / job_id
    try:
        pal = THEMES[opts['theme']]
        with lock:
            jobs[job_id]['state'] = 'working'
            jobs[job_id]['message'] = 'Przygotowuję kadry…'
            jobs[job_id]['progress'] = 5
        logo = None
        if logo_path:
            with Image.open(logo_path) as im:
                logo = ImageOps.exif_transpose(im).convert('RGBA').copy()
        segments = []
        dur = 1.55 if opts['pace']=='fast' else 2.25
        n = len(input_photos)
        for i, src in enumerate(input_photos):
            slide = directory / f'slide-{i:02d}.png'
            clip = directory / f'clip-{i:02d}.mp4'
            scene(src, slide, pal, opts['title'], opts['brand'], opts['subtitle'], i+1, n, logo)
            render_clip(slide, clip, dur, motion=True)
            segments.append(clip)
            with lock:
                jobs[job_id]['progress'] = min(87, 8 + round((i+1)/n*75))
                jobs[job_id]['message'] = f'Montuję ujęcie {i+1} z {n}…'
        end_slide = directory / 'ending.png'
        end_clip = directory / 'clip-end.mp4'
        ending(end_slide, pal, opts['title'], opts['brand'], opts['cta'], logo)
        render_clip(end_slide, end_clip, 1.5, motion=False)
        segments.append(end_clip)
        concat_txt = directory / 'playlist.txt'
        concat_txt.write_text(''.join("file '"+str(p)+"'\n" for p in segments), encoding='utf8')
        silent = directory / 'silent.mp4'
        ff_run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(concat_txt),
                '-c','copy','-movflags','+faststart',str(silent)], timeout=90)
        out = directory / 'reelagent.mp4'
        if audio_path:
            with lock:
                jobs[job_id]['message'] = 'Dodaję muzykę…'
                jobs[job_id]['progress'] = 93
            total_duration = n*dur + 1.5
            fade_start = max(0, total_duration - 0.7)
            ff_run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(silent),'-stream_loop','-1','-i',str(audio_path),
                    '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','128k',
                    '-af',f'afade=t=out:st={fade_start:.3f}:d=0.7','-t',f'{total_duration:.3f}',
                    '-movflags','+faststart',str(out)], timeout=100)
        else:
            shutil.copy2(silent, out)
        with lock:
            jobs[job_id].update({'state':'ready','progress':100,'message':'Film gotowy!',
                                 'duration':round(n*dur+1.5, 1), 'bytes':out.stat().st_size})
        # Remove user originals and intermediate assets; retain final for short preview window.
        for p in directory.iterdir():
            if p != out:
                try: p.unlink()
                except OSError: pass
    except Exception as exc:
        logger.exception('Render failed for job %s', job_id)
        with lock:
            jobs[job_id].update({'state':'error','message':str(exc)[:420]})
        shutil.rmtree(directory, ignore_errors=True)


def cleanup():
    now = time.time()
    with lock:
        expired = [key for key, val in jobs.items() if val['state'] != 'working' and now-val['created'] > MAX_AGE]
        for key in expired:
            jobs.pop(key, None)
    for key in expired:
        shutil.rmtree(TMP_ROOT/key, ignore_errors=True)


@app.get('/')
def home():
    return FileResponse(BASE / 'static' / 'index.html', media_type='text/html')


@app.get('/api/health')
def health():
    return {'ok':True, 'version':'1.0'}


@app.post('/api/jobs')
async def create_job(request: Request,
                     photos: list[UploadFile] = File(...),
                     brand: str = Form('Moja marka'),
                     title: str = Form('Zobacz naszą historię'),
                     subtitle: str = Form('Małe rzeczy robią różnicę'),
                     cta: str = Form('Wpadaj do nas!'),
                     theme: str = Form('cafe'),
                     pace: str = Form('fast'),
                     pin: str = Form(''),
                     audio: UploadFile | None = File(None),
                     logo: UploadFile | None = File(None)):
    cleanup()
    required_pin = os.getenv('APP_PIN','').strip()
    if required_pin and pin != required_pin:
        raise HTTPException(403, 'Nieprawidłowy kod dostępu.')
    if theme not in THEMES or pace not in ('fast','calm'):
        raise HTTPException(400, 'Nieprawidłowy styl lub tempo.')
    if not MIN_PHOTOS <= len(photos) <= MAX_PHOTOS:
        raise HTTPException(400, 'Dodaj od 2 do 8 zdjęć.')
    with lock:
        active = sum(1 for j in jobs.values() if j['state'] in ('queued','working'))
        if active >= 2:
            raise HTTPException(429, 'Generator jest zajęty. Spróbuj ponownie za chwilę.')
    data = {'brand':brand.strip()[:50] or 'Moja marka', 'title':title.strip()[:75] or 'Zobacz nasze zdjęcia',
            'subtitle':subtitle.strip()[:100], 'cta':cta.strip()[:80] or 'Do zobaczenia!',
            'theme':theme, 'pace':pace}
    job_id = uuid.uuid4().hex
    directory = TMP_ROOT/job_id
    directory.mkdir(mode=0o700)
    paths = []
    total = 0

    async def save_upload(up: UploadFile, name: str, max_bytes: int) -> Path:
        nonlocal total
        dest = directory/name
        amount = 0
        with dest.open('wb') as f:
            while chunk := await up.read(1024 * 1024):
                amount += len(chunk)
                total += len(chunk)
                if amount > max_bytes or total > MAX_BYTES_TOTAL:
                    raise HTTPException(413, 'Pliki są za duże. Wybierz mniejsze zdjęcia.')
                f.write(chunk)
        if amount == 0:
            raise HTTPException(400,'Pusty plik.')
        return dest

    def verify_image(p: Path):
        try:
            with Image.open(p) as im:
                im.verify()
            with Image.open(p) as im:
                w,h=im.size
                if w*h > 40_000_000 or min(w,h) < 100:
                    raise HTTPException(400,'Zdjęcie ma nieodpowiednie wymiary.')
        except HTTPException:
            raise
        except (UnidentifiedImageError, OSError, ValueError):
            raise HTTPException(400,'Nie udało się odczytać jednego ze zdjęć. Spróbuj JPG albo PNG.')

    try:
        for i, upload in enumerate(photos):
            p = await save_upload(upload, f'photo-{i:02d}.input', MAX_BYTES_PER_IMAGE)
            verify_image(p)
            paths.append(p)
        audio_path = None
        if audio and audio.filename:
            if Path(audio.filename).suffix.lower() not in ('.mp3','.m4a','.wav','.aac'):
                raise HTTPException(400, 'Muzyka: wybierz MP3, WAV lub M4A.')
            audio_path = await save_upload(audio, 'audio.input', MAX_AUDIO_BYTES)
        logo_path = None
        if logo and logo.filename:
            logo_path = await save_upload(logo, 'logo.input', MAX_BYTES_PER_IMAGE)
            verify_image(logo_path)
        with lock:
            jobs[job_id] = {'state':'queued','message':'Czekam na montaż…','progress':0,'created':time.time()}
        pool.submit(generate_video,job_id,paths,data,audio_path,logo_path)
        return {'id':job_id}
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise


@app.get('/api/jobs/{job_id}')
def get_job(job_id: str):
    cleanup()
    with lock:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404,'Film wygasł albo nie istnieje.')
        return {k:v for k,v in job.items() if k!='created'}


@app.get('/api/jobs/{job_id}/video')
def get_video(job_id: str, download: int = 0):
    cleanup()
    with lock:
        job = jobs.get(job_id)
        if not job or job['state'] != 'ready':
            raise HTTPException(404,'Film nie jest jeszcze gotowy.')
    p=TMP_ROOT/job_id/'reelagent.mp4'
    if not p.exists():
        raise HTTPException(404,'Plik już wygasł.')
    return FileResponse(p, media_type='video/mp4', filename='moja-rolka.mp4', content_disposition_type='attachment' if download else 'inline')


@app.exception_handler(413)
async def too_large(request: Request, exc: HTTPException):
    return JSONResponse(status_code=413, content={'detail':exc.detail})
