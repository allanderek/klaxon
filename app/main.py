"""An attempt at a web application that consolidates your
online life. The idea is that one place will provide you
with a list of things to do, such as 'You have unread Facebook
events, unread important emails, some rss feeds to read, and a
twitter notification'. Something like that, not really sure how
will all work in the end. If at all.
"""

import requests
import flask
from flask import request, make_response
from flask.ext.sqlalchemy import SQLAlchemy
import flask_wtf
import wtforms
from authomatic.providers import oauth2
from authomatic.adapters import WerkzeugAdapter
from authomatic import Authomatic

import threading


def async(f):
    def wrapper(*args, **kwargs):
        thr = threading.Thread(target=f, args=args, kwargs=kwargs)
        thr.start()
    return wrapper


import os
basedir = os.path.abspath(os.path.dirname(__file__))


class Configuration(object):
    SECRET_KEY = b'\xa0a\xd7nCN\x84\xd4Hn\xd5*\xa2\x89z\xdb\xf8w\xbd\xab)\xd3O\xd1'  # noqa
    LIVE_SERVER_PORT = 5000
    database_file = os.path.join(basedir, '../../db.sqlite')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + database_file
    ADMINS = ['allan.clark@gmail.com']

application = flask.Flask(__name__)
application.config.from_object(Configuration)
application.config.from_pyfile('private/settings.py')


database = SQLAlchemy(application)


class DBUser(database.Model):
    __tablename__ = 'users'
    id = database.Column(database.Integer, primary_key=True)


AUTHORISATON_CONFIG = {
    'google': {'class_': oauth2.Google,
               'consumer_key': application.config['GOOGLE_CONSUMER_KEY'],
               'consumer_secret': application.config['GOOGLE_CONSUMER_SECRET'],
               'scope': ['profile', 'email']
               }
}
authomatic = Authomatic(AUTHORISATON_CONFIG,
                        str(application.config['SECRET_KEY']),
                        report_errors=False)


@application.route('/login/<provider_name>/', methods=['GET', 'POST'])
def login(provider_name):
    response = make_response()
    adapter = WerkzeugAdapter(request, response)
    result = authomatic.login(adapter, provider_name)
    # If there is no LoginResult object, the login procedure is still pending.
    if result:
        if result.user:
            # We need to update the user to get more info.
            result.user.update()
        # The rest happens inside the template.
        return render_template('home.html', result=result)

    # Don't forget to return the response.
    return response


@application.template_test('plural')
def is_plural(container):
    return len(container) > 1


@application.template_filter('flash_bootstrap_category')
def flash_bootstrap_category(flash_category):
    return {'success': 'success',
            'info': 'info',
            'warning': 'warning',
            'error': 'danger',
            'danger': 'danger'}.get(flash_category, 'info')


def redirect_url(default='frontpage'):
    """ A simple helper function to redirect the user back to where they came.

        See: http://flask.pocoo.org/docs/0.10/reqcontext/ and also here:
        http://stackoverflow.com/questions/14277067/redirect-back-in-flask
    """

    return (flask.request.args.get('next') or flask.request.referrer or
            flask.url_for(default))


def render_template(*args, **kwargs):
    """ A simple wrapper, the base template requires some arguments such as
    the feedback form. This means that this argument will be in all calls to
    `flask.render_template` so we may as well factor it out."""
    return flask.render_template(*args, feedback_form=FeedbackForm(), **kwargs)


class FeedbackForm(flask_wtf.Form):
    feedback_name = wtforms.StringField("Name:")
    feedback_email = wtforms.StringField("Email:")
    feedback_text = wtforms.TextAreaField("Feedback:")


@application.route("/")
def frontpage():
    return render_template('frontpage.html')


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
import flask.ext.testing
import urllib
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
import pytest


class BasicFunctionalityTest(flask.ext.testing.LiveServerTestCase):

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

# A lightweight way to write down a few simple todos. Of course using the
# issue tracker is the better way to do this, this is just a lightweight
# solution for relatively *obvious* defects/todos.

# TODO: Figure out why the phantomjs instances continue to run after the
# tests are all finished.

if __name__ == "__main__":
    application.run(debug=True, threaded=True)
