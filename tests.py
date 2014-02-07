#!/usr/bin/env python3

import unittest, unittest.mock
import pickle
import os
import time
import shutil

from copy import deepcopy
from main import Engine, Event
from database import DataBase
from fileutils import get_size, get_created, get_hash, get_file_and_dir


class EmptyEngineClass( unittest.TestCase ):
	DEFAULT_CFG = [ r'D:\disk\Projects\pyMediaMonitor\TEST_DIR' ]
	DEFAULT_CFG_DB = { 'dir': 'TEST_DIR',
					   'tags': {},
					   'media': [] }
	def setUp( self ):
		self.defOutReturn = True
		self.engine = Engine()
		self.engine.cfg = self.DEFAULT_CFG
		self.engine.db.db = deepcopy( self.DEFAULT_CFG_DB )

	def tearDown( self ):
		del self.engine


########################################################################
# TODO: Test info in prepareEvent						   			   #
# TODO: Test RENAMED in prepareEvent (file and directory)  			   #
# TODO: Test RENAMED in processEvent (file and directory)  			   #
# TODO: Test flags in find in database					   			   #
# TODO: Test update in database (file and directory)	   			   #
# TODO: Do something with root argument in updateAllInPath 			   #
# TODO: Make prepareEvent and processEvent deal with UPDATED event 	   #
########################################################################


class TestUpdateAll( EmptyEngineClass ):
	def test_new_file( self ):
		files = [os.path.join( self.DEFAULT_CFG[0], 'file_1' )]
		ev = Event( None, None, None, None )
		with unittest.mock.patch( 'glob.iglob', return_value = files ) as glob_mock:
			with unittest.mock.patch( 'os.path.isdir', return_value = False ):
				with unittest.mock.patch( 'main.Engine.prepareEvent', return_value = ev ) as p:
					self.engine.updateAllInPath( self.DEFAULT_CFG[0], self.DEFAULT_CFG[0] )
					p.assert_called_once_with( files[0], self.DEFAULT_CFG[0], Event.ACTION.NEW )

	def test_new_dir_empty( self ):
		side_effect = lambda x: files if x == os.path.join(self.DEFAULT_CFG[0], '*') else []
		files = [os.path.join( self.DEFAULT_CFG[0], 'dir_1' )]
		ev = Event( None, None, None, None )
		with unittest.mock.patch( 'glob.iglob', side_effect = side_effect ):
			with unittest.mock.patch( 'os.path.isdir', return_value = True ):
				with unittest.mock.patch( 'main.Engine.prepareEvent', return_value = ev ) as p:
					self.engine.updateAllInPath( self.DEFAULT_CFG[0], self.DEFAULT_CFG[0] )
					self.assertEqual( p.call_count, 0 )

	def test_new_dir_with_one_file( self ):
		side_effect_iglob = lambda x: dirs if x == os.path.join(self.DEFAULT_CFG[0], '*') else files
		side_effect_isdir = lambda x: True if x == os.path.join(dirs[0]) else False
		dirs = [os.path.join( self.DEFAULT_CFG[0], 'dir_1' )]
		files = [os.path.join( dirs[0], 'file_1' )]
		ev = Event( None, None, None, None )
		with unittest.mock.patch( 'glob.iglob', side_effect = side_effect_iglob ):
			with unittest.mock.patch( 'os.path.isdir', side_effect = side_effect_isdir ):
				with unittest.mock.patch( 'main.Engine.prepareEvent', return_value = ev ) as p:
					self.engine.updateAllInPath( self.DEFAULT_CFG[0], self.DEFAULT_CFG[0] )
					p.assert_called_once_with( files[0], self.DEFAULT_CFG[0], Event.ACTION.NEW )

	def test_new_dir_with_dir( self ):
		side_effect = lambda x: dirs if x == os.path.join(self.DEFAULT_CFG[0], '*') else dirs_inside
		dirs = [os.path.join( self.DEFAULT_CFG[0], 'dir_1' )]
		dirs_inside = [os.path.join( dirs[0], 'dir_inside' )]
		ev = Event( None, None, None, None )
		with unittest.mock.patch( 'glob.iglob', side_effect = side_effect ):
			with unittest.mock.patch( 'os.path.isdir', return_value = True ):
				with unittest.mock.patch( 'main.Engine.prepareEvent', return_value = ev ) as p:
					self.engine.updateAllInPath( self.DEFAULT_CFG[0], self.DEFAULT_CFG[0] )
					p.assert_called_once_with( dirs_inside[0], self.DEFAULT_CFG[0], Event.ACTION.BROKEN_STRUCTURE )


class TestEngineTasks( EmptyEngineClass ):
	def setResult( self, result ):
		self.result = result

	def launch_worker( self ):
		self.engine.queue.put( 'quit' )
		self.engine.worker.run()

	def test_quit( self ):
		self.launch_worker()

	def test_task_len_3( self ):
		q = ( 'query', { 'file': 'no_file' }, lambda x: None )
		self.engine.queue.put( q )
		self.launch_worker()

	def test_task_len_2( self ):
		q = ( 'query', { 'file': 'no_file' } )
		self.engine.queue.put( q )
		self.launch_worker()

	def test_task_len_invalid( self ):
		q = ( 'query', { 'file': 'no_file' }, 1, 2 )
		self.engine.queue.put( q )
		with self.assertRaises( TypeError ):
			self.launch_worker()

	def test_query( self ):
		self.engine.db.add( file = 'filename', hash = 'xxx' )
		q = ( 'query', { 'file': 'filename', 'hash': 'xxx' }, self.setResult )
		self.engine.queue.put( q )
		self.launch_worker()
		self.assertEqual( self.result, self.engine.db.find( file = 'filename' ) )


class TestProcessEvent( EmptyEngineClass ):
	def construct_event( self, action, d = '', isdir = False ):
		ev = Event( 'filename', d, isdir, self.DEFAULT_CFG[0] )
		ev.action = action
		return ev

	#def test_NOT_PROCESSING( self ):
	#	ev = self.construct_event( Event.ACTION.NOT_PROCESSING )

	def test_NEW( self ):
		ev = self.construct_event( Event.ACTION.NEW, 'test_dir' )
		ev.info = 'xxx'
		self.engine.processEvent( ev )
		res = self.engine.db.find( file = 'filename', dir = 'test_dir', hash = ev.info )
		self.assertEqual( len( res ), 1 )

	def test_MISSING( self ):
		ev = self.construct_event( Event.ACTION.MISSING, 'test_dir' )
		self.engine.db.add( file = 'filename', dir = 'test_dir' )
		self.engine.processEvent( ev )
		res = self.engine.db.find( file = 'filename', dir = 'test_dir')
		self.assertEqual( len( res ), 0 )

	def test_DUPLICATE( self ):
		self.engine.db.add( file = 'duplicate', hash = 'duplicate' )
		ev = self.construct_event( Event.ACTION.DUPLICATE, 'test_dir' )
		ev.info = self.engine.db.find( file = 'duplicate', dir = 'test_dir' )
		with unittest.mock.patch( 'os.unlink', return_value = None ) as unlink_path:
			self.engine.processEvent( ev )
			unlink_path.assert_called_once_with( ev.path )
			self.assertEqual( self.engine.ignoreFiles, [ev.path] )

	def test_RENAMED( self ):
		pass


class TestPrepareEvent( EmptyEngineClass ):
	def test_NEW_file_not_in_db_not_exists( self ):
		ev = Event( 'filename', '', False, self.DEFAULT_CFG[0] )
		ev.action = Event.ACTION.NEW
		newEv = self.engine.prepareEvent( ev.path, self.DEFAULT_CFG[0], ev.action )
		self.assertEqual( newEv.action, Event.ACTION.NOT_PROCESSING )

	def test_NEW_file_not_in_db_exists( self ):
		ev = Event( 'filename', '', False,self.DEFAULT_CFG[0] )
		ev.action = Event.ACTION.NEW
		with unittest.mock.patch( 'os.path.exists', return_value = True ) as exists_test:
			newEv = self.engine.prepareEvent( ev.path, self.DEFAULT_CFG[0], ev.action )
			exists_test.assert_called_once_with( ev.path )
		ev.isInDB = False
		ev.info = None
		self.assertEqual( ev, newEv )

	def test_NEW_file_already_in_db_not_exists( self ):
		self.engine.db.add( file = 'filename', hash = 'xxx' )
		ev = Event( 'filename', '', False, self.DEFAULT_CFG[0] )
		ev.action = Event.ACTION.NEW
		newEv = self.engine.prepareEvent( ev.path, self.DEFAULT_CFG[0], ev.action )
		ev.action = Event.ACTION.MISSING	# Функция должна обнаружить пропажу файла, так как в базе он есть
		ev.isInDB = True
		self.assertEqual( ev, newEv )

	def test_NEW_file_already_in_db_exists_bad_hash( self ):
		self.engine.db.add( file = 'filename', hash = 'xxx' )
		ev = Event( 'filename', '', False, self.DEFAULT_CFG[0] )
		ev.action = Event.ACTION.NEW
		with unittest.mock.patch( 'os.path.exists', return_value = True ) as exists_test:
			newEv = self.engine.prepareEvent( ev.path, self.DEFAULT_CFG[0], ev.action )
			exists_test.assert_called_once_with( ev.path )
		ev.isInDB = True
		ev.action = Event.ACTION.BAD_HASH	# Так как оказывается, что тот файл, который сейчас на диске не совпадает с тем, что в базе.
		ev.info = self.engine.db.find( file = 'filename' )
		self.assertEqual( ev, newEv )

	def test_NEW_file_already_in_db_exists_good_hash( self ):
		self.engine.db.add( file = 'filename', hash = None )
		ev = Event( 'filename', '', False, self.DEFAULT_CFG[0] )
		ev.action = Event.ACTION.NEW
		with unittest.mock.patch( 'os.path.exists', return_value = True ) as exists_test:
			newEv = self.engine.prepareEvent( ev.path, self.DEFAULT_CFG[0], ev.action )
			exists_test.assert_called_once_with( ev.path )
		self.assertEqual( Event.ACTION.NOT_PROCESSING, newEv.action )		# Файл на диске совпал с тем, что в базе -  игнорируем.

	def test_NEW_file_not_in_db_another_file_in_db_with_same_hash( self ):
		self.engine.db.add( file = 'duplicate', hash = 'xxx' )
		ev = Event( 'filename', '', False, self.DEFAULT_CFG[0] )
		ev.action = Event.ACTION.NEW
		with unittest.mock.patch( 'os.path.exists', return_value = True ) as exists_test:
			with unittest.mock.patch( 'fileutils.get_hash', return_value = 'xxx' ) as get_hash_patch:
				newEv = self.engine.prepareEvent( ev.path, self.DEFAULT_CFG[0], ev.action )
				get_hash_patch.assert_called_once_with( ev.path )
				exists_test.assert_called_once_with( ev.path )
		self.assertEqual( Event.ACTION.DUPLICATE, newEv.action )		# Файл на диске имеет такой же хэш как и файл в базе - дубликат
		self.assertEqual( self.engine.db.find( file = 'duplicate' ), newEv.info )

	def test_MISSING_file_not_in_db_not_exists( self ):
		ev = Event( 'filename', '', False, self.DEFAULT_CFG[0] )
		ev.action = Event.ACTION.MISSING
		newEv = self.engine.prepareEvent( ev.path, self.DEFAULT_CFG[0], ev.action )
		self.assertEqual( newEv.action, Event.ACTION.NOT_PROCESSING )	# Файл, который удалили, и так не было в базе - не обрабатываем его.

	def test_MISSING_file_not_in_db_exists( self ):
		ev = Event( 'filename', '', False, self.DEFAULT_CFG[0] )
		ev.action = Event.ACTION.MISSING
		with unittest.mock.patch( 'os.path.exists', return_value = True ) as exists_test:
			newEv = self.engine.prepareEvent( ev.path, self.DEFAULT_CFG[0], ev.action )
			exists_test.assert_called_once_with( ev.path )
		ev.action = Event.ACTION.NEW		# Пришло событие об удалении файла, а он есть, добавляем в базу.
		ev.isInDB = False
		ev.info = None
		self.assertEqual( ev, newEv )

	def test_MISSING_file_already_in_db_not_exists( self ):
		self.engine.db.add( file = 'filename' )
		ev = Event( 'filename', '', False, self.DEFAULT_CFG[0] )
		ev.action = Event.ACTION.MISSING
		newEv = self.engine.prepareEvent( ev.path, self.DEFAULT_CFG[0], ev.action )
		ev.isInDB = True
		self.assertEqual( ev, newEv )		# Файла на диске нет, а в базе есть - пропажа файла.

	def test_MISSING_file_already_in_db_exists_bad_hash( self ):
		self.engine.db.add( file = 'filename', hash = 'xxx' )
		ev = Event( 'filename', '', False, self.DEFAULT_CFG[0] )
		ev.action = Event.ACTION.MISSING
		with unittest.mock.patch( 'os.path.exists', return_value = True ) as exists_test:
			newEv = self.engine.prepareEvent( ev.path, self.DEFAULT_CFG[0], ev.action )
			exists_test.assert_called_once_with( ev.path )
		ev.isInDB = True
		ev.action = Event.ACTION.BAD_HASH					# Файл на диске есть, в базе есть, но они не совпали.
		ev.info = self.engine.db.find( file = 'filename' )
		self.assertEqual( ev, newEv )

	def test_MISSING_file_already_in_db_exists_good_hash( self ):
		self.engine.db.add( file = 'filename', hash = None )
		ev = Event( 'filename', '', False, self.DEFAULT_CFG[0] )
		ev.action = Event.ACTION.MISSING
		with unittest.mock.patch( 'os.path.exists', return_value = True ) as exists_test:
			newEv = self.engine.prepareEvent( ev.path, self.DEFAULT_CFG[0], ev.action )
			exists_test.assert_called_once_with( ev.path )
		self.assertEqual( Event.ACTION.NOT_PROCESSING, newEv.action )	# Файл на диске совпал с тем, что в базе -  игнорируем.

	def test_double_item_in_db( self ):
		self.engine.db.add( file = 'filename', hash = None )
		self.engine.db.add( file = 'filename', hash = None )
		ev = Event( 'filename', '', False, self.DEFAULT_CFG[0] )
		ev.action = Event.ACTION.NEW
		self.assertRaises( RuntimeError, self.engine.prepareEvent, ev.path, self.DEFAULT_CFG[0], ev.action )

	def test_RENAMED_file_not_in_db( self ):
		ev = Event( 'filename', '', False, self.DEFAULT_CFG[0] )
		ev.action = Event.ACTION.RENAMED
		with unittest.mock.patch( 'os.path.exists', return_value = True ) as exists_test:
			new_path = os.path.join( self.DEFAULT_CFG[0], 'new_filename' )
			newEv = self.engine.prepareEvent( ev.path, self.DEFAULT_CFG[0], ev.action, new_path )
			exists_test.assert_called_once_with( ev.path )
		self.assertEqual( Event.ACTION.NEW, newEv.action )	# Файл был переименован, но в базе его нет - новый файл
		self.assertEqual( new_path, newEv.path )	

	def test_RENAMED_file_already_in_db( self ):
		self.engine.db.add( file = 'filename', hash = None )
		ev = Event( 'filename', '', False, self.DEFAULT_CFG[0] )
		ev.action = Event.ACTION.RENAMED
		with unittest.mock.patch( 'os.path.exists', return_value = True ) as exists_test:
			new_path = os.path.join( self.DEFAULT_CFG[0], 'new_filename' )
			newEv = self.engine.prepareEvent( ev.path, self.DEFAULT_CFG[0], ev.action, new_path )
			exists_test.assert_called_once_with( ev.path )
		self.assertEqual( Event.ACTION.RENAMED, newEv.action )	# Файл был переименован, в базе есть - нужно обновить базу
		self.assertEqual( get_file_and_dir( new_path, self.DEFAULT_CFG[0], False ), newEv.info )


class TestEngineCfg( unittest.TestCase ):
	def setUp( self ):
		self.engine = Engine()
		self.engine.loadCfg()
		self.assertEqual( self.engine.cfg, self.engine.DEFAULT_CFG )

	def test_write_cfg( self ):
		self.engine.writeCfg( 'TEST_DIR/test_cfg_2' )
		self.engine.loadCfg( 'TEST_DIR/test_cfg_2' )
		self.assertEqual( self.engine.cfg, self.engine.DEFAULT_CFG )
		os.unlink( 'TEST_DIR/test_cfg_2' )


class TestFileUtils( unittest.TestCase ):
	testData = b'12345689abcdefghijklmnopqrsuvwxyz_'

	def setUp( self ):
		with open( 'TEST_DIR/tmp file', 'wb' ) as f:
			f.write( self.testData )

	def tearDown( self ):
		os.unlink( 'TEST_DIR/tmp file' )

	def test_get_size( self ):
		self.assertEqual( get_size( 'TEST_DIR/tmp file' ), len( self.testData ) )

	def test_get_hash( self ):
		self.assertEqual( get_hash( 'TEST_DIR/tmp file' ), 'bf5c8c903440047e4bcd6f532b8d662a46144b7709e9c633734fd8c127df8c17' )

	def test_get_created( self ):
		self.assertTrue( get_created( 'TEST_DIR/tmp file' ) - int( time.time() ) < 60 )			# Винда как-то косячит, поэтому время создания немного отстаёт. (кэш?)

	def test_get_file_and_dir_with_file( self ):
		f, d = get_file_and_dir( 'C:/test_dir/test_file', 'C:/' )
		self.assertEqual( f, 'test_file' )
		self.assertEqual( d, 'test_dir' )

	def test_get_file_and_dir_with_dir( self ):
		f, d = get_file_and_dir( 'C:/test_dir/', 'C:/', True )
		self.assertEqual( f, '' )
		self.assertEqual( d, 'test_dir' )

	def test_get_file_and_dir_with_file_with_long_root( self ):
		f, d = get_file_and_dir( 'C:/test_dir/test_file', 'C:/test_dir/' )
		self.assertEqual( f, 'test_file' )
		self.assertEqual( d, '' )

	def test_get_file_and_dir_with_file_with_dir_as_file( self ):
		f, d = get_file_and_dir( 'C:/test_dir/test_dir_2', 'C:/test_dir/', True )
		self.assertEqual( f, '' )
		self.assertEqual( d, 'test_dir_2' )


class TestDB( unittest.TestCase ):
	dbData = {	'dir': 'TEST_DIR',
				'tags': { 'test_tag_1': 1,
					 	  'test  tag 2': 2,
					 	  'test!/|-@ tag    3': 1,
					 	  'тест тэг 4': 4 },
			  	'media': [ 	{ 'file': '1.jpg', 'dir': 'test_content', 'size': 587370, 'created': 1389078966, 'tags': { 'тест тэг 4', 'test!/|-@ tag    3' },
			  				  'url': 'http://2.bp.blogspot.com/-722WR2hJZNk/T4HplxWF9WI/AAAAAAAAles/nzwyIIR-If0/s1600/162985+-+artist+john_joseco+cake+celestia.jpg',
			  				  'hash': None, 'google': 'princess celestia cake' },
			  				{ 'file': '2.jpg', 'dir': 'test content 2', 'size': 622645, 'created': 1389078965, 'tags': { 'тест тэг 4', 'test_tag_1', 'test  tag 2' },
			  				  'url': 'http://poniez.net/images/2012/07/16/3Bz2F.jpg',
			  				  'hash': None, 'google': 'мир пони' },
			  				{ 'file': '3.jpg', 'dir': 'тест контент 3', 'size': 5784745, 'created': 1389078965, 'tags': { 'тест тэг 4', 'test  tag 2' },
			  				  'url': 'https://static1.e621.net/TEST_DIR/sample/01/76/017691130342c69beb81ce71e2399df0.jpg',
			  				  'hash': None, 'google': 'luna celestia' },
			  				{ 'file': '4.jpg', 'dir': 'unknown dir', 'size': 5784745, 'created': 1389078955, 'tags': { 'тест тэг 4' },
			  				  'url': 'https://pp.vk.me/c409823/v409823018/8ad0/9_S0XT7uEcQ.jpg',
			  				  'hash': None, 'google': None }
			  			 ]
		 	 }

	def setUp( self ):
		self.db = DataBase()
		self.db.db = deepcopy( self.dbData )

	def tearDown( self ):
		del self.db

	def test_load_db( self ):
		with open( 'TEST_DIR/test_db', 'wb' ) as f:
			pickle.dump( self.dbData, f )
		self.db.load_db( 'xxxxxxxxxxxxxxxxxxxxxxx' )
		self.assertEqual( self.db.db, self.db.EMPTY_DB )
		self.db.load_db( 'TEST_DIR/test_db' )
		self.assertEqual( self.db.db, self.dbData )
		os.unlink( 'TEST_DIR/test_db' )

	def test_find_file( self ):
		self.assertEqual( self.db.find( file = '3.jpg' ), [ self.dbData['media'][2] ] )

	def test_find_dir( self ):
		self.assertEqual( self.db.find( dir = 'test_content' ), [ self.dbData['media'][0] ] )

	def test_find_size( self ):
		self.assertEqual( self.db.find( size = 0 ), [] )
		
	def test_find_created( self ):
		self.assertEqual( self.db.find( created = 1389078966 ), [ self.dbData['media'][0] ] )
		
	def test_find_tags( self ):
		self.assertEqual( self.db.find( tags = {'test  tag 2'} ), [ self.dbData['media'][1], self.dbData['media'][2] ] )
		
	def test_find_url_regex( self ):
		self.assertEqual( self.db.find( url = r'\.net/' ), [ self.dbData['media'][1], self.dbData['media'][2] ] )
		
	def test_find_hash( self ):
		self.assertEqual( self.db.find( hash = None ), [ self.dbData['media'][0], self.dbData['media'][1], self.dbData['media'][2], self.dbData['media'][3] ] )
		
	def test_find_google( self ):
		self.assertEqual( self.db.find( google = None ), [ self.dbData['media'][3] ] )

	def test_find_both_hash_url( self ):
		self.assertEqual( self.db.find( hash = None, url = 'net' ), [ self.dbData['media'][1], self.dbData['media'][2] ] )

	def test_add( self ):
		self.db.add( file = 'test', hash = 'xxx' )
		found = self.db.find( file = 'test' )
		self.assertEqual( len( found ), 1 )
		self.assertEqual( self.db.db['tags']['Unsorted'], 1 )
		self.assertEqual( found[0]['hash'], 'xxx' )
		self.assertIn( found[0], self.db.db['media'] )
		self.assertEqual( found[0]['created'], None )

	def test_add_with_tag( self ):
		self.db.add( file = 'test_tag', tags = {'unique_test_tag'} )
		self.assertIn( 'unique_test_tag', self.db.find( file = 'test_tag' )[0]['tags'] )
		self.assertIn( 'unique_test_tag', self.db.db['tags'] )
		self.assertEqual( self.db.db['tags']['unique_test_tag'], 1 )

	def test_add_full( self ):
		elem = self.dbData['media'][3]
		elem['file'] = 'test.png'
		self.db.add( **elem )
		self.assertEqual( self.db.find( file = 'test.png' ), [elem] )
		self.assertEqual( self.db.db['tags']['тест тэг 4'], self.dbData['tags']['тест тэг 4'] + 1 )

	def test_remove( self ):
		self.assertIn( self.dbData['media'][0], self.db.db['media'] )
		self.db.remove( file = '1.jpg' )
		self.assertNotIn( self.dbData['media'][0], self.db.db['media'] )
		self.assertEqual( self.db.db['tags']['тест тэг 4'], self.dbData['tags']['тест тэг 4'] - 1 )
		self.assertNotIn( 'test!/|-@ tag    3', self.db.db['tags'].keys() )

if __name__ == "__main__":
	unittest.main()