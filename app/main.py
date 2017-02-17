"""An attempt at a web application that consolidates your
online life. The idea is that one place will provide you
with a list of things to do, such as 'You have unread Facebook
events, unread important emails, some rss feeds to read, and a
twitter notification'. Something like that, not really sure how
will all work in the end. If at all.
"""

import requests
import requests_oauthlib
import flask
from flask import request, make_response
from flask_sqlalchemy import SQLAlchemy
import flask_wtf
import wtforms

import threading


def async(f):
    def wrapper(*args, **kwargs):
        thr = threading.Thread(target=f, args=args, kwargs=kwargs)
        thr.start()
    return wrapper


import os

def generated_file_path(additional_path):
    basedir = os.path.abspath(os.path.dirname(__file__))
    generated_dir = os.path.join(basedir, '../generated/')
    return os.path.join(generated_dir, additional_path)

class Configuration(object):
    SECRET_KEY = b'\xa0a\xd7nCN\x84\xd4Hn\xd5*\xa2\x89z\xdb\xf8w\xbd\xab)\xd3O\xd1'  # noqa
    LIVE_SERVER_PORT = 5000
    database_file = generated_file_path('play.db')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + database_file
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMINS = ['allan.clark@gmail.com']
    DEBUG=True

application = flask.Flask(__name__)
application.config.from_object(Configuration)
application.config.from_pyfile('private/settings.py')


database = SQLAlchemy(application)

def set_database(database_filename='test.db', reset_database=False):
    """Allows us to set the database name so that we could, for example, run
    the develop server with the test database, which would then have all the
    test data, that may be useful either just to avoid inputting it by hand or
    to figure out why a test is failing.
    """
    database_file = generated_file_path(database_filename)
    application.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + database_file
    if reset_database:
        with application.app_context():
            database.drop_all()
            database.create_all()
            database.session.commit()

class User(database.Model):
    __tablename__ = 'user'
    id = database.Column(database.Integer, primary_key=True)

# TODO: Could this be a constant?
def user_id_column(nullable=True):
    return database.Column(database.Integer, database.ForeignKey('user.id'), nullable=nullable)
def user_column(key_field, **kwargs):
    return database.relationship(User, foreign_keys=[key_field], **kwargs)

class AccountLink(database.Model):
    """Links a klaxon account to a login from an external provider such
    google, or twitter."""
    external_user_id = database.Column(database.String, primary_key=True)
    provider_name = database.Column(database.String, nullable=False)

    user_id = user_id_column(nullable=False)
    user = user_column(user_id)

class UserLink(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    category = database.Column(database.String, nullable=False)
    name = database.Column(database.String, nullable=False)
    address = database.Column(database.String, nullable=False)

    user_id = user_id_column(nullable=False)
    user = user_column(user_id, backref=database.backref('links', lazy='dynamic'))


@application.route('/login/<provider_name>/', methods=['GET', 'POST'])
def login(provider_name):
    scope = ['https://www.googleapis.com/auth/userinfo.email']
    client_id = application.config['GOOGLE_CONSUMER_KEY']
    redirect_uri = flask.url_for('login', provider_name=provider_name, _external=True)
    oauth = requests_oauthlib.OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scope)

    state = request.args.get('state', None)
    if not state:
        authorization_url, state = oauth.authorization_url(
            'https://accounts.google.com/o/oauth2/auth',
            # access_type and approval_prompt are Google specific extra
            # parameters.
            access_type="offline", approval_prompt="force")

        return flask.redirect(authorization_url)

    flask.session['state'] = state
    code = request.args.get('code')
    oauth.fetch_token(
        'https://accounts.google.com/o/oauth2/token',
        code=code,
        # Google specific extra parameter used for client
        # authentication
        client_secret=application.config['GOOGLE_CONSUMER_SECRET'])

    profile_response = oauth.get('https://www.googleapis.com/oauth2/v1/userinfo')
    # Fields should be:
    # {'id', 'verified_email', 'given_name', 'link', 'gender', 'name',
    # 'picture', 'family_name', 'email'}
    profile = profile_response.json()
    # TODO: Deal with errors/refusals that sort of thing.

    account_link = AccountLink.query.filter_by(
        external_user_id=profile['id'],
        provider_name=provider_name).first()
    # So probably we actually want to ask the user if they want to create
    # an account or something like that. Alternatively we have login as
    # separate from 'sign-up with' and here we would just error and say
    # "No such account, would you like to sign-up, or perhaps you have
    # already signed-up with a different provider?"
    if account_link:
        user = account_link.user
    else:
        user = User()
        database.session.add(user)
        account_link = AccountLink(
            external_user_id = profile['id'],
            provider_name = provider_name,
            user = user
            )
        database.session.add(account_link)
        database.session.commit()

    flask.session['user.id'] = user.id
    return redirect(default='frontpage')


@application.template_test('plural')
def is_plural(container):
    return len(container) > 1


def redirect_url(default='frontpage'):
    """ A simple helper function to redirect the user back to where they came.

        See: http://flask.pocoo.org/docs/0.10/reqcontext/ and also here:
        http://stackoverflow.com/questions/14277067/redirect-back-in-flask
    """

    result = (flask.request.args.get('next') or flask.request.referrer or
            flask.url_for(default))
    return result

def redirect(default='frontpage'):
    return flask.redirect(redirect_url(default=default))


def render_template(*args, **kwargs):
    """ A simple wrapper, the base template requires some arguments such as
    the feedback form. This means that this argument will be in all calls to
    `flask.render_template` so we may as well factor it out."""
    return flask.render_template(*args, feedback_form=FeedbackForm(), **kwargs)


def get_current_user():
    user_id = flask.session.get('user.id', None)
    if user_id:
        user = User.query.filter_by(id = user_id).first()
        # Note that this will return 'None' if there is no such user, which may
        # we be what we want but is questionable.
        return user
    return None

def unauthorized_response(message=None):
    message = message or 'You must be logged-in to do that.'
    response = flask.jsonify({'message': message})
    response.status_code = 401
    return response

@application.route("/logout/")
def logout():
    del flask.session['user.id']
    return redirect(default='frontpage')

@application.route("/")
def frontpage():
    user = get_current_user()
    if user:
        return render_template('home.html', user=user)
    return render_template('frontpage.html')


class AddUpdateLinkForm(flask_wtf.FlaskForm):
    link_id = wtforms.HiddenField('link_id')
    category = wtforms.StringField("Email:")
    name = wtforms.StringField("Name:")
    address = wtforms.TextAreaField("Feedback:")


@application.route("/add-update-link", methods=['POST'])
def add_update_link():
    assert request.method == 'POST'
    user = get_current_user()
    # TODO: Test this is out, in particular I guess you could use two
    # windows to test this out manually.
    if not user:
        return unauthorized_response()
    form = AddUpdateLinkForm(request.form)
    if form.link_id.data:
        link = UserLink.query.filter_by(id=form.link_id.data).first()
        # TODO: What to do if we do not find it?
    else:
        link = UserLink(user=user)
        database.session.add(link)
    link.category = form.category.data
    link.name = form.name.data
    link.address = form.address.data
    database.session.commit()
    return flask.jsonify({'link_id': link.id})

@async
def send_email_message_mailgun(email):
    sandbox = "sandboxadc7751e75ba41dca5e4ab88e3c13306.mailgun.org"
    url = "https://api.mailgun.net/v3/{0}/messages".format(sandbox)
    sender_address = "mailgun@{0}".format(sandbox)
    if email.sender_name is not None:
        sender = "{0} <{1}>".format(email.sender_name, sender_address)
    else:
        sender = sender_address
    api_key = application.config['MAILGUN_API_KEY']
    return requests.post(url,
                         auth=("api", api_key),
                         data={"from": sender,
                               "to": email.recipients,
                               "subject": email.subject,
                               "text": email.body})


class Email(object):
    """ Simple representation of an email message to be sent."""

    def __init__(self, subject, body, sender_name, recipients):
        self.subject = subject
        self.body = body
        self.sender_name = sender_name
        self.recipients = recipients


def send_email_message(email):
    # We don't want to actually send the message every time we're testing.
    # Note that if we really wish to record the emails and check that the
    # correct ones were "sent" out, then we have to do something a bit clever
    # because this code will be executed in a different process to the
    # test code. We could have some kind of test-only route that returns the
    # list of emails sent as a JSON object or something.
    if not application.config['TESTING']:
        send_email_message_mailgun(email)


class FeedbackForm(flask_wtf.FlaskForm):
    feedback_name = wtforms.StringField("Name:")
    feedback_email = wtforms.StringField("Email:")
    feedback_text = wtforms.TextAreaField("Feedback:")


@application.route('/give_feedback', methods=['POST'])
def give_feedback():
    form = FeedbackForm()
    if not form.validate_on_submit():
        message = ('Feedback form has not been validated.'
                   'Sorry it was probably my fault')
        flask.flash(message, 'error')
        return flask.redirect(redirect_url())
    feedback_email = form.feedback_email.data.lstrip()
    feedback_name = form.feedback_name.data.lstrip()
    feedback_content = form.feedback_text.data
    subject = 'Feedback for Klaxon'
    sender_name = 'Klaxon Feedback Form'
    recipients = application.config['ADMINS']
    message_body = """
    You got some feedback from the 'klaxon' web application.
    Sender's name = {0}
    Sender's email = {1}
    Content: {2}
    """.format(feedback_name, feedback_email, feedback_content)
    email = Email(subject, message_body, sender_name, recipients)
    send_email_message(email)
    flask.flash("Thanks for your feedback!", 'info')
    return flask.redirect(redirect_url())

# Now for some testing.
import flask_testing
import urllib
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
import pytest


class BasicFunctionalityTest(flask_testing.LiveServerTestCase):

    def create_app(self):
        application.config['TESTING'] = True
        # Default port is 5000
        application.config['LIVESERVER_PORT'] = 8943

        # Don't use the production database but a temporary test
        # database.
        application.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///test.db"

        self.driver = webdriver.PhantomJS()
        self.driver.set_window_size(1120, 550)
        return application

    def get_url(self, local_url):
        return "/".join([self.get_server_url(), local_url])

    def assertCssSelectorExists(self, css_selector):
        """ Asserts that there is an element that matches the given
        css selector."""
        # We do not actually need to do anything special here, if the
        # element does not exist we fill fail with a NoSuchElementException
        # however we wrap this up in a pytest.fail because the error message
        # is then a bit nicer to read.
        try:
            self.driver.find_element_by_css_selector(css_selector)
        except NoSuchElementException:
            pytest.fail("Element {0} not found!".format(css_selector))

    def assertCssSelectorNotExists(self, css_selector):
        """ Asserts that no element that matches the given css selector
        is present."""
        with pytest.raises(NoSuchElementException):
            self.driver.find_element_by_css_selector(css_selector)

    def fill_in_and_submit_form(self, fields, submit):
        for field_css, field_text in fields.items():
            self.fill_in_text_input_by_css(field_css, field_text)
        self.click_element_with_css(submit)

    def click_element_with_css(self, selector):
        element = self.driver.find_element_by_css_selector(selector)
        element.click()

    def fill_in_text_input_by_css(self, input_css, input_text):
        input_element = self.driver.find_element_by_css_selector(input_css)
        input_element.send_keys(input_text)

    def check_flashed_message(self, message, category):
        category = flash_bootstrap_category(category)
        selector = 'div.alert.alert-{0}'.format(category)
        elements = self.driver.find_elements_by_css_selector(selector)
        if category == 'error':
            print("error: messages:")
            for e in elements:
                print(e.text)
        self.assertTrue(any(message in e.text for e in elements))

    def open_new_window(self, url):
        script = "$(window.open('{0}'))".format(url)
        self.driver.execute_script(script)

    def test_feedback(self):
        self.driver.get(self.get_url('/'))
        feedback = {'#feedback_email': "example_user@example.com",
                    '#feedback_name': "Avid User",
                    '#feedback_text': "I hope your feedback form works."}
        self.fill_in_and_submit_form(feedback, '#feedback_submit_button')
        self.check_flashed_message("Thanks for your feedback!", 'info')

    def test_server_is_up_and_running(self):
        response = urllib.request.urlopen(self.get_server_url())
        assert response.code == 200

    def test_frontpage_links(self):
        """ Just make sure we can go to the front page and that
        the main menu is there and has at least one item."""
        self.driver.get(self.get_server_url())
        main_menu_css = 'nav .container #navbar ul li'
        self.assertCssSelectorExists(main_menu_css)

    def setUp(self):
        database.create_all()
        database.session.commit()

    def tearDown(self):
        self.driver.quit()
        database.session.remove()
        database.drop_all()


if __name__ == "__main__":
    application.run(debug=True, threaded=True)
