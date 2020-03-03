import psycopg2, hashlib, binascii, os, datetime

def hash_password(password):
    """Hash a password for storing."""
    salt = hashlib.sha256(os.urandom(60)).hexdigest().encode('ascii')
    pwdhash = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'), 
                                salt, 100000)
    pwdhash = binascii.hexlify(pwdhash)
    return (salt + pwdhash).decode('ascii')
 
def verify_password(stored_password, provided_password):
    """Verify a stored password against one provided by user"""
    salt = stored_password[:64]
    stored_password = stored_password[64:]
    pwdhash = hashlib.pbkdf2_hmac('sha512', 
                                  provided_password.encode('utf-8'), 
                                  salt.encode('ascii'), 
                                  100000)
    pwdhash = binascii.hexlify(pwdhash).decode('ascii')
    return pwdhash == stored_password


con = psycopg2.connect(host="localhost",database="example",user="postgres",password="test123")

cursor = con.cursor()

#cursor.execute("DROP TABLE USERS;")
# cursor.execute("DROP TABLE CLIENTS;")
cursor.execute("DROP TABLE LOGS;")

cursor.execute("CREATE TABLE IF NOT EXISTS USERS (id serial PRIMARY KEY, username varchar NOT NULL, read boolean DEFAULT TRUE, write boolean DEFAULT FALSE);")
cursor.execute("CREATE TABLE IF NOT EXISTS CLIENTS (id serial PRIMARY KEY, client varchar NOT NULL,month DATE NOT NULL, status smallint DEFAULT 0);")
cursor.execute("CREATE TABLE IF NOT EXISTS LOGS (id serial PRIMARY KEY, username varchar NOT NULL, changed_table varchar NOT NULL, row integer NOT NULL, col varchar NOT NULL, previous_value varchar NOT NULL, new_value varchar NOT NULL, timestamp timestamp NOT NULL);")
#Insert a new user with the default permission of being able to read but not being able to write
#cursor.execute("INSERT INTO USERS (username) VALUES (%s)", ("testusername",))

#Update the permission of a user
#cursor.execute("UPDATE USERS SET write=true WHERE username=%s", ("testusername",))

#delete all the rows in the table
#cursor.execute("DELETE FROM USERS;")

#add a bunch of test users
#s = ("(%s)," * 10)[:-1]
#cursor.execute("INSERT INTO USERS (username) VALUES {0}".format(s), tuple(map(lambda x: "testuser" + str(x+1) + "@company.org",range(10))))

#add an admin user
#cursor.execute("INSERT INTO USERS (username, write) VALUES ('Ahsan@company.org', true);")

#insert a bunch of clients with months
# clientnames = list(map(lambda x: "Client-" + str(x), range(5)))
# today = datetime.date.today()
# clienttuples = list(map(lambda x: tuple([x ,datetime.date(today.year,today.month,1)]) ,clientnames))
# #print(",".join(clienttuples))
# sql = "INSERT INTO CLIENTS (client, month) VALUES (%s,%s)"
# for client in clienttuples:
#     cursor.execute(sql,client)

sql = "INSERT INTO LOGS (username, changed_table, row, col, previous_value, new_value, timestamp) VALUES (%s,%s,%s,%s,%s,%s,%s)"

logtuples = [
    ("testuser1@company.org", "Users", 4, "write", "false", "true", datetime.datetime.now()),
    ("testuser1@company.org", "Users", 5, "write", "true", "false", datetime.datetime.now()),
    ("testuser1@company.org", "Clients", 14, "id", "null", "14", datetime.datetime.now()),
    ("testuser1@company.org", "Clients", 3, "status", "0", "1", datetime.datetime.now()),
    ("testuser1@company.org", "Clients", 3, "status", "1", "2", datetime.datetime.now()),
]

for tup in logtuples:
    cursor.execute(sql, tup)
    

con.commit()

cursor.close()

con.close()