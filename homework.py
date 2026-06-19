"""Основные функции модуля бота."""

from http import HTTPStatus
from json import JSONDecodeError
import logging
import os
from sys import stdout
import time

from dotenv import load_dotenv
import requests
from telebot import TeleBot

from exceptions import (
    NoEnvirVariablesError,
    NotValidHomeworkStatusError,
    NotValidResponseError,
    UnreachableEndpointError,
)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s'
)
handler = logging.StreamHandler(stream=stdout)
handler.setLevel(logging.DEBUG)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens() -> None:
    """Проверить, если все необходимые переменные окружения."""
    env_vars = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
    errors = [env_var for env_var in env_vars if not globals().get(env_var)]
    if errors:
        raise NoEnvirVariablesError(
            f'Нет необходимых переменных окружения - {", ".join(errors)}.')


def send_message(bot: TeleBot, message: str | None) -> None:
    """Отправить сообщение об изменении статуса домашней работы."""
    if message:
        try:
            bot.send_message(TELEGRAM_CHAT_ID, message)
        except Exception as error:
            logger.error(
                f'Сбой при отправке сообщения - {error}',
                exc_info=True
            )
        else:
            logger.debug('Сообщение успешно отправлено.')


def get_api_answer(timestamp: int) -> dict:
    """Отправить запрос к API и вернуть ответ в случае успеха."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.RequestException as error:
        raise UnreachableEndpointError(f'Ошибка при запросе к API {error}')
    if response.status_code != HTTPStatus.OK:
        raise UnreachableEndpointError(
            f'Эндпоинт недоступен -  {response.status_code}')
    try:
        response_data = response.json()
    except JSONDecodeError as error:
        raise NotValidResponseError(f'Невалидный JSON {error}')
    return response_data


def check_response(response: dict) -> tuple:
    """Проверить ответ API на соответствие с документацией.

    Вернуть временную метку и информацию о домашней работе.
    """
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарем.')
    if 'homeworks' not in response or 'current_date' not in response:
        raise NotValidResponseError(
            'Содержание ответа не соответствует документации.')
    homeworks = response.get('homeworks')
    homework = None
    if not isinstance(homeworks, list):
        raise TypeError('Ключ homeworks должен быть списком')
    if homeworks:
        homework = homeworks[0]
    current_date = response.get('current_date')
    if not isinstance(current_date, int):
        raise TypeError('Ключ current_date должен быть числом.')
    return current_date, homework


def parse_status(homework: dict | None) -> str | None:
    """Получить статус домашней работы."""
    if homework:
        if 'homework_name' not in homework:
            raise NotValidResponseError(
                'В информации о домашней работе нет ключа homework_name')
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
        if homework_status not in HOMEWORK_VERDICTS:
            raise NotValidHomeworkStatusError(
                'Неожиданный статус домашней работы в ответе API.')
        verdict = HOMEWORK_VERDICTS.get(homework_status)
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        logger.debug('Нет новых статусов домашней работы.')


def main() -> None:
    """Основная логика работы бота."""
    try:
        check_tokens()
    except NoEnvirVariablesError as error:
        logger.critical(error, exc_info=True)
        return
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error = ''
    while True:
        current_error_message = ''
        try:
            response = get_api_answer(timestamp)
            new_timestamp, homework = check_response(response)
            status_message = parse_status(homework)
            send_message(bot, status_message)
            last_error = ''
            timestamp = new_timestamp
        except (
            NotValidHomeworkStatusError,
            NotValidResponseError,
            TypeError,
            UnreachableEndpointError,
        ) as error:
            current_error_message = f'Возникла ошибка {error}'
            logger.error(error, exc_info=True)
        except Exception as error:
            current_error_message = f'Сбой в работе программы: {error}'
            logger.error(current_error_message, exc_info=True)
        if current_error_message and current_error_message != last_error:
            send_message(bot, current_error_message)
            last_error = current_error_message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
