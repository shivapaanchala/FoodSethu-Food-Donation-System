from flask import (
    Flask,
    render_template,
    request,
    session,
    redirect,
    url_for
)

from flask_mysqldb import MySQL
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from datetime import datetime

from config import Config

app = Flask(__name__) 

app.secret_key = Config.SECRET_KEY

app.config["MYSQL_HOST"] = Config.MYSQL_HOST
app.config["MYSQL_USER"] = Config.MYSQL_USER
app.config["MYSQL_PASSWORD"] = Config.MYSQL_PASSWORD
app.config["MYSQL_DB"] = Config.MYSQL_DB

mysql = MySQL(app)

@app.before_request
def require_login():

    allowed_routes = [
        'home',
        'login',
        'register',
        'static'
    ]

    if request.endpoint in allowed_routes:
        return

    if 'user_id' not in session:
        return redirect(url_for('login'))
    

@app.route('/')
def home():

    if 'role' in session:

        if session['role'] == 'hostel':
            return redirect(
                url_for('hostel_dashboard')
            )

        elif session['role'] == 'orphanage':
            return redirect(
                url_for('orphanage_dashboard')
            )

    return render_template('index.html')

@app.route('/test-db')
def test_db():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT 1")
        cur.close()
        return "Database Connected Successfully!"
    except Exception as e:
        return f"Connection Error: {str(e)}"
    

    
@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        full_name = request.form['full_name']
        email = request.form['email']

        password = generate_password_hash(
    request.form['password']
)
        
        role = request.form['role']

        cur = mysql.connection.cursor()

        cur.execute(
            """
            SELECT *
            FROM users
            WHERE email=%s
            """,
            (email,)
        )

        existing_user = cur.fetchone()

        if existing_user:

           cur.close()

           return render_template(
               'message.html',
               status="warning",
               message="Email already registered. Please use another email.",
               next_url=url_for('register'),
               button_text="Back To Registration"
            )
        
        cur.execute(
            """
            INSERT INTO users(full_name, email, password, role)
            VALUES(%s, %s, %s, %s)
            """,
            (full_name, email, password, role)
        )

        mysql.connection.commit()

        cur.close()

        return render_template(
           'message.html',
           status="success",
           message="Your registration has been successful!",
           next_url=url_for('login'),
           button_text="Go To Login"
        )

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        login_input = request.form['login_input']
        password = request.form['password']

        cur = mysql.connection.cursor()

        cur.execute(
            """
            SELECT *
            FROM users
            WHERE email=%s OR full_name=%s
            """,
            (login_input, login_input)
        )

        user = cur.fetchone()

        cur.close()

        if user:

            stored_password = user[3]
            role = user[4]

            if check_password_hash(
                stored_password,
                password
            ):

                session['user_id'] = user[0]
                session['user_name'] = user[1]
                session['role'] = user[4]

                if role == "hostel":
                    return redirect(
                        url_for('hostel_dashboard')
                    )

                elif role == "orphanage":
                    return redirect(
                        url_for('orphanage_dashboard')
                    )

        return "Invalid Username/Email or Password"

    return render_template('login.html')

@app.route('/add-food', methods=['GET', 'POST'])
def add_food():

    if session['role'] != 'hostel':
        return redirect(url_for('login'))

    if request.method == 'POST':

        food_item = request.form['food_item']
        quantity = request.form['quantity']
        location = request.form['location']
        prepared_time = request.form['prepared_time']
        expiry_time = request.form['expiry_time']

        cur = mysql.connection.cursor()

        cur.execute(
            """
            INSERT INTO food_donations
            (
                hostel_id,
                food_item,
                quantity,
                location,
                prepared_time,
                expiry_time
            )
            VALUES(%s,%s,%s,%s,%s,%s)
            """,
            (
                session['user_id'],
                food_item,
                quantity,
                location,
                prepared_time,
                expiry_time
            )
        )

        mysql.connection.commit()

        cur.close()

        return render_template(
            'donation_added.html'
        )

    return render_template('add_food.html')

@app.route('/view-donations')
def view_donations():

    if session['role'] != 'orphanage':
        return redirect(url_for('login'))

    print("VIEW DONATIONS FUNCTION RUNNING")

    location = request.args.get('location')

    cur = mysql.connection.cursor()

    if location:

        print("SEARCHED LOCATION =", location)

        cur.execute("""
            SELECT *
            FROM food_donations
            WHERE status='Available'
            AND location LIKE %s
        """, (f"%{location}%",))
    else:
        cur.execute("""
            SELECT *
            FROM food_donations
            WHERE status='Available'
        """)

    donations = cur.fetchall()

    print("RESULT =", donations)

    cur.close()

    updated_donations = []

    current_time = datetime.now().time()

    for donation in donations:

        expiry_time = donation[6]

        warning = "Safe"

        current_seconds = (
            current_time.hour * 3600 +
            current_time.minute * 60 +
            current_time.second
        )

        expiry_seconds = expiry_time.total_seconds()

        remaining_seconds = expiry_seconds - current_seconds

        if remaining_seconds <= 7200:
            warning = "⚠ Expires Soon"

        if remaining_seconds <= 0:
            warning = "❌ Expired"

        updated_donations.append(
            donation + (warning,)
        )

    return render_template(
        'view_donations.html',
        donations=updated_donations
    )

@app.route('/accept-donation/<int:donation_id>')
def accept_donation(donation_id):

    cur = mysql.connection.cursor()

    cur.execute(
        """
        UPDATE food_donations
        SET status='Accepted'
        WHERE id=%s
        """,
        (donation_id,)
    )

    mysql.connection.commit()

    cur.close()

    return "Donation Accepted Successfully!"

@app.route('/my-donations')
def my_donations():

    if session['role'] != 'hostel':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    cur.execute(
        """
        SELECT *
        FROM food_donations
        WHERE hostel_id = %s
        """,
        (session['user_id'],)
    )

    donations = cur.fetchall()

    cur.close()

    return render_template(
        'my_donations.html',
        donations=donations
    )

@app.route('/profile')
def profile():

    if 'user_id' not in session:
        return "Not Logged In"

    return f"""
    User ID: {session['user_id']} <br>
    Name: {session['user_name']} <br>
    Role: {session['role']}
    """


@app.route('/check-secret')
def check_secret():
    return str(app.secret_key) 

@app.route('/test-session')
def test_session():

    session['test'] = 'working'

    return "Session Saved"

@app.route('/hostel-dashboard')
def hostel_dashboard():

    if session['role'] != 'hostel':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    cur.execute(
        """
        SELECT COUNT(*)
        FROM food_donations
        WHERE hostel_id=%s
        """,
        (session['user_id'],)
    )

    total = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*)
        FROM food_donations
        WHERE hostel_id=%s
        AND status='Accepted'
        """,
        (session['user_id'],)
    )

    accepted = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*)
        FROM food_donations
        WHERE hostel_id=%s
        AND status='Available'
        """,
        (session['user_id'],)
    )

    available = cur.fetchone()[0]

    cur.close()

    return render_template(
        'hostel_dashboard.html',
        total=total,
        accepted=accepted,
        available=available
    ) 

@app.route('/orphanage-dashboard')
def orphanage_dashboard():

    if session['role'] != 'orphanage':
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    cur.execute(
        """
        SELECT COUNT(*)
        FROM food_donations
        WHERE status='Available'
        """
    )

    available = cur.fetchone()[0]

    cur.execute(
        """
        SELECT COUNT(*)
        FROM food_donations
        WHERE status='Accepted'
        """
    )

    accepted = cur.fetchone()[0]

    cur.close()

    return render_template(
        'orphanage_dashboard.html',
        available=available,
        accepted=accepted
    )

@app.route('/mark-delivered/<int:donation_id>')
def mark_delivered(donation_id):

    cur = mysql.connection.cursor()

    cur.execute(
        """
        UPDATE food_donations
        SET status='Delivered'
        WHERE id=%s
        AND hostel_id=%s
        """,
        (
            donation_id,
            session['user_id']
        )
    )

    mysql.connection.commit()

    if cur.rowcount == 0:

        cur.close()

        return """
        <div style='
            text-align:center;
            margin-top:100px;
            font-size:25px;
            color:red;
        '>

        ⚠ Access Denied!

        <br><br>

        You cannot modify another user's donation.

        <br><br>

        <a href='/hostel-dashboard'>
            Back To Dashboard
        </a>

        </div>
        """

    cur.close()

    return redirect('/my-donations')

@app.route('/donation-history')
def donation_history():

    cur = mysql.connection.cursor()

    cur.execute(
        """
        SELECT *
        FROM food_donations
        WHERE status IN ('Accepted', 'Delivered')
        """
    )

    donations = cur.fetchall()

    cur.close()

    return render_template(
        'donation_history.html',
        donations=donations
    )

@app.route('/delete-donation/<int:donation_id>')
def delete_donation(donation_id):

    cur = mysql.connection.cursor()

    cur.execute(
        """
        DELETE FROM food_donations
        WHERE id=%s
        AND hostel_id=%s
        """,
        (
           donation_id,
           session['user_id']
        )
   )

    mysql.connection.commit()

    if cur.rowcount == 0:

        cur.close()

        return """
        <div style='
            text-align:center;
            margin-top:100px;
            font-size:25px;
            color:red;
        '>

        ⚠ Access Denied!

        <br><br>

        You cannot delete another user's donation.

        <br><br>

        <a href='/hostel-dashboard'>
            Back To Dashboard
        </a>

        </div>
        """

    cur.close()

    return redirect('/my-donations')

@app.route('/edit-donation/<int:donation_id>', methods=['GET', 'POST'])
def edit_donation(donation_id):

    if request.method == 'POST':

        food_item = request.form['food_item']
        quantity = request.form['quantity']
        location = request.form['location']
        prepared_time = request.form['prepared_time']
        expiry_time = request.form['expiry_time']

        cur = mysql.connection.cursor()

        cur.execute(
            """
            UPDATE food_donations
            SET food_item=%s,
                quantity=%s,
                location=%s,
                prepared_time=%s,
                expiry_time=%s
            WHERE id=%s
            AND hostel_id=%s
            """,
            (
                food_item,
                quantity,
                location,
                prepared_time,
                expiry_time,
                donation_id,
                session['user_id']
            )
        )

        mysql.connection.commit()

        cur.close()

        return redirect('/my-donations')

    cur = mysql.connection.cursor()

    cur.execute(
    """
    SELECT *
    FROM food_donations
    WHERE id=%s
    AND hostel_id=%s
    """,
   (
        donation_id,
        session['user_id']
   )
   )
    donation = cur.fetchone()

    if not donation:

        cur.close()

        return """
        <div style='
            text-align:center;
            margin-top:100px;
            font-size:25px;
            color:red;
        '>

        ⚠ Access Denied!<br><br>

        You cannot edit another user's donation.

        <br><br>

        <a href='/hostel-dashboard'>
            Back To Dashboard
        </a>

        </div>
        """

    cur.close()

    return render_template(
    'edit_donation.html',
    donation=donation
    )

@app.route('/logout')
def logout():

    session.clear()

    return redirect(url_for('login'))


if __name__ == "__main__":
    app.run(debug=True) 
