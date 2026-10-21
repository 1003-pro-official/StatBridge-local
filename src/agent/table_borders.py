"""Closed border presets shared by screen and file rendering."""
from typing import Literal
BorderStyle=Literal['none','thin','medium','thick','dotted','dotted_medium','dotted_thick','dashed','dashed_medium','dashed_thick','double']

def border_spec(style):
    width=3 if style in {'thick','dotted_thick','dashed_thick','double'} else 2 if style in {'medium','dotted_medium','dashed_medium'} else 1
    kind='dotted' if style.startswith('dotted') else 'dashed' if style.startswith('dashed') else 'double' if style=='double' else 'solid'
    return width,kind

def excel_border(style):
    # OOXML cannot encode independent widths for dotted borders.
    return {'none':None,'dotted_medium':'dotted','dotted_thick':'dotted','dashed_medium':'mediumDashed','dashed_thick':'mediumDashed'}.get(style,style)
