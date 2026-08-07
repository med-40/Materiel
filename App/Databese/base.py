"""
database/base.py
-----------------
Base واحد مشترك لكل موديلات النظام (بغض النظر عن الوحدة). هذا ما يسمح لـ
SQLAlchemy يعرف كل الجداول عند إنشاء قاعدة البيانات، ويسمح بعمل علاقات
(ForeignKey) بين وحدات مختلفة عند الحاجة (مثال: maintenance يشير إلى
equipment) دون كسر استقلالية الوحدات على مستوى الكود.

قاعدة مهمة: لا تُنشئ Base منفصل لكل وحدة. وحدة واحدة = Base واحد للمشروع كله.
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
