"""Inspect the encoded MP4, decode every frame, audit audio and build a visual contact sheet."""
from pathlib import Path
import subprocess,json,hashlib,math,array,re,sys
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent
movie=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root/'output/DubGuard_Hackathon_Demo.mp4'
probe=root/'remotion/node_modules/@remotion/compositor-win32-x64-msvc/ffprobe.exe'
ffmpeg=next((root.parent/'.venv/Lib/site-packages/imageio_ffmpeg/binaries').glob('*.exe'))
metadata=json.loads(subprocess.check_output([str(probe),'-v','error','-show_streams','-show_format','-count_frames','-of','json',str(movie)]))
streams=metadata['streams']; video=next(x for x in streams if x['codec_type']=='video'); audio=next(x for x in streams if x['codec_type']=='audio')
assert video['width']==1920 and video['height']==1080 and video['codec_name']=='h264' and video['avg_frame_rate']=='30/1'
assert audio['codec_name']=='aac'
assert int(video['nb_read_frames'])==6450
assert abs(float(metadata['format']['duration'])-215)<.1
assert movie.stat().st_size<300_000_000
decode=subprocess.run([str(ffmpeg),'-v','error','-i',str(movie),'-f','null','-'],capture_output=True,text=True)
assert decode.returncode==0 and not decode.stderr.strip(),decode.stderr
black=subprocess.run([str(ffmpeg),'-hide_banner','-i',str(movie),'-vf','blackdetect=d=0.15:pix_th=0.03:pic_th=0.98','-an','-f','null','-'],capture_output=True,text=True)
black_events=[x for x in black.stderr.splitlines() if 'black_start:' in x]
raw=subprocess.check_output([str(ffmpeg),'-v','error','-i',str(movie),'-vn','-ac','1','-ar','24000','-f','f32le','-'])
samples=array.array('f');samples.frombytes(raw)
peak=max(abs(x) for x in samples)
clipped=sum(abs(x)>=1 for x in samples)
intervals=[]
for a,b in [(1,5),(26,33),(78,80.58),(133.4,141.6),(208.1,213.6)]:
    selected=samples[int(a*24000):int(b*24000)]
    rms=math.sqrt(sum(x*x for x in selected)/len(selected));intervals.append({'from':a,'to':b,'rms_dbfs':20*math.log10(max(rms,1e-12))})
qa=root/'private/final-frames';qa.mkdir(exist_ok=True)
times=[1,7,12,17,22,32,52,66,74,79,85,91,99,105,112,122,130,138,146,153,160,168,178,183,188,197,211,214]
sheet=Image.new('RGB',(1920,math.ceil(len(times)/4)*300),'#07131e');draw=ImageDraw.Draw(sheet)
for i,t in enumerate(times):
    p=qa/f'{t:03}.jpg'
    subprocess.run([str(ffmpeg),'-v','error','-y','-ss',str(t),'-i',str(movie),'-frames:v','1','-q:v','2',str(p)],check=True)
    im=Image.open(p);im.thumbnail((480,270));x=i%4*480;y=i//4*300;sheet.paste(im,(x,y));draw.text((x+10,y+277),f'{t//60:02}:{t%60:02}',fill='#55ddc5')
sheet.save(root/'output/Contact_Sheet.jpg',quality=94)
originals=json.loads((root/'private/recording-results.json').read_text())
hash_checks=[{'file':Path(r['file']).name,'sha256':r['sha256'],'unchanged':hashlib.sha256(Path(r['file']).read_bytes()).hexdigest()==r['sha256']} for r in originals]
assert all(r['unchanged'] for r in hash_checks)
result={'file':str(movie),'duration_seconds':float(metadata['format']['duration']),'resolution':[video['width'],video['height']],'fps':video['avg_frame_rate'],'video_codec':video['codec_name'],'audio_codec':audio['codec_name'],'audio_sample_rate':audio['sample_rate'],'frames':video['nb_read_frames'],'bytes':movie.stat().st_size,'megabytes_decimal':round(movie.stat().st_size/1e6,2),'sha256':hashlib.sha256(movie.read_bytes()).hexdigest(),'all_frames_decode_cleanly':True,'black_intervals':black_events,'audio_peak_dbfs':20*math.log10(peak),'clipped_audio_samples':clipped,'audio_checks':intervals,'originals':hash_checks,'visual_correction_pass':['Relocated callouts away from editable policy fields','Enlarged original evidence footage while preserving provisional warning','Raised historical AMD provenance above subtitle safe area','Connected architecture rule-check and optional AMD rows'],'limits':{'published_portal_guidance':'Under 300 MB, within 5 minutes','authenticated_form_verified':False,'independent_human_listening':False,'public_ui':'Older deployment; current source recorded locally'}}
(root/'output/verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ['originals','visual_correction_pass','limits']},indent=2))
