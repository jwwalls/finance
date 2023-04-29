import os
import time

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)
current_time = time.ctime()
# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    stocks = db.execute("SELECT symbol, SUM(shares) as shares, price FROM transactions WHERE ? GROUP BY symbol", session["user_id"])
    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    total_value = cash[0]['cash'];
    for stock in stocks:
        stock['price'] = int(stock['price'])
        total_value += stock['price'] * stock['shares']
        #stock['shares'] = int(stock['shares'])
    return render_template("index.html", stocks=stocks, cash=cash[0]['cash'], value=total_value )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        cash =db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        return render_template("buy.html", cash=cash)
    else:
        shares = request.form.get("shares")
        symbol = request.form.get("symbol")
        try:
            shares = int(shares)
        except ValueError:
            return apology("INVALID SHARES")
        if not lookup(symbol):
            return apology("Invalid Symbol")
        if shares < 0:
            return apology("Invalid number of shares")

        stock = lookup(symbol.upper())
        transaction_cost = shares * stock["price"]
        user_cash = db.execute("SELECT cash from users WHERE id = ?", session["user_id"])
        if transaction_cost > user_cash[0]['cash']:
            return apology("Insufficent Funds")
        new_balance = user_cash[0]['cash'] - transaction_cost
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_balance, session["user_id"])
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, time) VALUES (?,?,?,?,?)",session["user_id"], symbol, shares, stock['price'], current_time)
        flash("sold!")

        return redirect("/")



@app.route("/history")
@login_required
def history():

    transactions_db = db.execute("SELECT * FROM transactions WHERE user_id = ?", session["user_id"])
    return render_template("history.html", transactions=transactions_db)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        if lookup(request.form.get("symbol")):
            company = lookup(request.form.get("symbol"))
            return render_template("quoted.html", company=company)
        else:
            return apology("not found")
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    session.clear()
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username")

        elif not request.form.get("password"):
            return apology("must provide password")

        elif not request.form.get("password") == request.form.get("confirmation"):
            return apology("Passwords Do Not Match!")

        elif not db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username")):
            db.execute("INSERT INTO users (username, hash) VALUES (?,?)", request.form.get("username"), generate_password_hash(request.form.get("password")))
        else:
            return apology("Username is taken")

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        session["user_id"] = rows[0]["id"]
        return redirect("/")
    else:
        return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "GET":
        symbols = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol", session["user_id"])
        return render_template("sell.html", symbols = [row['symbol'] for row in symbols])
    else:
        shares = int(request.form.get("shares"))
        symbol = request.form.get("symbol")
        try:
            shares = int(shares)
        except ValueError:
            return apology("INVALID SHARES")
        if not lookup(symbol):
            return apology("Invalid Symbol")
        if shares <= 0:
            return apology("Invalid number of shares")

        stock = lookup(symbol.upper())
        transaction_cost = shares * stock["price"]
        user_cash = db.execute("SELECT cash from users WHERE id = ?", session["user_id"])
        user_shares = db.execute("SELECT SUM(shares) as shares FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol",session["user_id"],symbol)

        if user_shares[0]['shares'] < shares:
           return apology("Not Enough Shares")

        new_balance = user_cash[0]['cash'] + transaction_cost
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_balance, session["user_id"])
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, time) VALUES (?,?,?,?,?)",session["user_id"], symbol, (-1)*shares, stock['price'], current_time)
        flash("bought!")

        return redirect("/")


