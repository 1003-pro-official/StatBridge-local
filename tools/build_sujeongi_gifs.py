"""Deterministically assemble the supplied 8-row sprite sheet into GIFs.

No image generation, model calls, background removal, or application changes.
"""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

from PIL import Image, ImageDraw, ImageFont, ImageSequence

ROWS = [0, 126, 252, 390, 517, 639, 762, 885, 1024]
ACTIONS = [
    ('idle', '기본 대기 · 눈 깜빡임', [800, 450, 450, 180, 500, 180, 140, 600]),
    ('wave', '손 흔들기', [220] * 8),
    ('happy', '미소 · 기쁨', [320] * 8),
    ('thinking', '생각 중', [450] * 8),
    ('explaining', '설명하기', [350] * 8),
    ('working', '작업 중 · 타이핑', [200] * 8),
    ('coffee', '커피 마시기', [350] * 8),
    ('cheer', '좋아요 · 응원', [280] * 8),
]
SIZE = (384, 256)
SCALE = 1.48


def hair_intervals(image, top, bottom):
    selected = []
    for x in range(150, image.width):
        count = sum(max(image.getpixel((x, y))) < 130
                    for y in range(top + 5, min(top + 80, bottom)))
        if count > 8:
            selected.append(x)
    groups = []
    for x in selected:
        if not groups or x > groups[-1][-1] + 3:
            groups.append([x])
        else:
            groups[-1].append(x)
    result = [(g[0], g[-1]) for g in groups if len(g) > 15]
    if len(result) != 8:
        raise ValueError(f'Expected 8 character heads at row {top}, found {result}')
    return result


def build(source, destination):
    image = Image.open(source).convert('RGB')
    if image.size != (1536, 1024):
        raise ValueError('This extraction layout expects the supplied 1536x1024 sheet.')
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'size': SIZE, 'loop': 0, 'background': 'opaque original checkerboard; not transparent',
                'actions': []}
    representatives = []
    for row, (name, title, durations) in enumerate(ACTIONS):
        top, bottom = ROWS[row:row+2]
        hair = hair_intervals(image, top, bottom)
        centers = [(a+b)/2 for a,b in hair]
        cuts = [150] + [round((a+b)/2) for a,b in zip(centers,centers[1:])] + [image.width]
        frames = []
        boxes = []
        for index, center in enumerate(centers):
            left, right = cuts[index], cuts[index+1]
            # The supplied sheet is not a uniform atlas: neighboring hands
            # and question marks cross midpoint boundaries in these cells.
            left = {('wave', 1): 325, ('wave', 2): 469,
                    ('explaining', 6): 1190,
                    ('thinking', 1): 323}.get((name, index), left)
            if (name, index) == ('wave', 0):
                right = 312
            box = (left, top, right, bottom)
            cell = image.crop(box)
            cell = cell.resize((round(cell.width*SCALE), round(cell.height*SCALE)), Image.Resampling.LANCZOS)
            frame = Image.new('RGB', SIZE, 'white')
            # Equal head position and scale; don't resize each different-width
            # cell independently to fit, which makes the character pulse.
            x = round(SIZE[0]/2 - (center-left)*SCALE)
            frame.paste(cell, (x, 16))
            frames.append(frame)
            boxes.append(box)
        # One palette per animation avoids per-frame palette/color flicker.
        palette_image = Image.new('RGB', (SIZE[0]*8, SIZE[1]), 'white')
        for index, frame in enumerate(frames):
            palette_image.paste(frame, (index*SIZE[0], 0))
        palette = palette_image.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
        indexed = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in frames]
        target = destination / f'sujeongi-{name}.gif'
        indexed[0].save(target, save_all=True, append_images=indexed[1:],
                        duration=durations, loop=0, disposal=2, optimize=False)
        with Image.open(target) as animation:
            decoded = [f.convert('RGB').copy() for f in ImageSequence.Iterator(animation)]
            timings = []
            for index in range(animation.n_frames):
                animation.seek(index)
                timings.append(animation.info['duration'])
            assert animation.size == SIZE and animation.info.get('loop') == 0
            assert len(decoded) >= 2 and len({f.tobytes() for f in decoded}) >= 2
            assert sum(timings) == sum(durations)
        representatives.append(frames[0])
        manifest['actions'].append({'file':target.name,'title':title,'source_frames':8,
            'encoded_frames':len(decoded),'duration_ms':sum(timings),'bytes':target.stat().st_size,
            'crop_boxes':boxes,'head_centers':centers})
    preview = Image.new('RGB', (SIZE[0]*4, (SIZE[1]+45)*2), '#f5f6fb')
    draw = ImageDraw.Draw(preview)
    font_path = Path('C:/Windows/Fonts/malgun.ttf')
    font = ImageFont.truetype(str(font_path), 20) if font_path.exists() else ImageFont.load_default()
    for i, ((name,title,_), frame) in enumerate(zip(ACTIONS,representatives)):
        x,y = (i%4)*SIZE[0], (i//4)*(SIZE[1]+45)
        preview.paste(frame, (x,y))
        draw.text((x+12,y+SIZE[1]+8),title,fill='#263247',font=font)
    preview.save(destination/'preview.png')
    (destination/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (destination/'README.txt').write_text(
        '수정이 동작별 GIF 8종\n384x256, 동작별 8개 원본 프레임, 무한 반복.\n'
        '원본의 불균일한 프레임 위치를 머리 중심 기준으로 정렬했습니다.\n'
        '체크무늬는 원본 PNG에 포함된 배경이며 실제 투명 배경이 아닙니다.\n'
        '원본에 그려진 프레임 숫자와 효과는 보존했습니다.\n'
        '각 프레임의 표정·소품 차이를 새로 그리거나 보간하지 않았으므로 원본에 의한 변화는 남습니다.\n'
        '현재 StatBridge1의 public/sujeongi.gif 및 UI 코드는 변경하지 않았습니다.\n'
        'manifest.json에 원본 해시, 추출 좌표, 실제 재생시간, 디코딩 검증 결과가 있습니다.\n', encoding='utf-8')
    archive = destination.parent / (destination.name+'.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
        for file in sorted(destination.iterdir()):
            bundle.write(file,arcname=file.name)
    print(json.dumps({'destination':str(destination),'archive':str(archive),'actions':manifest['actions']},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    build(args.source,args.destination)
