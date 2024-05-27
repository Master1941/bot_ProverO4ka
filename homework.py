import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import Not200Exception, MsgException

load_dotenv()

logging.basicConfig(level=logging.INFO)

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


def check_tokens():
    """Проверяет доступность переменных окружения."""
    required_tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    return all(required_tokens)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logging.debug('Начала отправки сообщения в Telegram.')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f'Сообщение успешно отправленно: {message}')
    except telegram.error.TelegramError as error:
        msg = (f'Сообщение не отправленно {error}')
        logging.error(msg)
        raise MsgException(msg)


def get_api_answer(timestamp):
    """
    Делает запрос к API-сервиса.
    В случае успешного запроса должна вернуть ответ API,
    приведя его из формата JSON к типам данных Python.
    """
    payload = {'from_date': timestamp}
    try:
        logging.debug('Начала запроса к API.')
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=payload
        )
    except Exception as error:
        raise Exception(f'Любые другие сбои при запросе к эндпоинту: {error}')
    if response.status_code != HTTPStatus.OK:
        msg_error = (
            f'Эндпоинт {ENDPOINT} недоступен: {response.status_code}'
        )
        raise Not200Exception(f'Ошибка: {msg_error}')
    try:
        return response.json()
    except Exception as error:
        raise Exception(f'Ошибка json: {error}')


def check_response(response):
    """
    Проверяет ответ API на соответствие документации.
    В качестве параметра функция получает ответ API,
    приведенный к типам данных Python.
    """
    if not isinstance(response, dict):
        tip = type(response)
        raise TypeError(
            f'Данные не представлены в виде списка! Тип ответа: {tip}'
        )
    if 'homeworks' not in response:
        raise KeyError('В ответе отсутствует ключ "homeworks".')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Данные не представлены в виде списка!')
    if not homeworks:
        raise Exception('Не получен список работ.')
    return homeworks


def parse_status(homework):
    """
    Извлекает из информации о конкретной домашней работе статус этой работы.
    В качестве параметра функция получает только один элемент из списка
    домашних работ. В случае успеха, функция возвращает подготовленную для
    отправки в Telegram строку, содержащую один из вердиктов
    словаря HOMEWORK_VERDICTS.
    """
    if 'homework_name' not in homework:
        raise KeyError('Ключ "homework_name" отсутствует.')
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Статус не коректный: {status}')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        msg = ('Отсутствует переменная окружения.'
               'Программа принудительно останавливается.')
        logging.critical(msg)
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    msg_old = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeforks = check_response(response)
            message = parse_status(homeforks[0])
            if msg_old != message:
                send_message(bot, message)
                timestamp = int(time.time())
                msg_old = message
            else:
                logging.debug('Отсутствие в ответе новых статусов.')
        except MsgException as error:
            logging.debug(f'Ошибка: {error}')
        except (Exception, Not200Exception, KeyError, TypeError) as error:
            message = (f'Сбой в работе программы: {error}')
            logging.error(message)
            send_message(bot, message)
        else:
            logging.info('Итерация прошла без исключений.')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
