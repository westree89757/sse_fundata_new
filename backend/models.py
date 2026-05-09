from pydantic import BaseModel
from typing import Optional


class ETFBasic(BaseModel):
    code: str
    name: str
    total_shares: Optional[float] = None
    nav: Optional[float] = None


class ETFDaily(BaseModel):
    code: str
    date: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    total_shares: Optional[float] = None
    turnover: Optional[float] = None


class ETFBasicResponse(ETFBasic):
    latest_volume: Optional[float] = None
    latest_date: Optional[str] = None


class ETFListResponse(BaseModel):
    etfs: list[ETFBasicResponse]


class IndexDaily(BaseModel):
    date: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
