import os

from flask.ext.script import Manager
from flask.ext.migrate import Migrate, MigrateCommand

from app.main import application, database, set_database

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


@manager.command
def remake_db(really=False, addverifiers=True, staff=True, port=None):
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



def run_command(command):
    """ We frequently inspect the return result of a command so this is just
        a utility function to do this. Generally we call this as:
        return run_command ('command_name args')
    """
    result = os.system(command)
    return 0 if result == 0 else 1


@manager.command
def coffeelint():
    return run_command('coffeelint app/coffee')


@manager.command
def coffeebuild():
    return run_command('coffee -c -o app/static/compiled-js app/coffee')


@manager.command
def test_browser(name):
    """Run a single browser test, given its name (excluding `test_`)"""
    command = "python -m unittest app.browser_tests.test_{}".format(name)
    return run_command(command)


@manager.command
def test_casper(name=None):
    """Run the specified single CasperJS test, or all if not given"""
    from app.test_browser import PhantomTest
    phantom_test = PhantomTest('test_run')
    phantom_test.set_single(name)
    result = phantom_test.test_run()
    return (0 if result == 0 else 1)


@manager.command
def test_main():
    """Run the python only tests defined within app/main.py"""
    return run_command("py.test app/main.py")


@manager.command
def test():
    casper_result = test_casper()
    main_result = test_main()
    return max([casper_result, main_result])


@manager.command
def coverage(quick=False, browser=False, phantom=False):
    rcpath = os.path.abspath('.coveragerc')

    quick_command = 'test_package app.tests'
    # once all browser tests are converted to phantom, we can remove the
    # phantom option
    browser_command = 'test_package app.browser_tests'
    phantom_command = 'test_module app.browser_tests.phantom'
    full_command = 'test_all'

    if quick:
        manage_command = quick_command
    elif browser:
        manage_command = browser_command
    elif phantom:
        manage_command = phantom_command
    else:
        manage_command = full_command

    if os.path.exists('.coverage'):
        os.remove('.coverage')
    os.system(("COVERAGE_PROCESS_START='{0}' "
               "coverage run manage.py {1}").format(rcpath, manage_command))
    os.system("coverage combine")
    os.system("coverage report -m")
    os.system("coverage html")


@manager.command
def run_test_server():
    """Used by the phantomjs tests to run a live testing server"""
    # running the server in debug mode during testing fails for some reason
    application.DEBUG = True
    application.TESTING = True
    port = application.config['LIVE_SERVER_PORT']
    application.run(port=port, use_reloader=False, threaded=True)

if __name__ == "__main__":
    manager.run()
