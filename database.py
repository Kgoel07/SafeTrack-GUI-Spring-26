import sqlite3
from datetime import datetime

# data = [(time, node_id, latitude, longitude, status), ...]

def init_db(db:str ="nodes.db"):
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        cur.execute(f'''CREATE TABLE IF NOT EXISTS nodes
                (time TEXT,
                node_id INTEGER,
                latitude REAL,
                longitude REAL,
                status TEXT)''')
        
        
def get_db(db:str = "nodes.db") -> list:
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT *, MAX(time) FROM nodes GROUP BY node_id")
        data = cur.fetchall()
    return data

def add_to_db(vals:tuple, db:str = "nodes.db"):
    if isinstance(vals, tuple) and list(map(type,vals)) == [str, int, float, float, str]:
        print(vals, "VALS")
        with sqlite3.connect(db) as conn:
            conn.execute(f"INSERT INTO nodes VALUES (?,?,?,?,?)",vals)
            try:
                conn.commit()
            except Exception:
                pass
            # emit a signal so UI (or other listeners) can refresh user-visible nodes
            try:
                import login
                # login.user_signals is a QObject with `user_update` signal
                login.user_signals.user_update.emit()
            except Exception as e:
                print(f"[signals] user_update emit failed: {e}")
            
    else:
        print("***ERROR: VALUE FORMATTING FAILED***")

# Deletes rows before given time
def delete_before_time(time, table:str = "nodes", db:str ="nodes.db"):
    time_format = "%Y-%m-%d %H:%M:%S"
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        try:
            time = datetime.fromisoformat(time)
            time = time.strftime(time_format)
            if table == "nodes":
                cur.execute(f'''DELETE FROM nodes WHERE time < ?''', (time,))
                conn.commit()
            elif table == "notifications":
                cur.execute(f'''DELETE FROM notifications WHERE time < ?''', (time,))
                conn.commit()
        except ValueError:
            print("***ERROR: TIME FORMATTING FAILED (YYYY-MM-DD HH:MM:SS)***")
            return -1

def print_db(db:str = "nodes.db"):
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM nodes")
        data = cur.fetchall()
        for row in data:
            print(row, end="\n")

def get_nodes(db:str = "nodes.db") -> list:
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT DISTINCT node_id FROM nodes")
        data = cur.fetchall()
        data = [row[0] for row in data]
    return data if data else []

# Returns most recent row for every node: [(time, node_id, latitude, longitude, status), ...]
def get_latest_node_rows(db:str = "nodes.db") -> list:
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        cur.execute(f'''SELECT n.time, n.node_id, n.latitude, n.longitude, n.status
                        FROM nodes n
                        JOIN (SELECT node_id, MAX(time) AS t FROM nodes GROUP BY node_id) latest
                          ON n.node_id = latest.node_id AND n.time = latest.t
                        GROUP BY n.node_id
                        ORDER BY n.node_id''')
        data = cur.fetchall()
    return data

def get_node_info(node_id:int,db:str = "nodes.db") -> list:
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM nodes WHERE node_id = ? ORDER BY time DESC",(node_id,))
        node_data = cur.fetchall()
    return node_data

def get_recent_info(node_id:int, db:str = "nodes.db") -> list:
    try:
        return [get_node_info(node_id,db)[0]]
    except IndexError:
        return []

# Returns most recent GPS location
def get_GPS(node_id:int, db:str = "nodes.db") -> tuple:
    try:
        data = get_recent_info(node_id, db)
        # Return as stored: (longitude, latitude)
        return data[0][2], data[0][3]
    except IndexError:
        return ()

# Returns most recent status
def get_status(node_id:int, db:str = "nodes.db") -> str:
    try:
        data = get_recent_info(node_id, db)
        return data[0][-1]
    except IndexError:
        return ""

def in_db(node_id:int, db:str = "nodes.db") -> bool:
    if get_status(node_id, db) != "":
        return True
    return False


# Notification functions

# Notif = (time, node_id, status, title, message)

def init_notif_db(db:str = "nodes.db"):
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        cur.execute(f"CREATE TABLE IF NOT EXISTS notifications (time TEXT, node_id INTEGER, status TEXT,Title TEXT, Message TEXT, is_read INTEGER DEFAULT 0)")

def add_notif(vals:tuple, db:str = "nodes.db"):
    with sqlite3.connect(db) as conn:
        conn.execute(f"INSERT INTO notifications (time, node_id, status, Title, Message, is_read) VALUES (?,?,?,?,?,?)",vals)
        try:
            conn.commit()
        except Exception:
            pass

def mark_notif_read(notif_id:int, db:str = "nodes.db"):
    with sqlite3.connect(db) as conn:
        conn.execute(f"UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
        conn.commit()

def get_notifs(db:str = "nodes.db") -> list:
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM notifications")
        data = cur.fetchall()
    return data

def get_unread_notifs(db:str = "nodes.db") -> list:
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT time, node_id, status, Title, Message, is_read FROM notifications WHERE is_read = 0 ORDER BY time DESC")
        data = cur.fetchall()
    return data

def mark_all_notifs_read(db:str = "nodes.db"):
    with sqlite3.connect(db) as conn:
        conn.execute(f"UPDATE notifications SET is_read = 1 WHERE is_read = 0")
        conn.commit()

def get_logs(db:str = "nodes.db") -> list:
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT time, node_id, status, Title, Message FROM notifications ORDER BY time DESC")
        data = cur.fetchall()
    return data

def print_notifs(db:str = "nodes.db",  only_unread:bool = False):
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        if only_unread:
            cur.execute(f"SELECT time, node_id, status, Title, Message FROM notifications WHERE is_read = 0")
        else:
            cur.execute(f"SELECT * FROM notifications")
        data = cur.fetchall()
        for row in data:
            print(row, end="\n")


'''CAUTION: The following functions are for testing purposes only. Do not use in backend code as they may cause data loss.'''

def CLEAR_DB(db:str = "nodes.db"): 
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM nodes")
        conn.commit()

def CLEAR_NOTIF_DB(db:str = "nodes.db"):
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM notifications")
        conn.commit()

if __name__ == "__main__":
    print_db()
    print_notifs()