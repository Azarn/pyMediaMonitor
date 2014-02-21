#!/usr/bin/env python3

import pickle
import os
import watchdog.events
import watchdog.observers
import threading
import time
import glob
import queue
import fileutils

from database import DataBase

class Event:
	class ACTION:
		NOT_PROCESSING		= 0
		NEW					= 1
		MISSING				= 2
		RENAMED				= 3
		UPDATED				= 4
		DUPLICATE			= 5
		SIMILAR				= 6
		BAD_HASH			= 7
		FOUND_BETTER		= 8
		BROKEN_STRUCTURE	= 9
	def __init__( self, fileName, directory, isDir, watchdir, info = None ):
		self.action = self.ACTION.NOT_PROCESSING
		self.fileName = fileName
		self.isDir = isDir
		self.directory = directory
		self.watchdir = watchdir
		self.info = info
		self.isInDB = False
	def __eq__( self, other ):
		if self.action == other.action and self.fileName == other.fileName and self.isDir == other.isDir:
		   if self.directory == other.directory and self.watchdir == other.watchdir and self.info == other.info:
			   if self.isInDB == other.isInDB:
				   return True
		return False
	def __str__( self ):
		return 'Action:{0}, fileName:{1}, directory:{2}, isDir:{3}, watchdir:{4}, isInDB:{5}, info:{6}'.format(
			self.action, self.fileName, self.directory, self.isDir, self.watchdir, self.isInDB, self.info )
	@property
	def path( self ):
		return os.path.join( self.watchdir, self.directory, self.fileName )


class Engine( watchdog.events.FileSystemEventHandler ):
	#DEFAULT_CFG = [r'D:\disk\Projects\pyMediaMonitor\WATCH_DIR']
	DEFAULT_CFG = [r'D:\disk\Pictures\ponies']
	DEFAULT_CFG_NAME = 'cfg'

	def __init__( self, outFunc = None ):
		watchdog.events.FileSystemEventHandler.__init__( self )
		if not outFunc:
			outFunc = lambda x: True
		self.outFunc = outFunc
		self.ignoreFiles = []
		self.db = DataBase()
		self.queue = queue.Queue()
		self.worker = threading.Thread( target = self.worker )

	def setNotifyOnChange( self, path, isRecursive = False ):
		self.observer = watchdog.observers.Observer()
		self.observer.schedule( self, path = path, recursive = isRecursive )
		self.observer.start()

	def loadCfg( self, cfgName = None ):
		if not cfgName:
			cfgName = self.DEFAULT_CFG_NAME
		try:
			with open( cfgName, 'rb' ) as f:
				self.cfg = pickle.load( f )
		except FileNotFoundError:
			self.cfg = self.DEFAULT_CFG

	def writeCfg( self, cfgName = None ):
		if not cfgName:
			cfgName = self.DEFAULT_CFG_NAME
		with open( cfgName, 'wb' ) as f:
			pickle.dump( self.cfg, f )

	def run( self ):
		self.loadCfg()
		self.db.load_db()
		self.setNotifyOnChange( self.cfg[0], True )
		self.worker.start()
		try:
			while True:
				inp = input()
				if inp == 'd':
					print( self.db.db )
				elif inp == 'u':
					self.updateAllInPath( self.cfg[0], self.cfg[0] )
				time.sleep( 0.5 )
		except KeyboardInterrupt:
			self.queue.put( 'quit' )
			self.worker.join()

	def worker( self ):
		while True:
			o = self.queue.get( True )
			if isinstance( o, str ) and o == 'quit':
				break

			if len( o ) == 3:
				task, query, func = o
			elif len( o ) == 2:
				task, query = o
				func = lambda x: None
			else:
				raise TypeError( 'Неверный формат задания! Его длина равна {0}.'.format( len( o ) ) )

			if func == None:
				func = lambda x: None

			if task == 'query':
				func( self.db.find( **query ) )

	def addTask( self, task, resultFunc, **data ):
		self.queue.put( ( task, resultFunc, data ) )

	def updateAllInPath( self, path, root ):
		path = os.path.join( path, '*' )
		for f1 in glob.iglob( path ):
			if os.path.isdir( f1 ):
				path2 = os.path.join( f1, '*' )
				for f2 in glob.iglob( path2 ):
					if os.path.isdir( f2 ):
						self.processEvent( self.prepareEvent( f2, root, Event.ACTION.BROKEN_STRUCTURE ) )
					else:
						self.processEvent( self.prepareEvent( f2, root, Event.ACTION.NEW ) )
			else:
				self.processEvent( self.prepareEvent( f1, root, Event.ACTION.NEW ) )

	def processEvent( self, event ):
		if event.action != Event.ACTION.NOT_PROCESSING and self.outFunc( event ):
			if event.action == Event.ACTION.NEW:
				self.db.add( file = event.fileName, dir = event.directory, hash = event.info )				# TODO: Делать запрос в гугл ( и другие операции )
			elif event.action == Event.ACTION.MISSING:
				self.db.remove( file = event.fileName, dir = event.directory )
			elif event.action == Event.ACTION.DUPLICATE:
				self.ignoreFiles.append( event.path )
				os.unlink( event.path )
			elif event.action == Event.ACTION.UPDATED:
				self.db.update( { 'file': event.fileName, 'dir': event.directory },
								{ 'hash': event.info } )
			elif event.action == Event.ACTION.RENAMED:
				if event.isDir:
					self.db.update( { 'dir': event.directory },
									{ 'dir': event.info[1] } )
				else:
					#self.ignoreFiles.append( event.info[0] )
					self.db.update( { 'file': event.fileName, 'dir': event.directory },
									{ 'file': event.info[0], 'dir': event.info[1] } )
			else:
				pass
				#raise NotImplementedError( 'processEvent called with "{0}"!'.format( event ) )

	def prepareEvent( self, path, root, basicAction, info = None ):													# Создаем Event
		isDir = os.path.isdir( path )
		f, d = fileutils.get_file_and_dir( path, root, isDir )
		res_path = self.db.find( flags = { 're': False }, file = f, dir = d )
		basicEvent = Event( f, d, isDir, root, info )
		if len( res_path ) or basicAction == Event.ACTION.RENAMED:
			basicEvent.isInDB = True

		if not isDir and ( basicAction in (Event.ACTION.MISSING, Event.ACTION.NEW, Event.ACTION.RENAMED, Event.ACTION.UPDATED) ):
			if len( res_path ) > 1:
				raise RuntimeError( 'В базе данных сразу две записи об одном файле! Нужна полная проверка базы.' )
			if os.path.exists( path ):
				f_hash = fileutils.get_hash( path )
				res_hash = self.db.find( hash = f_hash )
				if len( res_path ):
					if res_path[0]['hash'] != f_hash:								# Файл есть на диске и в базе не совпал хэш.
						if basicAction == Event.ACTION.UPDATED:
							basicEvent.action = Event.ACTION.UPDATED
							basicEvent.info = f_hash
						else:
							basicEvent.action = Event.ACTION.BAD_HASH				# Файл не был модифицирован, а значит это дубль.
							basicEvent.info = res_path
					elif basicAction == Event.ACTION.RENAMED:
						basicEvent.action = basicAction
						basicEvent.info = fileutils.get_file_and_dir( info, root, isDir )
				elif len( res_hash ):												# Файла в базе нет, но есть другой с таким же значением хэша.
					basicEvent.isInDB = True
					basicEvent.action = Event.ACTION.DUPLICATE
					basicEvent.info = res_hash
				else:
					basicEvent.action = Event.ACTION.NEW							# Файл есть над диске, но в базе его нет.
					if basicAction == Event.ACTION.RENAMED:
						new_f, new_d = fileutils.get_file_and_dir( info, root, isDir )
						basicEvent.fileName = new_f
						basicEvent.directory = new_d
					basicEvent.info = f_hash
			elif len( res_path ):													# Файла на диске нет, но в базе есть.
				basicEvent.action = Event.ACTION.MISSING
		else:
			basicEvent.action = basicAction
				 
		#print( '[EVENT]:', basicEvent )
		return basicEvent


	def on_any_event( self, event ):
		print( event )
		info = None
		if isinstance( event, watchdog.events.FileCreatedEvent ):
			evType = Event.ACTION.NEW
		elif isinstance( event, watchdog.events.FileDeletedEvent ):
			evType = Event.ACTION.MISSING
		elif isinstance( event, watchdog.events.FileMovedEvent ):
			evType = Event.ACTION.RENAMED
			info = event.dest_path								
		elif isinstance( event, watchdog.events.FileModifiedEvent ):
			evType = Event.ACTION.UPDATED
		else:
			return
		if event.src_path in self.ignoreFiles:
			self.ignoreFiles.remove( event.src_path )
			return
		else:
			print( event.src_path, self.ignoreFiles )
		self.processEvent( self.prepareEvent( event.src_path, self.cfg[0], evType, info ) )	


if __name__ == '__main__':
	Engine().run()