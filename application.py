import csv
import requests
import json
import re

from flask import Flask, session, render_template, request, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.exc import DataError, IntegrityError

app = Flask(__name__)

# Sensitive data is stored on an external file
f = open("database.csv")
reader = csv.reader(f)
for pw, ip, port, goodreadskey in reader:
    pw = pw
    ip = ip
    port = port
    goodreadskey = goodreadskey

# Set up database
engine = create_engine(f"postgresql://postgres:{pw}@{ip}:{port}/")
db = scoped_session(sessionmaker(bind=engine))

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Non route function
def mailcheck(self):
    valid = re.search(r'[A-Za-z0-9\_\.-]+@[A-Za-z0-9\_-]+\.[A-Za-z\.]+', self)
    return valid

# Generate API for books
@app.route("/api/books/<string:book_isbn>")
def bookapi(book_isbn):
    book = db.execute(f"SELECT * FROM books WHERE isbn='{book_isbn}'").fetchone()
    if book is None:
        return jsonify({"error":"Book ISBN not found"}),404
    local_reviews = db.execute(f"SELECT COUNT(*) FROM reviews WHERE bookisbn='{book_isbn}'").fetchall()
    avgscore = db.execute(f"SELECT AVG(userscore) FROM reviews WHERE bookisbn='{book_isbn}'").fetchall()
    if avgscore[0][0] is None:
        avgscore = "null"
    else:
        avgscore = str(round(avgscore[0][0], 2))
    res = requests.get("https://www.goodreads.com/book/review_counts.json",params={"key": goodreadskey, "isbns": book_isbn})
    res = res.json()
    return jsonify({
        "book_isbn": book_isbn,
        "title": book.title,
        "author": book.author,
        "year": book.year,
        "local_reviews": {
            "review_count": local_reviews[0][0],
            "average_score": avgscore
        },
        "goodread_reviews": {
            "review_count": res["books"][0]["work_ratings_count"],
            "average_score": res["books"][0]["average_rating"]
        }
    })

# Specific book route
@app.route("/books/<string:book_isbn>")
def bookdata(book_isbn):
    review_check = None
    score = None
    book = db.execute(f"SELECT * FROM books WHERE isbn='{book_isbn}'").fetchone()
    res = requests.get("https://www.goodreads.com/book/review_counts.json",params={"key": goodreadskey, "isbns": book_isbn})
    res = res.json()
    rates = res["books"][0]["work_ratings_count"]
    avg = res["books"][0]["average_rating"]
    reviews = db.execute(f"SELECT * FROM reviews WHERE bookisbn='{book_isbn}'").fetchall()
    text = ''
    if "current_user" in session:
        review_check = db.execute(f"SELECT content FROM reviews WHERE poster='{session['current_user']}' AND bookisbn='{book_isbn}'").fetchone()
        if review_check == None:
            review_check = False
        if review_check:
            review_check = review_check[0]
            score = db.execute(f"SELECT userscore FROM reviews WHERE poster='{session['current_user']}' AND bookisbn='{book_isbn}'").fetchone()
            score = score[0]
    return render_template("bookdata.html", book=book, rates=rates, avg=avg, current_user=session["current_user"], review_check=review_check, reviews=reviews, score=score, text=text)

# List of all books, can be filtered by searching - TBD: Paginating results
@app.route("/books/", methods=["GET", "POST"])
def books():
    total_books = db.execute("SELECT COUNT(*) FROM books").fetchall()
    total_books = total_books[0][0]
    booklist = db.execute("SELECT * FROM books ORDER BY author, title").fetchall()
    if request.method == "POST":
        seek = request.form.get("seek")
        seek = seek.replace("'", "''").replace("%", "\%").replace("_", "\_")
        booklist = db.execute(f"SELECT * FROM books WHERE title ILIKE '%%{seek}%%' OR author ILIKE '%%{seek}%%' OR isbn ILIKE '%%{seek}%%' ORDER BY author, title").fetchall()
    l = 0
    for book in booklist:
        l += 1
    return render_template("books.html", current_user=session["current_user"], booklist=booklist, l=l, t=total_books)

# Start page
@app.route("/")
def index():
    if "current_user" not in session:
        session["current_user"] = None
    return render_template("index.html", current_user=session["current_user"])

# User information change
@app.route("/profile/<string:username>/<string:field>", methods=["GET","POST"])
def infochange(username, field):
    if field not in ("mailchange", "passchange"):
        text = "Página inexistente."
        return render_template("message.html", current_user=session["current_user"], text=text)
    elif username != session["current_user"]:
        text = "No cuentas con acceso a esta página."
        return render_template("message.html", current_user=session["current_user"], text=text)
    else:
        if request.method == "GET":
            text = ""
        if request.method == "POST":
            o = request.form.get("o")
            n = request.form.get("n")
            c = request.form.get("c")
            if o and n and c:
                if field == "passchange":
                    check = db.execute(f"SELECT * FROM users WHERE username = '{username}' and password = '{o}'").fetchone()
                    if check:
                        if len(n) > 5:
                            if n == c:
                                db.execute(f"UPDATE users SET password = :p WHERE username = '{username}'",{"p": n})
                                db.commit()
                                text = "Se ha modificado correctamente la contraseña"
                            else:
                                text = "La nueva contraseña y su confirmación deben coincidir"
                        else:
                            text = "La nueva contraseña debe tener al menos 6 caracteres."
                    else:
                        text = "La contraseña actual ingresada es incorrecta."
                if field == "mailchange":
                    check = db.execute(f"SELECT * FROM users WHERE username = '{username}' and email = '{o}'").fetchone()
                    if check:
                        if mailcheck(n):
                            if n == c:
                                db.execute(f"UPDATE users SET email = :e WHERE username = '{username}'",{"e": n})
                                db.commit()
                                text = "Se ha modificado correctamente la dirección de correo"
                            else:
                                text = "La nueva dirección de correo y su confirmación deben coincidir"
                        else:
                            text = "La nueva dirección de correo debe ser una casilla de correo válida."
                    else:
                        text = "La casilla actual ingresada es incorrecta."
            else:
                text = "Los tres campos son obligatorios."
        return render_template("infochange.html", current_user=session["current_user"], field=field, text=text, username=username)

# Login
@app.route("/login", methods=["GET","POST"])
def login():
    text = ""
    if request.method == "POST":
        u = request.form.get("u")
        u = u.replace("'", "''").replace("%", "\%").replace("_", "\_")
        p = request.form.get("p")
        p = p.replace("'", "''").replace("%", "\%").replace("_", "\_")
        isvalid = db.execute(f"SELECT username, password FROM users WHERE username = '{u}'").fetchone()
        if isvalid is None:
            text = "El usuario ingresado no existe."
        else:
            isvalid = db.execute(f"SELECT username, password FROM users WHERE username = '{u}' and password = '{p}'").fetchone()
            if isvalid is None:
                text = "La contraseña es incorrecta."
            else:
                session["current_user"] = u
                text = f"Bienvenido {session['current_user']}. Has iniciado sesión correctamente."
    return render_template("login.html", text=text, current_user=session["current_user"])

# Logout
@app.route("/logout")
def logout():
    if "current_user" in session:
        session["current_user"] = None
        text = "Se ha cerrado correctamente la sesión."
    else:
        text = "Ninguna sesión se encuentra activa."

    return render_template("logout.html", current_user=session["current_user"], text=text)

# User profile page
@app.route("/profile/<string:username>")
def profile(username):
    text = ""
    user = db.execute(f"SELECT * FROM users WHERE username='{username}'").fetchone()
    if user is None:
        text = "Usuario inexistente"
    else:
        user = user["username"]
        reviews = db.execute(f"SELECT COUNT(*) FROM reviews WHERE poster='{user}'").fetchall()
        reviews = reviews[0][0]
        score = db.execute(f"SELECT AVG(userscore) FROM reviews WHERE poster='{user}'").fetchall()
        score = score[0][0]
        if score:
            score = round(score,2)
        else:
            score = "N/D"
    return render_template("profile.html", current_user=session["current_user"], reviews=reviews, score=score, text=text, user=user)

# Registering a user
@app.route("/register", methods=["GET","POST"])
def register():
    text = ""
    if request.method == "POST":
        u = request.form.get("u")
        p = request.form.get("p")
        e = request.form.get("e")
        if len(u) < 4:
            text = "El usuario debe tener al menos 4 caracteres."
        elif len(p) < 6:
            text = "La contraseña debe tener al menos 6 caracteres"
        elif mailcheck(e) == None:
            text = "Debe ser una casilla de mail válida."
        else:
            try:
                db.execute("INSERT INTO users (username, password, email) VALUES (:u,:p,:e)",{"u": u, "p": p, "e": e})
                db.commit()
                session["current_user"] = u
                text = f"Se ha registrado correctamente. Ha iniciado sesión como {u}."
            except IntegrityError:
                text = "Ese usuario ya se encuentra en uso."
    return render_template("register.html", current_user=session["current_user"], text=text)

# Code run when adding or editing reviews.
@app.route("/books/<string:book_isbn>/review", methods=["POST"])
def review(book_isbn):
    if request.method == "POST":
        r = request.form.get("r")
        s = request.form.get("s")
        book = db.execute(f"SELECT * FROM books WHERE isbn='{book_isbn}'").fetchone()
        res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": goodreadskey, "isbns": book_isbn})
        res = res.json()
        rates = res["books"][0]["work_ratings_count"]
        avg = res["books"][0]["average_rating"]
        reviews = db.execute(f"SELECT * FROM reviews WHERE bookisbn='{book_isbn}'").fetchall()
        checker = db.execute(f"SELECT * FROM reviews WHERE bookisbn = '{book_isbn}' AND poster = '{session['current_user']}'").fetchone()
        if len(r)<10 or s==None:
            checker = None
        if checker is None:
            try:
                db.execute("INSERT INTO reviews (content, bookisbn, poster, userscore) VALUES (:r,:b,:c,:s)", {"r": r, "b": book_isbn, "c": session["current_user"], "s": s})
                db.commit()
                text="Se agregó una reseña."
            except IntegrityError:
                text="La reseña no es válida. Debe tener un mínimo de 10 caracteres y una asignación de puntaje."
        else:
            try:
                db.execute(f"UPDATE reviews SET content = :r, userscore = :s WHERE bookisbn = '{book_isbn}' AND poster = '{session['current_user']}'", {"r": r, "s": s})
                db.commit()
                text="Se editó una reseña."
            except IntegrityError or DataError:
                text="La reseña no fue editada. La nueva reseña debe tener un mínimo de 10 caracteres y una asignación de puntaje."
    return render_template("bookdata.html", book=book, rates=rates, avg=avg, current_user=session["current_user"], review_check=review_check, reviews=reviews, score=score, text=text)