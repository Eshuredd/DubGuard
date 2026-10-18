"""Generate generic licensed Kokoro narration locally, never evaluation speech."""
import os
os.environ['OMP_NUM_THREADS']='4'
from pathlib import Path
import json, subprocess, sys
import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro
import onnxruntime as ort
root=Path(__file__).resolve().parent
assets=root/'remotion/public/narration'; assets.mkdir(parents=True,exist_ok=True)
cues=json.loads((root/'remotion/src/narration.json').read_text())
options=ort.SessionOptions();options.intra_op_num_threads=4
session=ort.InferenceSession(str(root/'private/models/kokoro-v1.0.int8.onnx'),sess_options=options,providers=['CPUExecutionProvider'])
kokoro=Kokoro.from_session(session,str(root/'private/models/voices-v1.0.bin'))
ffmpeg=str(next((root.parent/'.venv/Lib/site-packages/imageio_ffmpeg/binaries').glob('*.exe')))
receipt=[]
for cue in cues:
    target=assets/(cue['id']+'.wav')
    if target.exists():
        samples,rate=sf.read(target)
    else:
        samples,rate=kokoro.create(cue['text'].replace('DubGuard','Dub Guard'),voice='af_heart',speed=1.0,lang='en-us')
        sf.write(target,samples,rate)
    duration=len(samples)/rate; available=cue['end']-cue['start']
    speed=max(.78,duration/(available*.94))
    normalized=assets/(cue['id']+'.m4a')
    subprocess.run([ffmpeg,'-y','-v','error','-i',str(target),'-af',f'atempo={speed},loudnorm=I=-17:TP=-2:LRA=7','-c:a','aac','-b:a','192k',str(normalized)],check=True)
    receipt.append({**cue,'original_duration':duration,'duration':duration/speed,'speed':speed,'voice':'Kokoro af_heart generic synthetic narration'})
    print(cue['id'],round(duration,2),'speed',round(speed,3),flush=True)
(root/'remotion/src/voice-timing.json').write_text(json.dumps(receipt,indent=2))
def tc(t):
    ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
subs=[];n=0
for cue in receipt:
    words=cue['text'].split(); chunks=[words[i:i+10] for i in range(0,len(words),10)];used=0
    for chunk in chunks:
        start=cue['start']+used/len(words)*cue['duration'];used+=len(chunk);end=cue['start']+used/len(words)*cue['duration'];n+=1
        subs.append(f'{n}\n{tc(start)} --> {tc(end)}\n'+ ' '.join(chunk)+'\n')
(root/'output').mkdir(exist_ok=True)
(root/'output/DubGuard_Subtitles.srt').write_text('\n'.join(subs),encoding='utf-8')
(root/'output/Voiceover.txt').write_text('\n\n'.join(f"{tc(c['start'])[:8]}  {c['text']}" for c in cues),encoding='utf-8')
