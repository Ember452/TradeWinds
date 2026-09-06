"""SQLAlchemy 模型:一个聚合一个模块,统一继承 Base。"""

from tradewinds.models.base import Base
from tradewinds.models.user import User

__all__ = ["Base", "User"]
