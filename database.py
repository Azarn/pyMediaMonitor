#!/usr/bin/env python3

import pickle
import re
import os.path

from fileutils import get_size, get_created, get_hash

class DataBase:
	EMPTY_DB = { 'dir': 'TEST_DIR',
				 'tags': {},
				 'media': [] }

	REQUIRED_FIELDS = { 'file' }
	DEFAULT_NONE_ITEMS = [ 'url', 'google' ]							# TODO: Вроде в словарях можно сразу задавать все возможные ключи.

	def __init__( self ):
		pass

	def load_db( self, dbFile = None ):
		if dbFile == None:
			dbFile = 'db'
		try:
			with open( dbFile, 'rb' ) as f:
				self.db = pickle.load( f )
		except FileNotFoundError:
			self.db = self.EMPTY_DB

	def find( self, flags = {}, **pattern ):
		res = []
		for i in self.db['media']:
			for k, v in pattern.items():
				if k == 'tags':
					if v < i['tags']:										# если v подмножество i['tags']
						continue
				elif flags.get( 're', True ) and type( v ) is str and i[k] != None:
					#print( '[DEBUG]:', v, i[k], i, '[/DEBUG]' )
					if re.search( v, i[k] ) != None:
						continue
				if i[k] != v:
					break
			else:
				res.append( i )
		return res

	def update( self, search_data, update_data ):
		if not self.REQUIRED_FIELDS < set( search_data.keys() ) and set( search_data.keys() ) != self.REQUIRED_FIELDS:
			raise NameError( 'Обязательные аргументы не были переданы! Нужны как минимум: ' + ','.join( self.REQUIRED_FIELDS ) )
		if not search_data.get( 'dir' ):
			search_data['dir'] = ''
		for elem in self.find( **search_data ):
			elem.update( update_data )
		print( 'DB_UPDATE:', 'In', search_data, 'Data:', update_data )

	def add( self, **data ):
		if not self.REQUIRED_FIELDS < set( data.keys() ) and set( data.keys() ) != self.REQUIRED_FIELDS:
			raise NameError( 'Обязательные аргументы не были переданы! Нужны как минимум: ' + ','.join( self.REQUIRED_FIELDS ) )
		if not data.get( 'dir' ):
			data['dir'] = ''
		f = os.path.join( self.db['dir'], data['dir'], data['file'] )
		if not data.get( 'size' ):
			data['size'] = get_size( f )
		if not data.get( 'created' ):
			data['created'] = get_created( f )
		if not data.get( 'hash' ):
			data['hash'] = get_hash( f )
		if not data.get( 'tags' ):
			data['tags'] = { 'Unsorted' }
		for t in data['tags']:									
			self.db['tags'][t] = self.db['tags'].get( t, 0 ) + 1	# TODO: Использовать здесь defaultdict
		for i in self.DEFAULT_NONE_ITEMS:
			data[i] = data.get( i )
		print( 'DB_ADD:', data )
		self.db['media'].append( data )

	def remove( self, **pattern ):
		for i, v in enumerate( self.db['media'].copy() ):				# TODO: Найти способ избежать копирования массива
			if v in self.find( **pattern ):
				self.db['media'].pop( i )
				for t in v['tags']:
					count = self.db['tags'][t] - 1
					if count == 0:
						del self.db['tags'][t]							# TODO: Использовать defaultdict !!!
					else:
						self.db['tags'][t] = count
