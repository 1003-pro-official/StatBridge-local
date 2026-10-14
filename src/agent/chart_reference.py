"""Bounded, verified image/PDF references; never execute uploaded content."""
import base64
import io
from pathlib import PurePosixPath
from pydantic import BaseModel, Field, model_validator


class ChartReference(BaseModel):
    name: str = Field(max_length=120)
    mime: str
    data_url: str = Field(max_length=5_600_000)

    @model_validator(mode='after')
    def verify_content(self):
        from PIL import Image
        from pypdf import PdfReader
        allowed = {'image/png': 'PNG', 'image/jpeg': 'JPEG', 'image/webp': 'WEBP', 'application/pdf': 'PDF'}
        if self.mime not in allowed or not self.data_url.startswith(f'data:{self.mime};base64,'):
            raise ValueError('PNG, JPG, WebP 또는 PDF를 올려 주세요.')
        try:
            raw = base64.b64decode(self.data_url.split(',', 1)[1], validate=True)
            if not raw or len(raw) > 4_000_000:
                raise ValueError('참고 파일은 하나당 최대 4MB입니다.')
            if self.mime == 'application/pdf':
                if not raw.startswith(b'%PDF-'):
                    raise ValueError('PDF 형식이 올바르지 않습니다.')
                pdf = PdfReader(io.BytesIO(raw))
                if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 5:
                    raise ValueError('암호 없는 1~5쪽 PDF를 올려 주세요.')
            else:
                with Image.open(io.BytesIO(raw)) as image:
                    if image.format != allowed[self.mime] or image.width * image.height > 16_000_000:
                        raise ValueError('이미지 형식 또는 해상도를 확인해 주세요. 최대 1600만 화소입니다.')
                    image.verify()
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError('읽을 수 없는 파일입니다. 정상 이미지 또는 PDF를 선택해 주세요.') from exc
        self.name = PurePosixPath(self.name.replace('\\', '/')).name or 'reference'
        return self
