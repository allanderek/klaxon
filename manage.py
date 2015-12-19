import os

from flask.ext.script import Manager
from flask.ext.migrate import Migrate, MigrateCommand

from app.main import application, database

migrate = Migrate(application, database)
manager = Manager(application)
manager.add_command('db', MigrateCommand)


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
