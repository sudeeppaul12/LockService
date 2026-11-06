
from flask import Flask, render_template, redirect, url_for

app = Flask(__name__)

# Homepage
@app.route("/")
def home():
    return redirect(url_for("login"))

# Login page
@app.route("/login")
def login():
    return render_template("login_screen.html")

# Customer dashboard
@app.route("/customer/dashboard")
def customer_dashboard():
    return render_template("customer_dashboard.html")

# Staff dashboard
@app.route("/staff/dashboard")
def staff_dashboard():
    return render_template("staff_dashboard.html")

# Run website
if __name__ == "__main__":
    app.run(debug=True)
