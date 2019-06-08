#!/usr/bin/env python3
#
# This is a small standalone Python2 webserver.
# It servers as a REST/Websocket PubSub and logging server
# and allows serveral input devices for Inventory marking to work together
#
# Prototype, based on the inventory clapperboard webserver
#
#  Dependencies:  Tornado, Json-Patch, Pygit2
#
#  Install on Ubuntu as:
#
#    apt install python3-tornado python3-pygit2 python3-jsonpatch
#
# Quickly written by SvenK at 2019-04-26, 2019-05-10

#builtins
import os, sys, csv, io, re, platform, datetime, random, string, subprocess, hashlib, time, errno, inspect
from collections import defaultdict, OrderedDict
from itertools import islice
from os.path import join

# libraries/dependencies
import tornado.ioloop, tornado.web, tornado.websocket
from tornado.escape import json_decode, json_encode
from tornado.web import HTTPError
from json import load as json_load # from file
import jsonpatch # pip3 install jsonpatch or so
import pygit2 # apt install python3-pygit2
#import sh # apt install python-sh

timestr = lambda: datetime.datetime.now().replace(microsecond=0).isoformat()

def make_handler(callback):
	class MiniHandler(tornado.web.RequestHandler):
		def set_default_headers(self):
			self.set_header('Content-Type', 'application/json')
			self.set_header("Access-Control-Allow-Origin", "*")  # todo, restrict this to same domain (from config)
			self.set_header("Access-Control-Allow-Headers", "x-requested-with")
			self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
		def get(self): return callback(self)
	return MiniHandler

write_encoded = lambda fun: lambda req: req.write(json_encode(fun(req)))

webserver_routes = []
def register(path):
	def decorator(fun_or_cls):
		webserver_routes.append( (path, make_handler(write_encoded(fun_or_cls)) if not inspect.isclass(fun_or_cls) else fun_or_cls ))
		return fun_or_cls
	return decorator

class Box(dict):
	"Mini-and-less-performant variant of https://news.ycombinator.com/item?id=14273863"
	def __getattr__(self, key):
		return Box(self[key]) if isinstance(self[key],dict) else self[key]

flatten = lambda x: [inner for outer in x for inner in outer ] # simple flatten 2d
randomString = lambda stringLength=10: ''.join(random.choice(string.ascii_lowercase) for i in range(stringLength))
make_default_identifier = lambda ip_as_str: ip_as_str + randomString(3)
author_legal = lambda author: bool(re.match('^[a-zA-Z0-9][a-zA-Z0-9-_.\s]+$', author))

# Do locking with semaphores; https://www.tornadoweb.org/en/stable/locks.html
# Assuming only a single process runs

def read_json_file(filename):
	# probably todo: file locking
	with open(filename, "r") as fh:
		return json_load(fh) # may raise ValueError if no valid JSON in file

def write_json_file(filename, data):
	# todo: file locking
	# Such as https://github.com/dmfrey/FileLock/blob/master/filelock/filelock.py#L15
	# or https://docs.python.org/2/library/fcntl.html#fcntl.lockf
	with open(filename, "w") as fh:
		fh.write(json_encode(data))

static_file_path = os.path.dirname(__file__)
config = Box(read_json_file("./inventory-editor-config.json"))

#message_file = "markers-%s.csv" % timestr()

#   a {media repository} holds several {media collections} which are directories holding photos.

master = pygit2.Repository(config.paths.inventory_repository)

repo_file = lambda fname: join(config.paths.inventory_repository, fname)
workdir_path = lambda author: join(config.paths.patches_directory, author)
workdir_file = lambda author, fname: join(config.paths.patches_directory, author, fname)
signature = lambda author: pygit2.Signature(author, author+"@t29-inventory-server")
extgit = lambda *cmds: subprocess.call(["git"]+list(cmds), cwd=config.paths.inventory_repository)

@register(config.server.git_log_path)
def git_log(req):
	"""Provides a small machine readable git log"""
	max_items = 10
	return [ {
		"author": commit.committer.name,
		"date": datetime.datetime.utcfromtimestamp(commit.commit_time).isoformat(),
		"id": commit.id.hex,
		"message": commit.message
	    } for commit in islice(master.walk(master.head.target, pygit2.GIT_SORT_TOPOLOGICAL), max_items)
	]

app = tornado.web.Application(webserver_routes + [
    ('/', make_handler(lambda req: req.redirect("app/"))),
    (r'/(.*)', tornado.web.StaticFileHandler, {
         'path': static_file_path,
	 "default_filename": "index.html"
    })
], debug=True)

print("Starting Tornado server on port %d" % config.server.port)
app.listen(config.server.port)
tornado.ioloop.IOLoop.current().start()







