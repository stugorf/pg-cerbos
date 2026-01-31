from sqlalchemy import Column, Integer, Text, Boolean, TIMESTAMP, text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Policy(Base):
    __tablename__ = "policies"
    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    path = Column(Text, nullable=False)
    rego_text = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, server_default=text("1"))
    published = Column(Boolean, nullable=False, server_default=text("false"))
    bundle_name = Column(Text, nullable=False, server_default=text("'main'"))
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    created_by = Column(Text)