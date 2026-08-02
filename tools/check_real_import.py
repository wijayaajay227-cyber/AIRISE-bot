import importlib
m = importlib.import_module('real')
print('MODULE_OK', getattr(m, 'BOT_NAME', 'NO_NAME'))
