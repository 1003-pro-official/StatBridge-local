"""Transparent GIF assembly from the user-approved sprite sheet workflow."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

import numpy as np
from scipy import ndimage as ndi
from PIL import Image, ImageDraw, ImageFont, ImageSequence

from build_sujeongi_gifs import ROWS, ACTIONS, SIZE, SCALE, hair_intervals


def cutout(cell):
    rgb = np.array(cell.convert('RGB'))
    high, low = rgb.max(axis=2), rgb.min(axis=2)
    # The supplied sheet has a baked-in achromatic checkerboard. Protect
    # colored skin/hair/effects and enclosed white clothing, not just white.
    foreground = ~((high.astype(int)-low.astype(int) <= 3) & (low >= 182))
    foreground = ndi.binary_closing(foreground, iterations=2, border_value=0)
    foreground = ndi.binary_fill_holes(foreground)
    labels, count = ndi.label(foreground)
    sizes = np.bincount(labels.ravel())
    strong = (high.astype(int)-low.astype(int) > 12) | (low < 182)
    evidence = ndi.sum(strong,labels,index=np.arange(len(sizes)))
    keep = (sizes >= 8) & (evidence >= 4)
    keep[0] = False
    foreground = keep[labels]
    main_label = np.argmax(np.where(keep,sizes,0))
    # Clothing/light laptop interiors can open onto the bottom crop edge.
    # Restore the white interior between their visible outlines row by row.
    for y in range(round(cell.height * .57), cell.height):
        xs = np.flatnonzero(labels[y] == main_label)
        if len(xs) > 8:
            foreground[y, xs[0]:xs[-1]+1] = True
    alpha = np.uint8(foreground)*255
    return Image.fromarray(np.dstack([rgb, alpha]))


def save_gif(path, frames, durations):
    film = Image.new('RGB', (SIZE[0]*len(frames), SIZE[1]), 'black')
    for i, frame in enumerate(frames):
        film.paste(frame.convert('RGB'), (i*SIZE[0], 0))
    palette = film.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    indexed = []
    for frame in frames:
        p = frame.convert('RGB').quantize(palette=palette, dither=Image.Dither.NONE)
        pixels = np.array(p)
        pixels[np.array(frame.getchannel('A')) < 128] = 255
        p = Image.fromarray(pixels, mode='P')
        p.putpalette(palette.getpalette()[:765]+[0,0,0])
        p.info['transparency'] = 255
        indexed.append(p)
    indexed[0].save(path, save_all=True, append_images=indexed[1:],
                    duration=durations, loop=0, transparency=255,
                    background=255, disposal=2, optimize=False)
    with Image.open(path) as gif:
        total = 0
        decoded = []
        for i in range(gif.n_frames):
            gif.seek(i)
            frame = gif.convert('RGBA')
            alpha = np.array(frame.getchannel('A'))
            assert alpha[0,0] == 0 and (alpha == 0).any() and (alpha == 255).any()
            assert frame.size == SIZE
            total += gif.info['duration']
            decoded.append(frame.copy())
        assert total == sum(durations) and gif.info.get('loop') == 0
    return {'file':path.name,'frames':len(decoded),'duration_ms':total,
            'transparent_every_frame':True,'loop':0}


def build(source, destination):
    source_image = Image.open(source).convert('RGB')
    assert source_image.size == (1536,1024)
    destination.mkdir(parents=True, exist_ok=True)
    records, all_frames, all_durations, previews = [], [], [], []
    font = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 18)
    qa = Image.new('RGB', (192*8,148*8), '#243249')
    for row, (name,title,original_durations) in enumerate(ACTIONS):
        top,bottom = ROWS[row:row+2]
        centers = [(a+b)/2 for a,b in hair_intervals(source_image,top,bottom)]
        cuts = [150]+[round((a+b)/2) for a,b in zip(centers,centers[1:])]+[1536]
        frames = []
        for index,center in enumerate(centers):
            left,right = cuts[index:index+2]
            left = {('wave',1):325,('wave',2):469,('explaining',6):1190,
                    ('thinking',1):323}.get((name,index),left)
            if (name,index) == ('wave',0): right = 312
            cell = cutout(source_image.crop((left,top,right,bottom)))
            cell = cell.resize((round(cell.width*SCALE),round(cell.height*SCALE)),Image.Resampling.LANCZOS)
            frame = Image.new('RGBA',SIZE,(0,0,0,0))
            frame.alpha_composite(cell,(round(SIZE[0]/2-(center-left)*SCALE),16))
            frames.append(frame)
            bg = Image.new('RGBA',SIZE,'#243249')
            bg.alpha_composite(frame)
            qa.paste(bg.convert('RGB').resize((192,128)),(index*192,row*148))
            ImageDraw.Draw(qa).text((index*192+5,row*148+128),f'{name} {index+1}',fill='white')
        # Play forward and back to avoid an abrupt final-to-first pose jump.
        # No cross-fade: blending separate drawings creates double faces/hands.
        order = list(range(8))+list(range(6,0,-1))
        if name == 'idle':
            order = list(range(8))
            durations = original_durations
        else:
            base = {'wave':160,'happy':240,'thinking':320,'explaining':260,
                    'working':160,'coffee':280,'cheer':220}[name]
            durations = [base]*len(order)
            durations[0] += 350
            durations[7] += 250
        ordered = [frames[i] for i in order]
        record = save_gif(destination/f'sujeongi-{name}.gif',ordered,durations)
        record.update(action=title,source_frames=8,playback_order=order)
        records.append(record)
        previews.append(frames[0])
        # Neutral interludes separate distinct gestures in the combined loop.
        if row:
            all_frames.append(neutral)
            all_durations.append(500)
        all_frames.extend(ordered)
        all_durations.extend(durations)
        if row == 0: neutral = frames[0]
    all_frames.append(neutral)
    all_durations.append(800)
    records.append(save_gif(destination/'sujeongi-all-actions.gif',all_frames,all_durations))
    qa.save(destination/'frames-dark-background-qa.png')
    preview = Image.new('RGB',(384*4,301*2),'#f1f4fa')
    for i,frame in enumerate(previews):
        x,y = (i%4)*384,(i//4)*301
        bg = Image.new('RGBA',SIZE,'#243249' if i%2 else '#f1f4fa')
        bg.alpha_composite(frame)
        preview.paste(bg.convert('RGB'),(x,y))
        ImageDraw.Draw(preview).text((x+12,y+263),ACTIONS[i][1],fill='#243249',font=font)
    preview.save(destination/'preview.png')
    manifest = {'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                'size':SIZE,'background':'transparent','method':'deterministic sprite extraction',
                'limitations':'8 original poses; no invented motion or optical-flow interpolation; original frame numbers retained',
                'animations':records}
    (destination/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (destination/'README.txt').write_text(
        '수정이 투명 GIF: 동작별 8종 + 전체 동작 연결 1종\n'
        '384x256, 무한 반복, 모든 프레임 투명도 디코딩 검증.\n'
        '손 흔들기/미소/생각/설명/작업/커피/좋아요와 눈 깜빡임 포함.\n'
        '체크 배경 제거, 머리 중심 정렬, 왕복 재생과 동작 사이 대기 적용.\n'
        '원본 8개 포즈를 사용하므로 새 중간 동작을 만든 고프레임 애니메이션은 아닙니다.\n'
        'GIF의 투명도는 이진이며, 원본의 옷 위 프레임 번호는 유지됩니다.\n'
        '앱의 public/sujeongi.gif 및 코드는 변경하지 않았습니다.\n',encoding='utf-8')
    archive = destination.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for f in sorted(destination.iterdir()): z.write(f,f.name)
    with zipfile.ZipFile(archive) as z: assert z.testzip() is None
    print(json.dumps(records,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    args = parser.parse_args()
    build(args.source,args.destination)
