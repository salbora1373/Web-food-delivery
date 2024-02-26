from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import os
import sqlite3
import json
import datetime
from utils import User, connect_db, authenticate_user, isCustomer, isRestaurant, getUserPostcode, restaurantName, insertAccountHolder, allowed_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"



login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.init_app(app)

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static/uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

#button to show orders instead ->keith 
#showing_restaurants, edit_order, datetime.datetime.now().hour : Keith
# fix restaurant orders, check if email already exists -> Hussain
# turn view_orders/customer into a table, table headings, order_id and restaurant_name -> ALi
#register_customer styling -> Mina

@login_manager.user_loader
def load_user(user_id):
  user = User()
  user.id = user_id
  return user


@app.route('/login', methods=['GET', 'POST'])
def login():

  if (current_user.is_authenticated):
    if (isCustomer()):
      postcode = getUserPostcode()
      return redirect(url_for('get_list_restaurants', postcode=postcode))
    else:
      return redirect(url_for('restaurant_dashboard'))

  if request.method == 'POST':
    email = request.form['email']
    password = request.form['password']
    user = authenticate_user(email, password)

    if user:
      login_user(user)

      if isCustomer():
        print(int(current_user.id))
        postcode = getUserPostcode()
        return redirect(url_for('get_list_restaurants', postcode=postcode))
      else:
        return render_template('restaurant_dashboard.html')
    else:
      print('flash here')
      flash('Login failed. Check your email and password.', 'error')

  return render_template('login.html')


@app.route('/restaurant_dashboard')
@login_required
def restaurant_dashboard():
  return render_template('restaurant_dashboard.html')


@app.route('/logout')
@login_required
def logout():
  logout_user()
  return redirect(url_for('index'))


@app.route('/')
def index():
  if (current_user.is_authenticated):
    return redirect(url_for('login'))
  return render_template('register.html')


@app.route('/register_customer', methods=['GET', 'POST'])
def register_customer():
  if request.method == 'POST':
    firstName = request.form['fname']
    lastName = request.form['lname']
    email = request.form['email']
    password = request.form['password']
    postcode = request.form['postcode']
    address = request.form['address']
    #session['name'] = request.form['name']

    conn = connect_db()
    last_row_id = insertAccountHolder(email, password, postcode, address, conn)

    conn.execute(
        'INSERT INTO Customer (CustomerID, FirstName, LastName) VALUES (?, ?, ?  )',
        (last_row_id, firstName, lastName))
    conn.commit()
    conn.close()
    return render_template('register_success.html')
  return render_template('register_customer.html')


@app.route('/register_restaurant', methods=['GET', 'POST'])
def register_restaurant():
  if request.method == 'POST':
    name = request.form['name']
    description = request.form['description']
    opening_time = request.form['opening_time']
    closing_time = request.form['closing_time']

    email = request.form['email']
    password = request.form['password']
    address = request.form['address']
    postcode = request.form['postcode']
    postcodes = request.form['postcodes']
    #session['name'] = request.form['name']
    postcodes_array = postcodes.split(',')

    if 'picture' in request.files:
      picture = request.files['picture']
      if picture and allowed_file(picture.filename):
        filename = secure_filename(picture.filename)
        upload_folder = app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
          os.makedirs(upload_folder)
        filename = f"{name}.jpeg"
        picture.save(os.path.join(upload_folder, filename))
      else:
        filename = "default restaurant.jpg"
    else:
      filename = "default restaurant.jpg"
    conn = connect_db()
    last_row_id = insertAccountHolder(email, password, postcode, address, conn)
    postcodes_array = [int(num) for num in postcodes_array]
    conn.execute(
        'INSERT INTO Restaurant (RestaurantID, OpeningTime, ClosingTime, Description, Picture, RestaurantName) VALUES (?, ?, ?,?,? ,? )',
        (last_row_id, opening_time, closing_time, description, filename, name))
    for item in postcodes_array:
      conn.execute(
          'INSERT INTO PostCodes (PostCode, RestaurantID) VALUES (?, ?)',
          (item, last_row_id))
    conn.commit()
    conn.close()
    print(name, description, email, password, address, postcode)
    return render_template('register_success.html')
  return render_template('register_restaurant.html')


@app.route('/restaurant_list/<postcode>')
@login_required
def get_list_restaurants(postcode):
  if isCustomer():
    conn = connect_db()
    rows = conn.execute(
        """SELECT Restaurant.* from PostCodes JOIN
	        Restaurant on Restaurant.RestaurantID =
	        PostCodes.RestaurantID JOIN AccountHolder on
	        AccountHolder.Postcode = PostCodes.Postcode where
	        AccountHolder.ID = ?""", (int(current_user.id), )).fetchall()
    conn.close()

    restaurants = []
    for row in rows:
      restaurant_dict = dict(row)
      image_filename = restaurant_dict['Picture']
      image_path = url_for('static', filename=f'uploads/{image_filename}')
      restaurant_dict['image_path'] = image_path
      restaurants.append(restaurant_dict)

    return render_template('restaurant_list.html',
                           restaurants=restaurants,
                           postcode=postcode)
  else:
    return redirect(url_for('index'))


@app.route('/restaurant/add_to_menu', methods=['GET', 'POST'])
@login_required
def add_to_menu():
  if (isCustomer()):
    return redirect(url_for("index"))

  restaurant_id = current_user.id

  conn = connect_db()
  hasMenu = conn.execute('SELECT * FROM hasMenu WHERE RestaurantID = ?',
                         (int(restaurant_id), )).fetchall()
  menuId = 0
  if (len(hasMenu) == 0):
    print('no menu')
    menuId = conn.execute('INSERT INTO hasMenu(RestaurantID) VALUES(?)',
                          (restaurant_id, )).lastrowid
    conn.commit()
  else:
    menuId = conn.execute(
        'SELECT RestaurantID from hasMenu WHERE RestaurantID=?',
        (restaurant_id, )).fetchone()['RestaurantID']

  menu_items = conn.execute(
      """SELECT Items.*  FROM contains 
  JOIN Items on Items.ItemID = contains.ItemID 
  where MenuId = ?;""", (int(restaurant_id), )).fetchall()

  if request.method == 'POST':
    item = request.form['item']
    category = request.form['category']
    price = request.form['price']
    description = request.form['description']

    if 'picture' in request.files:
      picture = request.files['picture']
      if picture and allowed_file(picture.filename):
        filename = secure_filename(picture.filename)
        upload_folder = app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
          os.makedirs(upload_folder)
        filename = f"{item}.jpeg"
        picture.save(os.path.join(upload_folder, filename))
      else:
        if category == '1':
          filename = "appetizer.jpg"
        elif category == '2':
          filename = "main.jpg"
        elif category == '3':
          filename = "dessert.jpg"
        elif category == '4':
          filename = "drink.jpg"
    else:
      if category == '1':
        filename = "appetizer.jpg"
      elif category == '2':
        filename = "main.jpg"
      elif category == '3':
        filename = "dessert.jpg"
      elif category == '4':
        filename = "drink.jpg"

    itemId = conn.execute(
        'INSERT INTO Items (ItemName, Picture, CategoryId, Price, ItemDescription) '
        'VALUES (?, ?, ?, ?, ?)',
        (item, filename, int(category), price, description)).lastrowid

    conn.execute(
        'INSERT INTO contains (MenuID, ItemID) VALUES (?, ?)',
        (menuId, itemId),
    )

    conn.commit()
    conn.close()
    return redirect(url_for('add_to_menu'))
  conn.close()
  return render_template('restaurant_menu_add.html', items=menu_items)


@app.route('/menu/<restaurant_id>', methods=['GET', 'POST'])
@login_required
def menu_items(restaurant_id):
  if (isRestaurant()):
    return redirect(url_for("restaurant_dashboard"))

  session.modified = True
  session['restaurant_id'] = restaurant_id
  conn = connect_db()

  rows = conn.execute(
      """SELECT *  FROM contains 
  JOIN Items on Items.ItemID = contains.ItemID 
  JOIN Category on Category.CategoryId = Items.CategoryId
  where MenuId = ?;""", (int(restaurant_id), )).fetchall()

  name = conn.execute(
      """SELECT RestaurantName from Restaurant where RestaurantID = ?""",
      (int(restaurant_id), )).fetchone()
  name = name['RestaurantName']
  menuItems = []
  for row in rows:
    menu_dict = dict(row)
    image_filename = menu_dict['Picture']
    image_path = url_for('static', filename=f'uploads/{image_filename}')
    menu_dict['image_path'] = image_path
    menuItems.append(menu_dict)

  conn.close()
  return render_template('menu_items_restaurant.html',
                         items=menuItems,
                         name=name)


#removal
@app.route('/cart', methods=['GET', 'POST'])
@login_required
def cart():
  if (isRestaurant()):
    return redirect(url_for('restaurant_dashboard'))

  if (('cart' not in session) or
      ('total' not in session)) or ('additionalText' not in session):

    session['cart'] = []
    session['total'] = 0
    session['additionalText'] = None

  if request.method == "POST":
    items = request.form['items']
    total = request.form['total']
    additionalText = request.form['additionalText']

    if (items):
      session['cart'] = json.loads(items)
      session['total'] = total
      session['additionalText'] = additionalText

    else:
      session['cart'] = []

    return redirect(url_for("cart"))
  return render_template("cart.html",
                         cart=session['cart'],
                         total=session['total'],
                         additionalText=session['additionalText'])


@app.route('/order_customer', methods=['GET', 'POST'])
@login_required
def order_customer():
  if (isRestaurant()):
    return redirect(url_for('restaurant_dashboard'))

  print(session['cart'], session['total'])
  conn = connect_db()

  items = session['cart']
  total = session['total']
  additionalText = session['additionalText']
  restaurant_id = session['restaurant_id']
  user_id = int(
      current_user.id)  #used as example. Please change user id when you login

  order_id = conn.execute(
      """INSERT INTO Orders(CustomerId, RestaurantId, 
      Status, AdditionalText, EstimatedDeliveryTime,             
      TotalCost, Order_Time) 
        VALUES(? , ? , ? , ? ,?, ? , ?)""",
      (user_id, restaurant_id, 'Processing', additionalText, '', total,
       datetime.datetime.now().isoformat())).lastrowid

  for item in items:
    conn.execute(
        """INSERT INTO OrderItem(OrderId, FoodId, Quantity) VALUES(?, ?, ?)""",
        (order_id, item['item'], item['quantity']))

  conn.commit()
  conn.close()
  return render_template('menu_item_success.html')


@app.route('/view_orders/customer')
@login_required
def view_orders_customer():
  if (isRestaurant()):
    return redirect(url_for("index"))

  conn = connect_db()
  customer_id = current_user.id
  past_orders = conn.execute(
      """SELECT strftime('%d/%m/%Y %H:%M',Order_Time) as Order_Time, TotalCost, Status,OrderId from Orders where CustomerId = ? """,
      (customer_id, )).fetchall()
  conn.close()
  return render_template('view_orders_customer.html', past_orders=past_orders)


@app.route('/view_orders/customer/<order_id>')
@login_required
def view_order_customer(order_id):
  if (isRestaurant()):
    return redirect(url_for('restaurant_dashboard'))

  conn = connect_db()
  customer_id = current_user.id
  order_data = conn.execute(
      """SELECT Items.ItemName, OrderItem.Quantity, Items.Price, Orders.TotalCost FROM Orders
        JOIN OrderItem
        ON OrderItem.OrderId = Orders.OrderId
        JOIN Items
        ON Items.ItemId = OrderItem.FoodId
        Where OrderItem.OrderId = ?
         AND Orders.CustomerId=?""", (int(order_id), customer_id)).fetchall()
  print()
  conn.close()
  return render_template('view_order_customer.html',
                         order_data=order_data,
                         total_cost=order_data[0]['TotalCost'])


@app.route('/view_orders/restaurant')
@login_required
def view_orders():
  if (isCustomer()):
    return redirect(url_for("index"))

  conn = connect_db()
  restaurant_id = current_user.id
  # Processing -> Preparing -> Completed| Cancelled
  processing = conn.execute(
      """SELECT  OrderId, Order_Time , Status FROM Orders
  Where Orders.RestaurantId = ? AND Status ='Processing' """,
      (restaurant_id, )).fetchall()
  pending = conn.execute(
      """SELECT  OrderId, Order_Time , Status FROM Orders
  Where Orders.RestaurantId = ? AND Status ='Preparing' """,
      (restaurant_id, )).fetchall()
  completed = conn.execute(
      """SELECT  OrderId, Order_Time , Status FROM Orders
  Where Orders.RestaurantId = ? AND Status ='Complete' """,
      (restaurant_id, )).fetchall()
  canceled = conn.execute(
      """SELECT  OrderId, Order_Time , Status FROM Orders
  Where Orders.RestaurantId = ? AND Status ='Canceled' """,
      (restaurant_id, )).fetchall()
  conn.close()
  return render_template('view_orders_restaurant.html',
                         processing=processing,
                         pending=pending,
                         completed=completed,
                         canceled=canceled)


@app.route('/order/edit/<order_id>', methods=['GET', 'POST'])
@login_required
def edit_order(order_id):
  if (isCustomer()):
    return redirect(url_for("index"))

  conn = connect_db()
  restaurant_id = current_user.id
  current_order = conn.execute(
      """SELECT Items.ItemName, OrderItem.Quantity, Orders.TotalCost, time(Orders.Order_Time) as Order_Time,
      Orders.Status
      FROM Orders
        JOIN OrderItem
        ON OrderItem.OrderId = Orders.OrderId
        JOIN Items
        ON Items.ItemId = OrderItem.FoodId
        Where Orders.OrderId = ?
        AND Orders.RestaurantId=?""",
      (int(order_id), restaurant_id)).fetchall()
  total_cost = current_order[0]['TotalCost']
  order_time = (current_order[0]['Order_Time'])
  if request.method == "POST":
    new_status = request.form.get('status')

    conn = connect_db()
    conn.execute(
        "UPDATE Orders SET Status = ? WHERE OrderId = ? AND RestaurantId = ?",
        (new_status, order_id, restaurant_id))
    conn.commit()
    conn.close()
    return redirect(url_for("view_orders"))

  conn.close()
  return render_template('edit_order.html',
                         current_order=current_order,
                         total_cost=total_cost,
                         order_time=order_time)


if __name__ == '__main__':
  app.run(debug=True, host='0.0.0.0', port=8080)
