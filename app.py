import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

#Heroku postgres DB
#uri = os.getenv("postgres://lihwoixnwuffzj:35d43f4c69271cc00c4f0531336275819487765c55d9eefe1b42bba292f40b68@ec2-54-208-104-27.compute-1.amazonaws.com:5432/d9pl5vl57f70v7")
#if uri.startswith("postgres://"):
#    uri = uri.replace("postgres://", "postgresql://")
#db = SQL(uri)

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

@app.route("/")
@login_required
def index():
    username = session["username"]
    #Update Stock Prices
    update_portfolio = db.execute("SELECT * FROM purchased WHERE username = ?", username)
    for row in update_portfolio:
        #updates the price
        db.execute("UPDATE purchased SET stock_price = ? WHERE username = ? AND symbol = ?", lookup(row["symbol"])["price"],username,row["symbol"])
        db.execute("UPDATE purchased SET total_current = ? WHERE username = ? AND purchase_id =?", (row["stock_price"] * row["number_shares"]),username, row["purchase_id"])

    #Get values from database
    current_portfolio = db.execute("SELECT symbol, number_shares, SUM(number_shares), SUM(total_price_bought), stock_price FROM purchased WHERE username = ? GROUP BY symbol", username)

    #if no stocks show site
    if not current_portfolio:
        #share for placeholder
        return render_template("index.html")

    #get total
    total_portfolio = db.execute("SELECT SUM(total_price_bought),SUM(total_current) FROM purchased WHERE username = ?", username)

    #get user info
    user_data = db.execute("SELECT * FROM users WHERE username = ?", username)

    return render_template("index.html", portfolio=current_portfolio, total_portfolio_shares=total_portfolio, user_info = user_data)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        username = session["username"]

        #Getting the symbol into global variable so it can pass

        symbol_pre = request.form.get("symbol")
        symbol = symbol_pre.strip()
        session["symbol"] = symbol

        shares = request.form.get("shares",type=int)
        session["shares"] = shares

        if not symbol:
            return apology("Must provide ticker", 403)

        elif not lookup(symbol):
            return apology("Must provide VALID ticker", 403)

        elif not shares:
            return apology("Put number of shares", 403)

        elif (shares < 1):
            return apology("Number of shares must be above 1", 403)

        #Calculate total price of shares requested to be purchased
        #print((lookup(symbol)["price"])*shares)
        total_price = (lookup(symbol)["price"]) * shares

        #Check how much money is in the account
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        user_cash = cash[0]["cash"]

        #If money - shares total price > 0 then make transaction go through and figure out new balance of account and update
        if ((user_cash - total_price) > 0):
            new_balance = user_cash - total_price
            db.execute("UPDATE users SET cash = ? WHERE id = ?", new_balance, session["user_id"])
        else:
            return apology("You don't have enough money", 403)

        #insert purchase into the database
        db.execute("INSERT INTO purchased (username, symbol, number_shares, total_price_bought,stock_price,total_current) VALUES (?,?,?,?,?,?)", username, lookup(symbol)["symbol"],shares,total_price,lookup(symbol)["price"],total_price)

        #insert purchase into history
        db.execute("INSERT INTO history (username, symbol, number_shares, total_price_bought,stock_price,total_current) VALUES (?,?,?,?,?,?)", username, lookup(symbol)["symbol"],shares,total_price,lookup(symbol)["price"],total_price)

        return redirect("/purchased")

    else:
        return render_template("buy.html")

@app.route("/purchased", methods=["GET", "POST"])
@login_required
def purchased():
    #Rendering the purchased page
    balance = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])
    current_balance = balance[0]["cash"]
    shares = session["shares"]
    buystock = lookup(session["symbol"])

    return render_template("purchased.html", buystock=buystock, current_balance=current_balance, shares=shares)


# Working on the history page!!!

@app.route("/history", methods=["GET"])
@login_required
def history():

    #get username
    #current_user = db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])
    #user = current_user[0]["username"]

    #Get values from database

    history = db.execute("SELECT symbol, number_shares, total_price_bought, stock_price, datestamp FROM history WHERE username = ?", session["user"])
    HISTORY_LOG = history

    #for row in history:
        #HISTORY_LOG = row

    return render_template("history.html", history_log=HISTORY_LOG)


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
        session["username"] = rows[0]["username"]

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

        # Ensure stock was submitted
        if not request.form.get("symbol"):
            return apology("must provide stock ticker", 403)

        #print(session["user_id"])

        # Submission
        symbol = request.form.get("symbol")
        session["symbol"] = symbol

         # Redirect user to quoted page
        return redirect("/quoted")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")



@app.route("/quoted", methods=["GET", "POST"])
@login_required
def quoted():
        #print(SYMBOL)
        return render_template("quoted.html", quotestock=lookup(session["symbol"]))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Submission
        username = request.form.get("username")
        password = generate_password_hash(request.form.get("password"))

        # Query database for username
        db.execute("INSERT INTO users (username,hash) VALUES (?,?)", username, password)

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    username = session["username"]
    current_portfolio = db.execute("SELECT symbol,SUM(number_shares) FROM purchased WHERE username = ? GROUP BY symbol", username)

    if request.method == "POST":

        symbol = request.form.get("symbol")
        shares = request.form.get("shares",type=int)

        session["symbol"] = symbol
        session["shares"] = shares

        if not symbol:
            return apology("Must provide ticker", 403)

        elif not lookup(symbol):
            return apology("Must provide VALID ticker", 403)

        #elif not in PORTFOLIO:
            #return apology("Must provide ticker in your portfolio", 403)

        elif not shares:
            return apology("Put number of shares", 403)

        elif (shares < 1):
            return apology("Number of shares must be above 1", 403)

        #update balance
        balance = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])
        CURRENT_BALANCE = balance[0]["cash"]
        session["balance"] = CURRENT_BALANCE

        #price of stocks sold
        total_price = lookup(symbol)["price"] * shares

        #adding sold quantity to blanace
        CURRENT_BALANCE = CURRENT_BALANCE + total_price

        db.execute("UPDATE users SET cash=? WHERE id=?",CURRENT_BALANCE,session["user_id"])

        #add transaction to list
        db.execute("INSERT INTO purchased (username, symbol, number_shares, total_price_bought,stock_price,total_current) VALUES (?,?,?,?,?,?)", username, lookup(symbol)["symbol"],(shares*-1),(total_price*-1),lookup(symbol)["price"],(total_price*-1))

        #add transaction to history
        db.execute("INSERT INTO history (username, symbol, number_shares, total_price_bought,stock_price,total_current) VALUES (?,?,?,?,?,?)", username, lookup(symbol)["symbol"],(shares*-1),(total_price*-1),lookup(symbol)["price"],(total_price*-1))

        stock_zero = db.execute("SELECT SUM(number_shares) FROM purchased WHERE symbol = ?", symbol)

        if (stock_zero[0]["SUM(number_shares)"]) == 0:
            db.execute("DELETE FROM purchased WHERE symbol = ?", symbol)

        return redirect("/sold")

    else:
        current_portfolio = db.execute("SELECT symbol,SUM(number_shares) FROM purchased WHERE username = ? GROUP BY symbol", username)

        if not current_portfolio:
            return render_template("sell.html")
        else:
            return render_template("sell.html", portfolio=current_portfolio)


@app.route("/sold", methods=["GET", "POST"])
@login_required
def sold():
    return render_template("sold.html", sellstock=lookup(session["symbol"]),current_balance=session["balance"], shares=session["shares"])

@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash():
    if request.method == "POST":
        cash_request = request.form.get("cash_request", type=int)
        session["cash_request"] = request.form.get("cash_request", type=int)

        if not cash_request:
            return apology("Provide numeric value", 403)
        elif cash_request < 0:
            return apology("Must provide number greater than 0", 403)
        else:
            balance = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])

            db.execute("UPDATE users SET cash = (? + ?) WHERE id=?", balance[0]["cash"],cash_request, session["user_id"])
            return redirect("/cash_confirmation")

    else:
        #Rendering GET cash page
        balance = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])
        CURRENT_BALANCE = balance[0]["cash"]

        return render_template("cash.html", current_balance=CURRENT_BALANCE)

@app.route("/cash_confirmation", methods=["GET", "POST"])
@login_required
def cash_confirmation():
    balance = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])
    CURRENT_BALANCE = balance[0]["cash"]
    CASH_REQUEST = session["cash_request"]

    return render_template("cash_confirmation.html", current_balance=CURRENT_BALANCE, cash_request=CASH_REQUEST)