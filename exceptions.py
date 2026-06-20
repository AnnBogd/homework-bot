"""Кастомные исключения."""


class NoEnvirVariablesError(Exception):
    """Выбросить при отсутствии необходимых переменных окружения."""

    pass


class NotValidHomeworkStatusError(Exception):
    """Выбросить при неожиданном статусе домашней работы."""

    pass


class UnreachableEndpointError(Exception):
    """Выбросить при недоступности эндпоинта."""

    pass
