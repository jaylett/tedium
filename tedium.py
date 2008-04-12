#!/usr/bin/python
#
# Tedium runner
#
# Copyright (C) 2008 James Aylett
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
# FEATURE: CGI mechanism for reply (just some Javascript?)
# FEATURE: Graham-Bayes scoring on tweets with thresholds for digest, cgi
# FEATURE: option on authors to show all replies *from* them
# FIXME: assumes UTC coming out of twitter
# FIXME: should probably store the id of a tweet as the tweet PK
# QUESTION: does @<username> count as reply when not at start of tweet?
#
# On a Mac:
#
# download python-json and extract json.py into this directory (this is an
# utter bitch as it isn't packaged for easy_install)
# sudo easy_install pysqlite

import tedium

if __name__ == '__main__':
    tedium.main()
