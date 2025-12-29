import pytest
import sqlite3

@pytest.fixture
def db_conn():
    conn = sqlite3.connect('Celestial.db')
    yield conn
    conn.close()

def test_no_impossible_coordinates(db_conn):
    cursor = db_conn.cursor()
    query = cursor.execute("""SELECT COUNT(*) FROM Celestial 
    WHERE ra < 0 OR ra >= 360
    OR dec < -90 OR dec > 90 """)

    count = query.fetchone()[0]
    assert count == 0 

def test_ra_circular(db_conn):
    start, end = 350, 10
    cursor = db_conn.cursor()
    query = cursor.execute(f"""SELECT COUNT(*) from Celestial
    WHERE ra >= {start} OR ra <= {end} """)
    count = query.fetchone()[0]
    assert count > 0 

def test_float_ra(db_conn):
    cursor = db_conn.cursor()
    query = cursor.execute("""SELECT COUNT(*) FROM Celestial
    WHERE typeof(ra) NOT IN ('real', 'integer');""")

    count = query.fetchone()[0]
    assert count == 0

def test_float_dec(db_conn):
    cursor = db_conn.cursor()
    query = cursor.execute("""SELECT COUNT(*) FROM Celestial
    WHERE typeof(dec) NOT IN ('real', 'integer');""")

    count = query.fetchone()[0]
    assert count == 0