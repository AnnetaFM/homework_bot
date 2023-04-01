import logging
import os
import requests
import telegram
import time


from dotenv import load_dotenv
from json import JSONDecodeError

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


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logger.addHandler(
    logging.StreamHandler()
)


def check_tokens():
    '''Проверяем наличие всех необходимых токенов'''
    if not PRACTICUM_TOKEN:
        logging.critical(
            'Не задан токен для доступа к API сервиса Практикум.Домашка')
        raise ValueError(
            'Не задан токен для доступа к API сервиса Практикум.Домашка')
    if not TELEGRAM_TOKEN:
        logging.critical('Не задан токен для доступа к Telegram API')
        raise ValueError('Не задан токен для доступа к Telegram API')
    if not TELEGRAM_CHAT_ID:
        logging.critical('Не задан ID чата для отправки сообщений в Telegram')
        raise ValueError('Не задан ID чата для отправки сообщений в Telegram')


def send_message(bot, message):
    '''Отправка сообщения в Telegram'''
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Сообщение успешно отправлено в Telegram: {message}')
    except Exception as sending_error:
        logging.error(f'Ошибка отправки сообщения в Telegram: {sending_error}')


def get_api_answer(timestamp):
    '''Получение статуса домашней работы с API сервиса Практикум.Домашка'''
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code == 200:
            logger.info(
                f'Запрос получен. Статус ответа: {response.status_code}'
            )
            clear_response = response.json()
            if 'error' in clear_response:
                message = clear_response.get('error')
                logger.error(
                    f'Ошибка формата ответа сервера {message}'
                )
                raise SystemError('Ошибка формата ответа сервера')
            else:
                return clear_response
        else:
            message = ('Сбой в работе программы: '
                       f'Эндпоинт {ENDPOINT} недоступен. '
                       f'Код ответа API: {response.status_code}')
            logger.error(message)
            raise response.raise_for_status()
    except JSONDecodeError:
        logger.error('Ошибка декодирования JSON')
    except requests.RequestException as e:
        logger.error(f'Ошибка запроса API: {e}')


def check_response(response):
    '''Проверка ответа от API сервиса Практикум.Домашка'''
    if not isinstance(response, dict):
        raise TypeError("В ответе от API ожидался словарь")
    if 'homeworks' not in response:
        raise KeyError(
            'В ответе от API отсутствует ожидаемый ключ "homeworks"')
    if not isinstance(response["homeworks"], list):
        raise TypeError('В ответе от API ожидался список домашних работ')
    return True


def parse_status(homework):
    '''Парсинг статуса домашней работы.'''
    homework_name = homework.get('homework_name')
    if homework_name:
        homework_status = homework.get('status')
        if homework_status in HOMEWORK_VERDICTS.keys():
            verdict = HOMEWORK_VERDICTS.get(homework_status)
            message = ('Изменился статус проверки работы '
                       f'"{homework_name}". {verdict}')
            return message
        else:
            error = 'Неожиданный статус домашней работы'
            logger.error(error)
            raise KeyError(error)
    else:
        error = 'Статус домашней работы отсутствует'
        logger.error(error)
        raise KeyError(error)


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            if not response:
                time.sleep(RETRY_PERIOD)
                continue
            if check_response(response):
                homeworks = response['homeworks']
                for homework in homeworks:
                    status = homework['status']
                    if status == 'approved' or 'rejected' or 'reviewing':
                        message = parse_status(homework)
                        send_message(bot, message)
            timestamp = response['current_date']
        except Exception as e:
            logging.error(f'Бот упал с ошибкой: {e}')
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
