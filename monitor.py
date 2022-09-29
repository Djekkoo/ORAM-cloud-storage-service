import os
import time
import random
import hashlib
from pprint import pprint

# load local classes
from updatemonitor import UpdateMonitor
from client import Client

# load settings
from settings import Settings
settings = Settings()

# Class which monitors file system changes(storage dir), and communicates with updatemonitor and client class
class Monitor():

	# load monitor class, set local settings and connect with UpdateMonitor
	# clear_database re-creates an empty database 
	def __init__(self, clear_database=False):

		# get update monitor
		self.update = UpdateMonitor()

		# get client for communication with server
		self.client = Client()
		if clear_database == True:
			self.client.reset_database()

		### load index
		self.index = self.update.read_index()

		# index has not yet been created -> create it and upload files
		if self.index == {}:
			# print("No file index found")
			self.update.create_index(self.get_files_information())
			self.index = self.update.read_index()
			
			# created index, so upload files content to server
			self.upload_index_files()


	# upload all files (in blocks) to server (invoked when a brand new index is generated)
	def upload_index_files(self):
		for file in self.index['files']:
			self.upload_file(file)

	# upload a file to the server (in blocks)
	# file must be present in the index
	def upload_file(self, file, changed_block_list=None):
		blocks = self.update.parseBlockList(self.index['files'][file]['blocks'])
		with open(file, 'rb') as tmp_file:
			for i in range(len(blocks)):
				block_content = self.client.padd_content(tmp_file.read(settings.blockSize))
				# changed_block_list is used during file changes, see explanation in method find_changes
				if changed_block_list == None or blocks[i] in changed_block_list:
					self.client.write(blocks[i], block_content)


	# download file from server (collect blocks from update-monitor, and request data from client)
	def download_file(self, file):
		blocks = self.update.parseBlockList(self.index['files'][file]['blocks'])
		cmp_size = self.index['files'][file]['size']
		file_content = bytes()
		# pprint("READ FILE: " + str(file))
		# pprint(blocks)
		# pprint(cmp_size)
		for i in range(len(blocks)):
			tmp_data = self.client.read(blocks[i])
			if cmp_size >= settings.blockSize:
				cmp_size -= settings.blockSize
			else:
				tmp_data = tmp_data[:cmp_size]
				cmp_size = 0
			file_content += tmp_data

		return file_content



	# find all (recursive) files in settings.source_directory, and collect information about it
	def get_files_information(self):
		dirs = [settings.source_directory]
		result = {} # result variable
		for d in dirs:
			content = os.listdir(d)
			for path in content:
				tmp_path = d + '/' + path
				# skip index file
				if tmp_path in settings.ignore_files:
					continue

				# found file: store information about it in result variable: result
				if os.path.isfile(tmp_path):
					result[tmp_path] = {
						'size': os.path.getsize(tmp_path),
						'last_modified': os.path.getmtime(tmp_path)
					}

					# FILE HASH
					if settings.file_hash == True:
						result[tmp_path]['hash'] = self.get_file_hash(tmp_path)


				# found directory, add recursion
				else:
					dirs.append(tmp_path)

		# return result
		return result

	# Get SHA256 hash of file
	def get_file_hash(self, file):
		sha256_hash = hashlib.sha256()
		with open(file,"rb") as f:
			# Read and update hash string value in blocks of settings.blocksize
			for byte_block in iter(lambda: f.read(settings.blockSize),b""):
				sha256_hash.update(byte_block)
		return sha256_hash.hexdigest()

	# monitor changes and invoke update-monitor when found
	def find_changes(self):
		# get all files in source directory
		files = self.get_files_information()

		# check for deletions
		tmp_list = []
		for file in self.index['files']:
			if file not in files:
				tmp_list.append(file)

		# potential renames instead of rewrites
		hash_list = {}
		# delete files from index (no need to update deleted blocks on the server, they will be automatically recycled)
		for file in tmp_list:
			if settings.file_hash == True:
				hash_list[self.index['files'][file]['hash']] = self.update.parseBlockList(self.index['files'][file]['blocks'])
				self.update.processDeletion(file)
			else:
				self.update.processDeletion(file)

		# check for additions and changes
		for file in files:
			# check for new files (always upload all blocks of new files to server)
			if file not in self.index['files']:
				reuse_blocks = []
				# file hash enabled? If so, check if the file was renamed instead of created
				if settings.file_hash and files[file]['hash'] in hash_list:
					reuse_blocks = hash_list[files[file]['hash']]
				
				upload_file = self.update.processAddition(file, files[file], reuse_blocks)

				# true new file or file_hash is turned off ->  upload file to server
				if upload_file:
					self.upload_file(file)

			# check for changes (if block_hash is true: upload only the changed blocks, if not: re-upload all blocks)
			elif self.index['files'][file]['last_modified'] != files[file]['last_modified']:
				# changed_block_list is None when settings.block_hash is False, and contains a list of changed blocks when True
				changed_block_list = self.update.processUpdate(file, files[file])
				# re-upload file to server
				self.upload_file(file, changed_block_list)

		









# run monitor and continue to look for changes until interruption
if __name__ == "__main__":
	monitor = Monitor()
	try:
		while True:
			time.sleep(1)
			monitor.find_changes()
	except KeyboardInterrupt:
		exit()
    









