from pathlib import Path
import json,subprocess,shutil,hashlib,array,math
root=Path(__file__).resolve().parent
public=root/'remotion/public';public.mkdir(exist_ok=True)
ffmpeg=str(next((root.parent/'.venv/Lib/site-packages/imageio_ffmpeg/binaries').glob('*.exe')))
source=root/'private/capture/browser-original.webm'
events={r['name']:r['seconds'] for r in json.loads((root/'private/capture/events.json').read_text())}
def cut(name,start,end,pad=0):
    assert pad >= 0, (name, pad)
    subprocess.run([ffmpeg,'-y','-v','error','-ss',str(start),'-i',str(source),'-t',str(end-start+pad),'-an','-vf',f'trim=duration={end-start},setpts=PTS-STARTPTS,fps=30,tpad=stop_mode=clone:stop_duration={pad}','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',str(public/(name+'.mp4'))],check=True)
cut('landing',events['landing'],events['create'],20-(events['create']-events['landing']))
cut('create',events['create'],events['saved'],25-(events['saved']-events['create']))
cut('upload',events['upload'],events['preview-play'],8-(events['preview-play']-events['upload']))
cut('analysis',events['preview-play'],events['human'],37-(events['human']-events['preview-play']))
cut('human',events['human'],events['end'])
original=root.parent/'recorded-evaluation/on-off.wav';shutil.copyfile(original,public/'on-off.wav')
pcm=subprocess.check_output([ffmpeg,'-v','error','-i',str(original),'-f','f32le','-ac','1','-ar','16000','-'])
samples=array.array('f');samples.frombytes(pcm)
bins=160;peaks=[max(abs(x) for x in samples[int(i*len(samples)/bins):int((i+1)*len(samples)/bins)]) for i in range(bins)]
(root/'remotion/src/waveform.json').write_text(json.dumps(peaks))
amd=json.loads((root.parent/'reports/phase4/amd_smoke_inspection.json').read_text())
(root/'remotion/src/amd-evidence.json').write_text(json.dumps({k:amd[k] for k in ['actual_model','latency_ms','usage','citation_checks','recorded_attempts','additional_http_calls','deterministic_decision']},indent=2))
for p in (root.parent/'frontend/public').rglob('*.woff2'):
    d=public/'fonts'/p.name;d.parent.mkdir(exist_ok=True);shutil.copyfile(p,d)
print('Assets prepared; original SHA-256',hashlib.sha256(original.read_bytes()).hexdigest())
