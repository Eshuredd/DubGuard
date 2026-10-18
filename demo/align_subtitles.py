"""Align exact narration script to locally recognized TTS word timing; never label evaluation audio."""
from pathlib import Path
import json,re,difflib
from faster_whisper import WhisperModel
root=Path(__file__).resolve().parent
model=WhisperModel(str(root.parent/'.dubguard-data/models/tiny.en'),device='cpu',compute_type='int8',cpu_threads=4,local_files_only=True)
timing=json.loads((root/'remotion/src/voice-timing.json').read_text())
captions=[]
norm=lambda s:re.sub('[^a-z0-9]','',s.lower())
for cue in timing:
    segments,_=model.transcribe(str(root/'remotion/public/narration'/(cue['id']+'.m4a')),language='en',word_timestamps=True,vad_filter=False,condition_on_previous_text=False)
    recognized=[w for seg in segments for w in seg.words]
    expected=cue['text'].split(); mapping={}
    for match in difflib.SequenceMatcher(None,list(map(norm,expected)),[norm(w.word) for w in recognized]).get_matching_blocks():
        for j in range(match.size):mapping[match.a+j]=recognized[match.b+j].start
    starts=list(range(0,len(expected),8))
    if len(starts)>1 and len(expected)-starts[-1]<=2:starts.pop()
    boundaries=[min(cue['duration'],max(0,mapping.get(i,i/len(expected)*cue['duration']))) for i in starts]+[cue['duration']]
    boundaries[0]=0
    for j,i in enumerate(starts):
        end=starts[j+1] if j+1<len(starts) else len(expected)
        captions.append({'start':cue['start']+boundaries[j],'end':cue['start']+max(boundaries[j]+.15,boundaries[j+1]),'text':' '.join(expected[i:end])})
    print(cue['id'],len(mapping),'/',len(expected),flush=True)
(root/'remotion/src/subtitles.json').write_text(json.dumps(captions,indent=2))
def tc(t):
    ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
(root/'output/DubGuard_Subtitles.srt').write_text('\n\n'.join(f"{i+1}\n{tc(c['start'])} --> {tc(c['end'])}\n{c['text']}" for i,c in enumerate(captions)),encoding='utf-8')
