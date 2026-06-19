"""Кастомные исключения."""


class NoEnvirVariablesError(Exception):
    """Выбросить при отсутствии необходимых переменных окружения."""

    pass


class NotValidResponseError(Exception):
    """Выбросить при несоответствии ответа документации."""

    pass


class NotValidHomeworkStatusError(Exception):
    """Выбросить при неожиданном статусе домашней работы."""

    pass


class UnreachableEndpointError(Exception):
    """Выбросить при недоступности эндпоинта."""

    pass
