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
# FEATURE: CGI mechanisms for post & reply
# FEATURE: CGI mechanism to toggle author_include_replies
# FEATURE: Graham-Bayes scoring on tweets with thresholds for digest, cgi
# FIXME: when we mark last_*, we use max(tweet_published) from too late
# FIXME: assumes UTC coming out of twitter
# FIXME: change to Atom to avoid HTML entities (JSON is lovely, twitter not)
# FIXME: should probably store the id of a tweet as the tweet PK

import tedium

if __name__ == '__main__':
    tedium.main()
