#!/usr/bin/env python3

import os.path
import hashlib
import time

def wait_for_file( f ):
	def wrapper( *args, **kwargs ):
		res = None
		for i in range( 10 ):
			res = f( *args, **kwargs )
			if res != None:
				break
			else:
				time.sleep( 0.01 )
		if i != 0:
			print( i, f, args, kwargs )
		return res
	return wrapper

def get_file_and_dir( path, root, is_dir = False ):
	path = os.path.normpath( path )
	root = os.path.normpath( root )
	path = path.split( root )[1]							# TODO: Если есть возможность, то сделать это через функции стандартной библиотеки.
	if is_dir:
		path = os.path.join( path, '' )						# TODO: Костыль, нужна нормальная замена!
	head, fileName = os.path.split( path )					# TODO: Может есть функция, которая сразу разобьёт путь на части?
	head, directory = os.path.split( head )
	return fileName, directory

#@wait_for_file
def get_size( fileName ):
	try:
		return os.path.getsize( fileName )
	except FileNotFoundError:
		return None

#@wait_for_file
def get_created( fileName ):
	try:
		return int( os.path.getctime( fileName ) )
	except FileNotFoundError:
		return None

#@wait_for_file
def get_hash( fileName ):
	m = hashlib.sha256()
	try:
		with open( fileName, "rb" ) as f:
			while True:
				data = f.read( 4096 )
				if data:
					m.update( data )
				else:
					break
		return m.hexdigest()
	except ( PermissionError, FileNotFoundError ):
		return None