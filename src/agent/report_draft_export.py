"""Downloadable report PDF: a bounded PNG plus server-owned draft sentences."""
import base64
import binascii
import io
import textwrap


def render_draft_pdf(draft, image_data_url, *, image_width=None, image_height=None):
    from PIL import Image
    from report_export import EXPORT_LOCK, _font
    if not image_data_url.startswith('data:image/png;base64,'):
        raise ValueError('보고서 그래프는 PNG 이미지여야 합니다.')
    try:
        content = base64.b64decode(image_data_url.split(',', 1)[1], validate=True)
        if len(content) > 8_000_000:
            raise ValueError('보고서 이미지가 8MB를 초과합니다.')
        with Image.open(io.BytesIO(content)) as opened:
            if opened.format != 'PNG' or opened.width * opened.height > 32_000_000:
                raise ValueError('보고서 PNG 이미지의 크기를 확인해 주세요.')
            image = opened.convert('RGB')
    except (binascii.Error, OSError, Image.DecompressionBombError) as exc:
        raise ValueError('보고서 그래프 이미지를 읽지 못했습니다.') from exc
    layout = draft['plotlyFigure']['layout']
    width = int(layout.get('width') or 496)
    height = int(layout.get('height') or 419)
    if image_width is not None or image_height is not None:
        from output_dimensions import validate_output_dimensions
        validate_output_dimensions(image_width,image_height)
        if (image.width, image.height) != (image_width, image_height):
            raise ValueError('보고서 이미지가 지정한 픽셀 크기와 일치하지 않습니다.')
    elif abs(image.width / image.height - width / height) > .01:
        raise ValueError('현재 초안 그래프의 이미지 비율과 일치하지 않습니다. 초안을 다시 작성해 주세요.')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    font = _font()
    sources = []
    for source in draft.get('sources', []):
        parts = ['한국은행' if source.get('organizationId') == '301' else '', source.get('source', ''), source.get('tableId', '')]
        label = ' · '.join(p for p in parts if p)
        if label and label not in sources:
            sources.append(label)
    source_text = '자료: ' + (', '.join(sources) or '현재 조회 자료')
    scope = ' / '.join(f"{s['label']}: {s['start']}~{s['end']} ({s.get('unit') or '단위 없음'})" for s in draft['scope']['series'])
    output = io.BytesIO()
    with EXPORT_LOCK, matplotlib.rc_context({'font.family': font.get_name(), 'pdf.fonttype': 42, 'axes.unicode_minus': False}):
        figures = []
        with PdfPages(output, metadata={'Title': draft.get('title') or '보고서 초안', 'Creator': 'StatBridge'}) as pdf:
            def page():
                fig = plt.figure(figsize=(8.27, 11.69), facecolor='white')
                figures.append(fig)
                fig.text(.08, .035, '관측 자료로 작성한 보고서 초안 · 검토 후 사용해 주세요.', fontproperties=font, fontsize=8, color='#60798c')
                return fig
            fig = page()
            y = 11.0
            def write(text, *, size=10.5, columns=42, gap=.12, color='#172f43'):
                nonlocal fig, y
                for line in textwrap.wrap(str(text), columns) or ['']:
                    if y < .85:
                        pdf.savefig(fig)
                        plt.close(fig)
                        fig = page(); y = 11.0
                    fig.text(.08, y/11.69, line, va='top', fontproperties=font, fontsize=size, color=color)
                    y -= size * 1.65 / 72
                y -= gap
            try:
                write(draft.get('title') or '통계 분석 보고서', size=17, columns=28, gap=.15)
                write(scope, size=8, columns=58, gap=.18, color='#60798c')
                available_width = 8.27 * .84
                if y < 3.5:
                    pdf.savefig(fig);plt.close(fig);fig=page();y=11.0
                available_height = min(5.5, y - 1.0)
                scale = min(available_width/image.width, available_height/image.height)
                w, h = image.width*scale, image.height*scale
                axes = fig.add_axes([(.5-w/8.27/2), (y-h)/11.69, w/8.27, h/11.69])
                axes.imshow(image, aspect='equal', interpolation='none'); axes.set_axis_off()
                y -= h + .12
                write(source_text, size=8, columns=58, gap=.22, color='#60798c')
                for paragraph in draft['paragraphs']:
                    write(paragraph, gap=.17)
                pdf.savefig(fig)
            finally:
                for current in figures:
                    plt.close(current)
    return output.getvalue()
