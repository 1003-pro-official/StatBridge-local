from typing import Literal
from pydantic import Field,model_validator
from expression_tree_schema import ClosedModel,SourceSelection,MAX_SOURCES

class MissingInput(ClosedModel):
    alias:str=Field(pattern=r'^[a-z][a-z0-9_]{0,47}$')
    required_data:str=Field(min_length=1,max_length=200)
    reason:str=Field(min_length=1,max_length=500)
    unit:str=Field(default='',max_length=100)
    frequency:Literal['D','M','Q','S','Y']
    lookback:int=Field(default=0,ge=0,le=6000)

class PartialInputs(ClosedModel):
    action:Literal['request_inputs']
    calculation_guide:str=Field(default='',max_length=1800)
    available_sources:list[SourceSelection]=Field(default_factory=list,max_length=MAX_SOURCES)
    missing:list[MissingInput]=Field(min_length=1,max_length=MAX_SOURCES)
    start_period:str=Field(pattern=r'^\d{4}(?:\d{2}){0,2}$')
    end_period:str=Field(pattern=r'^\d{4}(?:\d{2}){0,2}$')

    @model_validator(mode='after')
    def same_frequency(self):
        if len(self.available_sources)+len(self.missing)>MAX_SOURCES:
            raise ValueError(f'API 자료와 보완 파일은 합계 최대 {MAX_SOURCES}개 시계열입니다.')
        if len({s.frequency for s in self.available_sources}|{s.frequency for s in self.missing})!=1:
            raise ValueError('API 자료와 보완 파일에는 같은 주기가 필요합니다.')
        return self
