"""Positive integer dimensions with a total allocation budget, no per-axis preset limits."""
MAX_PIXELS=32_000_000

def validate_output_dimensions(width,height):
    if type(width) is not int or type(height) is not int or width<1 or height<1:
        raise ValueError('출력 너비와 높이는 1 이상의 정수로 입력해 주세요.')
    if width*height>MAX_PIXELS:
        raise ValueError('출력 이미지의 총 픽셀 수가 3,200만을 넘습니다. 비율을 유지하며 크기를 줄여 주세요.')
    return width,height
