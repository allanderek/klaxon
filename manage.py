import os

from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand

from app.main import application, database, set_database
import app.main as main

migrate = Migrate(application, database)
manager = Manager(application)
manager.add_command('db', MigrateCommand)

@manager.command
def develop(database=None, reset_database=False):
    """Develop locally and test out the server manually. Note that
    'reset_database' has no effect unless you set the database name.
    """
    # Developing locally means that the sample ATS when using Oauthlib will have
    # a problem because by default Oauthlib insists that we use https rather than
    # http. To do this, we should be able to create a self-signed certificate,
    # but I haven't been able to get this to work for some reason. Hence, instead
    # we disable the https requirement for local development only.
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    # '--threaded' is required when we make a request to ourselves, this is when
    # testing the sample API or the sample ATS. In the case of the sample API,
    # it is the dev.prechecked.com server that is making a request to the sample
    # API which would generally be on a different server but here is a request to
    # ourselves. In the case of the sample ATS, it is the ATS which is making a
    # request to the main prechecked app, normally the ATS would be a different
    # server but here it is making a call to itself.

    extra_dirs = [
        'app/static/css',
        'app/static/js',
        'app/templates'
        ]
    extra_files = extra_dirs[:]
    for extra_dir in extra_dirs:
        for dirname, dirs, files in os.walk(extra_dir):
            for filename in files:
                filename = os.path.join(dirname, filename)
                if os.path.isfile(filename):
                    extra_files.append(filename)

    if database is not None:
        set_database(database_filename=database, reset_database=reset_database)

    port = 8080
    host = '0.0.0.0'
    application.run(
        host=host,
        port=port,
        use_reloader=True,
        threaded=True,
        extra_files=extra_files)
    return 0
    # command = 'python manage.py runserver -h 0.0.0.0 -p 8080 --threaded'
    # return run_command(command)

default_links = [
    ('stable', 'Gmail', 'https://mail.google.com/mail/u/0/#inbox'),
    ('stable', 'Calendar', 'https://calendar.google.com/calendar/render?tab=mc#main_7'),
    ('stable', 'Dragon Go', 'http://www.dragongoserver.net/status.php'),
    ('stable', 'Tesuji-Charm', 'http://allanderek.pythonanywhere.com/status'),
    ('stable', 'TweetDeck', 'https://tweetdeck.twitter.com/'),
    ('stable', 'CommaFeed', 'https://www.commafeed.com/#/feeds/view/category/all'),
    ('stable', 'HashNode', 'https://hashnode.com/'),
    ('stable', 'HackerNews', 'https://news.ycombinator.com/newest'),
    ('stable', 'BBC Russian', 'http://www.bbc.com/russian'),
    ('stable', 'Tumblr', 'https://www.tumblr.com/blog/allanderek'),
    ('stable', 'Facebook', 'https://www.facebook.com/'),
    ('stable', 'CoinBase', 'https://www.coinbase.com/dashboard'),
    ('stable', 'IG', 'https://www.ig.com/uk/login'),
    ('stable', 'CodeInstitute', 'http://lms.codeinstitute.net/members/allanderek/dashboard/'),
    ('stable', 'My Blog', 'http://allanderek.github.io/'),

    ('queue', 'Hunted Apply', 'http://www.huntedapplications.com/apply.html'),
    ('queue', 'Python jobs board', 'https://www.python.org/jobs/location/telecommute/'),
    ('queue', 'Jobs4Bitcoins', 'https://www.reddit.com/r/Jobs4Bitcoins/'),
    ('queue', 'Outsourcely', 'https://www.outsourcely.com/remoteworker'),
    ('queue', 'RedditFreelance', 'https://www.reddit.com/r/freelanceuk/'),
    ('queue', 'RemotePython', 'https://www.remotepython.com/jobs/?country=any'),
    ('queue', 'Flask Token based authentication', 'https://realpython.com/blog/python/token-based-authentication-with-flask/'),
    ('queue', 'Kodi HTG', 'http://www.howtogeek.com/290346/kodi-is-not-a-piracy-application/'),

    ('dev-stable', 'C9', 'https://c9.io/allanderek'),
    ('dev-stable', 'Remi-running-app', 'https://remi-allanderek.c9users.io:8081/'),
    ('dev-stable', 'GitHub', 'https://github.com/'),
    ('dev-stable', 'Proggit', 'https://www.reddit.com/me/m/programming/'),
    ('dev-stable', 'Code Review Stack Exchange', 'http://codereview.stackexchange.com/questions'),
    ('dev-stable', 'Tomatoes timer', 'http://www.tomato.es/#'),

    ('dev-queue', 'git tips', 'https://adaptechsolutions.net/git-pro-tips/'),
    ('dev-queue', 'XSS-Game', 'https://xss-game.appspot.com/level4'),
    ('dev-queue', 'Bug Hunter University', 'https://sites.google.com/site/bughunteruniversity/behind-the-scenes/rewards-philosophy'),
    ('dev-queue', 'Content Security Policy', 'https://developers.google.com/web/fundamentals/security/csp/'),
    ('dev-queue', 'Py-Week', 'https://pyweek.org/23/'),
    ('dev-queue', 'Google Reward Program (bounties)', 'https://www.google.com/about/appsecurity/reward-program/'),
    ('dev-queue', 'Python Import system', 'https://docs.python.org/3/reference/import.html'),
    ('dev-queue', 'Installing GitHub Enterprise', 'https://help.github.com/enterprise/2.8/admin/guides/installation/installing-github-enterprise-on-openstack-kvm/'),
    ('dev-queue', 'Py-heat', 'https://github.com/csurfer/pyheat'),
    ('dev-queue', 'Sijax', 'http://pythonhosted.org/Sijax/index.html'),
    ]

@manager.command
def remake_db(really=False, addallan=False):
    if not really:
        print("You should probably use 'python manage.py db upgrade' instead.")
        print("If you really want to use remake_db, provide option --really.")
        print("")
        print("(See https://flask-migrate.readthedocs.org/en/latest/ for"
              " details.)")
        return 0
    else:
        database.drop_all()
        database.create_all()
        database.session.commit()
    if addallan:
        user = main.User()
        database.session.add(user)
        account_link = main.AccountLink(
            external_user_id = '118290736503630814624',
            provider_name = 'google',
            user = user
            )
        database.session.add(account_link)
        for category, name, address in default_links:
            link = main.UserLink(
                user = user,
                category = category,
                name = name,
                address = address
                )
            database.session.add(link)
        database.session.commit()



def run_command(command):
    """ We frequently inspect the return result of a command so this is just
        a utility function to do this. Generally we call this as:
        return run_command ('command_name args')
    """
    result = os.system(command)
    return 0 if result == 0 else 1

@manager.command
def test(db_file=None, browser=None):
    command = 'py.test --cov=app -rw --fulltrace app/main.py'
    if db_file is not None:
        command += " --db_file={}".format(db_file)
    if browser is not None:
        command += " --browser={}".format(browser)
    return run_command(command) or run_command('coverage html')


if __name__ == "__main__":
    manager.run()
