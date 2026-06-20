"""Основные функции модуля бота."""

from http import HTTPStatus
import logging
import os
from sys import stdout
import time

from dotenv import load_dotenv
import requests
from telebot import apihelper, TeleBot

from exceptions import (
    NoEnvirVariablesError,
    NotValidHomeworkStatusError,
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
    '%(asctime)s %(funcName)s %(lineno)d [%(levelname)s] %(message)s'
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
        error_message = (
            f'Нет необходимых переменных окружения - {", ".join(errors)}.')
        logger.critical(error_message, exc_info=True)
        raise NoEnvirVariablesError(error_message)


def send_message(bot: TeleBot, message: str) -> None:
    """Отправить сообщение об изменении статуса домашней работы."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except (apihelper.ApiException, requests.RequestException) as error:
        logger.error(
            f'Сбой при отправке сообщения - {error}',
            exc_info=True
        )
    else:
        logger.debug('Сообщение успешно отправлено.')


def get_api_answer(timestamp: int) -> dict:
    """Отправить запрос к API и вернуть ответ в случае успеха."""
    payload = {'from_date': timestamp}
    try:
        logger.info(
            f'Запрос к API. Url {ENDPOINT}, параметры {payload}.'
        )
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload
        )
    except requests.RequestException as error:
        raise ConnectionError(
            f'Ошибка при запросе к API {error}. '
            f'Url {ENDPOINT}, параметры {payload}.'
        )
    if response.status_code != HTTPStatus.OK:
        raise UnreachableEndpointError(
            f'Эндпоинт недоступен -  {response.status_code}'
            f'Url {ENDPOINT}, параметры {payload}.'
        )
    response_data = response.json()
    logger.info('Запрос успешно отправлен.')
    return response_data


def check_response(response: dict) -> list:
    """Проверить ответ API на соответствие с документацией.

    Вернуть список с информацией о домашних работах.
    """
    logger.info('Начало проверки ответа сервера.')
    if not isinstance(response, dict):
        raise TypeError(
            'Ответ API должен быть словарем.'
            f'Получен {type(response).__name__}'
        )
    if 'homeworks' not in response:
        raise KeyError(
            'Содержание ответа не соответствует документации.'
            'Отсутствует ключ homeworks.'
        )
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(
            'Ключ homeworks должен быть списком'
            f'Получен {type(homeworks).__name__}'
        )
    logger.info('Ответ сервера успешно проверен.')
    return homeworks


def parse_status(homework: dict) -> str:
    """Получить статус домашней работы и вернуть сообщение со статусом."""
    logger.info('Начало проверки статуса домашней работы.')
    if 'homework_name' not in homework:
        raise KeyError(
            'В информации о домашней работе нет ключа homework_name')
    homework_name = homework.get('homework_name')
    if 'status' not in homework:
        raise KeyError(
            'В информации о домашней работе нет ключа status')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise NotValidHomeworkStatusError(
            'Неожиданный статус домашней работы в ответе API.')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    logger.info('Статус домашней работы успешно проверен.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> None:
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                homework = homeworks[0]
                status_message = parse_status(homework)
                send_message(bot, status_message)
            else:
                logger.debug('Статус домашней работы не обновился.')
            last_error = ''
            timestamp = response.get('current_date') or int(time.time())
        except Exception as error:
            current_error_message = f'Сбой в работе программы: {error}'
            logger.error(current_error_message, exc_info=True)
            if current_error_message != last_error:
                send_message(bot, current_error_message)
                last_error = current_error_message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
