import math


class Settings():
	def __init__(self):

		# server-client network settings
		self.HOST = "localhost"
		self.PORT = 9991
		self.skip_network_connection = True # client initialised Server class and directly calls handle_request method, rather then perform network communication

		# communication encryption settings
		self.encryption_password = 'secret_encryption_password'
		self.encryption_nonce_length = 8 # (64bit) - AES settings, not changable

		# Block settings
		self.blockSize = 50000#20000*200000 #50kb
		self.server_storage_size = self.blockSize*8176 #8176 #16380#3100#12000000#2000000000 #620000 #500mb
		self.N_blocks = math.ceil(self.server_storage_size / self.blockSize) #1000

		# storage/file settings
		self.source_directory = './storage-v2'
		self.server_directory = './storage-blocks'
		self.index_file = self.source_directory + '/' + '.index'


		# file conversion settings
		self.file_hash = True
		self.block_hash = True
		self.blocks_use_extends = True

		# ORAM settings
		self.oram = 'trivial'#'pathoram'#'trivial'#'sqrt'
		self.oram_index_file = self.source_directory + '/' + '.oram-index'
		self.oram_cache_file = self.source_directory + '/' + '.oram-cache'
		self.oram_Z_blocks_per_bucket = 16
		self.oram_eviction_rate = 5 # used by trivial oram

		# config files, located in self.source_directory, and should be ignored by file changes monitor
		self.ignore_files = [self.index_file, self.oram_index_file, self.oram_cache_file]