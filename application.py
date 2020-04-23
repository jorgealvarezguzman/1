import os

from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_session import Session
from flask_login import LoginManager, login_user, current_user, logout_user
from models import *
from sqlalchemy import or_
import requests

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
Session(app)

# Set up database
db.init_app(app)

# Set up LoginManager class
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@app.route("/")
def index():
    db.create_all()
    if current_user.is_authenticated:
        return render_template("index.html")
    return render_template("login.html")


@app.route("/login", methods=["POST", "GET"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    email = request.form.get("email")
    password = request.form.get("password")

    user_id =db.session.query(User.id).filter_by(email=email, password=password)

    if user_id.scalar():
        # Login and validate the user.
        # user should be an instance of your `User` class
        user = User.query.get(user_id)
        login_user(user)
        return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/register", methods=["POST"])
def register():
    name = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")

    # Check if user already exists
    if db.session.query(User.id).filter_by(email=email).scalar():
        return render_template("error.html", message = "User already exists. Use a different email.")

    # Add user
    user = User(name=name, email=email, password=password)
    db.session.add(user)
    db.session.commit()

    return render_template("success.html", message="You are now registered.")


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/search", methods = ["POST", "GET"])
def search():
    """list all books with search pattern"""
    search = request.form.get("search")
    books = Book.query.filter(or_(Book.title.ilike(f'%{search}%'),
            Book.isbn.ilike(f'%{search}%'),
            Book.author.ilike(f'%{search}%')))

    if books.scalar() is None:
        return render_template("error.html", message = "No books matched your query.")

    return render_template("books.html", books=books)


@app.route("/book/<int:book_id>")
def book(book_id):
    """book details."""

    book = Book.query.get(book_id)
    if book is None:
        return render_template("error.html", message="The book was not found.")

    reviews = book.reviews

    #get data from Goodreads
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": os.getenv("GOODREADS_KEY"), "isbns": book.isbn})
    if res.status_code == 200:
        goodreads = res.json()["books"][0]
        return render_template("book_goodreads.html", book=book, reviews=reviews, average_rating = goodreads["average_rating"], number_of_ratings = goodreads["work_text_reviews_count"])

    return render_template("book.html", book=book, reviews=reviews)


@app.route("/review/<int:book_id>", methods=["POST"])
def review(book_id):
        book = Book.query.get(book_id)

        user_id=current_user.get_id()
        review_from_user = Review.query.filter_by(user_id=user_id, book_id=book_id)

        # If user has not reviewed this book
        if review_from_user.scalar() is None:
            review_rating = request.form.get("form_review_rating")
            review_text = request.form.get("form_review_text")
            current_user.add_review(review_rating, review_text, book_id)

        reviews = book.reviews

        return render_template("book.html", book=book, reviews=reviews)


@app.route("/api/<string:isbn>")
def book_api(isbn):
    book = Book.query.filter_by(isbn=isbn).first()

    if book is None:
        return jsonify({"error": "ISBN not in database."}), 404

    review_count = 0
    average_score = 0
    reviews = book.reviews

    for review in reviews:
        review_count += 1
        average_score += review.review_rating

    average_score = average_score/review_count

    return jsonify({
            "title": book.title,
            "author": book.author,
            "year": book.year,
            "isbn": book.isbn,
            "review_count": review_count,
            "average_score": average_score
        })
