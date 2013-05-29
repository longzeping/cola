#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Created on 2013-5-29

@author: Chine
'''

import os
import re

from cola.core.urls import UrlPatterns, Url
from cola.core.parsers import Parser
from cola.core.opener import MechanizeOpener
from cola.core.errors import DependencyNotInstalledError
from cola.core.config import Config
from cola.job import Job

try:
    from BeautifulSoup import BeautifulSoup
except ImportError:
    raise DependencyNotInstalledError('BeautifulSoup')

try:
    from dateutil.parser import parse
except ImportError:
    raise DependencyNotInstalledError('python-dateutil')

try:
    from mongoengine import connect, DoesNotExist, \
                            Document, StringField, DateTimeField
except ImportError:
    raise DependencyNotInstalledError('mongoengine')

user_conf = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wiki.yaml')
user_config = Config(user_conf)

mongo_host = user_config.job.mongo.host
mongo_port = user_config.job.mongo.port
db_name = user_config.job.db
connect(db_name, host=mongo_host, port=mongo_port)

class WikiDocument(Document):
    title = StringField()
    content = StringField()
    last_update = DateTimeField()

class WikiParser(Parser):
    def __init__(self, **kw):
        opener_cls = MechanizeOpener
        super(WikiParser, self).__init__(opener=opener_cls, **kw)
        
    def store(self, title, content, last_update):
        try:
            doc = WikiDocument.objects.get(title=title)
            if last_update > doc.last_update:
                doc.content = content
                doc.last_update = last_update
                doc.update()
        except DoesNotExist:
            doc = WikiDocument(title=title, content=content, last_update=last_update)
            doc.save()
    
    def parse(self, url=None):
        url = url or self.url
        opener = self.opener()
        
        html = opener.open(url)
        soup = BeautifulSoup(html)
        
        title = soup.head.title.text
        if '-' in title:
            title = title.split('-')[0].strip()
        content = soup.find('div', attrs={'id': 'mw-content-text', 'class': 'mw-content-ltr'})
        content.table.extract()
        content = content.text.split('Preprocessor', 1)[0]
        last_update = soup.find('li', attrs={'id': 'footer-info-lastmod'}).text
        if u'on' in last_update:
            last_update = last_update.rsplit(u'on', 1)[1].strip('.')
            last_update = parse(last_update)
        else:
            last_update = last_update.rsplit(u'于', 1)[1].strip('。')
            last_update = re.sub(r'\([^\)]+\)\s', '', last_update)
            last_update = last_update.replace(u'年', '-').replace(u'月', '-').replace(u'日', '')
            last_update = parse(last_update)
            
        self.store(title, content, last_update)

url_patterns = UrlPatterns(
    Url(r'^http://(zh|en).wikipedia.org/wiki/[^(:|/)]+$', 'wiki_page', WikiParser)
)

def get_job():
    return Job('wikipedia crawler')