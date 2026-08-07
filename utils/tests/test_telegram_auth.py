import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from django.test import TestCase, override_settings

from utils.telegram_auth import verify_init_data, get_telegram_user_id, InitDataError

TEST_TOKEN = "123456:TEST-TOKEN-FOR-SIGNATURE-CHECK"


def make_init_data(token=TEST_TOKEN, user_id=555, auth_date=None, extra=None):
    """Telegram algoritmi bo'yicha haqiqiy imzo hosil qiladi."""
    fields = {
        'auth_date': str(int(auth_date if auth_date is not None else time.time())),
        'query_id': 'AAH_test',
        'user': json.dumps({'id': user_id, 'first_name': 'Test'}, separators=(',', ':')),
    }
    if extra:
        fields.update(extra)
    check_string = '\n'.join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields['hash'] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


@override_settings(BOT_TOKEN=TEST_TOKEN)
class VerifyInitDataTests(TestCase):

    def test_valid_signature_accepted(self):
        data = verify_init_data(make_init_data(user_id=777))
        self.assertEqual(data['user']['id'], 777)

    def test_get_telegram_user_id_returns_signed_id(self):
        self.assertEqual(get_telegram_user_id(make_init_data(user_id=999)), 999)

    def test_one_character_change_rejected(self):
        init_data = make_init_data()
        hash_value = init_data.rsplit('hash=', 1)[1]
        flipped = ('b' if hash_value[0] != 'b' else 'c') + hash_value[1:]
        tampered = init_data.replace(f"hash={hash_value}", f"hash={flipped}")
        with self.assertRaises(InitDataError):
            verify_init_data(tampered)

    def test_modified_user_id_rejected(self):
        """Imzo o'zgarmasdan user.id almashtirilsa — rad etilishi shart."""
        init_data = make_init_data(user_id=111)
        tampered = init_data.replace('%22id%22%3A111', '%22id%22%3A222')
        self.assertNotEqual(tampered, init_data)
        with self.assertRaises(InitDataError):
            verify_init_data(tampered)

    def test_wrong_token_rejected(self):
        with self.assertRaises(InitDataError):
            verify_init_data(make_init_data(token="999:OTHER-BOT-TOKEN"))

    def test_missing_hash_rejected(self):
        with self.assertRaises(InitDataError):
            verify_init_data("user=%7B%22id%22%3A1%7D&auth_date=1")

    def test_empty_init_data_rejected(self):
        with self.assertRaises(InitDataError):
            verify_init_data("")

    def test_expired_init_data_rejected(self):
        old = time.time() - 7200
        with self.assertRaises(InitDataError):
            verify_init_data(make_init_data(auth_date=old), max_age_seconds=3600)

    @override_settings(BOT_TOKEN='')
    def test_unset_token_closes_endpoint(self):
        """BOT_TOKEN sozlanmagan bo'lsa — ochiq qolmasligi, xato ko'tarishi shart."""
        with self.assertRaises(InitDataError):
            verify_init_data(make_init_data())
