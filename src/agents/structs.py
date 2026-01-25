from pydantic import BaseModel, Field
from typing import Literal

class AnalystDecision(BaseModel):
    """시장 분석가의 판단 결과 구조"""
    decision: Literal["CONFIRM", "REJECT"] = Field(..., description="매수 진입 승인 여부")
    confidence: int = Field(..., ge=0, le=100, description="판단에 대한 확신도 (0-100)")
    reasoning: str = Field(..., description="판단 근거 및 기술적 분석 요약")

class GuardianDecision(BaseModel):
    """위험 관리자의 판단 결과 구조"""
    decision: Literal["SAFE", "WARNING"] = Field(..., description="매매 진행 안전 여부")
    reasoning: str = Field(..., description="리스크 분석 내용")
