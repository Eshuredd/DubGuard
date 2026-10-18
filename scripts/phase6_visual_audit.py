"""Build local screenshot contact sheets for visual review; no network or audio."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

root = Path('reports/phase6')
names = ['landing', 'scenarios', 'microphone', 'recording-preview', 'local-evidence', 'amd-mocked', 'dashboard', 'policy-editor', 'critical-signoff', 'approved-signoff']
for stage in ['before', 'after']:
    canvas = Image.new('RGB', (1800, 3000), '#e3e9f1')
    draw = ImageDraw.Draw(canvas)
    for index, name in enumerate(names):
        x, y = (index % 5)*360, (index // 5)*1500
        draw.text((x+8,y+8), f'{stage.upper()} / {name}', fill='#14253d')
        for size, top, height in [('desktop', 30, 630), ('mobile', 680, 800)]:
            with Image.open(root/stage/f'{name}-{size}.png') as source:
                thumb = ImageOps.contain(source.convert('RGB'), (344, height))
                canvas.paste(thumb, (x+8+(344-thumb.width)//2,y+top))
    canvas.save(root/f'{stage}-visual-index.jpg', quality=92)

# Readable lower review area: verify decision controls and history, not just hero.
for name in ['critical-signoff', 'approved-signoff']:
    for size in ['desktop', 'mobile']:
        with Image.open(root/'after'/f'{name}-{size}.png') as source:
            h = min(source.height, 1900)
            source.crop((0, source.height-h, source.width, source.height)).save(root/'after'/f'{name}-lower-{size}.png')
