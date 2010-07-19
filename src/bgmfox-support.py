#!/usr/bin/python
# coding: utf-8
          
import cgi
import os
import re
from datetime import datetime, date, time
from dateutil import zoneinfo

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.ext.db import Key
from google.appengine.ext.webapp.util import login_required

NUM_MAX_MESSAGE = 10	

class Message(db.Model):
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
	
class MainPage(webapp.RequestHandler):
	def get(self):
		title = ''
		content = ''
		offset = 0
		has_next = False
		has_previous = False
		if len(self.request.get('id')) > 0:
			id = int(self.request.get('id'))
			message = Message.get_by_id(id)
			if message.title.find('Re:[') < 0:
				title = u'Re:[1]' + message.title
			else:
				p = re.compile(r'^Re:\[(\d+)\]')
				re_num = int(p.match(message.title).group(1))
				title = p.sub('Re:[' + str(re_num + 1) + ']', message.title)
								
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

		template_values = {
			'messages': messages,
			'title': title,
			'content': content,
			'has_previous': has_previous,
			'has_next': has_next,
			'prev_offset': offset - NUM_MAX_MESSAGE,
			'next_offset': offset + NUM_MAX_MESSAGE,
			'num_max_message': NUM_MAX_MESSAGE,
			}

		path = os.path.join(os.path.dirname(__file__), 'index.html')
		self.response.out.write(template.render(path, template_values))
	
class WriteMessageHandler(webapp.RequestHandler):
	def post(self):
		user = users.get_current_user()
		if user == None:
			self.redirect(users.create_login_url(self.request.uri))
			return
		
		message = Message()
			
		message.name = self.request.get('name') if len(self.request.get('name')) > 0 else "名無し"
		message.user = user
		message.remote_addr = self.request.remote_addr
		message.content = self.request.get('content')
		message.title = self.request.get('title') if len(self.request.get('title')) > 0 else "無題"
		message.put()
		self.redirect('/')
		
class DeleteMessageHandler(webapp.RequestHandler):
	@login_required
	def get(self):
		id = int(self.request.get('id'))
		message = Message.get_by_id(id)
		if message.user == users.get_current_user():
			message.delete()
			
		self.redirect('/')
		
class SearchMessageHandler(webapp.RequestHandler):
	def get(self):
		messages = []
		if len(self.request.get('keyword')) > 0:
			keywords = cgi.escape(self.request.get('keyword')).split()
			messages_query = Message.all().order('-date')
			for message in messages_query:
				if message.contains(keywords):
					messages.append(message)
					if len(messages) >= NUM_MAX_MESSAGE:
						break
					
			for message in messages:
				message.changeTimeZone()
					  
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
