import math
import sys
import os
import random
import json

from pprint import pprint
from settings import Settings
settings = Settings()

# ORAM implementation class (Trivial ORAM - shi et al.)
class Trivial():

		# init oram (Set properties and connect to server)
		def __init__(self, client):
			self.client = client

			self.index = self.read_index()

			# tmp counter
			self.failed_evictions_count = 0

			# trivial ORAM has no shelter, however this variable exists to ease the oram testing script. This value is always 0.
			self.local_max_shelter_size = 0

			# pprint(self.index)

			# index has not yet been created -> create it and store in settings.oram_index_file
			if self.index == {}:
				# print("No file index found - generate new index file")

				# create index local variables
				self.init_oram()

				# write index to settings.oram_index_file
				self.update_index()


		# read index fileand return data
		def read_index(self):
			if os.path.exists(settings.oram_index_file):
				with open(settings.oram_index_file, 'r') as index_file:
					self.index = json.load(index_file)

					# index of other ORAM type: error
					if self.index['general']['oram_type'] != settings.oram:
						print("Found oram index for oram type: " + str(self.index['general']['oram_type']) + ".\nPlease remove it to continue.")
						exit()

			else:
				self.index = {}

			return self.index

		# write/update self.index to settings.index_file
		def update_index(self):
			# write index
			with open(settings.oram_index_file, 'w') as index_file:
				json.dump(self.index, index_file)


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
				'root_bucket': N_buckets-1
			}

			self.index['pos_map'] = {}   # local_block_id => leaf bucket node


		
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

		# get child buckets of bucket_id
		# returns pair (child_l, child_r)
		def bucketGetChildren(self, bucket_id):
			buckets_per_layer = self.getBucketsPerDepth()
			
			# find depth
			depth = 0
			for tmp_depth in range(0, len(buckets_per_layer)):
				if bucket_id in buckets_per_layer[tmp_depth]:
					depth = tmp_depth

			# leaf nodes dont have children, error handling
			if depth == len(buckets_per_layer)-1:
				pprint("Leaf nodes dont have children, cant perform bucketsGetChildren() over bucket_id: " + str(bucket_id))
				exit()

			# calculate children
			diff = (buckets_per_layer[depth][-1] - bucket_id)*2
			
			r_child = buckets_per_layer[depth+1][-1-diff]
			l_child = buckets_per_layer[depth+1][-1-diff-1]

			return (l_child, r_child)


		# get list of buckets per depth
		def getBucketsPerDepth(self):
			# prepare result variable
			result = [None]*(self.index['general']['max_depth']+1)

			# set leaf buckets as last entry, and root bucket as first entry
			result[self.index['general']['max_depth']] = list(range(0, self.index['general']['N_leaves']))
			result[0] = [self.index['general']['root_bucket']]

			# fill in the in-betweens
			for i in range(self.index['general']['max_depth']-1, 0, -1):
				tmp_result = []
				prev_result = result[i+1]
				for j in range(1, int(len(prev_result)/2)+1):
					tmp_result.append(prev_result[-1]+j)

				result[i] = tmp_result

			# return result
			return result


		# read all entries in bucket, and remove the data matching block_id
		# returns data
		def bucketReadAndRemove(self, bucket_id, block_id):
			# get blocks of bucket
			bucket_blocks = self.bucketGetBlocks(bucket_id)
			result = None

			# read and write to all blocks
			for virtual_block_id in bucket_blocks:
				(tmp_data, tmp_block_id) = self.client._send("R", virtual_block_id, self.client.generate_dummy_block(), 0)
				if str(tmp_block_id) not in self.index['pos_map']:
					tmp_block_id = 0

				# if entry contains real data?
				if tmp_block_id != 0:

					# is this the bucket that we want to read?
					if tmp_block_id == block_id: #self.index['block_map'][str(virtual_block_id)] == block_id:
						# rewrite dummy value to server
						self.client._send("W", virtual_block_id, self.client.generate_dummy_block(), 0)

						# store result 
						result = tmp_data

					# wrong block, write it back to the server
					else:
						self.client._send("W", virtual_block_id, tmp_data, tmp_block_id)

				# entry contains dummy value, rewrite dummy value to server
				else:
					self.client._send("W", virtual_block_id, self.client.generate_dummy_block(), 0)

			# return result
			return result


			
		# add new entry to bucket
		# if block_id and data == None, write dummy value
		# returns boolean success (succesfully written)
		def bucketAdd(self, bucket_id, block_id, data):
			# get blocks of bucket
			bucket_blocks = self.bucketGetBlocks(bucket_id)
			success = False

			# read and write to all blocks
			for virtual_block_id in bucket_blocks:
				(tmp_data, tmp_block_id) = self.client._send("R", virtual_block_id, self.client.generate_dummy_block(), 0)
				if str(tmp_block_id) not in self.index['pos_map']:
					tmp_block_id = 0

				# real data?
				if tmp_block_id != 0: 
					# rewrite data to same block
					self.client._send("W", virtual_block_id, tmp_data, tmp_block_id)

				# dummy block -> write added entry to bucket
				elif success == False:

					# write dummy value to bucket, so generate dummy block
					if block_id == 0 and data == None:
						data = self.client.generate_dummy_block()
					
					# write to server and update result variable
					self.client._send("W", virtual_block_id, data, block_id)
					success = True

				# dummy block, while data has already been written to bucket -> write dummy value
				else:
					self.client._send("W", virtual_block_id, self.client.generate_dummy_block(), 0)

			# return success boolean
			return success




		# read(pop) any value from bucket, 
		# if only dummy values exist: return dummy value (=None)
		# if value exists, return pair (block_id, data)
		def bucketPop(self, bucket_id):
			# get blocks of bucket
			bucket_blocks = self.bucketGetBlocks(bucket_id)

			# read all blocks in bucket
			results = []
			result = None
			for virtual_block_id in bucket_blocks:
				(tmp_data, tmp_block_id) = self.client._send("R", virtual_block_id, self.client.generate_dummy_block(), 0)
				if str(tmp_block_id) not in self.index['pos_map']:
					tmp_block_id = 0

				# if block contains real value
				if tmp_block_id != 0: 
					# store in results array
					results.append((tmp_block_id, tmp_data))

			# pop result from list
			if len(results) >= 1:
				result = results[0]
				del results[0]


			# (re-)write bucket to server
			for virtual_block_id in bucket_blocks:
				# real content?
				if len(results) >= 1:
					# get values
					(tmp_block_id, tmp_data) = results[0]
					del results[0]

					# write to block
					self.client._send("W", virtual_block_id, tmp_data, tmp_block_id)

				# write dummy value
				else:
					self.client._send("W", virtual_block_id, self.client.generate_dummy_block(), 0)


			# return result
			return result



		# Read(data=None) or Write(data=bytes) operation
		def access(self, block_id, data=None):
			
			##### perform readAndRemove (even if block_id is not yet stored in the server, this is required to ensure indistinguishability of read and write operations)
			# find leaf position to read from
			l_pos = self.index['pos_map'].get(str(block_id), None)
			if l_pos == None and data == None:
				print("Cannot read block_id: " + str(block_id) + ". It is not stored in any bucket")
				exit()

			# block is not stored in server, create random l_pos to perform phantom readAndRemove over.
			if l_pos == None:
				l_pos = random.randint(0, self.index['general']['N_leaves']-1)

			# find (inverse) path
			path = self.path(l_pos)
			path.reverse() # start from leaf to root

			# perform readAndRemove over all buckets on path to find stored result
			result = None
			for bucket_id in path:
				tmp_data = self.bucketReadAndRemove(bucket_id, block_id)
				# found result?
				if tmp_data != None:
					result = tmp_data

			##### perform Add (write block back to root node)
			# if operation is Read, write the found result back to the server
			if data == None:
				data = result

			# generate new leaf position for block
			self.index['pos_map'][str(block_id)] = random.randint(0, self.index['general']['N_leaves']-1)

			# write to root node
			self.bucketAdd(self.index['general']['root_bucket'], block_id, data)

			##### call Evict
			self.evict()
			
			##### update index file and return result
			self.update_index()

			return result

		# pop results from buckets and add them to child nodes
		def evict(self):
			# list that stores all blocks that have been evicted from parent bucket, but whose child bucket is already full
			failed_additions = []

			# loop over each depth
			bucketPerDepth = self.getBucketsPerDepth()
			for depth in range(0, self.index['general']['max_depth']): # skip max depth (leaves)
				# get v(eviction rate) buckets to evict
				buckets = []
				if len(bucketPerDepth[depth]) <= settings.oram_eviction_rate:
					buckets = bucketPerDepth[depth]
				else:
					buckets = random.sample(bucketPerDepth[depth], settings.oram_eviction_rate)
				
				# evict each (sampled) bucket in current depth
				for bucket_id in buckets:
					# get children
					(l_child, r_child) = self.bucketGetChildren(bucket_id)

					# pop bucket
					tmp_res = self.bucketPop(bucket_id)

					# bucket only contains dummies, write dummy value to both children
					if tmp_res == None:
						self.bucketAdd(l_child, 0, self.client.generate_dummy_block())
						self.bucketAdd(r_child, 0, self.client.generate_dummy_block())

					# bucket contains real value, write it to the proper child
					else:
						# find path of popped block
						(tmp_block_id, tmp_data) = tmp_res
						tmp_path = self.path(self.index['pos_map'][str(tmp_block_id)])
						# write real value to left child
						success = False
						if l_child in tmp_path:	
							success = self.bucketAdd(l_child, tmp_block_id, tmp_data)
							self.bucketAdd(r_child, 0, self.client.generate_dummy_block())

						# write real value to right child
						elif r_child in tmp_path:
							self.bucketAdd(l_child, 0, self.client.generate_dummy_block())
							success = self.bucketAdd(r_child, tmp_block_id, tmp_data)

						# child bucket is full
						if not success:
							# store popped entry 
							failed_additions.append((tmp_block_id, tmp_data))

							# remove popped entry from position list
							del self.index['pos_map'][str(tmp_block_id)]

							# if l_child in tmp_path:
							# 	pprint("Failed to add block "+str(tmp_block_id)+" to child bucket "+str(l_child))
							# else:
							# 	pprint("Failed to add block "+str(tmp_block_id)+" to child bucket "+str(r_child))
								
			# add failed additions to root bucket (through access method)
			for (tmp_id, tmp_data) in failed_additions:
				self.access(tmp_id, tmp_data)

			self.failed_evictions_count += len(failed_additions)


