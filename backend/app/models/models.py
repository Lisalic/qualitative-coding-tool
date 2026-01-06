from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
try:
	from app.database import Base
except Exception:
	from backend.app.database import Base

