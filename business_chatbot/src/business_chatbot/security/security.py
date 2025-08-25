from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_login import LoginManager
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from flask_mysqldb import MySQL

app = Flask(__name__)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'business_expert'
mysql = MySQL(app)
@app.route('/test_db')
def test_db():
    cursor = mysql.connection.cursor()
    cursor.execute("SHOW TABLES;")
    tables = cursor.fetchall()
    cursor.close()
    return str(tables)


app.config["SECRET_KEY"] = "supersecretkey"
app.config["JWT_SECRET_KEY"] = "jwt-secret"  # change in production!
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
jwt = JWTManager(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@app.route('/register', methods=['GET', 'POST'])
def register():
    data = request.json
    email = data.get("username")
    password = data.get("password")
    hashed_pw = generate_password_hash(password)
    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO user(email, password) VALUES (%s, %s)", (email, hashed_pw))
    mysql.connection.commit()
    cursor.close()
    token = create_access_token(identity={"username": email})
    return jsonify(access_token=token), 200

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM user WHERE email=%s", (username,))
    user = cursor.fetchone()
    print(user)
    cursor.close()

    if user and check_password_hash(user[1], password):  # user[1] = password column
        token = create_access_token(identity={"username": username})
        return jsonify(access_token=token), 200

    return jsonify(msg="Invalid credentials"), 401


if __name__ == "__main__":
    app.run(debug=True)

