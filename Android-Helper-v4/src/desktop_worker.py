"""Bridge between the C# window and the original Android script.

Google sign-in is opened in Android; no account credentials are accepted.
The original billing and confirmation functions are retained in core.py.
Only automatic navigation to the subscription page is disabled: it has its
own button in the application, so it cannot cover the checkout unexpectedly.
"""
import argparse
import json
import os
import sys
import traceback
from pathlib import Path

def configure_streams():
    # PyInstaller may ignore PYTHONIOENCODING at startup on a Western Windows
    # locale. Set the actual streams explicitly before any Russian/Chinese text.
    for name in ('stdout', 'stderr'):
        stream = getattr(sys, name)
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace', line_buffering=True)
    if hasattr(sys.stdin, 'reconfigure'):
        sys.stdin.reconfigure(encoding='utf-8')

def event(kind, **fields):
    if isinstance(fields.get('text'), str):
        from ru_logs import localize
        fields['text'] = localize(fields['text'])
    # JSON events remain ASCII-safe even if an exception precedes initialization.
    print('@@' + json.dumps({'kind': kind, **fields}, ensure_ascii=True), flush=True)

def explain(error):
    text = str(error)
    if '没有 root' in text:
        return 'В MuMu включите Root и перезапустите эмулятор. Затем повторите проверку.'
    if '没有检测到设备' in text:
        return 'MuMu не подключён. Запустите его и включите ADB → Enable local connection.'
    if '找不到 adb' in text:
        return 'ADB отсутствует. Распакуйте весь пакет вместе с папкой runtime.'
    if 'frida-server 启动失败' in text:
        return 'Frida не запустилась внутри Android. Проверьте root; подробности есть в журнале.'
    return text

def main():
    configure_streams()
    import ru_logs
    ru_logs.install(sys)
    if sys.argv[1:] == ['--self-test']:
        import core
        import frida
        assert core.FRIDA_JS and core.MODULE_B64
        print('Проверка UTF-8 завершена ✅', flush=True)
        event('self-test', frida=frida.__version__, resources=True, login_opener=True)
        return 0
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['check', 'list', 'pro12', 'pro6', 'pro6b', 'pro6c', 'subscriptions', 'play', 'open-login', 'open-play', 'open-one'])
    parser.add_argument('--adb', required=True)
    args = parser.parse_args()
    os.environ['ADB_PATH'] = args.adb
    data = Path(os.environ.get('ANDROID_HELPER_DATA', str(Path.cwd())))
    data.mkdir(parents=True, exist_ok=True)
    os.chdir(data)
    import core
    import frida
    import android_launch
    core.ADB_CANDIDATES.insert(0, args.adb)
    core.launch_app = lambda: android_launch.launch(core, core.PKG)

    # Use Frida on the exact Android selected by ADB, not another attached device.
    def selected_frida(timeout=10):
        port = core.sh('forward', 'tcp:0', 'tcp:27042', check=True).strip()
        if not port.isdigit(): raise RuntimeError('ADB не выделил порт для Frida.')
        return frida.get_device_manager().add_remote_device('127.0.0.1:' + port)
    frida.get_usb_device = selected_frida

    # Keep the checkout visible. Explicit navigation is available separately.
    core.verify = lambda: ''
    original_process = core.process
    records = []
    def process(*a, **kw):
        try:
            result = original_process(*a, **kw)
        except Exception as error:
            event('error', text=ru_logs.localize(str(error)))
            raise
        records.append(result)
        event('result', status=result.get('status'), confirmed=bool(result.get('sheet', {}).get('confirmed')))
        return result
    core.process = process

    original_note = core.note
    def note(message):
        if not str(message).strip().startswith('token='): original_note(message)
    core.note = note
    core.step = lambda message: event('progress', text=str(message))
    event('progress', text='Подключение к Android…')
    if args.action == 'open-login':
        core.ADB = args.adb
        core.pick_device()
        core.sh('shell', 'am', 'start', '-a', 'android.settings.ADD_ACCOUNT_SETTINGS',
                '--esa', 'account_types', 'com.google', check=True)
        event('progress', text='Дождитесь загрузки входа Google в MuMu и продолжите вручную.')
        event('navigation', target='open-login')
        return 0
    if args.action in ('open-play', 'open-one'):
        core.ADB = args.adb
        core.pick_device()
        package = core.VENDING if args.action == 'open-play' else core.PKG
        android_launch.launch(core, package)
        event('navigation', target=args.action)
        return 0
    if args.action in ('subscriptions', 'play'):
        core.ADB = args.adb
        core.pick_device()
        uri = 'https://play.google.com/store/account/subscriptions' if args.action == 'subscriptions' else 'market://details?id=com.google.android.apps.subscriptions.red'
        core.sh('shell', 'am', 'start', '-a', 'android.intent.action.VIEW', '-d', uri, check=True)
        event('navigation', target=args.action)
        return 0
    if args.action == 'check':
        sys.argv = ['core', '--check']
        core.main()
        if not core.sh('shell', 'pidof', core.VENDING).strip():
            event('error', text='ADB, root и Frida проверены, но Play Маркет не запустился. Откройте его вручную в MuMu или перезапустите MuMu, затем повторите проверку.')
            return 1
        if not core.sh('shell', 'pm', 'path', core.PKG).startswith('package:'):
            event('error', text='Установите Google One в MuMu. Для этого нажмите «Установить Google One», затем повторите проверку.')
            return 1
        event('ready')
        return 0
    plan = 'pro12' if args.action == 'list' else args.action
    sys.argv = ['core', '--account', 'current@device', '--no-add', '--force', '--plan', plan]
    if args.action == 'list': sys.argv.append('--list')
    if args.action in ('pro6', 'pro6b', 'pro6c'): sys.argv.append('--stack')
    core.main()
    if not records or records[-1].get('status') not in ('listed', 'launched', 'subscribed'):
        event('error', text='Операция не завершилась. Причина указана в журнале. Следующий шаг пока не запускайте.')
        return 1
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except SystemExit as error:
        if isinstance(error.code, str):
            event('error', text=explain(error.code))
            sys.exit(1)
        raise
    except Exception as error:
        event('error', text=explain(error))
        traceback.print_exc()
        sys.exit(1)
