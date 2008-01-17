#!/usr/bin/python
#
# Copyright (C) 2008 James Aylett
#
# tedium: a natural result of too much twitter
#                     or
# tedium: the Twitter Digest Manager
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301
# USA
#
# Run once to set up username/password, run on cron to grab latest
# tweets, run as CGI to see recent activity, run with an email address
# to get a digest. It figures out the context.
#
# If you run it as a CGI, it'll choose the first CSS file in the same
# directory (assuming the CGI process can read that
# directory). The bulk is a simple <ol>. Classnames used are:
#
#   time, author, tweet       layout of the tweet (three <span>s inside <li>)
#   protected	              applied to <li> if updates are protected
#   new                       applied to <li> if tweet after last CGI view
#   notindigest               applied to <li> if tweet after last email digest
#
# When you view the CGI, anything on there won't appear on a future
# email digest.
#
# For CGI it's *strongly* advised that you run under suexec or via
# userv, so it's running as you rather than as the web user. You might
# also prefer to use cgi_driver.py instead of copying everything into
# your web space. (You'll need to edit it slightly.)
#
# Everything is stored in ~/.tedium, or somewhere else if you pass in
# a directory to the Tedium class constructor. (See down the bottom,
# and above in the sample CGI launcher.) You should change the
# permissions on the directory so they aren't readable by anyone other
# than you (hence suexec/userv for CGI) since it will contain your
# twitter login credentials.
#
# For CGI access, you must run behind some sort of HTTP authentication.
# Either use digest, or basic behind HTTPS, or anything over a local
# connection, or something like that. Connections to twitter use HTTPS.
#
# Currently there is no way of editing this, but if you want to see
# replies to a particular user in the digest, set
# author_include_replies to 1 in the authors table for them (use the
# sqlite3 client). Otherwise, only replies to you are shown.
#
# FEATURE: CGI option to restrict replies as digest
# FEATURE: CGI mechanisms for post & reply
# FEATURE: Graham-Bayes scoring on tweets with thresholds for digest, cgi
# FIXME: when we mark last_*, we use max(tweet_published) from too late
# FIXME: assumes UTC coming out of twitter
# FIXME: change to Atom to avoid HTML entities (JSON is lovely, twitter not)
# FIXME: should probably store the id of a tweet as the tweet PK

import os, sys, getopt

import tedium
import tedium.Cgi
import tedium.Tedium

def usage():
    print u"Usage: %s [options] [email [name]]" % sys.argv[0]
    print u"Options:"
    print u"\t--help\t\tThis message"
    print u"\t--confdir d\tUse ``d'' instead of ~/.tedium"
    print u"\t--reconfigure\tReconfigure tedium"
    print u"\t--test\t\tdon't require auth, don't update timestamps"
    print
    print u"Will force configuration the first time."
    print u"Subsequent runs will update from Twitter."
    print u"Call with email address and optional name to generate digest."
    print u"Run as CGI for web interface."

if __name__ == '__main__':
    try:
        try:
            optlist, args = getopt.getopt(sys.argv[1:], 'hc:rt', ['help', 'confdir=', 'reconfigure', 'test'])
        except getopt.GetoptError:
            usage()
            sys.exit(2)

        confdir = None
        reconfigure = False
        is_test = False

        for opt, arg in optlist:
            if opt in ('-h', '--help'):
                usage()
                sys.exit()
            if opt in ('-c', '--confdir'):
                confdir = arg
            if opt in ('r', '--reconfigure'):
                reconfigure = True
            if opt in ('t', '--test'):
                is_test = True

        t = tedium.Tedium.Tedium(confdir, is_test)
        if reconfigure:
            t.reconfigure()
            sys.exit()

        if len(args)>0:
            if len(args)>1:
                t.digest(args[0], args[1])
            else:
                t.digest(args[0])
        elif os.environ.get('GATEWAY_INTERFACE')=='CGI/1.1':
            cgi = tedium.Cgi.TediumCgi(t)
            cgi.do_get()
        else:
            # Get latest tweets (possibly prompt for configuration first)
            t.update()
    except tedium.TediumError, e:
        sys.stdout.write(str(e))
        sys.stdout.write("\n")
        print e.aux
