"""Russian presentation of legacy logs; the Android/billing logic is unchanged."""
import re
import os

MESSAGES = {
    '环境自检通过，可以开始跑号了':'Базовая проверка окружения завершена',
    '已跳过 Play 账号校验（--force）':'Используется текущий аккаунт Play; проверьте его вручную (--force)',
    '设备已连接':'Android подключён', '已连接模拟器':'Эмулятор подключён',
    '已通过 adb root 提权':'Получен root через ADB',
    'frida-server 已在运行':'Frida уже работает в Android',
    'frida-server 已启动':'Frida запущена в Android',
    'frida-server 启动失败':'Не удалось запустить Frida в Android',
    '设备上没有 frida-server，尝试用本地 frida 版本自动下载…':'Загрузка Frida для Android…',
    '计费模块已就位':'Модуль оплаты готов', '计费模块已推送':'Модуль оплаты скопирован',
    '正在推送计费模块（一次性）…':'Копирование модуля оплаты в Android…',
    'Play 商店进程在跑':'Play Маркет работает',
    'Play 商店没在跑，正在拉起…':'Запуск Play Маркета…',
    'Play 商店已拉起':'Play Маркет запущен',
    'Play 商店没起来，计费查询可能卡住（试试手动打开 Play 商店或重启模拟器）':'Play Маркет не запустился. Откройте его вручную или перезапустите MuMu.',
    '注入计费模块，查询免费试用':'Получение предложений Google Play…',
    '检查收银台金额（只在 0 元时确认）':'Проверка суммы в окне оплаты…',
    '已拉起收银台':'Окно оплаты открыто',
    '已确认 0 元订阅':'Скрипт подтвердил подписку с распознанной нулевой ценой',
    '已确认免费试用':'Скрипт подтвердил бесплатный период',
    '没有检测到收银台（可能这个号已经订阅过）':'Окно оплаты не обнаружено; проверьте текущую подписку и экран MuMu.',
    '当前金额':'Сумма сейчас', '不是 0 元，不点确认':'не равна нулю; подтверждение не нажато',
    '该账号不符合免费试用条件':'Аккаунт не соответствует условиям бесплатного периода',
    '不点确认':'Подтверждение не нажато',
    '处理账号':'Текущий аккаунт', '进度':'Шаг', '汇总':'Итог', '结果':'Результат',
    '明细已保存到':'Отчёт сохранён в', '个账号，开始执行':'аккаунт(ов); начало операции', '共':'Всего',
    '正在读取当前订阅的 purchaseToken…':'Чтение токена действующей подписки…',
    '已读到 purchaseToken':'Токен действующей подписки получен',
    '将用订阅升级模式叠加':'Будет использован режим обновления подписки',
    '没读到 purchaseToken，将退回 queryPurchases 方式（可能拿不到）':'Токен не прочитан; попытка запроса действующей подписки через Google Play.',
    '已清除设备代理':'Прокси внутри Android отключён', '原为':'предыдущее значение',
    '避免网络不通':'для подключения к Google Play',
    '已临时关闭':'Временно остановлено приложение Android',
    '它会拦截 Play 的网络':'оно может перехватывать соединение Play Маркета',
    '下载':'Загрузка', '设备':'Android', '未知':'неизвестно', '账号':'аккаунт',
    '未确认到':'Не удалось подтвердить', '已完成':'Завершено',
}

def localize(text):
    for original, translated in sorted(MESSAGES.items(), key=lambda item: -len(item[0])):
        text = text.replace(original, translated)
    # Preserve technical details and numbers from new messages, without showing
    # untranslated Chinese fragments. These can be added to MESSAGES explicitly.
    text = re.sub(r'[\u3400-\u9fff]+', 'сообщение компонента', text)
    text = text.translate(str.maketrans({'：':': ', '（':' (', '）':') ', '，':', ', '。':'.'}))
    if os.environ.get('ANDROID_HELPER_LANGUAGE') == 'en':
        from en_logs import translate
        text = translate(text)
    return text

class RussianStream:
    def __init__(self, stream): self.stream = stream
    def write(self, text): return self.stream.write(localize(text))
    def flush(self): return self.stream.flush()
    def __getattr__(self, name): return getattr(self.stream, name)

def install(sys):
    for name in ('stdout', 'stderr'):
        stream = getattr(sys, name)
        if not isinstance(stream, RussianStream): setattr(sys, name, RussianStream(stream))
