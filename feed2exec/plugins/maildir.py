"""Maildir plugin
==============

The maildir plugin will save a feed item into a Maildir folder.

The configuration is a little clunky, but it should be safe against
hostile feeds.

:param str prefix: trusted prefix path
:param str to_addr: the email to use as "to" (defaults to USER@localdomain)
:param dict feed: the feed
:param dict item: the updated item
"""

import datetime
import getpass
import logging
import mailbox
import os.path
import socket
import time

from feed2exec.feeds import make_dirs_helper


class Output(object):
    def __init__(self, prefix, to_addr=None, feed=None, entry=None):
        msg = mailbox.MaildirMessage()
        t = entry['published_parsed']
        if isinstance(t, (datetime.datetime, datetime.date, datetime.time)):
            try:
                msg.set_date(t.timestamp())
            except AttributeError:
                # py2, less precision
                msg.set_date(int(t.strftime('%s')))
        elif isinstance(t, time.struct_time):
            msg.set_date(time.mktime(t))
        msg['From'] = feed['name']
        msg['To'] = to_addr or "%s@%s" % (getpass.getuser(), socket.getfqdn())
        msg['Subject'] = entry['title']
        body = u'''{link}

{summary}'''.format(**entry)
        msg.add_header('Content-Transfer-Encoding', 'quoted-printable')
        msg.set_payload(body.encode('utf-8'))
        msg.set_charset('utf-8')

        make_dirs_helper(prefix)
        folder = os.path.basename(os.path.abspath(feed['name']))
        path = os.path.join(prefix, folder)
        logging.debug('established folder path %s', path)
        # XXX: LOCKING!
        maildir = mailbox.Maildir(path, create=True)
        self.key = maildir.add(msg)
        maildir.flush()
        logging.info('saved entry %s to %s',
                     entry['guid'], os.path.join(path, self.key))
