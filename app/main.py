"""An attempt at a web application that consolidates your
online life. The idea is that one place will provide you
with a list of things to do, such as 'You have unread Facebook
events, unread important emails, some rss feeds to read, and a
twitter notification'. Something like that, not really sure how
will all work in the end. If at all.
"""
import logging

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
    TEST_SERVER_PORT = 5001
    database_file = generated_file_path('play.db')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + database_file
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMINS = ['allan.clark@gmail.com']
    DEBUG=True
    LOG_LEVEL=logging.DEBUG

application = flask.Flask(__name__)
application.config.from_object(Configuration)
application.config.from_pyfile('private/settings.py')

logger = logging.getLogger()
logger.setLevel(application.config['LOG_LEVEL'])

database = SQLAlchemy(application)

def set_database(db_file='test.db', reset_database=False):
    """Allows us to set the database name so that we could, for example, run
    the develop server with the test database, which would then have all the
    test data, that may be useful either just to avoid inputting it by hand or
    to figure out why a test is failing.
    """
    database_file = generated_file_path(db_file)
    application.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + database_file
    if reset_database or not os.path.exists(database_file):
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

@application.context_processor
def inject_feedback_form():
    return dict(feedback_form=FeedbackForm())

@application.template_filter('suppress_none')
def supress_none(s, default=''):
    return s if s is not None else default

# TODO: Obviously this is probably pretty generalisable to other account kinds.
# We probably just need to take the provider_name as an argument.
def google_account_link_and_login(google_profile_id, automatic_signup=True):
    """Takes in a google account profile id and looks up the klaxon account
    linked to that google id. Then logs in that user. So obviously it is
    important that this is not called unless we really have authorisation from
    the user. If 'automatic_signup' is set to True, then if no account link exists
    we create a new klaxon account and link it to the given google profile id.
    Basically I'm not sure this is best behaviour I think we should probably
    separate sign-up, from login. If someone logs-in with google and we do not
    have a current-signup we suggest that the user either:
    1. Has signed up before but not linked their account to their google account
    2. Has never signed-up before
    3. Has signed up with a different google account.
    But for now, we just sign-them-up automatically.
    """
    provider_name = 'google'
    account_link = AccountLink.query.filter_by(
        external_user_id=google_profile_id,
        provider_name=provider_name).first()
    # So probably we actually want to ask the user if they want to create
    # an account or something like that. Alternatively we have login as
    # separate from 'sign-up with' and here we would just error and say
    # "No such account, would you like to sign-up, or perhaps you have
    # already signed-up with a different provider?"
    assert automatic_signup
    if account_link:
        user = account_link.user
    else:
        user = User()
        database.session.add(user)
        account_link = AccountLink(
            external_user_id = google_profile_id,
            provider_name = provider_name,
            user = user
            )
        database.session.add(account_link)
        database.session.commit()

    flask.session['user.id'] = user.id
    return redirect(default='frontpage')

def do_google_login():
    provider_name = 'google'
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

    return google_account_link_and_login(profile['id'], automatic_signup=True)


# TODO: Does this need to be both a 'GET' and a 'POST'?
@application.route('/login/<provider_name>/', methods=['GET', 'POST'])
def login(provider_name):
    assert provider_name == 'google'
    return do_google_login()



@application.template_test('plural')
def is_plural(container):
    return len(container) > 1


def redirect(default='frontpage'):
    """ A simple helper function to redirect the user back to where they came.

        See: http://flask.pocoo.org/docs/0.10/reqcontext/ and also here:
        http://stackoverflow.com/questions/14277067/redirect-back-in-flask
    """
    redirect_url = (flask.request.args.get('next') or flask.request.referrer or
            flask.url_for(default))
    return flask.redirect(redirect_url)


def get_current_user():
    user_id = flask.session.get('user.id', None)
    if user_id:
        user = User.query.filter_by(id = user_id).first()
        # Note that this will return 'None' if there is no such user, which may
        # we be what we want but is questionable.
        return user
    return None

def error_response(response_code, message):
    """Used for producing an ajax response that indicates failure."""
    response = flask.jsonify({'message': message})
    response.status_code = response_code
    return response

def unauthorized_response(message=None):
    message = message or 'You must be logged-in to do that.'
    return error_response(401, message)

def bad_request_response(message=None):
    message = message or 'The client made a bad request.'
    return error_response(400, message)

def success_response(results=None):
    results = results or {}
    results['success'] = True
    return flask.jsonify(results)

@application.route("/logout/")
def logout():
    if 'user.id' in flask.session:
        del flask.session['user.id']
    return redirect(default='frontpage')

@application.route("/")
def frontpage():
    user = get_current_user()
    if user:
        return flask.render_template('home.html', user=user)
    return flask.render_template('frontpage.html')


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

@application.route("/delete-link", methods=['POST'])
def delete_link():
    assert request.method == 'POST'
    user = get_current_user()
    # TODO: Test this is out, in particular I guess you could use two
    # windows to test this out manually.
    if not user:
        return unauthorized_response()
    if not 'link_id' in request.form:
        return bad_request_response(message='The request contained no link id.')

    # TODO: Should have .one() with a generic way to deal with an SQL error.
    # Note that this also catches the case where someone is attempting to delete
    # someone else's link.
    link = UserLink.query.filter_by(id=request.form.get('link_id'), user_id=user.id).first()
    if not link:
        return bad_request_response(message='No such user link.')

    database.session.delete(link)
    database.session.commit()

    return success_response()

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

    def log_email_message(self):
        logging.debug("------ Email message ------")
        logging.debug("From: {}".format(self.sender_name))
        logging.debug("To: {}".format(self.recipients))
        logging.debug("Subject: {}".format(self.subject))
        logging.debug("Message: {}".format(self.body))
        logging.debug("------- End email message -----")


def send_email_message(email):
    # We don't want to actually send the message every time we're testing.
    # Note that if we really wish to record the emails and check that the
    # correct ones were "sent" out, then we have to do something a bit clever
    # because this code will be executed in a different process to the
    # test code. We could have some kind of test-only route that returns the
    # list of emails sent as a JSON object or something.
    if not application.config['TESTING'] and not application.config['DEBUG']:
        send_email_message_mailgun(email)
    else:
        email.log_email_message()


class FeedbackForm(flask_wtf.FlaskForm):
    feedback_name = wtforms.StringField("Name:")
    feedback_email = wtforms.StringField("Email:")
    feedback_text = wtforms.TextAreaField("Feedback:")


@application.route('/give_feedback', methods=['POST'])
def give_feedback():
    form = FeedbackForm()
    if not form.validate_on_submit():
        message = """Feedback form has not been validated.
            Sorry it was probably my fault"""
        return bad_request_response(message=message)
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
    return success_response()

# Now for some testing.
import flask.testing
from selenium import webdriver
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, InvalidElementStateException, TimeoutException
# from selenium.webdriver.common.action_chains import ActionChains
# from selenium.webdriver.common.keys import Keys
import pytest
# Currently just used for the temporary hack to quit the phantomjs process
# see below in quit_driver.
import signal

import threading
import wsgiref.simple_server

import unittest.mock as mock

def setup_testing(db_file='test.db'):
    reset_database = db_file == 'test.db'
    set_database(db_file=db_file, reset_database=reset_database)
    application.config['TESTING'] = True


class ServerThread(threading.Thread):
    def setup(self, db_file='test.db'):
        setup_testing(db_file=db_file)
        self.port = application.config['TEST_SERVER_PORT']

    def run(self):
        self.httpd = wsgiref.simple_server.make_server('localhost', self.port, application)
        self.httpd.serve_forever()

    def stop(self):
        self.httpd.shutdown()

class BrowserClient(object):
    """Interacts with a running instance of the application via animating a
    browser."""
    def __init__(self, db_file='test.db', browser="phantom",):
        self.server_thread = ServerThread()
        self.server_thread.setup(db_file=db_file)
        self.server_thread.start()

        driver_class = {
            'phantom': webdriver.PhantomJS,
            'chrome': webdriver.Chrome,
            'firefox': webdriver.Firefox
            }.get(browser)
        self.driver = driver_class()
        self.driver.set_window_size(1200, 760)


    def finalise(self):
        self.driver.close()
        # A bit of hack this but currently there is some bug I believe in
        # the phantomjs code rather than selenium, but in any case it means that
        # the phantomjs process is not being killed so we do so explicitly here
        # for the time being. Obviously we can remove this when that bug is
        # fixed. See: https://github.com/SeleniumHQ/selenium/issues/767
        self.driver.service.process.send_signal(signal.SIGTERM)
        self.driver.quit()

        self.server_thread.stop()
        self.server_thread.join()


    @property
    def page_source(self):
        return self.driver.page_source

    def log_current_page(self, message=None, output_basename=None):
        content = self.page_source
        if message:
            logging.info(message)
        # This is frequently what we really care about so I also output it
        # here as well to make it convenient to inspect (with highlighting).
        basename = output_basename or 'log-current-page'
        file_name = generated_file_path(basename + '.html')
        with open(file_name, 'w') as outfile:
            if message:
                outfile.write("<!-- {} --> ".format(message))
            outfile.write(content)
        filename = generated_file_path(basename + '.png')
        self.driver.save_screenshot(filename)

    def scroll_to_element(self, element):
        self.driver.execute_script("return arguments[0].scrollIntoView();", element)

    def wait_for_condition(self, condition, timeout=5):
        """Wait for the given condition and if it does not occur then log the
        the current page and fail the current test. If timeout is given then
        that is how long we wait.
        """
        wait = WebDriverWait(self.driver, timeout)
        try:
            element = wait.until(condition)
            return element
        except TimeoutException:
            self.log_current_page()
            pytest.fail("Waiting on a condition timed out, current page logged.")

    def wait_for_element_to_be_clickable(self, selector, **kwargs):
        element_spec = (By.CSS_SELECTOR, selector)
        condition = expected_conditions.element_to_be_clickable(element_spec)
        return self.wait_for_condition(condition, **kwargs)

    def wait_for_element(self, selector, **kwargs):
        element_spec = (By.CSS_SELECTOR, selector)
        condition = expected_conditions.presence_of_element_located(element_spec)
        return self.wait_for_condition(condition, **kwargs)

    def css_exists(self, css_selector):
        """ Asserts that there is an element that matches the given
        css selector."""
        # We do not actually need to do anything special here, if the
        # element does not exist we fill fail with a NoSuchElementException
        # however we wrap this up in a pytest.fail because the error message
        # is then a bit nicer to read.
        try:
            self.wait_for_element(css_selector)
        except NoSuchElementException:
            self.log_current_page()
            pytest.fail('Element "{0}" not found! Current page logged.'.format(css_selector))

    def check_css_selector_doesnt_exist(self, css_selector):
        """Assert that there is no element that matches the given css selector.
        Note that we do not use 'wait_for_element' since in that case a successful
        test woult take the whole timeout time."""
        try:
            self.driver.find_element_by_css_selector(css_selector)
        except NoSuchElementException:
            return
        self.log_current_page()
        pytest.fail("""Element "{0}" was found on page when expected not to be
        present. Current page logged.""".format(css_selector))

    def click(self, selector, **kwargs):
        """ Click an element given by the given selector. Passes its kwargs on
        to wait for element, so in particular accepts 'no_fail' which means the
        current test is not failed if the element does not exist (nor appear
        once waited upon).
        """
        try:
            self.wait_for_element(selector, **kwargs)
            element = self.driver.find_element_by_css_selector(selector)
            self.scroll_to_element(element)
            self.wait_for_element_to_be_clickable(selector)
            element.click()
            # TODO: We should probably check somethings work with pressing Enter.
            # element.send_keys(Keys.ENTER)
        except NoSuchElementException:
            if not kwargs.get('no_fail', False):
                self.log_current_page()
                pytest.fail('Element "{0}" not found! Current page logged.'.format(selector))
        except InvalidElementStateException as e:
            message = """Invalid state exception: {}.
            Current page logged.""".format(selector)
            self.log_current_page(message=message)
            pytest.fail(message + ": " + e.msg)


def make_url(endpoint, **kwargs):
    with application.app_context():
        return flask.url_for(endpoint, **kwargs)

def google_login_user(client, google_id):
    mock_do_google_login = mock.create_autospec(
        do_google_login,
        side_effect=lambda : google_account_link_and_login(google_id))
    with mock.patch('main.do_google_login', mock_do_google_login):
        client.click('#google-login-link')
        client.css_exists('#logout-link')


@pytest.fixture(scope='module')
def client(request):
    options = ['db_file', 'browser']
    kwargs = {k: request.config.getoption('--{}'.format(k), None) for k in options}
    kwargs = {k:v for k,v in kwargs.items() if v is not None}
    client = BrowserClient(**kwargs)
    request.addfinalizer(client.finalise)
    return client


def test_main(client):
    port = application.config['TEST_SERVER_PORT']
    application.config['SERVER_NAME'] = 'localhost:{}'.format(port)

    # Start off by logging out, so we ensure that we are currently logged
    # out, in order to start the rest of the test.
    client.driver.get(make_url('logout'))
    assert 'Klaxon' in client.page_source

    test_google_id = '1234'
    google_login_user(client, test_google_id)
