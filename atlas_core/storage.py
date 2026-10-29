"""SQLite storage shared by all feature modules."""
from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path
from .sample import demo

class InventoryStore:
    def __init__(self, path): self.path = Path(path)
    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path)
        try:
            with con:
                con.execute('CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY CHECK(id=1), content TEXT NOT NULL)')
                yield con
        finally: con.close()
    def read(self):
        with self.connection() as con:
            row = con.execute('SELECT content FROM inventory WHERE id=1').fetchone()
            if row:
                state = json.loads(row[0]); state.setdefault('stencils', []); return state
            state = demo()
            con.execute('INSERT INTO inventory VALUES (1, ?)', (json.dumps(state),))
            return state
    def write(self, state):
        with self.connection() as con:
            con.execute('INSERT OR REPLACE INTO inventory VALUES (1, ?)', (json.dumps(state),))
