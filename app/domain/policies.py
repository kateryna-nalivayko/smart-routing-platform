"""
domain/policies.py

Бізнес-правила (Domain Policies) — інкапсулюють логіку призначення
техніків до заявок, розрахунку штрафів, перевірку feasibility.
"""

from datetime import date
from math import atan2, cos, radians, sin, sqrt

# ══════════════════════════════════════════════════════════════════════
# ROUTING POLICY — Правила призначення техніків
# ══════════════════════════════════════════════════════════════════════

class RoutingPolicy:
    """
    Інкапсулює бізнес-правила розподілу техніків по заявках.
    Незалежний від infrastructure.
    """

    @staticmethod
    def can_assign(technician, service_request) -> tuple[bool, str]:
        """
        Hard constraints — чи може технік виконати заявку?

        Перевірки:
          1. Технік активний
          2. Технік НЕ в forbidden_technicians
          3. Навички відповідають (ієрархія: senior >= medior >= junior)
          4. Capabilities співпадають (фізична витривалість, висота, тощо)
          5. Якщо потрібен пропуск — технік має бути в permit_holders
          6. Технік працює у день візиту

        Returns:
            (can_assign: bool, reason: str)
        """

        # 1. Активність
        if not technician.is_active:
            return False, "Технік неактивний"

        # 2. Forbidden list
        if technician.id in service_request.forbidden_technician_ids:
            return False, "Технік у списку заборонених для цього об'єкта"

        # 3. Навички (ієрархія)
        for required_skill in service_request.required_skills:
            tech_skill = next(
                (s for s in technician.skills
                 if s.service_type == required_skill.service_type),
                None
            )

            if not tech_skill:
                return False, f"Відсутня навичка {required_skill.service_type.value}"

            if tech_skill.level.hierarchy_value < required_skill.level.hierarchy_value:
                return False, (
                    f"Недостатній рівень {required_skill.service_type.value}: "
                    f"потрібен {required_skill.level.value}, є {tech_skill.level.value}"
                )

        # 4. Capabilities (фізичні вимоги)
        req = service_request.requirements
        cap = technician.capabilities

        if req.physically_demanding and not cap.physically_demanding:
            return False, "Потрібна фізична витривалість"

        if req.living_walls and not cap.living_walls:
            return False, "Потрібні навички роботи з living walls"

        if req.heights and not cap.heights:
            return False, "Потрібна готовність до висотних робіт"

        if req.lift and not cap.lift:
            return False, "Потрібен сертифікат оператора підйомника"

        if req.pesticides and not cap.pesticides:
            return False, "Потрібен дозвіл на застосування пестицидів"

        if req.citizenship and not cap.citizenship:
            return False, "Потрібен технік-громадянин країни"

        # 5. Перепустка
        if service_request.requires_permit:
            if technician.id not in service_request.permit_holder_ids:
                return False, "Потрібен пропуск на об'єкт"

        # 6. Робочий графік (перевіримо чи технік працює в день візиту)
        # Це буде перевірятись в optimizer через time_windows

        return True, "OK"

    @staticmethod
    def calculate_preference_score(technician, service_request) -> int:
        """
        Soft constraints — бонус/штраф для OR-Tools.

        Правила:
          - Технік є current_technician → бонус -1000 (негативний = краще для OR-Tools)
          - Технік в preferred_technicians → бонус -500
          - Інше → 0

        Returns:
            Оцінка (негативна = краще, позитивна = гірше)
        """

        # Current technician — найсильніший бонус
        if technician.id == service_request.current_technician_id:
            return -1000

        # Preferred technician
        if technician.id in service_request.preferred_technician_ids:
            return -500

        return 0

    @staticmethod
    def is_optimization_feasible(
        technicians: list,
        service_requests: list,
        target_date: date
    ) -> tuple[bool, str]:
        """
        Перевірка: чи достатньо ресурсів для виконання всіх заявок?

        Правила:
          1. Є хоча б один активний технік
          2. Є хоча б одна pending заявка
          3. Сумарний доступний час техніків >= сумарний час заявок (з буфером 20%)
          4. Навички техніків покривають вимоги хоча б 80% заявок

        Returns:
            (is_feasible: bool, reason: str)
        """

        # 1. Перевірка наявності техніків
        active_techs = [t for t in technicians if t.is_active]
        if not active_techs:
            return False, "Немає активних техніків"

        # 2. Перевірка наявності заявок
        from .value_objects import ServiceStatus
        pending_requests = [
            r for r in service_requests
            if r.status == ServiceStatus.PENDING
        ]
        if not pending_requests:
            return False, "Немає заявок зі статусом PENDING"

        # 3. Перевірка доступного часу
        TRAVEL_TIME_OVERHEAD = 15  # хвилин між зупинками (середнє)

        total_available_minutes = sum(
            t.get_available_minutes_on_date(target_date)
            for t in active_techs
        )

        total_required_minutes = sum(
            r.duration.minutes + TRAVEL_TIME_OVERHEAD
            for r in pending_requests
        )

        # Буфер 20% — не всі заявки вмістяться ідеально
        if total_available_minutes < total_required_minutes * 0.8:
            return False, (
                f"Недостатньо часу: доступно {total_available_minutes} хв, "
                f"потрібно мінімум {int(total_required_minutes * 0.8)} хв"
            )

        # 4. Перевірка покриття навичок
        assignable_count = 0
        for request in pending_requests:
            for tech in active_techs:
                can_assign, _ = RoutingPolicy.can_assign(tech, request)
                if can_assign:
                    assignable_count += 1
                    break  # Хоча б один технік може — достатньо

        coverage = assignable_count / len(pending_requests) * 100

        if coverage < 80:
            return False, (
                f"Недостатнє покриття навичок: лише {coverage:.0f}% заявок "
                f"можуть бути призначені"
            )

        return True, "OK"

    @staticmethod
    def build_assignment_matrix(
        technicians: list,
        service_requests: list
    ) -> dict[tuple, bool]:
        """
        Побудувати матрицю валідних комбінацій (технік, заявка).

        Використовується для фільтрації before OR-Tools.

        Returns:
            Dict[(tech_id, request_id), can_assign: bool]
        """
        matrix = {}

        for tech in technicians:
            for request in service_requests:
                can_assign, _ = RoutingPolicy.can_assign(tech, request)
                matrix[(tech.id, request.id)] = can_assign

        return matrix


# ══════════════════════════════════════════════════════════════════════
# OPTIMIZATION POLICY — Параметри OR-Tools
# ══════════════════════════════════════════════════════════════════════

class OptimizationPolicy:
    """
    Константи, штрафи, параметри для OR-Tools solver.
    """

    # ── Константи ──────────────────────────────────────────────────────
    MAX_DAILY_DISTANCE_KM = 200
    MAX_STOPS_PER_TECHNICIAN = 10
    AVERAGE_SPEED_KM_PER_HOUR = 30
    TRAVEL_TIME_PER_KM_MINUTES = 2  # ~30 км/год
    TIME_BUFFER_BETWEEN_STOPS = 15  # хвилин буфер між зупинками

    # ── Штрафи (Penalties) для OR-Tools ───────────────────────────────
    # Негативні значення = бонус, позитивні = штраф

    # Hard constraint: невиконана заявка
    PENALTY_UNASSIGNED_SERVICE = 10000

    # Soft constraints
    PENALTY_WRONG_TECHNICIAN = 1000      # Технік без preferred/current
    BONUS_PREFERRED_TECHNICIAN = -500    # З preferred list
    BONUS_CURRENT_TECHNICIAN = -1000     # Поточний технік (найсильніше)

    # Пріоритети заявок (множники)
    PRIORITY_WEIGHTS = {
        'low': 100,
        'normal': 1000,
        'high': 5000,
        'urgent': 10000,
    }

    @staticmethod
    def calculate_penalty_for_unassigned(service_request) -> int:
        """
        Розрахунок штрафу за невиконану заявку.
        Залежить від пріоритету.
        """
        base_penalty = OptimizationPolicy.PENALTY_UNASSIGNED_SERVICE
        priority_weight = OptimizationPolicy.PRIORITY_WEIGHTS.get(
            service_request.priority.value,
            1000
        )
        return base_penalty + priority_weight

    @staticmethod
    def build_distance_matrix(
        technicians: list,
        service_sites: list
    ) -> list[list[int]]:
        """
        Матриця відстаней між всіма точками (Haversine formula).

        Структура:
          [Дім Tech1, Дім Tech2, ..., Офіс, Site1, Site2, ...]

        Returns:
            Матриця відстаней у МЕТРАХ (int) для OR-Tools
        """
        all_locations = []

        # Додаємо домашні/офісні адреси техніків
        for tech in technicians:
            if tech.starts_from.value == 'home':
                all_locations.append((tech.home_location.latitude, tech.home_location.longitude))
            else:
                all_locations.append((tech.office_location.latitude, tech.office_location.longitude))

        # Додаємо об'єкти
        for site in service_sites:
            all_locations.append((site.location.latitude, site.location.longitude))

        # Будуємо матрицю
        n = len(all_locations)
        matrix = [[0] * n for _ in range(n)]

        for i in range(n):
            for j in range(n):
                if i != j:
                    lat1, lon1 = all_locations[i]
                    lat2, lon2 = all_locations[j]
                    distance_km = OptimizationPolicy._haversine(lat1, lon1, lat2, lon2)
                    matrix[i][j] = int(distance_km * 1000)  # метри

        return matrix

    @staticmethod
    def build_time_matrix(
        distance_matrix: list[list[int]]
    ) -> list[list[int]]:
        """
        Матриця часу між точками (на основі відстані + швидкість).

        Returns:
            Матриця часу у ХВИЛИНАХ (int) для OR-Tools
        """
        n = len(distance_matrix)
        time_matrix = [[0] * n for _ in range(n)]

        for i in range(n):
            for j in range(n):
                if i != j:
                    distance_km = distance_matrix[i][j] / 1000
                    travel_time = distance_km * OptimizationPolicy.TRAVEL_TIME_PER_KM_MINUTES
                    buffer = OptimizationPolicy.TIME_BUFFER_BETWEEN_STOPS
                    time_matrix[i][j] = int(travel_time + buffer)

        return time_matrix

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Розрахунок відстані між двома точками (Haversine formula).

        Returns:
            Відстань у кілометрах
        """
        R = 6371.0  # Радіус Землі в км

        lat1_rad = radians(lat1)
        lon1_rad = radians(lon1)
        lat2_rad = radians(lat2)
        lon2_rad = radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))

        return R * c

    @staticmethod
    def get_or_tools_parameters() -> dict:
        """
        Параметри для OR-Tools RoutingSearchParameters.

        Returns:
            Dict з параметрами solver
        """
        return {
            'first_solution_strategy': 'PATH_CHEAPEST_ARC',
            'local_search_metaheuristic': 'GUIDED_LOCAL_SEARCH',
            'time_limit_seconds': 30,
            'solution_limit': 100,
            'use_full_propagation': True,
        }