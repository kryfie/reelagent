"""Run: python tests/test_smoke.py; requires FastAPI, PIL, FFmpeg and httpx."""
import io
import sys
import time
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import app


def img_bytes(index):
    im=Image.new('RGB',(900,1400),[(193,125,76),(48,118,104),(93,79,154)][index%3]);d=ImageDraw.Draw(im)
    d.ellipse((90+index*40,300,750,950),fill=(255,210,133))
    d.rounded_rectangle((160,1000,740,1140),radius=45,fill=(86,47,32))
    buffer=io.BytesIO();im.save(buffer,'JPEG',quality=85);return buffer.getvalue()


def main():
    client=TestClient(app)
    resp=client.get('/');assert resp.status_code == 200 and 'reelagent' in resp.text.lower()
    for file in ['app.js','style.css']:
        assert client.get('/static/'+file).status_code == 200
    assert client.get('/api/health').json()['ok']
    bad=client.post('/api/jobs',files=[('photos',('a.jpg',img_bytes(0),'image/jpeg'))]);assert bad.status_code==400,bad.text
    data={'brand':'Churreria Mundo','title':'Świeże churros na dziś','subtitle':'Prosto z kuchni • Szczecin','cta':'Zapraszamy!','theme':'cafe','pace':'fast'}
    files=[('photos',(f'p{i}.jpg',img_bytes(i),'image/jpeg')) for i in range(3)]
    start=time.monotonic();r=client.post('/api/jobs',data=data,files=files)
    print('POST',r.status_code,r.text);assert r.status_code==200
    ident=r.json()['id']
    deadline=time.monotonic()+125
    while time.monotonic()<deadline:
        state=client.get('/api/jobs/'+ident).json()
        print('STATE',state['state'],state['progress'],state['message'][:100])
        if state['state'] in ('ready','error'):break
        time.sleep(1)
    assert state['state']=='ready',state
    file=client.get('/api/jobs/'+ident+'/video')
    assert file.status_code==200
    assert file.headers['content-type'].startswith('video/mp4')
    path=Path('/mnt/data/reelagent-smoke-test.mp4');path.write_bytes(file.content)
    ff=subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=width,height,codec_name','-show_entries','format=duration','-of','default=noprint_wrappers=1',str(path)],text=True)
    print('VIDEO',ff,'BYTES',len(file.content),'SECONDS',round(time.monotonic()-start,2))
    assert 'width=540' in ff and 'height=960' in ff and 'codec_name=h264' in ff
    print('SMOKE TEST PASS')

if __name__=='__main__':main()
