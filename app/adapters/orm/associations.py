"""

Таблиці Many-to-Many (association tables) без окремої ORM-моделі.
Первинний ключ у кожній — композитний (всі колонки).

Таблиці:
  technician_skills            — навички техніка
  service_required_skills      — мінімальні навички для об'єкта (hard constraint)
  service_preferred_technicians — бажані техніки для об'єкта (soft constraint)
  service_forbidden_technicians — заборонені техніки (hard constraint)
  service_permit_holders        — техніки з перепусткою (hard constraint)
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from .base import Base, SkillLevel, SkillType

# Навички техніка
# Один технік може мати кілька навичок різного рівня.
# Приклад з Excel: "interior - senior, exterior - medior"
technician_skills = Table(
    "technician_skills",
    Base.metadata,
    Column(
        "technician_id", PGUUID(as_uuid=True),
        ForeignKey("technicians.id", ondelete="CASCADE"),
        primary_key=True,
        comment="FK на техніка — при видаленні техніка записи видаляються каскадно",
    ),
    Column(
        "skill_type", SAEnum(SkillType, name="skill_type_enum"),
        primary_key=True,
        comment="Тип сервісу: interior | exterior | floral",
    ),
    Column(
        "skill_level", SAEnum(SkillLevel, name="skill_level_enum"),
        primary_key=True,
        comment="Рівень кваліфікації: junior | medior | senior",
    ),
    comment="Навички техніка (M2M). PK = (technician_id, skill_type, skill_level)",
)

# Необхідні навички для об'єкта (hard constraint)
# Яку кваліфікацію мінімально вимагає об'єкт.
# Приклад: "interior - medior" → технік має бути не нижче medior.
service_required_skills = Table(
    "service_required_skills",
    Base.metadata,
    Column(
        "service_site_id", PGUUID(as_uuid=True),
        ForeignKey("service_sites.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("skill_type",  SAEnum(SkillType,  name="skill_type_enum"),  primary_key=True),
    Column("skill_level", SAEnum(SkillLevel, name="skill_level_enum"), primary_key=True),
    comment="Мінімальні навички для обслуговування об'єкта (M2M, hard constraint)",
)

# Бажані техніки для об'єкта (soft constraint)
# OR-Tools враховує як бонус, але не як жорстке обмеження.
# З Excel: «Should be serviced by specific technician(s)»
service_preferred_technicians = Table(
    "service_preferred_technicians",
    Base.metadata,
    Column(
        "service_site_id", PGUUID(as_uuid=True),
        ForeignKey("service_sites.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "technician_id", PGUUID(as_uuid=True),
        ForeignKey("technicians.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    comment="Бажані техніки для об'єкта (M2M, soft constraint)",
)

# Заборонені техніки для об'єкта (hard constraint)
# OR-Tools повністю виключає таке призначення.
# З Excel: «Should NOT be serviced by the following technician(s)»
service_forbidden_technicians = Table(
    "service_forbidden_technicians",
    Base.metadata,
    Column(
        "service_site_id", PGUUID(as_uuid=True),
        ForeignKey("service_sites.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "technician_id", PGUUID(as_uuid=True),
        ForeignKey("technicians.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    comment="Заборонені техніки для об'єкта (M2M, hard constraint)",
)

# Техніки з перепусткою / допуском на об'єкт (hard constraint)
# Актуально лише коли service_sites.requires_permit = true.
# Деякі об'єкти (банки, держустанови) вимагають заздалегідь оформленого дозволу.
service_permit_holders = Table(
    "service_permit_holders",
    Base.metadata,
    Column(
        "service_site_id", PGUUID(as_uuid=True),
        ForeignKey("service_sites.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "technician_id", PGUUID(as_uuid=True),
        ForeignKey("technicians.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    comment=(
        "Техніки з перепусткою на об'єкт (M2M, hard constraint). "
        "Актуально лише коли service_sites.requires_permit = true."
    ),
)