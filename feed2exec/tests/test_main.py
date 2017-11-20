#!/usr/bin/python3
# coding: utf-8

from __future__ import division, absolute_import
from __future__ import print_function

import json
import re

from click.testing import CliRunner

import feed2exec.utils as utils
from feed2exec.feeds import SqliteStorage
from feed2exec.__main__ import main
from feed2exec.tests.test_feeds import (test_sample, test_nasa)
from feed2exec.tests.fixtures import (conf_path, db_path, static_boundary)  # noqa


def test_usage():
    runner = CliRunner()
    result = runner.invoke(main, ['--help'])
    assert 0 == result.exit_code


def test_basics(tmpdir_factory, conf_path, db_path, static_boundary):  # noqa
    runner = CliRunner()
    result = runner.invoke(main, ['--config', str(conf_path),
                                  '--database', str(db_path),
                                  'add',
                                  '--output', 'feed2exec.plugins.echo',
                                  test_sample['name'],
                                  test_sample['url']])
    assert conf_path.check()
    assert 0 == result.exit_code
    result = runner.invoke(main, ['--config', str(conf_path),
                                  '--database', str(db_path),
                                  'add',
                                  test_sample['name'],
                                  test_sample['url']])
    assert 2 == result.exit_code
    assert 'already exists' in result.output
    result = runner.invoke(main, ['--config', str(conf_path),
                                  '--database', str(db_path),
                                  'ls'])
    assert 0 == result.exit_code
    del test_sample['args']
    expected = json.dumps(test_sample, indent=2, sort_keys=True)
    assert expected == result.output.strip()
    result = runner.invoke(main, ['--config', str(conf_path),
                                  '--database', str(db_path),
                                  'rm', test_sample['name']])
    assert 0 == result.exit_code
    result = runner.invoke(main, ['--config', str(conf_path),
                                  '--database', str(db_path),
                                  'ls'])
    assert 0 == result.exit_code
    assert "" == result.output

    maildir = tmpdir_factory.mktemp('maildir')
    result = runner.invoke(main, ['--config', str(conf_path),
                                  '--database', str(db_path),
                                  'add',
                                  '--output', 'maildir',
                                  '--mailbox', str(maildir),
                                  test_nasa['name'],
                                  test_nasa['url']])
    assert conf_path.check()
    assert 'feed2exec.plugins.maildir' in conf_path.read()
    assert 0 == result.exit_code

    test_path = utils.find_test_file('planet-debian.xml')
    result = runner.invoke(main, ['--config', str(conf_path),
                                  '--database', str(db_path),
                                  'add', 'planet-debian',
                                  'file://' + test_path,
                                  '--args', 'to@example.com',
                                  '--mailbox', str(maildir)])
    result = runner.invoke(main, ['--config', str(conf_path),
                                  '--database', str(db_path),
                                  'fetch'])
    assert 0 == result.exit_code
    assert maildir.check()
    for path in maildir.join('planet-debian').join('new').visit():
        body = path.read()
        if 'Marier' in body:
            break
    else:  # sanity check
        assert False, "Francois Marier item not found"  # pragma: nocover


def test_parse(tmpdir_factory, conf_path, db_path):  # noqa
    runner = CliRunner()
    conf_path.remove()
    result = runner.invoke(main, ['--config', str(conf_path),
                                  '--database', str(db_path),
                                  'parse',
                                  '--output', 'feed2exec.plugins.echo',
                                  '--args', 'foo bar',
                                  test_sample['url']])
    assert 0 == result.exit_code
    assert not conf_path.check()
    assert db_path.check()
    assert "foo bar\n" == result.output


def test_planet(tmpdir_factory, static_boundary, betamax_session, conf_path, db_path):  # noqa
    """test i18n feeds for double-encoding

    previously, we would double-encode email bodies and subject, which
    would break display of any feed item with unicode.
    """
    mbox_dir = tmpdir_factory.mktemp('planet').join('Mail')
    if conf_path.check():
        conf_path.remove()
    if db_path.check():
        db_path.remove()
        del SqliteStorage.cache[str(db_path)]
    runner = CliRunner()

    result = runner.invoke(main, ['--config', str(conf_path),
                                  '--database', str(db_path),
                                  'add', 'planet-debian',
                                  'http://planet.debian.org/rss20.xml',
                                  '--args', 'to@example.com',
                                  '--output', 'feed2exec.plugins.mbox',
                                  '--mailbox', str(mbox_dir)])
    result = runner.invoke(main, ['--config', str(conf_path),
                                  '--database', str(db_path),
                                  'fetch'],
                           obj=betamax_session, catch_exceptions=False)
    assert 0 == result.exit_code
    r = re.compile('User-Agent: .*$', flags=re.MULTILINE)
    with open(utils.find_test_file('../cassettes/planet-debian.mbx')) as expected:  # noqa
        expected = r.sub('', expected.read())
        actual = r.sub('', mbox_dir.join('planet-debian.mbx').read())
        assert expected == actual
