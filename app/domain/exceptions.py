class DomainException(Exception):
    """
    Базовий клас для всіх доменних винятків.

    Використання:
        raise DomainException("Something went wrong")
    """
    pass


class InvalidServiceStatusTransition(DomainException):
    """
    Неприпустимий перехід статусу заявки.

    Приклад:
        Спроба перейти з COMPLETED → IN_PROGRESS
        raise InvalidServiceStatusTransition(
            f"Cannot transition from {old_status} to {new_status}"
        )
    """
    pass


class ServiceTimeWindowViolation(DomainException):
    """
    Порушення часового вікна заявки.

    Приклад:
        Спроба призначити заявку поза її time window
        raise ServiceTimeWindowViolation(
            f"Service {id} requires visit between {start} and {end}"
        )
    """
    pass


class InvalidRouteOperation(DomainException):
    """
    Неприпустима операція над маршрутом.

    Приклад:
        Спроба додати зупинку до завершеного маршруту
        raise InvalidRouteOperation(
            "Cannot add stop to completed route"
        )
    """
    pass


class TechnicianNotQualified(DomainException):
    """
    Технічник не має необхідної кваліфікації.

    Приклад:
        Технік не має потрібного skill type
        raise TechnicianNotQualified(
            f"Technician {tech_id} lacks {required_skill}"
        )
    """
    pass


class TechnicianNotAvailable(DomainException):
    """
    Технічник недоступний.

    Приклад:
        Технік вже має повний маршрут
        raise TechnicianNotAvailable(
            f"Technician {tech_id} is not available on {date}"
        )
    """
    pass


class OptimizationFailed(DomainException):
    """
    Помилка оптимізації маршрутів.

    Приклад:
        OR-Tools не знайшов рішення
        raise OptimizationFailed(
            "No feasible solution found within time limit"
        )
    """
    pass


class InsufficientTechnicians(DomainException):
    """
    Недостатньо техніків для виконання всіх заявок.

    Приклад:
        raise InsufficientTechnicians(
            f"Need {required} technicians, but only {available} available"
        )
    """
    pass


class NoFeasibleSolution(DomainException):
    """
    Неможливо знайти допустиме рішення.

    Приклад:
        Всі комбінації техніків/заявок порушують constraints
        raise NoFeasibleSolution(
            "No feasible solution exists for given constraints"
        )
    """
    pass


class PermitRequired(DomainException):
    """
    Потрібен permit для виконання заявки.

    Приклад:
        raise PermitRequired(
            f"Service {site_code} requires {permit_difficulty} permit"
        )
    """
    pass


class MultipleTechniciansRequired(DomainException):
    """
    Заявка потребує кількох техніків одночасно.

    Приклад:
        raise MultipleTechniciansRequired(
            f"Service {site_code} requires multiple technicians to work together"
        )
    """
    pass
