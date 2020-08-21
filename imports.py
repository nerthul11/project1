import csv

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

# Sensitive data is stored on an external file
f = open("database.csv")
reader = csv.reader(f)
for pw, ip, port, i in reader:
    pw = pw
    ip = ip
    port = port
    print(pw, ip, port)

engine = create_engine(f"postgresql://postgres:{pw}@{ip}:{port}/")
db = scoped_session(sessionmaker(bind=engine))

# Creates a Table labeled Books
def books():
    db.execute("CREATE TABLE books (id SERIAL PRIMARY KEY, isbn VARCHAR NOT NULL UNIQUE, title VARCHAR NOT NULL, author VARCHAR NOT NULL,year INTEGER NOT NULL )")
    print("Created 'books'")
    db.commit()

# Creates a Table labeled Users
def users():
    db.execute("CREATE TABLE users (id SERIAL PRIMARY KEY, username VARCHAR NOT NULL UNIQUE, password VARCHAR NOT NULL, email VARCHAR NOT NULL)")
    print("Created 'users'")
    db.commit()

# Creates a Table labeled Reviews
def reviews():
    db.execute("CREATE TABLE reviews (id SERIAL PRIMARY KEY, content VARCHAR NOT NULL, bookisbn VARCHAR NOT NULL, poster VARCHAR NOT NULL, userscore INTEGER NOT NULL)")
    print("Created 'reviews'")
    db.commit()

# Creates the three required tables to run application.py properly
def create_all():
    books()
    users()
    reviews()

# Completes books table with 5000 sample books
def add_books():
    f = open("books.csv")
    reader = csv.reader(f)
    for isbn, title, author, year in reader:
        if isbn != "isbn":
            db.execute("INSERT INTO books (isbn, title, author, year) VALUES (:isbn, :title, :author, :year)",
            {"isbn": isbn, "title": title, "author": author, "year": year})
            print(f"Added book {title} by {author} ({year}).")
    db.commit()

# This file should only be ran once in order to create the required tables and having the sample books stored.
def main():
    create_all()
    add_books()

if __name__ == "__main__":
    main()