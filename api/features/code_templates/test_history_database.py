"""Real isolated PG: history retention must keep newest versions even on timestamp ties."""
import os

import pytest

from api.features.code_templates import store
from api.platform import pg


def test_history_retains_latest_fifty_on_equal_timestamps(monkeypatch):
    dsn = os.environ.get('AUTH_TEST_PG_DSN')
    if not dsn:
        pytest.skip('Requires disposable auth_test DB')
    monkeypatch.setenv('OG_PG_DSN', dsn)
    monkeypatch.delenv('ROBO_AUTHORITY_SERVER', raising=False)
    assert pg.query('SELECT current_database() AS name')[0]['name'] == 'auth_test'
    store.ensure_schema()
    name, path = 'history-retention-test', 'Test.java'
    pg.execute('DELETE FROM public.app_code_template_history WHERE set_name=%s', (name,))
    pg.execute('DELETE FROM public.app_code_templates WHERE set_name=%s', (name,))
    # Force timestamps to collide, as concurrent writes or imported versions can.
    pg.execute("CREATE OR REPLACE FUNCTION public.test_history_timestamp() RETURNS trigger "
               "LANGUAGE plpgsql AS $$ BEGIN NEW.saved_at := '2026-10-12 00:00:00+00'; "
               "RETURN NEW; END $$")
    pg.execute('CREATE TRIGGER test_history_timestamp BEFORE INSERT ON '
               'public.app_code_template_history FOR EACH ROW '
               'EXECUTE FUNCTION public.test_history_timestamp()')
    try:
        for version in range(55):
            store.save(name, path, f'version {version}', 'test')
        entries = store.history(name, path)
        assert len(entries) == 50
        bodies = [store.history_body(name, path, entry['id']) for entry in entries]
        assert bodies == [f'version {version}' for version in range(54, 4, -1)]
        assert store.get(name, path)['body'] == 'version 54'
        store.save(name, 'Other.java', 'other file', 'test')
        assert len(store.history(name, 'Other.java')) == 1
        assert len(store.history(name, path)) == 50
    finally:
        pg.execute('DROP TRIGGER test_history_timestamp ON public.app_code_template_history')
        pg.execute('DROP FUNCTION public.test_history_timestamp()')
