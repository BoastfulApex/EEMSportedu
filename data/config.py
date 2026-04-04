import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# BOT_TOKEN = str(os.getenv("BOT_TOKEN"))
BOT_TOKEN = str(os.getenv("BOT_TOKEN"))
BOT_USERNAME = str(os.getenv("BOT_USERNAME", ""))  # @username (@ siz)
URL = str(os.getenv("URL"))

# Sayt asosiy manzili — URL ichida /web_app bo'lsa uni olib tashlaymiz
# Masalan: https://example.com/web_app → https://example.com
_raw_url = URL.rstrip('/')
BASE_URL = _raw_url[:-len('/web_app')] if _raw_url.endswith('/web_app') else _raw_url

GROUPS_ID = str(os.getenv("GROUPS_ID")).split(" ")
CHANNEL_ID = str(os.getenv("CHANNEL_ID"))
DATABASE = str(os.getenv("DATABASE"))
PGUSER = str(os.getenv("PGUSER"))
PGPASSWORD = str(os.getenv("PGPASSWORD"))

SLEEP_TIME = .3


ip = str(os.getenv("ip"))

# webhook settings
WEBHOOK_HOST = ip
WEBHOOK_PATH = f'/bot/{BOT_TOKEN}'
PORT = 5432
WEBHOOK_URL = f"https://{WEBHOOK_HOST}:{PORT}{WEBHOOK_PATH}"
WEBAPP_HOST = "0.0.0.0"  # or ip
WEBAPP_PORT = 5432



I18N_DOMAIN = 'testbot'
BASE_DIR = Path(__file__).parent.parent
LOCALES_DIR = BASE_DIR / 'locales'

WEBHOOK_SSL_CERT = BASE_DIR / "webhook_cert.pem"
WEBHOOK_SSL_PRIV = BASE_DIR / "webhook_pkey.pem"

