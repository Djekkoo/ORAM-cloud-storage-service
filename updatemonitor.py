import os
import json
import hashlib
from pprint import pprint
from settings import Settings
settings = Settings()


class UpdateMonitor():
	def __init__(self):
		self.source_directory = settings.source_directory
		self.index = {}
		# debugging files
		self.testFiles = []#'./storage-v2/medium_files/655kb.txt', './storage-v2/large_files/70mb.txt', './storage-v2/large_files/7mb.txt',
											#'./storage-v2/large_files/8mb.txt', './storage-v2/large_files/80mb.txt', './storage-v2/medium_files/656kb.txt']

	# create index file in source directory
	def create_index(self, files):
		# remove existing index
		if os.path.exists(settings.index_file):
			print("Removed old index to create a new one")
			os.remove(settings.index_file)

		# get ORAM specs
		blockSize = settings.blockSize

		# create JSON structure
		self.index = {
			'general': {
				'last_block_id': 0,
				'deleted_blocks': []
			},
			'files': {}
		}

		## add file information
		for file in files:
			self.index['files'][file] = {
				'size': files[file]['size'],
				'last_modified': files[file]['last_modified'],
				'blocks': []
			}

			# include file hash? 
			if settings.file_hash == True:
				self.index['files'][file]['hash'] = files[file]['hash']

			# assign blocks to file
			tmp_size = files[file]['size']
			while tmp_size > 0:
				self.index['general']['last_block_id'] += 1
				self.index['files'][file]['blocks'].append(self.index['general']['last_block_id'])
				tmp_size -= blockSize

			# include block hashes?
			if settings.block_hash == True:
				self.index['files'][file]['block_hash'] = []
				with open(file, "rb") as tmp_file:
					for byte_block in iter(lambda: tmp_file.read(settings.blockSize), b""):
						self.index['files'][file]['block_hash'].append(hashlib.sha256(byte_block).hexdigest())

			# encode blocks (apply extend)
			self.index['files'][file]['blocks'] = self.updateBlockList(self.index['files'][file]['blocks'])
			if file in self.testFiles:
				pprint("=====================INIT: " + str(file))
				pprint(self.index['files'][file]['blocks'])

		# write JSON to index file
		with open(settings.index_file, 'w') as index_file:
			json.dump(self.index, index_file)

	# read index file and return data
	def read_index(self):
		if os.path.exists(settings.index_file):
			with open(settings.index_file, 'r') as index_file:
				self.index = json.load(index_file)
		else:
			self.index = {}

		return self.index

	# write/update self.index to settings.index_file
	def update_index(self):
		# sort deleted blocks to prevent fragmentation
		self.index['general']['deleted_blocks'].sort()

		with open(settings.index_file, 'w') as index_file:
			json.dump(self.index, index_file)


	# obtain block list from index-based block list and unpack extends if enabled
	def parseBlockList(self, blocks):
		# if extends is not used, return regular block list from index
		if settings.blocks_use_extends == False:
			return blocks

		# extends is used, 
		extended_block_list = []
		for entry in blocks:
			if type(entry) == int:
				extended_block_list.append(entry)
			elif type(entry) == list:
				for block_id in range(entry[0], entry[1]+1):
					extended_block_list.append(block_id)
			else:
				pprint("PARSE BLOCK ERROR: " + str(type(entry)))
				pprint(entry)

		return extended_block_list

	# update block list from file to index, ensure that extends are used if necessary
	# returns stored extended result list
	def updateBlockList(self, blocks):
		# if extends is not used, set list of blocks as blocklist in index
		if settings.blocks_use_extends == False:
			return blocks

		# extends is used, transform block list into extends 
		extended_result = []
		for block_id in blocks:
			# first entry
			if len(extended_result) == 0:
				extended_result.append(block_id)
				continue
			
			# get basis of comparison
			cmp_value = extended_result[len(extended_result)-1]
			cmp_type = type(cmp_value)

			# blocks in sequence, transform previous int to tuple
			if cmp_type == int and cmp_value+1 == block_id:
				extended_result[len(extended_result)-1] = [cmp_value, block_id]
				continue

			# block_id follows previous extend range
			if cmp_type == list and cmp_value[1]+1 == block_id:
				extended_result[len(extended_result)-1] = [cmp_value[0], block_id]
				continue

			# block_id is unrelated, add new entry
			extended_result.append(block_id)

		return extended_result


	# triggered file change
	# returns changed_block_list
	# changed_block_list is [] when settings.block_hash is False, and contains a list of changed blocks when True
	def processUpdate(self, file, attributes):
		
		# get unpacked block list
		blocks = self.parseBlockList(self.index['files'][file]['blocks'])

		if file in self.testFiles:
			pprint("=====================UPDATE: " + str(file))
			pprint(self.index['files'][file]['blocks'])

		# check if the file size is supported by the assigned blocks
		cmp_size = attributes['size']
		cmp_size -= len(blocks)*settings.blockSize

		# file size got bigger then the limit supported by the assigned blocks, thus assign new blocks:
		while cmp_size > 0:
			# recycle blocks from deleted files
			if len(self.index['general']['deleted_blocks']) > 0:
				blocks.append(self.index['general']['deleted_blocks'].pop(0))

			# assign new blocks of higher ID
			else:
				self.index['general']['last_block_id'] += 1
				blocks.append(self.index['general']['last_block_id'])
			cmp_size -= settings.blockSize

			# if block hashes are enabled: add entry to block hash list
			if settings.block_hash == True:
				self.index['files'][file]['block_hash'].append('')

		# file size got smaller, thus needing less blocks
		while cmp_size <= -settings.blockSize:
			# remove latest block from file
			self.index['general']['deleted_blocks'].append(blocks.pop())
			cmp_size += settings.blockSize

			# if block hashes are enabled: remove last block hash from index
			if settings.block_hash == True:
				self.index['files'][file]['block_hash'].pop()


		# adjust size and latest modification date in index
		self.index['files'][file]['last_modified'] = attributes['last_modified']
		self.index['files'][file]['size'] = attributes['size']

		# adjust hash? If hash is enabled
		if settings.file_hash == True:
			self.index['files'][file]['hash'] = attributes['hash']

		# if block hash is enabled, update block hashes and see which blocks are unchanged
		changed_block_list = None
		if settings.block_hash == True:
			changed_block_list = []
			with open(file, "rb") as tmp_file:
				for block_index in range(0, len(blocks)):
					# calculate hash
					tmp_file.seek(block_index*settings.blockSize)
					tmp_block_hash = hashlib.sha256(tmp_file.read(settings.blockSize)).hexdigest()
					# compare / adjust
					if self.index['files'][file]['block_hash'][block_index] != tmp_block_hash:
						self.index['files'][file]['block_hash'][block_index] = tmp_block_hash
						changed_block_list.append(blocks[block_index])

					# self.index['files'][file]['block_hash']hashlib.sha256(byte_block).hexdigest())

		# update blocks in index
		self.index['files'][file]['blocks'] = self.updateBlockList(blocks)

		if file in self.testFiles:
			pprint(self.index['files'][file]['blocks'])

		self.update_index()
		return changed_block_list


	# triggered file deletion
	# returns deleted blocks
	def processDeletion(self, file):
		# free assigned blocks
		del_blocks = self.parseBlockList(self.index['files'][file]['blocks'])
		self.index['general']['deleted_blocks'].extend(del_blocks)
		# delete file entry in index
		tmp = self.index['files'][file]
		del self.index['files'][file]
		self.update_index()
		return tmp


	# triggered file addition
	# 'reuse_blocks' is only used with option file_hash, and when the file has been previously deleted (rename)
	# return True/False depending on upload file
	def processAddition(self, file, attributes, reuse_blocks=[]):
		self.index['files'][file] = {
			'size': attributes['size'],
			'last_modified': attributes['last_modified'],
			'blocks': []
		}

		blocks = []

		# adjust hash? If hash is enabled
		if settings.file_hash == True:
			self.index['files'][file]['hash'] = attributes['hash']

			### reuse blocks?
			if len(reuse_blocks) > 0 and all(x in self.index['general']['deleted_blocks'] for x in reuse_blocks):
				blocks = reuse_blocks
				# remove from deleted blocks
				for block_id in reuse_blocks:
					self.index['general']['deleted_blocks'].remove(block_id)

				# include (regenerate) block hashes?
				if settings.block_hash == True:
					self.index['files'][file]['block_hash'] = []
					with open(file, "rb") as tmp_file:
						for byte_block in iter(lambda: tmp_file.read(settings.blockSize), b""):
							self.index['files'][file]['block_hash'].append(hashlib.sha256(byte_block).hexdigest())

				# update blocks in index
				self.index['files'][file]['blocks'] = self.updateBlockList(blocks)
				if file in self.testFiles:
					pprint("==========Addition: " + str(file))
					pprint(self.index['files'][file]['blocks'])

				# update index
				self.update_index()
				return False


		### assign blocks to file
		tmp_size = attributes['size']
		while tmp_size > 0:
			# recycle blocks from deleted files
			if len(self.index['general']['deleted_blocks']) > 0:
				blocks.append(self.index['general']['deleted_blocks'].pop(0))

			# assign new blocks of higher ID
			else:
				self.index['general']['last_block_id'] += 1
				blocks.append(self.index['general']['last_block_id'])
			tmp_size -= settings.blockSize

		# include block hashes?
		if settings.block_hash == True:
			self.index['files'][file]['block_hash'] = []
			with open(file, "rb") as tmp_file:
				for byte_block in iter(lambda: tmp_file.read(settings.blockSize), b""):
					self.index['files'][file]['block_hash'].append(hashlib.sha256(byte_block).hexdigest())

		# update blocks in index
		self.index['files'][file]['blocks'] = self.updateBlockList(blocks)
		if file in self.testFiles:
			pprint("==========Addition: " + str(file))
			pprint(self.index['files'][file]['blocks'])

		# update index
		self.update_index()
		return True

