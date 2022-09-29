import math
import sys
import os
import random
import json

from pprint import pprint
from settings import Settings
settings = Settings()

# ORAM implementation class (PathORAM)
class Pathoram():

		# init oram (Set properties and connect to server)
		def __init__(self, client):
			self.client = client

			self.shelter = []
			self.index = self.read_index()

			self.local_max_shelter_size = 0 # in blocks

			# index has not yet been created -> create it and store in settings.oram_index_file
			if self.index == {}:
				# print("No file index found - generate new index file")

				# create index local variables
				self.init_oram()

				# write index to settings.oram_index_file and shelter to settings.oram_cache_file
				self.update_index()


		# read index file (and shelter) and return data
		def read_index(self):
			if os.path.exists(settings.oram_index_file):
				with open(settings.oram_index_file, 'r') as index_file:
					self.index = json.load(index_file)

					# index of other ORAM type: error
					if self.index['general']['oram_type'] != settings.oram:
						print("Found oram index for oram type: " + str(self.index['general']['oram_type']) + ".\nPlease remove it to continue.")
						exit()

					# init shelter
					self.shelter = []

					# read cache file
					with open(settings.oram_cache_file, 'rb') as cache_file:
						for i in range(0, len(self.index['shelter'])):
							if self.index['shelter'][i] != None:
								self.shelter.append(bytes(cache_file.read(settings.blockSize)))

					# set max local shelter size
					self.local_max_shelter_size = max(self.local_max_shelter_size, len(self.index['shelter']))

			else:
				self.index = {}

			return self.index

		# write/update self.index to settings.index_file, as well as write the shelter to the cache file
		def update_index(self):
			# write index
			with open(settings.oram_index_file, 'w') as index_file:
				json.dump(self.index, index_file)

			# write shelter
			with open(settings.oram_cache_file, 'wb') as cache_file:
				for i in range(0, len(self.index['shelter'])):
					if self.index['shelter'][i] != None:
						if self.shelter[i] != None and len(self.shelter[i]) == settings.blockSize:
							cache_file.write(self.shelter[i])
						else:
							# write dummy
							pprint("CACHE ERROR")
							exit()

			# set max local shelter size
			self.local_max_shelter_size = max(self.local_max_shelter_size, len(self.index['shelter']))



		# initialize ORAM structure and local variables
		def init_oram(self):
			
			# server has storage of N blocks, with Z blocks per bucket
			N_buckets_max = math.floor(settings.N_blocks/settings.oram_Z_blocks_per_bucket)

			### calculate tree depth and number of leaves
			buckets_increase = 1
			N_buckets = 0
			max_depth = -1
			while N_buckets + buckets_increase <= N_buckets_max:
				N_buckets += buckets_increase
				max_depth += 1
				buckets_increase *= 2

			N_leaves = int(buckets_increase/2)

			# N_buckets = total number of buckets (including leaves)
			# N_leaves = number of buckets at depth max_depth (leaf nodes as well as potential positions)
			# max_depth = depth of leaf nodes in tree structure
			self.index['general'] = {
				'oram_type': settings.oram,
				'N_buckets' : N_buckets,
				'N_leaves': N_leaves,
				'max_depth': max_depth,
			}
			self.index['pos_map'] = {}   # local_block_id => leaf bucket node
			self.index['shelter'] = []
			self.shelter = []


		# get list of blocks per bucket
		def bucketGetBlocks(self, bucket_id):
			# error check
			if bucket_id < 0 or bucket_id >= int(self.index['general']['N_buckets']): 
				print("Bucket " + str(bucket_id) + " is not in tree structure")
				exit()

			# get [settings.oram_Z_blocks_per_bucket] block ids
			result = []
			prev_block_id = bucket_id*settings.oram_Z_blocks_per_bucket # bucket 0: 0, bucket 2: 4, bucket 3: 8 (Z=4)
			while len(result) < settings.oram_Z_blocks_per_bucket:
				prev_block_id += 1
				result.append(prev_block_id)


			# return list
			return result

		
		# get path from leaves to root bucket (P(x) or P(x, l))
		# returns [root_bucket, sub_bucket_depth_1, sub_bucket_depth_(L-1), sub_bucket_L(=leaf bucket)]
		# if depth is set, return specific bucket
		def path(self, leaf_bucket, depth=None):
			# error checking
			if leaf_bucket >= self.index['general']['N_leaves']:
				print("Cannot find path of non-leaf bucket")
				return

			path = [None]*(self.index['general']['max_depth']+1)

			# set entry for max depth (leaf bucket)
			path[self.index['general']['max_depth']] = leaf_bucket

			# calculate buckets for other depths
			bucket_index_current_layer = 0 # start at leaf 0
			buckets_per_layer = self.index['general']['N_leaves']
			bucket_index = leaf_bucket
			for i in range(self.index['general']['max_depth']-1, -1, -1):
				# calculate next entry
				diff = bucket_index - bucket_index_current_layer
				if diff%2 == 1:
					diff -=1
				diff = int(diff/2)

				path[i] = bucket_index_current_layer + buckets_per_layer + diff
				# set values for next entry
				bucket_index = path[i]
				bucket_index_current_layer += buckets_per_layer
				buckets_per_layer = int(buckets_per_layer/2)
				
			# return values
			if depth != None and int(depth) < len(path):
				return path[int(depth)]

			return path



		# Read(data=None) or Write(data=bytes) operation
		def access(self, block_id, data=None):

			# input validation
			if data != None and len(data) != settings.blockSize:
				print("Writing to block: " + str(block_id) + ". Invalid block length.")
				exit()

			### position magic
			x_pos = self.index['pos_map'].get(str(block_id), None)
			if x_pos == None and data == None:
				print("Cannot read block_id: " + str(block_id) + ". It is not stored in any bucket")
				exit()

			# result variable
			result = None

			### calculate new leaf as position for block (RandomUniform)
			self.index['pos_map'][str(block_id)] = random.randint(0, self.index['general']['N_leaves']-1)

			# if x_pos == None (meaning this block does not yet exist in server storage)
			if x_pos == None:
				# create random x_pos leaf for future execution of readbucket and writebucket operations
				x_pos = random.randint(0, self.index['general']['N_leaves']-1)

				# set included (write) data as result
				result = data

			### read buckets from server and store result in stash
			tmp_path = self.path(x_pos)
			for l_depth in range(0, self.index['general']['max_depth']+1):
				# read all blocks of bucket in P(x_pos, l_depth) and add to stash
				for tmp_block_id in self.bucketGetBlocks(tmp_path[l_depth]):
					# read block and store in stash (if it contains a real block, and not dummy content)
					(tmp_data, local_block_id) = self.client._send("R", tmp_block_id, self.client.generate_dummy_block(), 0)
					if str(local_block_id) not in self.index['pos_map']:
						local_block_id = 0

					# check if content is real block or dummy block (this info is stored in the index)
					# local_block_id == 0: Dummy
					if local_block_id != 0:
						# write block to stash if not already in shelter
						if local_block_id not in self.index['shelter']:
							self.index['shelter'].append(local_block_id)
							self.shelter.append(tmp_data)
				

			### if result is not set, obtain read block from stash
			if result == None and block_id in self.index['shelter']:
				result = self.shelter[self.index['shelter'].index(block_id)]

			### if write: update stash
			if data != None and len(data) == settings.blockSize:
				# block already in shelter?
				if block_id in self.index['shelter']:
					# update shelter with data
					self.shelter[self.index['shelter'].index(block_id)] = data
				# block is not in shelter: add it to shelter.
				else:
					self.index['shelter'].append(block_id)
					self.shelter.append(data)


			### write blocks from stash back to read buckets
			for l_depth in range(self.index['general']['max_depth'], -1, -1):
				# find S'(tmp_stash) with all buckets that can be written to this bucket
				tmp_stash = [] # format: [(block_id, data),...]
				tmp_bucket_id = self.path(x_pos, l_depth)
				for shelter_index in range(0, len(self.index['shelter'])):
					# see if cached block can be written to bucket P(x_pos, l_depth)
					if tmp_bucket_id == self.path(self.index['pos_map'].get(str(self.index['shelter'][shelter_index])), l_depth):
						tmp_stash.append((self.index['shelter'][shelter_index], self.shelter[shelter_index]))

					# tmp_stash has reached the limit of a bucket, dont look for more
					if len(tmp_stash) == settings.oram_Z_blocks_per_bucket:
						break
				
				# remove blocks in tmp_stash from normal stash
				for (tmp_block_id, tmp_block_data) in tmp_stash:
					shelter_index = self.index['shelter'].index(tmp_block_id)
					del self.index['shelter'][shelter_index]
					del self.shelter[shelter_index]

				# supplement tmp_stash with dummies until bucket is full
				while len(tmp_stash) < settings.oram_Z_blocks_per_bucket:
					tmp_stash.append((0, self.client.generate_dummy_block()))

				# write tmp_stash to bucket
				bucket_blocks = self.bucketGetBlocks(tmp_bucket_id)
				for tmp_stash_index in range(0, settings.oram_Z_blocks_per_bucket):
					# collect info
					(tmp_block_id, tmp_block_data) = tmp_stash[tmp_stash_index]
					bucket_block_id = bucket_blocks[tmp_stash_index]

					# write stashed block to bucket block
					self.client._send("W", bucket_block_id, tmp_block_data, tmp_block_id)
				

			#### update index and stash to files
			self.update_index()

			#### return results
			return result
