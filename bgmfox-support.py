#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib
import cgi
import os
import re
from dateutil import zoneinfo

from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.ext.webapp.util import login_required

NUM_MAX_MESSAGE = 10

class GlobalIndex(db.Model):
    max_index = db.IntegerProperty(required=True, default=1)

class Message(db.Model):
    id = db.IntegerProperty()
    name = db.StringProperty()
    user = db.UserProperty(auto_current_user_add = True)
    remote_addr = db.StringProperty()
    date = db.DateTimeProperty(auto_now_add = True)
    title = db.StringProperty()
    content = db.TextProperty()

    def contains(self, keywords):
        for keyword in keywords:
            if self.content.find(keyword) < 0:
                return False
        return True

    def changeTimeZone(self):
        tz = zoneinfo.gettz('Asia/Tokyo')
        utc_tz = zoneinfo.gettz('UTC')
        self.date = self.date.replace(tzinfo=utc_tz).astimezone(tz)

    def colorizeQuotation(self):
        p = re.compile('^(>.*)$', re.MULTILINE)
        self.content = p.sub(r'<span class="quotation" >\1</span>', self.content)

    def colorizeKeyword(self, keywords):
        joined_str = "|".join(keywords)
        p = re.compile('(' + joined_str + ')')
        self.content = p.sub(r'<span class="keyword" >\1</span>', self.content)

class MainPage(webapp.RequestHandler):
    def get(self):
        title = ''
        content = ''
        error = ''
        offset = 0
        has_next = False
        has_previous = False
        if len(self.request.get('id')) > 0:
            id = self.request.get('id')
            message = Message.get_by_key_name('message' + str(id), GlobalIndex.get_by_key_name('message_index'))
            p = re.compile(r'^Re:\[(\d+)\]')
            match = p.match(message.title)
            if match != None:
                re_num = int(match.group(1))
                title = p.sub('Re:[' + str(re_num + 1) + ']', message.title)
            else:
                title = u'Re:[1]' + message.title

            content = u'>' + message.content.replace(u'\r\n', u'\r\n>') + u'\r\n\r\n'

        if len(self.request.get('offset')) > 0:
            offset = int(self.request.get('offset'))
            if offset >= NUM_MAX_MESSAGE:
                has_previous = True

        messages_query = Message.all().order('-date')  # '-' means descending order
        limit = offset + NUM_MAX_MESSAGE + 1
        count = messages_query.count(limit)
        if count == limit:
            has_next = True

        messages = messages_query.fetch(limit=NUM_MAX_MESSAGE, offset=offset)
        for message in messages:
            message.changeTimeZone()
            message.colorizeQuotation()

        if len(self.request.get('error')) > 0:
            error = urllib.unquote(self.request.get('error'))

        template_values = {
            'messages': messages,
            'title': title,
            'content': content,
            'has_previous': has_previous,
            'has_next': has_next,
            'prev_offset': offset - NUM_MAX_MESSAGE,
            'next_offset': offset + NUM_MAX_MESSAGE,
            'num_max_message': NUM_MAX_MESSAGE,
            'error': error,
            }

        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, template_values))

class WriteMessageHandler(webapp.RequestHandler):
    def post(self):
        user = users.get_current_user()
        if user == None:
            # save message to memcache
            memcache.set_multi({'name': self.request.get('name'),
                                'title': self.request.get('title'),
                                'content': self.request.get('content')},
                                time=3600)
            self.redirect(users.create_login_url(self.request.uri))
            return

        self.save_message(name = self.request.get('name'),
             user =user,
             remote_addr = self.request.remote_addr,
             content = self.request.get('content'),
             title = self.request.get('title')
            )
        self.redirect('/')

    @login_required
    def get(self):
        user = users.get_current_user()
        self.save_message(name = memcache.get('name'),
                     user =user,
                     remote_addr = self.request.remote_addr,
                     content = memcache.get('content'),
                     title = memcache.get('title')
                    )
        memcache.flush_all()
        self.redirect('/')

    def save_message(self, name, user, remote_addr, content, title):
        def txn():
            message_index = GlobalIndex.get_by_key_name('message_index')
            if message_index is None:
                message_index = GlobalIndex(key_name='message_index')
            new_id = message_index.max_index
            message_index.max_index += 1
            message_index.put()

            message = Message(key_name='message' + str(new_id), parent=message_index)
            message.id = new_id
            message.name = name if len(name) > 0 else u"名無し"
            message.user = user
            message.remote_addr = remote_addr
            message.content = content
            message.title = title if len(title) > 0 else u"無題"
            message.put()
        db.run_in_transaction(txn)

class DeleteMessageHandler(webapp.RequestHandler):
    @login_required
    def get(self):
        id = self.request.get('id')
        message = Message.get_by_key_name('message' + id, GlobalIndex.get_by_key_name('message_index'))
        error = ''
        if message is None:
            error = id + u'は存在しません'
        else:
            if message.user.user_id() == users.get_current_user().user_id():
                message.delete()
            else:
                error = users.get_current_user().email() + u'が書き込んだメッセージではありません'

        self.redirect('/?error=' + urllib.quote(error.encode('utf-8')))

class SearchMessageHandler(webapp.RequestHandler):
    def get(self):
        messages = []
        if len(self.request.get('keyword')) > 0:
            keywords = cgi.escape(self.request.get('keyword')).split()
            keywords = list(set(keywords))
            messages_query = Message.all().order('-date')
            for message in messages_query:
                if message.contains(keywords):
                    messages.append(message)
                    if len(messages) >= NUM_MAX_MESSAGE:
                        break

            for message in messages:
                message.changeTimeZone()
                message.colorizeKeyword(keywords)

        template_values = {
            'messages': messages,
            }
        path = os.path.join(os.path.dirname(__file__), 'search.html')
        self.response.out.write(template.render(path, template_values))

# main
application = webapp.WSGIApplication(
                                     [('/', MainPage),
                                      ('/write', WriteMessageHandler),
                                      ('/delete', DeleteMessageHandler),
                                      ('/search', SearchMessageHandler)],
                                      debug=True)


def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
