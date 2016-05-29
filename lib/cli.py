# Copyright © 2012-2015 Jakub Wilk <jwilk@jwilk.net>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the “Software”), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

'''
command-line interface
'''

import argparse
import concurrent.futures
import functools
import io
import multiprocessing
import os
import subprocess as ipc
import sys
import tempfile

from lib import check
from lib import ling
from lib import misc
from lib import paths
from lib import tags
from lib import terminal

__version__ = '0.25'

def initialize_terminal():
    if sys.stdout.isatty():
        terminal.initialize()
    if sys.stdout.errors != 'strict':
        return
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer,
        encoding=sys.stdout.encoding,
        errors='backslashreplace',
    )

class Checker(check.Checker):

    def tag(self, tagname, *extra):
        if tagname in self.options.ignore_tags:
            return
        try:
            tag = tags.get_tag(tagname)
        except KeyError:
            raise misc.DataIntegrityError(
                'attempted to emit an unknown tag: {tag!r}'.format(tag=tagname)
            )
        s = tag.format(self.fake_path, *extra, color=True)
        print(s)

def check_regular_file(filename, *, options):
    checker_instance = Checker(filename, options=options)
    checker_instance.check()

def copy_options(options, **update):
    kwargs = vars(options)
    kwargs.update(update)
    return argparse.Namespace(**kwargs)

class UnsupportedFileType(ValueError):
    pass

def check_deb(filename, *, options):
    if filename.endswith('.deb'):
        binary = True
    elif filename.endswith('.dsc'):
        binary = False
    else:
        raise UnsupportedFileType
    ignore_tags = set(options.ignore_tags)
    ignore_tags.add('unknown-file-type')
    with tempfile.TemporaryDirectory(prefix='i18nspector.deb.') as tmpdir:
        if binary:
            ipc.check_call(['dpkg-deb', '-x', filename, tmpdir])
            real_root = os.path.join(tmpdir, '')
        else:
            real_root = os.path.join(tmpdir, 's', '')
            with open(os.devnull) as bitbucket:
                ipc.check_call(
                    ['dpkg-source', '--no-copy', '--no-check', '-x', filename, real_root],
                    stdout=bitbucket  # dpkg-source would be noisy without this...
                )
        options = copy_options(options,
            ignore_tags=ignore_tags,
            fake_root=(real_root, os.path.join(filename, ''))
        )
        for root, dirs, files in os.walk(tmpdir):
            for path in files:
                path = os.path.join(root, path)
                if os.path.islink(path):
                    continue
                if os.path.isfile(path):
                    check_file(path, options=options)

def check_file(path, *, options):
    if options.unpack_deb:
        try:
            return check_deb(path, options=options)
        except UnsupportedFileType:
            pass
    return check_regular_file(path, options=options)

def check_file_s(path, *, options):
    '''
    check_file() with captured stdout
    '''
    orig_stdout = sys.stdout
    sys.stdout = io_stdout = io.StringIO()
    try:
        check_file(path, options=options)
    finally:
        sys.stdout = orig_stdout
    return io_stdout.getvalue()

def check_all(paths, *, options):
    if (len(paths) <= 1) or (options.jobs <= 1):
        for path in paths:
            check_file(path, options=options)
    else:
        executor = concurrent.futures.ProcessPoolExecutor(max_workers=options.jobs)
        with executor:
            check_file_opt = functools.partial(check_file_s, options=options)
            for s in executor.map(check_file_opt, paths):
                sys.stdout.write(s)

def parse_jobs(s):
    if s == 'auto':
        try:
            return multiprocessing.cpu_count()
        except NotImplementedError:
            return 1
    n = int(s)
    if n <= 0:
        raise ValueError
    return n
parse_jobs.__name__ = 'jobs'

def main():
    initialize_terminal()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--version', action='version', version='%(prog)s {}'.format(__version__))
    ap.add_argument('-l', '--language', metavar='<lang>', help='assume this language')
    ap.add_argument('--unpack-deb', action='store_true', help='allow unpacking Debian packages')
    ap.add_argument('-j', '--jobs', type=parse_jobs, metavar='<n>', default=None, help='use <n> processes')
    ap.add_argument('--parallel', type=int, metavar='<n>', default=None, help=argparse.SUPPRESS)  # renamed as -j/--jobs in 0.25
    ap.add_argument('--file-type', metavar='<file-type>', help=argparse.SUPPRESS)
    ap.add_argument('--traceback', action='store_true', help=argparse.SUPPRESS)
    ap.add_argument('files', metavar='<file>', nargs='+')
    options = ap.parse_args()
    files = options.files
    del options.files
    paths.check()
    if options.language is not None:
        try:
            language = ling.parse_language(options.language)
            language.fix_codes()
        except ling.LanguageError:
            if options.traceback:
                raise
            ap.error('invalid language')
        language.remove_encoding()
        language.remove_nonlinguistic_modifier()
        options.language = language
    if options.jobs is None:
        if options.parallel is not None:
            options.jobs = options.parallel
    if options.jobs is None:
        options.jobs = 1
    del options.parallel
    options.ignore_tags = set()
    options.fake_root = None
    Checker.patch_environment()
    check_all(files, options=options)

__all__ = ['main']

# vim:ts=4 sts=4 sw=4 et
