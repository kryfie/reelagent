"""Run: python tests/test_three_variants.py"""
import io, time, json, sys, subprocess, tempfile
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import app

def photo(color):
    im=Image.new('RGB',(360,640),color); b=io.BytesIO();im.save(b,'JPEG');return b.getvalue()

c=TestClient(app)
material=[{'type':'photo','ai_description':'golden churros close-up'}, {'type':'photo','ai_description':'cozy cafe interior'},{'type':'video','ai_description':'pouring coffee'}]
r=c.post('/api/director/plans',json={'media':material,'length':10,'auto_director':True})
assert r.status_code==200,r.text
j=r.json(); assert len(j['variants'])==3
assert [p['style'] for p in j['variants']]==['film','dynamic','story']
assert all(len(p['scenes'])==3 for p in j['variants'])
assert all(round(sum(s['duration'] for s in p['scenes'])+1.8,2)==10 for p in j['variants'])
assert all(set(s['index'] for s in p['scenes'])=={0,1,2} for p in j['variants'])
assert c.post('/api/director/plans',json={'media':material,'length':999}).status_code==400
assert c.post('/api/director/plans',json={'media':[{'type':'photo'}], 'length':15}).status_code==400
print('3 storyboard plans validated')
# Export only selected storyboard: one render job, not three.
clip=Path(tempfile.gettempdir())/'reelagent-v24-sample-input.mp4'
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','color=c=0xAC514A:size=360x640:rate=20','-t','2.0','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p',str(clip)],check=True,timeout=30)
sel=j['variants'][1]
assert sel['style']=='dynamic'
response=c.post('/api/jobs',files=[('media',('one.jpg',photo('#99483c'),'image/jpeg')),('media',('two.jpg',photo('#c5aa82'),'image/jpeg')),('media',('three.mp4',clip.read_bytes(),'video/mp4'))],data={'scene_text':json.dumps([{'caption':'Churros','detail':'Pyszne'},{'caption':'W kawiarni','detail':'Ciepło'},{'caption':'Nasza kawa','detail':'Spróbuj'}]),'brand':'Churreria Mundo','cta':'Wpadaj!','style':sel['style'],'length':'10','variant':str(sel['variant']),'auto_director':'true'})
assert response.status_code==200,response.text
job=response.json()['id']
for i in range(100):
    status=c.get('/api/jobs/'+job).json()
    if status['state'] in ['error','ready']:break
    time.sleep(.7)
assert status['state']=='ready',status
movie=c.get('/api/jobs/'+job+'/video')
assert movie.status_code==200 and movie.content[:4],movie.status_code
out=Path(tempfile.gettempdir())/'reelagent-v2-4-smoke.mp4';out.write_bytes(movie.content)
probe=subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(out)])
seconds=float(probe)
assert 9.7<seconds<10.3,seconds
print('Selected variant MP4 OK:',out,'seconds',seconds,'bytes',out.stat().st_size)
