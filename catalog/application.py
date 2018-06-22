from flask import Flask, render_template, request, redirect, jsonify, url_for, flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Category, CategoryItem, User
from flask import session as login_session
import random
import string

# IMPORTS FOR THIS STEP
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

app = Flask(__name__)
# Read our client id that was downloaded from our Google API
CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']

# Connect to the database
engine = create_engine('sqlite:///catalog.db',
                       connect_args={'check_same_thread': False})
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


@app.route('/login')
def showLogin():
    """This function renders the login.html page."""
    # Create a state variable to prevent cross site scripting attacks.
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in xrange(32))
    login_session['state'] = state
    # return "The current session state is %s" % login_session['state']
    return render_template('login.html', STATE=state)

# Begin JSON API Endpoint Functions.


@app.route('/category/<int:category_id>/items/JSON')
def categoryItems(category_id):
    """This function displays all of the items in a category in JSON format.

    Keyword arguments:
    category_id(int) An numeric id for identifying a category in the database.
    """
    items = session.query(CategoryItem).filter_by(
        category_id=category_id).all()
    return jsonify(category_items=[i.serialize for i in items])


@app.route('/category/JSON')
def categoriesJSON():
    """This function displays all of the categories in JSON format."""
    categories = session.query(Category).all()
    return jsonify(categories=[c.serialize for c in categories])


@app.route('/catalog/JSON')
def show_catalog():
    """This function shows all of the categories and items in the database
    in JSON format."""
    categories = session.query(Category).all()
    items = session.query(CategoryItem).all()
    return jsonify(
        categories=[
            c.serialize for c in categories], category_items=[
            i.serialize for i in items])


# End JSON API Endpoint Functions.

@app.route('/')
@app.route('/catalog')
def main_page():
    """Renders the home page of the application."""
    # Query the database for all of its data.
    categories = session.query(Category).all()
    items = session.query(CategoryItem).all()
    # Check to see if the user is logged in.
    # If the user is not logged in they cannot access some app features.
    if 'username' not in login_session:
        return render_template(
            'publiccategories.html',
            categories=categories,
            items=items)
    else:
        return render_template(
            'categories.html',
            categories=categories,
            items=items)

# Create a new category


@app.route('/category/new', methods=['GET', 'POST'])
def newCategory():
    """Render the html page for creating a new category in the catalog."""
    # Check to see if the user is allowed to create a new category.
    if 'username' not in login_session:
        return redirect('/login')
    # POST request allows us to modify our database.
    if request.method == 'POST':
        newCategory = Category(category_name=request.form['name'],
                               user_id=login_session['user_id'])
        session.add(newCategory)
        # Create the new category here.
        session.commit()
        flash('New Category Successfully Created')
        return redirect(url_for('main_page'))
    else:
        # GET Request for the html that contains the form for
        # creating a new category.
        return render_template('newCategory.html')


# Create a new item in a category

@app.route('/category/new/item', methods=['GET', 'POST'])
def newItem():
    """This function renders the page for creating a new item in a category."""

    # Check to see if the user is logged in.
    if 'username' not in login_session:
        return redirect('login')
    # POST request allows us to modify our database.
    if request.method == 'POST':
        # Gather the information from the form.
        newItem = CategoryItem(item_name=request.form['name'],
                               description=request.form['description'],
                               category_id=request.form['categories'],
                               user_id=login_session['user_id'])
        session.add(newItem)
        # Add the new item to the database.
        session.commit()
        flash('New Item Successfully Created')
        return redirect(url_for('main_page'))
    else:
        # Query for all the categories users can select
        categories = session.query(Category).all()
        # Return the html that contains the form for creating a new item.
        # Pass in the variable categories that the form needs to complete
        # its job.
        return render_template('newItem.html', categories=categories)


# Get all the items in a category

@app.route('/catalog/<string:category>/items')
def get_items(category):
    """Get the items in a category and render the correct template based
    on the end-user's login status.

    Keyword Arguments:
    category(str): A string representation of the category name.
    """
    # Query for all the categories users can select
    categories = session.query(Category).all()

    # Query for the category the user selected either by clicking or by url.
    selected_category = session.query(
        Category).filter_by(category_name=category).one()

    # Query for all the items that are associated with a category.
    selected_category_items = session.query(
        CategoryItem).filter_by(category_id=selected_category.id).all()
    # Render the template if the user is not logged in.
    if 'username' not in login_session:
        return render_template('publicitems.html', categories=categories,
                               selected_category=selected_category,
                               selected_category_items=selected_category_items)
    else:
        # Render the template if the user is logged in.
        return render_template('privateitems.html', categories=categories,
                               selected_category=selected_category,
                               selected_category_items=selected_category_items)


# Get the description of an item in a category.

@app.route('/catalog/<string:category>/<string:item>/')
def get_items_description(category, item):
    """Render the template for getting an item's description that belongs to
    a category. If the user is logged in and is authorized they can edit
    descriptions or delete the item entirely.

    Keyword Arguments:
    category(str): A string representation of the category name.
    item(str): A string representation of the item name.
    """
    selected_item = session.query(CategoryItem).filter_by(item_name=item).one()
    authorized_user = session.query(User).filter_by(
        id=selected_item.user_id).one()
    # Check to see if the user is logged in.
    if 'username' in login_session:
        username = login_session['username']
    else:
        username = None
        # Render the private template. The user who is logged in and
        # is authorized to edit and delete is provide links to do so
        # in this template.
    if 'username' in login_session and username == authorized_user.name:
        return render_template(
            'privateItemDescription.html',
            category=category,
            item=item,
            selected_item=selected_item)
    else:
        # Render the public template. Users who are not logged in cannot edit
        # item descriptions or delete items.
        return render_template(
            'publicItemDescription.html',
            category=category,
            item=item,
            selected_item=selected_item)


# Edit an item in a catalog.

@app.route(
    '/catalog/<string:category>/<string:item>/edit',
    methods=[
        'GET',
        'POST'])
def editCategoryItem(category, item):
    """This function allows the user to edit a item in a category.

    Keyword Arguments:
    category(str): A string representation of the category name.
    item(str): A string representation of the item name.
    """
    if 'username' not in login_session:
        return redirect('/login')
    elif 'username' in login_session:
        username = login_session['username']
    else:
        username = None
    categories = session.query(Category).all()
    # Item to be edited.
    edited_item = session.query(CategoryItem).filter_by(item_name=item).one()
    # Query for the user who is authorized to perform edits.
    authorized_user = session.query(User).filter_by(
        id=edited_item.user_id).one()
    if username != authorized_user.name:
        # Tell the user they are not allowed to edit items in this catalog.
        return """<script>function myFunction()
         {alert('You are not authorized to edit items in this catalog.
         Please create your own catalog in order to edit items.');}</script>
         <body onload='myFunction()''>"""
    if request.method == 'POST':
        # Take the information from the form and update the record in the
        # database.
        if request.form['name']:
            edited_item.item_name = request.form['name']
        if request.form['description']:
            edited_item.description = request.form['description']
        if request.form['category']:
            edited_item.category_id = request.form['category']
        session.add(edited_item)
        # Commit the changes to the database.
        session.commit()
        flash('Category Item Successfully Edited')
        return redirect(url_for('main_page'))
    else:
        # Render the template that contains the form for editing an item.
        # Pass in the variables that the template needs to complete its job.
        return render_template(
            'editItem.html',
            categories=categories,
            item=item)


@app.route(
    '/catalog/<string:category>/<string:item>/delete',
    methods=[
        'GET',
        'POST'])
def deleteCategoryItem(category, item):
    """This function allows the user to delete a item in a category.

    Keyword Arguments:
    category(str): A string representation of the category name.
    item(str): A string representation of the item name.
    """
    if 'username' not in login_session:
        return redirect('/login')
    elif 'username' in login_session:
        username = login_session['username']
    else:
        username = None
    # Query for the item that is to be deleted.
    itemToDelete = session.query(CategoryItem).filter_by(item_name=item).one()
    # Query for the user who is authorized to perform deletions.
    authorized_user = session.query(User).filter_by(
        id=itemToDelete.user_id).one()
    if username != authorized_user.name:
        return """<script>function myFunction()
         {alert('You are not authorized to delete items in this catalog.
         Please create your own catalog in order to delete items.');}</script>
         <body onload='myFunction()''>"""
    if request.method == 'POST':
        session.delete(itemToDelete)
        session.commit()
        flash('Category Item Successfully Deleted')
        return redirect(url_for('main_page'))
    else:
        return render_template('deleteItem.html', item=item)


@app.route('/gconnect', methods=['POST'])
def gconnect():
    """Taken from Udacity, this function allows us to provide sign in with
     google."""

    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(
            json.dumps('Current user is already connected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # see if user exists, if it doesn't make a new one
    user_id = getUserID(data["email"])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    # Over line limit, but should pass since it is Udacity code.
    output += """ style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> """
    flash("you are now logged in as %s" % login_session['username'])
    print "done!"
    return output


@app.route('/gdisconnect')
def gdisconnect():
    """Udacity code for disconnecting a user from google sign-in."""
    access_token = login_session.get('access_token')
    if access_token is None:
        print 'Access Token is None'
        response = make_response(json.dumps(
            'Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    print 'In gdisconnect access token is %s', access_token
    print 'User name is: '
    print login_session['username']
    # Over the line character limit but should pass because this is Udacity
    # code.
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print 'result is '
    print result
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        # Over the line character limit but should pass because this is Udacity
        # code.
        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        response = make_response(json.dumps(
            'Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response

# Helper functions.


def getUserID(email):
    """Returns a user id.
    Keyword Arguments:
    email(str): a string representation of an email address.
    """
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except BaseException:
        return None


def getUserInfo(user_id):
    """Return a user object.

    Keyword Arguments:
    user_id(int): An integer representation of a user_id.
    """
    user = session.query(User).filter_by(id=user_id).one()
    return user


def createUser(login_session):
    """Creates a new user and returns their user_id.

    Keyword Arguments:
    login_session(obj): A login session object.
    """
    # Create a new user from the login_session object.
    newUser = User(
        name=login_session['username'],
        email=login_session['email'],
        picture=login_session['picture'])
    # Add the user to the database.
    session.add(newUser)
    # Commit the changes.
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


if __name__ == '__main__':
    app.debug = True
    app.secret_key = 'super_secret_key'
    app.run(host='0.0.0.0', port=8000)
