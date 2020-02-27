"""
The MIT License

Copyright (c) 2015-2020 Just-Some-Bots (https://github.com/Just-Some-Bots)
Copyright (c) 2017-2020 Zenrac - Watora (https://github.com/Zenrac/Watora)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""


from __future__ import print_function

import os
import sys
import pathlib
import logging
import tempfile
import traceback
import subprocess

from shutil import disk_usage, rmtree
from multiprocessing import Process, Pipe, Queue

import asyncio

try:
    import uvloop
except ImportError:
    pass
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

loop = asyncio.get_event_loop()


class PIP(object):
    @classmethod
    def run(cls, command, check_output=False):
        if not cls.works():
            raise RuntimeError("Could not import pip.")

        try:
            return PIP.run_python_m(*command.split(), check_output=check_output)
        except subprocess.CalledProcessError as e:
            return e.returncode
        except:  # noqa: E722
            traceback.print_exc()
            print("Error using -m method")

    @classmethod
    def run_python_m(cls, *args, **kwargs):
        check_output = kwargs.pop('check_output', False)
        check = subprocess.check_output if check_output else subprocess.check_call
        return check([sys.executable, '-m', 'pip'] + list(args))

    @classmethod
    def run_pip_main(cls, *args, **kwargs):
        import pip

        args = list(args)
        check_output = kwargs.pop('check_output', False)

        if check_output:
            from io import StringIO

            out = StringIO()
            sys.stdout = out

            try:
                pip.main(args)
            except:  # noqa: E722
                traceback.print_exc()
            finally:
                sys.stdout = sys.__stdout__

                out.seek(0)
                pipdata = out.read()
                out.close()

                print(pipdata)
                return pipdata
        else:
            return pip.main(args)

    @classmethod
    def run_install(cls, cmd, quiet=False, check_output=False):
        return cls.run("install %s%s" % ('-q ' if quiet else '', cmd), check_output)

    @classmethod
    def run_show(cls, cmd, check_output=False):
        return cls.run("show %s" % cmd, check_output)

    @classmethod
    def works(cls):
        try:
            import pip  # noqa: F401
            return True
        except ImportError:
            return False


# Setup initial loggers
tmpfile = tempfile.TemporaryFile('w+', encoding='utf8')
log = logging.getLogger('launcher')
log.setLevel(logging.DEBUG)
# log.setLevel(logging.INFO)
sh = logging.StreamHandler(stream=sys.stdout)
sh.setFormatter(logging.Formatter(
    fmt="[%(asctime)s] - %(levelname)s: %(message)s"
))

sh.setLevel(logging.INFO)
log.addHandler(sh)

tfh = logging.StreamHandler(stream=tmpfile)
tfh.setFormatter(logging.Formatter(
    fmt="[%(asctime)s] - %(levelname)s - %(name)s: %(message)s"
))
tfh.setLevel(logging.DEBUG)
# tfh.setLevel(logging.INFO)
log.addHandler(tfh)


def _delete_old_audiocache(path=os.getcwd() + "//data//downloads"):
    try:
        rmtree(path)
        return True
    except OSError:  # noqa: E722
        try:
            os.rename(path, path + '__')
        except OSError:
            return False
        try:
            rmtree(path)
        except OSError:
            os.rename(path + '__', path)
            return False
    return True


def finalize_logging():
    if os.path.isfile("logs/watora.log"):
        log.info("Moving old musicbot log")
        try:
            if os.path.isfile("logs/watora.log.last"):
                os.unlink("logs/watora.log.last")
            os.rename("logs/watora.log", "logs/watora.log.last")
        except OSError:
            pass

    with open("logs/watora.log", 'w', encoding='utf8') as f:
        tmpfile.seek(0)
        f.write(tmpfile.read())
        tmpfile.close()

        f.write('\n')
        f.write(" PRE-RUN SANITY CHECKS PASSED ".center(80, '#'))
        f.write('\n\n')

    global tfh
    log.removeHandler(tfh)
    del tfh

    fh = logging.FileHandler("logs/watora.log", mode='a', encoding='utf8')
    fh.setFormatter(logging.Formatter(
        fmt="[%(asctime)s] - %(levelname)s: %(message)s"
    ))
    fh.setLevel(logging.DEBUG)
    log.addHandler(fh)

    sh.setLevel(logging.INFO)

    for logger in ['discord', 'lavalink', 'listenmoe']:
        dlog = logging.getLogger(logger)
        dlh = logging.StreamHandler(stream=sys.stdout)
        dlh.setFormatter(logging.Formatter(
            fmt="[%(asctime)s] - %(levelname)s: %(message)s"
        ))
        dlog.addHandler(dlh)

        dfh = logging.FileHandler(log.handlers[1].baseFilename)
        dfh.setFormatter(logging.Formatter(
            fmt="[%(asctime)s] - %(levelname)s: %(message)s"
        ))
        dlog.addHandler(dfh)

        dlh.setLevel(logging.INFO)
        dfh.setLevel(logging.INFO)


def bugger_off(msg="Press enter to continue . . .", code=1):
    input(msg)
    sys.exit(code)


# TODO: all of this
def sanity_checks(optional=True):
    log.info("Starting sanity checks")
    # Required

    # Make sure we're on python3.5+
    req_ensure_py3()

    # Fix windows encoding fuckery
    req_ensure_encoding()

    # Make sure we're in a writeable env
    req_ensure_env()

    # Make our folders if needed
    req_ensure_folders()

    # Optional
    if not optional:
        return

    # check disk usage
    opt_check_disk_space()

    log.info("Checks passed.")


def req_ensure_py3():
    log.info("Checking for python 3.5+")

    if sys.version_info < (3, 5):
        log.warning("Python 3.5+ is required. This version is %s",
                    sys.version.split()[0])
        log.warning("Attempting to locate python 3.5...")

        pycom = None

        if sys.platform.startswith('win'):
            log.info('Trying "py -3.5"')
            try:
                subprocess.check_output('py -3.5 -c "exit()"', shell=True)
                pycom = 'py -3.5'
            except:  # noqa: E722

                log.info('Trying "python3"')
                try:
                    subprocess.check_output('python3 -c "exit()"', shell=True)
                    pycom = 'python3'
                except:  # noqa: E722
                    pass

            if pycom:
                log.info("Python 3 found.  Launching bot...")
                pyexec(pycom, 'run.py')

                # I hope ^ works
                os.system('start cmd /k %s run.py' % pycom)
                sys.exit(0)

        else:
            log.info('Trying "python3.5"')
            try:
                pycom = subprocess.check_output(
                    'python3.5 -c "exit()"'.split()).strip().decode()
            except:  # noqa: E722
                pass

            if pycom:
                log.info(
                    "\nPython 3 found.  Re-launching bot using: %s run.py\n", pycom)
                pyexec(pycom, 'run.py')

        log.critical(
            "Could not find python 3.5.  Please run the bot using python 3.5")
        bugger_off()


def req_ensure_encoding():
    log.info("Checking console encoding")

    if sys.platform.startswith('win') or sys.stdout.encoding.replace('-', '').lower() != 'utf8':
        log.info("Setting console encoding to UTF-8")

        import io
        sys.stdout = io.TextIOWrapper(
            sys.stdout.detach(), encoding='utf8', line_buffering=True)
        # only slightly evil
        sys.__stdout__ = sh.stream = sys.stdout

        if os.environ.get('PYCHARM_HOSTED', None) not in (None, '0'):
            log.info("Enabling colors in pycharm pseudoconsole")
            sys.stdout.isatty = lambda: True


def req_ensure_env():
    log.info("Ensuring we're in the right folder")

    try:
        assert os.path.isdir('config'), 'folder "config" not found'
        assert os.path.isdir('config/i18n'), 'folder "config.i18n" not found'
        assert os.path.isfile(
            'config/i18n/english.json'), 'file "english.json" not found'
        assert os.path.isdir('cogs'), 'folder "cogs" not found'
        assert os.path.isdir('utils'), 'folder "utils" not found'
    except AssertionError as e:
        log.critical("Failed environment check, %s", e)
        bugger_off()

    try:
        os.mkdir('watora-test-folder')
    except Exception:
        log.critical("Current working directory does not seem to be writable")
        log.critical("Please move the bot to a write")
        bugger_off()
    finally:
        rmtree('watora-test-folder', True)

    if sys.platform.startswith('win'):
        log.info("Adding local bins/ folder to path")
        os.environ['PATH'] += ';' + os.path.abspath('bin/')
        sys.path.append(os.path.abspath('bin/'))  # might as well


def req_ensure_folders():
    pathlib.Path('logs').mkdir(exist_ok=True)


def opt_check_disk_space(warnlimit_mb=200):
    if disk_usage('.').free < warnlimit_mb * 1024 * 2:
        log.warning(
            "Less than %sMB of free space remains on this device" % warnlimit_mb)


#################################################

def pyexec(pycom, *args, pycom2=None):
    pycom2 = pycom2 or pycom
    os.execlp(pycom, pycom2, *args)


def restart(*args):
    pyexec(sys.executable, *args, *sys.argv, pycom2='python')


def main():
    # TODO: *actual* argparsing

    if '--no-checks' not in sys.argv:
        sanity_checks()

    finalize_logging()

    tried_requirementstxt = False

    m = None

    try:

        from bot import Watora
        m = Watora()

        sh.terminator = ''
        log.info("Connecting\n")
        sh.terminator = '\n'

        m.run()

    except SyntaxError:
        log.exception("Syntax error.")

    except ImportError:
        # TODO: if error module is in pip or dpy requirements...

        if not tried_requirementstxt:
            tried_requirementstxt = True

            log.exception("Error starting bot")
            log.info("Attempting to install dependencies...")

            err = PIP.run_install('--upgrade -r requirements.txt')

            if err:  # TODO: add the specific error check back as not to always tell users to sudo it
                print()
                log.critical("You may need to %s to install dependencies." %
                             ['use sudo', 'run as admin'][sys.platform.startswith('win')])
            else:
                print()
                log.info("Ok lets hope it worked")
                print()
        else:
            log.exception("Unknown ImportError, exiting.")

    except RuntimeError:
        log.info("Event loop is closed, disconnecting...")
    except ValueError as e:
        log.info("I'm guessing that your settings.json is invalid, ensure your ','")
        log.info(e)
    except Exception as e:
        log.warning("Error starting Watora")
        log.warning(e)
        log.warning(type(e))
        log.warning(sys.exc_info())
        traceback.print_exc()
        log.warning(traceback.format_exc())
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)

    finally:
        if not m or not m.init_ok:
            if any(sys.exc_info()):
                # How to log this without redundant messages...
                traceback.print_exc()

        loop.close()

    print()
    log.info("All done.")
    bugger_off()


if __name__ == '__main__':
    main()
