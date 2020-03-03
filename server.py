#!/usr/bin/python3
from flask import Flask, render_template, url_for, redirect, request, jsonify
from flask_oidc import OpenIDConnect
import psycopg2
import datetime
from psycopg2 import pool
from dotenv import load_dotenv
import os
load_dotenv()

required_env = ["DBHOST", "DBNAME", "DBUSER", "DBPASS", "APPSECRET", "APPHOST", "APPPORT", "APPDEBUG"]


for env in required_env:
    if(os.getenv(env) is None):
        print("Missing Environment Variable: " + env)
        exit(1)

# SQL statements to create tables if they do not exist
createUsersSQL = "CREATE TABLE IF NOT EXISTS USERS (id serial PRIMARY KEY, username varchar NOT NULL, read boolean DEFAULT TRUE, write boolean DEFAULT FALSE);"
createCLIENTSSQL = "CREATE TABLE IF NOT EXISTS CLIENTS (id serial PRIMARY KEY, client varchar NOT NULL,month DATE NOT NULL, status smallint DEFAULT 0);"
createLOGSSQL = "CREATE TABLE IF NOT EXISTS LOGS (id serial PRIMARY KEY, username varchar NOT NULL, changed_table varchar NOT NULL, row integer NOT NULL, col varchar NOT NULL, previous_value varchar NOT NULL, new_value varchar NOT NULL, timestamp timestamp NOT NULL);"


def malformedBodyResponse(key, msg):
    response = jsonify(error="missing key: [{}]".format(key), msg=msg)
    response.status_code = 400
    return response


# Create the connection pool for PostgreSQL
try:
    postgrePool = psycopg2.pool.SimpleConnectionPool(1, 10,
                                                     host=os.getenv("DBHOST"),
                                                     database=os.getenv("DBNAME"),
                                                     user=os.getenv("DBUSER"),
                                                     password=os.getenv("DBPASS")
                                                     )

    if(postgrePool):
        print("Connected to database successfully")
        psconnection = postgrePool.getconn()
        if(psconnection):
            pscursor = psconnection.cursor()
            pscursor.execute(createCLIENTSSQL)
            pscursor.execute(createLOGSSQL)
            pscursor.execute(createUsersSQL)
            psconnection.commit()
            print("Verified database has required tables")
            pscursor.close()
            postgrePool.putconn(psconnection)

except (Exception, psycopg2.DatabaseError) as error:
    print("Error connecting to database", error)
    if(postgrePool):
        postgrePool.closeall()
    print("PostgreSQL connection pool is closed")
    exit(1)


# Create the flask application
print("Creating Server Application with Flask")
app = Flask(__name__)
app.config.update({
    'SECRET_KEY': os.getenv("APPSECRET"),
    'OIDC_CLIENT_SECRETS': './client_secrets.json',
    'OIDC_ID_TOKEN_COOKIE_SECURE': False,
    'OIDC_SCOPES': ["openid", "profile", "email"],
    'OIDC_CALLBACK_ROUTE': '/authorization-code/callback'
})

oidc = OpenIDConnect(app)


@app.route("/")
@oidc.require_login
def home():
    return redirect(url_for("main"))


@app.route("/login")
@oidc.require_login
def login():
    return redirect(url_for("main"))

@app.route("/logout", methods=["GET", "POST"])
def logout():
    oidc.logout()
    return redirect(url_for("home"))


@app.route("/main", methods=["GET"])
@oidc.require_login
def main():
    user_email = oidc.user_getinfo(["email"])['email']
    
    conn = postgrePool.getconn()
    cursor = conn.cursor()
    
    cursor.execute("SELECT (write) FROM USERS WHERE username=%s;", (user_email,))

    returned_response = cursor.fetchall()
    if(len(returned_response) == 0):
        print("User was not in the database going to add them")
        cursor.execute("INSERT INTO USERS (username) VALUES (%s); SELECT (id) FROM USERS WHERE username=%s;", (user_email,user_email))
        returned_response = cursor.fetchall()
        logSQL = "INSERT INTO LOGS (username, changed_table, row, col, previous_value, new_value, timestamp) VALUES (%s,%s,%s,%s,%s,%s,%s)"
        logTup = ("server", "users", returned_response[0][0], "username", "none", user_email, datetime.datetime.today())
        write_permission = False

        cursor.execute(logSQL, logTup)
        conn.commit()
    else:
        write_permission = returned_response[0][0]
    
    
    cursor.close()
    postgrePool.putconn(conn)

    return render_template("webapp.html", write_permission=write_permission)


@app.route("/api/v1/clients", methods=["GET"])
@oidc.require_login
def getClients():
    # sql
    # SELECT DISTINCT client FROM clients;
    sql = "SELECT DISTINCT client FROM clients;"

    psconnection = postgrePool.getconn()
    pscursor = psconnection.cursor()

    pscursor.execute(sql)
    # values is a list of tupules with 1 value of each client name
    #[('Client-3',), ('Client-2',), ('Client-1',), ('Client-4',), ('Client-0',)]
    values = pscursor.fetchall()

    pscursor.close()
    postgrePool.putconn(psconnection)
    # return a list of client names as strings
    return jsonify(list(map(lambda x: x[0], values)))


@app.route("/api/v1/client", methods=["POST"])
@oidc.require_login
def updateClient():
    # parameters
    # clients primary key
    # client name
    # client year
    # client month
    # client status
    #   primary key makes name year and month not needed
    body = request.json

    if('status' not in body.keys()):
        return malformedBodyResponse("status", "status value required to update row")

    if('prime_key' in body.keys()):

        #check if the primary key exists
        checkSQL = "SELECT * FROM CLIENTS WHERE id=%s;"
        checkTUP = (body['prime_key'],)

        updateSQL = "UPDATE CLIENTS SET status=%s WHERE id=%s;SELECT * FROM CLIENTS WHERE id=%s;"
        updateTUP = tuple(map(int, (
            body['status'],
            body['prime_key'],
            body['prime_key']
        )))

        pscon = postgrePool.getconn()
        cursor = pscon.cursor()

        cursor.execute(checkSQL, checkTUP)
        check_response = cursor.fetchall()

        if(len(check_response) > 0):
            cursor.execute(updateSQL, updateTUP)
            updated_row = cursor.fetchall()

            logSQL = "INSERT INTO LOGS (username, changed_table, row, col, previous_value, new_value, timestamp) VALUES (%s,%s,%s,%s,%s,%s,%s);"
            logTup = (oidc.user_getinfo(["email"])['email'], "clients", updated_row[0][0], "status", check_response[0][3], updated_row[0][3], datetime.datetime.today())
            cursor.execute(logSQL, logTup)
        else:
            cursor.close()
            postgrePool.putconn(pscon)
            prime_key_not_found_response = jsonify(error="Primary key does not exist in the database")
            prime_key_not_found_response.status_code = 404
            return prime_key_not_found_response

        pscon.commit()
        cursor.close()
        postgrePool.putconn(pscon)
        return jsonify(updated_row)

    elif('client_name' in body.keys()):

        # check if the values already exist and if they do then update instead of inserting

        if(all(elem in body.keys() for elem in ["year", "month"])):
            
            #create a date object for the sql tuples
            month_date = datetime.date(int(body['year']), int(body['month']), 1)

            #Might be able to combine SQL operations into a single statement
            #sql and values to check if the client / month already exists in the database
            checkSQL = "SELECT * FROM CLIENTS WHERE client=%s AND month=%s;"
            checkTUP = (
                body['client_name'], 
                month_date
            )
            #sql and values to insert the client, month, and status of a row that doesn't exist
            insertSQL = "INSERT INTO CLIENTS (client,month,status) VALUES (%s,%s,%s);SELECT * FROM CLIENTS WHERE client=%s AND month=%s;"
            insertTUP = (
                body['client_name'],
                month_date,
                int(body['status']),
                body['client_name'], 
                month_date
            )
            #sql and values to Update an existing row with a new status
            updateSQL = "UPDATE CLIENTS SET status=%s WHERE client=%s AND month=%s;SELECT * FROM CLIENTS WHERE client=%s AND month=%s;"
            updateTUP = (
                int(body['status']),
                body['client_name'],
                month_date,
                body['client_name'], 
                month_date
            )

            #get the connection and cursor
            pscon = postgrePool.getconn()
            cursor = pscon.cursor()

            #attempt to get the specific client name and month
            #if it exists then update the value
            #if it doesn't exist then insert it into the database
            
            cursor.execute(checkSQL,checkTUP)
            checkresponse = cursor.fetchall()

            inserted_new_row = False

            if(len(checkresponse) > 0):
                #case where the row already exists
                cursor.execute(updateSQL,updateTUP)
            else:
                #case where the row doesn't exist
                cursor.execute(insertSQL,insertTUP)
                inserted_new_row = True
                
            returned_row = cursor.fetchall()

            logSQL = "INSERT INTO LOGS (username, changed_table, row, col, previous_value, new_value, timestamp) VALUES (%s,%s,%s,%s,%s,%s,%s);"

            if(inserted_new_row):
                logTup = (oidc.user_getinfo(["email"])['email'], "clients", returned_row[0][0], "status", "none", returned_row[0][3], datetime.datetime.today())
            else:
                logTup = (oidc.user_getinfo(["email"])['email'], "clients", returned_row[0][0], "status", checkresponse[0][3], returned_row[0][3], datetime.datetime.today())
            
            cursor.execute(logSQL, logTup)

            pscon.commit()
            #close the cursor and  return the connection
            cursor.close()
            postgrePool.putconn(pscon)
        else:
            return malformedBodyResponse("month & year", "month and year required in database")

        return jsonify(returned_row)

    else:
        return malformedBodyResponse("prime_key | client_name", "prime_key or client_name required to identify row")

    # if the client name exists then create a new row with the time

    # if the client doesn't exist already then fail

    # put the update in the log table

    return jsonify(error="Unreachable case at /api/v1/client")

@app.route('/api/v1/clients/status',methods=["GET"])
@oidc.require_login
def clientStatus():
    required_keys = ("clients[]", "starting_year", "starting_month", "ending_year", "ending_month")
    
    if(all(elem in request.args.keys() for elem in required_keys)):
        #case where all the keys exist in the request

        body = {
            "clients": request.args.getlist('clients[]'),
            "starting_year": request.args.get('starting_year'),
            "starting_month": request.args.get('starting_month'),
            "ending_year": request.args.get('ending_year'),
            "ending_month": request.args.get('ending_month')
        }

        startingdate = datetime.date(
            int(body['starting_year']),
            int(body['starting_month']),
            1
        )
        endingdate = datetime.date(
            int(body['ending_year']),
            int(body['ending_month']),
            1
        )

        sql = "SELECT * FROM CLIENTS WHERE month>=%s AND month<=%s;"
        tup = (startingdate, endingdate)

        conn = postgrePool.getconn()
        cursor = conn.cursor()

        cursor.execute(sql,tup)

        returned_values = cursor.fetchall()

        #filter out all of the values which the client is not requesting
        filtered_values = list(filter(lambda x: x[1] in body['clients'],returned_values))

        cursor.close()
        postgrePool.putconn(conn)

        return jsonify(filtered_values)

    else:
        return malformedBodyResponse(" | ".join(required_keys), "Missing a required key for request")

    return jsonify(error="Case that should not be reached in clients/status")

@app.route("/api/v1/client/new", methods=["POST"])
@oidc.require_login
def newClient():
    # parameters
    # client name

    user_email = oidc.user_getinfo(["email"])['email']
    
    conn = postgrePool.getconn()
    cursor = conn.cursor()
    
    cursor.execute("SELECT (write) FROM USERS WHERE username=%s;", (user_email,))

    write_permission = cursor.fetchall()[0]

    

    if(write_permission):
        if('new_client_name' in request.form.keys()):
            new_client_name = request.form.get('new_client_name')

            cursor.execute("SELECT DISTINCT client FROM clients;")
            if(new_client_name.upper() in list(map(lambda x: x[0].upper(),cursor.fetchall()))):
                pass
            else:
                today = datetime.datetime.today()
                datem = datetime.date(today.year, today.month, 1)
                cursor.execute("INSERT INTO CLIENTS (client, month) VALUES (%s,%s);SELECT * FROM CLIENTS WHERE client=%s AND month=%s",(new_client_name,datem,new_client_name,datem))
                returned_response = cursor.fetchall()
                logSQL = "INSERT INTO LOGS (username, changed_table, row, col, previous_value, new_value, timestamp) VALUES (%s,%s,%s,%s,%s,%s,%s);"
                logTup = (user_email, "clients", returned_response[0][0], "client", "none", new_client_name, datetime.datetime.today())
                cursor.execute(logSQL, logTup)
                conn.commit()

    cursor.close()
    postgrePool.putconn(conn)
    return redirect(url_for('main'))


if __name__ == '__main__':
    print("Starting the server")
    if(os.getenv("APPDEBUG").upper() is 'true'.upper()):
        print("Using the development server")
        app.run(host=os.getenv("APPHOST"), port=os.getenv("APPPORT"), debug=os.getenv("APPDEBUG").upper() is 'true'.upper())
    else:
        print("Using the production server")
        from waitress import serve
        serve(app, host=os.getenv("APPHOST"), port=os.getenv("APPPORT"))
