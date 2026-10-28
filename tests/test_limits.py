"""Security and director unit tests: run python tests/test_limits.py"""
import io, json, os, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from PIL import Image
from app import app, MAX_VIDEO_DURATION, MAX_TOTAL, MAX_VIDEO, MAX_IMAGE
from director import plan_scenes, role_from_caption


def photo():
    im=Image.new('RGB',(200,330),'#995b56');b=io.BytesIO();im.save(b,'JPEG');return b.getvalue()


def run():
    print('Limits:',MAX_VIDEO_DURATION,MAX_VIDEO,MAX_IMAGE,MAX_TOTAL)
    c=TestClient(app)
    x=[{'type':'photo'},{'type':'video','ai_description':'Someone is pouring chocolate into a cup'},{'type':'photo','ai_description':'A cozy coffee shop interior'}]
    for v in range(3):
        plan=plan_scenes(x,style='dynamic',length=15,variant=v,auto_director=True)
        assert plan[0]['index']==1,plan
        assert round(sum(z['duration'] for z in plan),1)==13.2,plan
    assert role_from_caption('A woman pouring coffee')=='action'
    r=c.post('/api/director/plan',json={'media':x,'style':'dynamic','length':15,'auto_director':True,'variant':1})
    assert r.status_code==200,r.text
    assert r.json()['scenes'][0]['index']==1
    r=c.post('/api/jobs',headers={'content-length':str(65*1024*1024)},data='')
    assert r.status_code==413, (r.status_code,r.text)
    pics=[('media',('p1.jpg',photo(),'image/jpeg')),('media',('p2.jpg',photo(),'image/jpeg'))]
    badvideo=Path(tempfile.gettempdir())/'reelagent-too-long-10-min.mp4'
    subprocess.run(['ffmpeg','-y','-loglevel','error','-f','lavfi','-i','color=black:size=160x160:rate=1','-t','600','-c:v','libx264','-preset','ultrafast',str(badvideo)],check=True,timeout=45)
    assert badvideo.stat().st_size < 1024*1024
    data={'scene_text':json.dumps([{},{}]),'style':'film','length':'10'}
    r=c.post('/api/jobs',files=[('media',('ten-minutes.mp4',badvideo.read_bytes(),'video/mp4')),pics[0]],data=data)
    assert r.status_code==400,(r.status_code,r.text)
    assert '8' in r.json()['detail'],r.json()
    # Deny even a small file, if its duration exceeds the limit.
    print('10-minute upload rejected:',r.json()['detail'])
    # Per-file size limit (POST filesize below global cap)
    r=c.post('/api/jobs',files=[('media',('oversized.mp4',b'\x00'*(MAX_VIDEO+1),'video/mp4')),pics[0]],data=data)
    assert r.status_code==413,(r.status_code,r.text)
    print('15MB/file upload rejected')
    print('ALL DIRECTOR AND UPLOAD LIMIT TESTS PASSED')

if __name__=='__main__':run()
