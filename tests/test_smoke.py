"""Smoke test: python tests/test_smoke.py (requires Pillow, httpx, FFmpeg)."""
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app, SAFE


def img_data(i):
    image = Image.new('RGB',(700,1200),[(169,95,62),(42,122,117),(82,62,145)][i%3]);draw=ImageDraw.Draw(image)
    draw.ellipse((90,220,590,930),fill=(250,211,132))
    buf=io.BytesIO();image.save(buf,format='JPEG',quality=80)
    return buf.getvalue()


def wait(client,id):
    deadline=time.time()+160
    while time.time()<deadline:
        s=client.get('/api/jobs/'+id).json()
        print(s['state'],s['progress'],s['message'],flush=True)
        if s['state']=='error': raise AssertionError(s)
        if s['state']=='ready':return s
        time.sleep(.75)
    raise AssertionError('Timed out')


def verify_video(raw):
    temp=Path(tempfile.gettempdir())/'reelagent-v2-test.mp4';temp.write_bytes(raw)
    inf=subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=codec_name,width,height','-show_entries','format=duration','-of','json',str(temp)],text=True)
    parsed=json.loads(inf)
    assert parsed['streams'][0]['codec_name']=='h264'
    assert parsed['streams'][0]['width']==540 and parsed['streams'][0]['height']==960
    assert float(parsed['format']['duration'])>=9.8
    print('Created',temp, 'bytes:',len(raw),'duration:',parsed['format']['duration'])
    return temp


def main():
    client=TestClient(app)
    assert '2.0' in client.get('/').text
    assert client.get('/static/app.js').status_code==200
    assert client.get('/api/health').json()['safe_zone']==list(SAFE)
    media=[('media',(f'p{i}.jpg',img_data(i),'image/jpeg')) for i in range(3)]
    bad=client.post('/api/jobs',files=media,data={'style':'wrong','scene_text':json.dumps([{}, {}, {}])})
    assert bad.status_code==400,bad.text
    captions=[{'caption':'Pyszne churros','detail':'Najlepsze do kawy'}, {'caption':'Świeżo na miejscu','detail':'Wpadnij do nas'},{'caption':'Chwila dla Ciebie','detail':'Dziś i jutro'}]
    response=client.post('/api/jobs',files=media,data={'style':'film','length':'10','brand':'Churreria Mundo','cta':'Wpadnij dziś!','scene_text':json.dumps(captions)})
    print('POST',response.status_code,response.text,flush=True);assert response.status_code==200
    result=wait(client,response.json()['id'])
    video=client.get('/api/jobs/'+response.json()['id']+'/video')
    assert video.status_code==200
    verify_video(video.content)
    # Validate real moving footage path as well.
    with tempfile.TemporaryDirectory() as d:
        sample=Path(d)/'input.mp4'
        subprocess.run(['ffmpeg','-y','-loglevel','error','-f','lavfi','-i','testsrc2=size=320x568:rate=20','-t','2',
                        '-an','-c:v','libx264','-preset','ultrafast',str(sample)],check=True)
        media2=[('media',('movie.mp4',sample.read_bytes(),'video/mp4')),('media',('photo.jpg',img_data(0),'image/jpeg'))]
        captions2=[{'caption':'Ruchomy kadr','detail':'To jest wideo'},{'caption':'Kawa i churros','detail':'Bezpieczne napisy'}]
        result=client.post('/api/jobs',files=media2,data={'style':'dynamic','length':'10','brand':'Test','cta':'Do zobaczenia','scene_text':json.dumps(captions2)})
        print('VIDEO POST',result.status_code,result.text,flush=True);assert result.status_code==200
        wait(client,result.json()['id'])
        verify_video(client.get('/api/jobs/'+result.json()['id']+'/video').content)
    print('ALL SMOKE TESTS PASSED')


if __name__=='__main__':main()
