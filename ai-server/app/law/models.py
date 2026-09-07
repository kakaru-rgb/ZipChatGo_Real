from pydantic import BaseModel, Field


class LawArticle(BaseModel):
    article_key: str
    article_number: str
    article_title: str | None = None
    effective_date: str | None = None
    text: str = Field(min_length=1)


class LawDocument(BaseModel):
    law_name: str
    law_type: str
    law_id: str
    law_serial_number: str
    promulgation_date: str | None = None
    promulgation_number: str | None = None
    effective_date: str | None = None
    revision_type: str | None = None
    source_url: str
    articles: list[LawArticle] = Field(min_length=1)
