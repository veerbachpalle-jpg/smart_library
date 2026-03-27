import sqlite3
from datetime import date, datetime, timedelta
from flask import Flask, render_template, request, redirect, jsonify, session
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = "secret123"
DATABASE = 'books.db'

# ─── Email Config ────────────────────────────────────────────────
EMAIL_SENDER   = "your_email@gmail.com"
EMAIL_PASSWORD = "your_app_password"
FINE_PER_DAY   = 5
ISSUE_DAYS     = 7

def send_email(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From']    = EMAIL_SENDER
        msg['To']      = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

# ─── DB ──────────────────────────────────────────────────────────
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def get_all_books():
    conn = get_db_connection()
    books = conn.execute("SELECT * FROM books LIMIT 50").fetchall()
    conn.close()
    return books

def search_books(query):
    conn = get_db_connection()
    books = conn.execute(
        "SELECT * FROM books WHERE title LIKE ? OR authors LIKE ?",
        ('%'+query+'%', '%'+query+'%')
    ).fetchall()
    conn.close()
    return books

def calculate_fine(due_date_str):
    if not due_date_str:
        return 0
    due   = datetime.strptime(due_date_str, "%Y-%m-%d").date()
    today = date.today()
    return max(0, (today - due).days * FINE_PER_DAY)

def days_remaining(due_date_str):
    if not due_date_str:
        return None
    due   = datetime.strptime(due_date_str, "%Y-%m-%d").date()
    today = date.today()
    return (due - today).days   # negative = overdue

# ─── Auth ────────────────────────────────────────────────────────
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
        conn.close()
        if user:
            session['user'] = user['username']
            session['role'] = user['role']
            return redirect('/')
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email    = request.form.get('email','')
        conn = get_db_connection()
        if conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone():
            conn.close()
            return render_template("signup.html", error="User already exists")
        conn.execute(
            "INSERT INTO users (username,password,role,email) VALUES (?,?,'student',?)",
            (username, password, email)
        )
        conn.commit()
        conn.close()
        if email:
            send_email(email, "Welcome to E-Library",
                f"<h2>Welcome, {username}!</h2><p>Your account has been created. Happy reading!</p>")
        return redirect('/login')
    return render_template("signup.html")

# ─── Home ────────────────────────────────────────────────────────
@app.route('/')
def home():
    books = get_all_books()
    # cart count for badge
    cart_count = 0
    if session.get('user'):
        conn = get_db_connection()
        cart_count = conn.execute(
            "SELECT COUNT(*) FROM cart WHERE username=?", (session['user'],)
        ).fetchone()[0]
        conn.close()
    return render_template("index.html", books=books, cart_count=cart_count)

@app.route('/search')
def search():
    query = request.args.get('q','')
    books = search_books(query)
    return jsonify([dict(b) for b in books])

# ─── Book Detail Page ────────────────────────────────────────────
@app.route('/book/<isbn>')
def book_detail(isbn):
    conn = get_db_connection()
    book = conn.execute("SELECT * FROM books WHERE isbn13=?", (isbn,)).fetchone()

    issue_info  = None
    days_left   = None
    in_cart     = False
    already_bought = False

    if session.get('user'):
        issue_info = conn.execute(
            "SELECT * FROM issued_books WHERE isbn=? AND username=? ORDER BY id DESC LIMIT 1",
            (isbn, session['user'])
        ).fetchone()
        if issue_info:
            days_left = days_remaining(issue_info['due_date'])

        in_cart = conn.execute(
            "SELECT 1 FROM cart WHERE username=? AND isbn=?",
            (session['user'], isbn)
        ).fetchone() is not None

        already_bought = conn.execute(
            "SELECT 1 FROM purchases WHERE username=? AND isbn=?",
            (session['user'], isbn)
        ).fetchone() is not None

    conn.close()
    return render_template("book_detail.html",
        book=book,
        issue_info=issue_info,
        days_left=days_left,
        in_cart=in_cart,
        already_bought=already_bought
    )

# ─── Issue / Return ──────────────────────────────────────────────
@app.route('/issue/<isbn>')
def issue_book(isbn):
    if not session.get('user'):
        return redirect('/login')
    conn = get_db_connection()
    due_date = (date.today() + timedelta(days=ISSUE_DAYS)).strftime("%Y-%m-%d")
    conn.execute(
        "INSERT INTO issued_books (username,isbn,issue_date,due_date) VALUES (?,?,DATE('now'),?)",
        (session['user'], isbn, due_date)
    )
    conn.execute("UPDATE books SET is_available=0 WHERE isbn13=?", (isbn,))
    conn.commit()
    user = conn.execute("SELECT email FROM users WHERE username=?", (session['user'],)).fetchone()
    book = conn.execute("SELECT title FROM books WHERE isbn13=?", (isbn,)).fetchone()
    conn.close()
    if user and user['email']:
        send_email(user['email'], "Book Issued - E-Library",
            f"<h2>Book Issued!</h2><p><b>{book['title']}</b></p>"
            f"<p>Due Date: <b>{due_date}</b></p>"
            f"<p>Fine: Rs.{FINE_PER_DAY}/day after due date.</p>")
    return redirect(f'/book/{isbn}')

@app.route('/return/<isbn>')
def return_book(isbn):
    if not session.get('user'):
        return redirect('/login')
    conn = get_db_connection()
    record = conn.execute(
        "SELECT * FROM issued_books WHERE isbn=? AND username=? ORDER BY id DESC LIMIT 1",
        (isbn, session['user'])
    ).fetchone()
    fine = calculate_fine(record['due_date']) if record else 0
    conn.execute("DELETE FROM issued_books WHERE isbn=? AND username=?", (isbn, session['user']))
    conn.execute("UPDATE books SET is_available=1 WHERE isbn13=?", (isbn,))
    conn.commit()
    user = conn.execute("SELECT email FROM users WHERE username=?", (session['user'],)).fetchone()
    book = conn.execute("SELECT title FROM books WHERE isbn13=?", (isbn,)).fetchone()
    conn.close()
    if user and user['email']:
        fine_msg = f"<p>Fine: Rs.{fine}</p>" if fine > 0 else "<p>Returned on time!</p>"
        send_email(user['email'], "Book Returned - E-Library",
            f"<h2>Book Returned!</h2><p><b>{book['title']}</b></p>{fine_msg}")
    if fine > 0:
        return redirect(f'/fine/{isbn}/{fine}')
    return redirect(f'/book/{isbn}')

@app.route('/fine/<isbn>/<int:fine>')
def fine_page(isbn, fine):
    conn = get_db_connection()
    book = conn.execute("SELECT title FROM books WHERE isbn13=?", (isbn,)).fetchone()
    conn.close()
    return render_template("fine.html", book=book, fine=fine)

# ─── Cart ────────────────────────────────────────────────────────
@app.route('/cart/add/<isbn>')
def cart_add(isbn):
    if not session.get('user'):
        return redirect('/login')
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO cart (username,isbn,added_date) VALUES (?,?,DATE('now'))",
            (session['user'], isbn)
        )
        conn.commit()
    except:
        pass
    conn.close()
    return redirect(f'/book/{isbn}')

@app.route('/cart/remove/<isbn>')
def cart_remove(isbn):
    if not session.get('user'):
        return redirect('/login')
    conn = get_db_connection()
    conn.execute("DELETE FROM cart WHERE username=? AND isbn=?", (session['user'], isbn))
    conn.commit()
    conn.close()
    return redirect('/cart')

@app.route('/cart')
def cart():
    if not session.get('user'):
        return redirect('/login')
    conn = get_db_connection()
    items = conn.execute("""
        SELECT cart.isbn, cart.added_date, books.title, books.authors,
               books.thumbnail, books.price, books.average_rating
        FROM cart
        JOIN books ON cart.isbn = books.isbn13
        WHERE cart.username=?
        ORDER BY cart.added_date DESC
    """, (session['user'],)).fetchall()
    conn.close()
    total = sum(i['price'] for i in items if i['price'])
    return render_template("cart.html", items=items, total=total)

# ─── Buy single from cart ────────────────────────────────────────
@app.route('/cart/buy/<isbn>')
def cart_buy_one(isbn):
    if not session.get('user'):
        return redirect('/login')
    conn = get_db_connection()
    book = conn.execute("SELECT * FROM books WHERE isbn13=?", (isbn,)).fetchone()
    conn.execute(
        "INSERT INTO purchases (username,isbn,price,purchase_date) VALUES (?,?,?,DATE('now'))",
        (session['user'], isbn, book['price'])
    )
    conn.execute("DELETE FROM cart WHERE username=? AND isbn=?", (session['user'], isbn))
    conn.commit()
    user = conn.execute("SELECT email FROM users WHERE username=?", (session['user'],)).fetchone()
    conn.close()
    if user and user['email']:
        send_email(user['email'], "Purchase Confirmed - E-Library",
            f"<h2>Purchase Successful!</h2><p><b>{book['title']}</b></p><p>Rs.{book['price']}</p>")
    return redirect('/cart')

# ─── Checkout all ────────────────────────────────────────────────
@app.route('/cart/checkout', methods=['POST'])
def cart_checkout():
    if not session.get('user'):
        return redirect('/login')
    conn = get_db_connection()
    items = conn.execute("""
        SELECT cart.isbn, books.title, books.price
        FROM cart JOIN books ON cart.isbn=books.isbn13
        WHERE cart.username=?
    """, (session['user'],)).fetchall()

    total = 0
    purchased_titles = []
    for item in items:
        conn.execute(
            "INSERT INTO purchases (username,isbn,price,purchase_date) VALUES (?,?,?,DATE('now'))",
            (session['user'], item['isbn'], item['price'])
        )
        total += item['price'] or 0
        purchased_titles.append(item['title'])

    conn.execute("DELETE FROM cart WHERE username=?", (session['user'],))
    conn.commit()

    user = conn.execute("SELECT email FROM users WHERE username=?", (session['user'],)).fetchone()
    conn.close()

    if user and user['email'] and purchased_titles:
        book_list = "".join(f"<li>{t}</li>" for t in purchased_titles)
        send_email(user['email'], "Order Confirmed - E-Library",
            f"<h2>Order Confirmed!</h2><ul>{book_list}</ul><p><b>Total: Rs.{total:.0f}</b></p><p>Thank you!</p>")

    return jsonify({
        "success": True,
        "count": len(purchased_titles),
        "total": total,
        "titles": purchased_titles
    })

# ─── Profile ─────────────────────────────────────────────────────
@app.route('/profile')
def profile():
    if not session.get('user'):
        return redirect('/login')
    conn = get_db_connection()
    purchases = conn.execute("""
        SELECT purchases.*, books.title FROM purchases
        JOIN books ON purchases.isbn=books.isbn13
        WHERE purchases.username=?
    """, (session['user'],)).fetchall()
    issued = conn.execute("""
        SELECT issued_books.*, books.title, books.isbn13 FROM issued_books
        JOIN books ON issued_books.isbn=books.isbn13
        WHERE issued_books.username=?
    """, (session['user'],)).fetchall()
    user_info = conn.execute("SELECT email FROM users WHERE username=?", (session['user'],)).fetchone()
    conn.close()
    issued_with_fines = [{
        'record': b,
        'fine': calculate_fine(b['due_date']),
        'days_left': days_remaining(b['due_date'])
    } for b in issued]
    return render_template("profile.html",
        purchases=purchases,
        purchase_count=len(purchases),
        issued=issued_with_fines,
        user_email=user_info['email'] if user_info else ''
    )

# ─── Purchases history ───────────────────────────────────────────
@app.route('/purchases')
def purchases():
    if not session.get('user'):
        return redirect('/login')
    conn = get_db_connection()
    data = conn.execute(
        "SELECT purchases.*, books.title, books.thumbnail, books.authors FROM purchases "
        "JOIN books ON purchases.isbn=books.isbn13 WHERE username=? ORDER BY purchase_date DESC",
        (session['user'],)
    ).fetchall()
    conn.close()
    return render_template("purchases.html", purchases=data)

# ─── Admin ───────────────────────────────────────────────────────
@app.route('/admin')
def admin():
    if not session.get('user') or session.get('role') != 'admin':
        return redirect('/')
    conn = get_db_connection()
    total_books     = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    available       = conn.execute("SELECT COUNT(*) FROM books WHERE is_available=1").fetchone()[0]
    issued_count    = conn.execute("SELECT COUNT(*) FROM issued_books").fetchone()[0]
    total_users     = conn.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0]
    total_revenue   = conn.execute("SELECT COALESCE(SUM(price),0) FROM purchases").fetchone()[0]
    total_purchases = conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
    overdue = conn.execute("""
        SELECT issued_books.*, books.title, users.email
        FROM issued_books JOIN books ON issued_books.isbn=books.isbn13
        JOIN users ON issued_books.username=users.username
        WHERE due_date < DATE('now')
    """).fetchall()
    all_issued = conn.execute("""
        SELECT issued_books.*, books.title FROM issued_books
        JOIN books ON issued_books.isbn=books.isbn13
        ORDER BY issue_date DESC
    """).fetchall()
    all_users = conn.execute("SELECT id, username, email, role FROM users").fetchall()
    recent_purchases = conn.execute("""
        SELECT purchases.*, books.title FROM purchases
        JOIN books ON purchases.isbn=books.isbn13
        ORDER BY purchase_date DESC LIMIT 10
    """).fetchall()
    conn.close()
    overdue_with_fines = [{'record': o, 'fine': calculate_fine(o['due_date'])} for o in overdue]
    return render_template("admin.html",
        total_books=total_books, available=available, issued_count=issued_count,
        total_users=total_users, total_revenue=total_revenue, total_purchases=total_purchases,
        overdue=overdue_with_fines, all_issued=all_issued,
        all_users=all_users, recent_purchases=recent_purchases
    )

@app.route('/admin/send_overdue_reminders')
def send_overdue_reminders():
    if not session.get('user') or session.get('role') != 'admin':
        return redirect('/')
    conn = get_db_connection()
    overdue = conn.execute("""
        SELECT issued_books.*, books.title, users.email, users.username
        FROM issued_books JOIN books ON issued_books.isbn=books.isbn13
        JOIN users ON issued_books.username=users.username
        WHERE due_date < DATE('now') AND users.email IS NOT NULL AND users.email != ''
    """).fetchall()
    conn.close()
    sent = 0
    for o in overdue:
        fine = calculate_fine(o['due_date'])
        if send_email(o['email'], "Overdue Book Reminder - E-Library",
            f"<h2>Overdue!</h2><p>Dear {o['username']},</p>"
            f"<p><b>{o['title']}</b> was due on {o['due_date']}.</p>"
            f"<p>Fine: Rs.{fine}</p><p>Please return immediately.</p>"):
            sent += 1
    return jsonify({"sent": sent, "total_overdue": len(overdue)})

@app.route('/admin/delete_user/<int:user_id>')
def delete_user(user_id):
    if not session.get('user') or session.get('role') != 'admin':
        return redirect('/')
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    return redirect('/admin')

if __name__ == '__main__':
    app.run(debug=True)


import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)