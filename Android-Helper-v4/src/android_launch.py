"""Launch an installed Android app through its actual launcher activity."""
import re
import time

def launch(core, package, wait=20):
    if not core.sh('shell', 'pm', 'path', package).startswith('package:'):
        raise RuntimeError('Приложение не установлено в MuMu: ' + package)
    resolution = core.sh('shell', 'cmd', 'package', 'resolve-activity', '--brief',
                         '-a', 'android.intent.action.MAIN',
                         '-c', 'android.intent.category.LAUNCHER', package)
    components = [s.strip() for s in resolution.splitlines()
                  if s.strip().startswith(package + '/') and re.fullmatch(r'[\w.$/]+', s.strip())]
    if not components: raise RuntimeError('Не найдена стартовая Activity приложения: ' + package)
    component = components[-1]
    output = core.sh('shell', 'am', 'start', '-W', '-n', component, timeout=40)
    if 'Error:' in output: raise RuntimeError('Android не смог открыть приложение: ' + package)
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        pids = re.findall(r'\b\d+\b', core.sh('shell', 'pidof', package))
        if pids: return int(pids[0])
        time.sleep(0.5)
    raise RuntimeError('Приложение не запустилось вовремя. Откройте его вручную в MuMu: ' + package)
