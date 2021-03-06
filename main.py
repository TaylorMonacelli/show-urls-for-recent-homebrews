#!/usr/bin/env python3

import argparse
import json
import logging
import os
import re
import sys
import time
from subprocess import PIPE, Popen

import jinja2

if sys.version_info[0] < 3:
    raise Exception("Must be using Python 3")

BREW_PATH = '/usr/local/bin/brew'
GIT_PATH = '/usr/local/bin/git'
HOMEBREW_FORMULA_GIT_DIR = '/usr/local/Homebrew/Library/Taps/homebrew/homebrew-core/.git'
TEMPLATE_DIR = os.path.dirname(os.path.realpath(__file__))
TEMPLATE_FILE = 'page.tmpl'
TEMPLATE_OUTPUT = f'/tmp/show-urls-for-recent-homebrews-{time.strftime("%A-%-I%M%p", time.localtime())}.html'
TEMPLATE_OUTPUT_SYMLINK = '/tmp/show-urls-for-recent-homebrews.html'
TERMINAL_NOTIFIER = '/usr/local/bin/terminal-notifier'

parser = argparse.ArgumentParser()


def convert_to_seconds(s):
    seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    return int(s[:-1]) * seconds_per_unit[s[-1]]


parser.add_argument(
    "-s",
    "--since",
    type=str,
    const=1,
    default='1d',
    nargs='?',
    help="show changes since this many seconds ago. eg for changes within the last 2 days, use -s 2d")

parser.add_argument(
    "-n",
    "--no-notify",
    action='store_true',
    default=False,
    help="Do not send notification to terminal.")

parser.add_argument(
    "--debug",
    action='store_true',
    default=False,
    help="debug")

args = parser.parse_args()

if args.debug:
    logging.basicConfig(level=logging.DEBUG)

my_env = os.environ.copy()
my_env["HOME"] = ""  # hide $HOME/.gitconfig from git
my_env["PATH"] = f'/usr/local/bin:{my_env["PATH"]}'

cmd = ['git', f'--git-dir={HOMEBREW_FORMULA_GIT_DIR}', 'log', '--format=%h',
       f'--since={convert_to_seconds(args.since)}.seconds.ago']
process = Popen(
    cmd,
    stdout=PIPE,
    stderr=PIPE,
    env=my_env,
    encoding='utf8')

stdout, stderr = process.communicate()
shas = stdout.split('\n')
shas.remove('')
logging.debug(f"{' '.join(cmd)} output: {' '.join(shas)}")

if not shas:
    sys.exit(0)

cmd = [
    GIT_PATH,
    f'--git-dir={HOMEBREW_FORMULA_GIT_DIR}',
    'diff',
    '--diff-filter=d',  # exclude deleted packages
    '--name-only',
    f'{shas[-1]}..master',
]
logging.debug(f"{' '.join(cmd)}")
process = Popen(
    cmd,
    stdout=PIPE,
    stderr=PIPE,
    env=my_env,
    encoding='utf8')
stdout, stderr = process.communicate()

pkg_re = re.compile(r"""
(?:Formula|Aliases)/   # filter on file paths that include aliases and formula only
([\_\-\w]+)            # package name must only have these characters
""", flags=re.I | re.VERBOSE)
pkgs = [m.group(1) for m in (pkg_re.search(pkg)
                             for pkg in stdout.split('\n')) if m]

cmd = [BREW_PATH, 'info', '--json'] + pkgs
logging.debug(f"{' '.join(cmd)}")
process = Popen(
    cmd,
    stdout=PIPE,
    stderr=PIPE,
    encoding='utf8')
stdout, stderr = process.communicate()

dct_brews = json.loads(stdout)

templateLoader = jinja2.FileSystemLoader(searchpath=TEMPLATE_DIR)
templateEnv = jinja2.Environment(loader=templateLoader)
template = templateEnv.get_template(TEMPLATE_FILE)
output = template.render(my_list=dct_brews)

with open(TEMPLATE_OUTPUT, 'w') as html:
    html.write(output)

if not args.no_notify:
    cmd = [
        TERMINAL_NOTIFIER,
        '-title',
        'Homebrew',
        '-message',
        'Homebrew updates',
        '-open',
        f'file://{TEMPLATE_OUTPUT}',
    ]
    process = Popen(
        cmd,
        stdout=PIPE,
        stderr=PIPE,
        encoding='utf8')
    stdout, stderr = process.communicate()

tmplink = f'{TEMPLATE_OUTPUT}.tmp'
os.symlink(TEMPLATE_OUTPUT, tmplink)
os.rename(tmplink, TEMPLATE_OUTPUT_SYMLINK)
